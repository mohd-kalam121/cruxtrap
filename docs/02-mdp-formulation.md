# CruxTrap — MDP Formulation of Honeypot–Attacker Interaction

This document is the mathematical core of the project. Everything the honeypot logs,
and everything the simulator measures, follows from the definitions here.

## 1. Setting

One SSH session is one **episode**. Within an episode the attacker issues commands
$c_1, c_2, \dots, c_T$ and the honeypot responds to each. The honeypot is the
**agent**; the attacker (and the emulated shell) is the **environment**. The episode
terminates when the attacker disconnects, the honeypot blocks, or a time-out fires.

We model this as a finite MDP $\mathcal{M} = (\mathcal{S}, \mathcal{A}, P, R, \gamma)$.

## 2. State space $\mathcal{S}$

A state is a pair

$$ s_t = (\kappa_t,\ \phi_t) \in \mathcal{K} \times \Phi $$

where

**$\kappa_t \in \mathcal{K}$ — command category** of $c_t$, obtained by a
deterministic classifier (regex table in `honeypot/classify.py`):

| Category | Examples | Intel value $v(\kappa)$ |
|---|---|---|
| `recon` | `uname -a`, `id`, `ps`, `netstat`, `cat /proc/cpuinfo` | 1 |
| `fs_browse` | `ls`, `cd`, `pwd`, `find`, `cat <non-sensitive>` | 1 |
| `cred_access` | `cat /etc/shadow`, `cat ~/.ssh/id_rsa`, `cat .bash_history` | 3 |
| `download` | `wget`, `curl`, `tftp`, `scp` | 4 |
| `execute` | `chmod +x`, `./payload`, `sh script.sh`, `python -c` | 4 |
| `persist` | `crontab`, `echo >> authorized_keys`, `useradd`, `systemctl enable` | 5 |
| `privesc` | `sudo`, `su`, `passwd` | 3 |
| `cleanup` | `history -c`, `rm /var/log/*`, `unset HISTFILE` | 4 |
| `benign` | `echo`, `clear`, `help` | 0 |
| `unknown` | anything unmatched | 1 |

**$\phi_t \in \Phi = \{\text{early}, \text{mid}, \text{late}\}$ — session phase**,
a function of the number of commands issued so far:

$$ \phi_t = \begin{cases} \text{early} & t \le 3 \\ \text{mid} & 4 \le t \le 10 \\ \text{late} & t > 10 \end{cases} $$

$|\mathcal{S}| = 10 \times 3 = 30$. This is deliberately small: it keeps the Q-table
interpretable, makes convergence fast enough to learn from hundreds (not millions) of
sessions, and lets every entry be shown on the dashboard.

> **Markov assumption.** $s_t$ discards the exact command history. The assumption is
> that the attacker's *next* command depends on what they just did and how far along
> they are, not on the full sequence. This is an approximation; Section 8 lists
> richer state features as extensions.

## 3. Action space $\mathcal{A}$

| Action | Honeypot behaviour | Cost $\chi(a)$ (seconds of attacker time consumed; higher = more "friction") |
|---|---|---|
| `ALLOW` | Return the faithful emulated output | 0 |
| `DELAY` | Sleep $\delta \sim U(1,4)$ s, then return faithful output | ~2.5 |
| `FAKE` | Return a *decoy* output — honeytoken credentials, fake keys, fabricated listing | 0 |
| `TARPIT` | Dribble output at a few bytes/second; total ~10–20 s | ~15 |
| `BLOCK` | Close the connection (terminal) | — |

$|\mathcal{A}| = 5$, so the Q-table has $150$ entries.

## 4. Transition dynamics $P(s' \mid s, a)$

Unknown and *not* modelled explicitly — this is what makes a model-free method
(Q-learning) appropriate. The dynamics are induced by the attacker: after the
honeypot's response, the attacker either issues another command (giving a new
$\kappa_{t+1}$, and $\phi_{t+1}$ advances deterministically) or disconnects
(terminal state $s_\bot$).

In the **simulator** (Phase 5) the attacker *is* given an explicit model so that we
can train and evaluate under controlled conditions:

- the next category follows a first-order Markov chain
  $\Pr(\kappa_{t+1} \mid \kappa_t)$ with a transition matrix per attacker type
  (`bot`, `script_kiddie`, `operator`), initialised from published Cowrie session
  statistics and refined from our own captures;
- the probability of continuing after action $a$ is
  $p_{\text{cont}}(a, \kappa, \text{type})$ — e.g. `TARPIT` sharply lowers it for
  bots (they time out), `FAKE` on `cred_access` raises it for operators (they chase
  the honeytoken), `BLOCK` sets it to 0.

## 5. Reward $R(s, a, s')$

The reward is the **intelligence captured by letting the session continue**, net of
the friction imposed:

$$
r_t \;=\; \underbrace{\mathbb{1}[\text{continue}]\;\big(w_e + w_v\, v(\kappa_{t+1})\big)}_{\text{engagement + value of what we see next}}
\;-\; \underbrace{w_c\, \chi(a_t)}_{\text{friction cost}}
\;+\; \underbrace{w_b\, \mathbb{1}[a_t = \text{BLOCK} \wedge \kappa_t \in \{\text{cleanup}\} \wedge \phi_t = \text{late}]}_{\text{justified block}}
$$

Default weights: $w_e = 1$, $w_v = 0.5$, $w_c = 0.02$, $w_b = 2$.

Interpretation:

- Every further command is worth $w_e$; high-value next commands are worth more.
- Friction (`DELAY`, `TARPIT`) is mildly penalised so the agent uses it only when it
  pays off (e.g. against bots that would leave anyway).
- `BLOCK` is normally bad (ends the stream of information) but earns a small bonus
  when the attacker is already covering their tracks late in the session, i.e. the
  session has stopped producing value.
- If the attacker disconnects, $r_t = -w_c\chi(a_t)$ — the action gained nothing.

The weights $w$ are hyper-parameters; RQ2 studies sensitivity to them.

## 6. Objective and learning algorithm

The agent seeks a policy $\pi : \mathcal{S} \to \mathcal{A}$ maximising expected
discounted return $\mathbb{E}\big[\sum_t \gamma^t r_t\big]$, $\gamma = 0.9$.

**Tabular Q-learning** (off-policy TD control):

$$
Q(s_t, a_t) \leftarrow Q(s_t, a_t) + \alpha\Big[r_t + \gamma \max_{a'} Q(s_{t+1}, a') - Q(s_t, a_t)\Big]
$$

with $Q(s_\bot, \cdot) = 0$. Behaviour policy is $\varepsilon$-greedy with
exponential decay $\varepsilon_k = \max(\varepsilon_{\min}, \varepsilon_0 \rho^k)$ per
episode $k$; defaults $\alpha = 0.1$, $\varepsilon_0 = 0.3$, $\rho = 0.995$,
$\varepsilon_{\min} = 0.05$.

**Warm start.** $Q(s, \text{ALLOW}) = 0.5$, all else $0$, so the untrained honeypot
behaves like a conventional one.

**Convergence.** Watkins & Dayan (1992): with finite $\mathcal{S}, \mathcal{A}$,
bounded rewards, every pair visited infinitely often, and step sizes satisfying
$\sum \alpha = \infty, \sum \alpha^2 < \infty$, $Q \to Q^*$ w.p. 1. We use constant
$\alpha$ (standard in non-stationary settings — the attacker population drifts), so
we expect convergence to a neighbourhood of $Q^*$, which the learning curves in
Phase 5 will show empirically.

**Persistence.** The Q-table and $\varepsilon$ are checkpointed to JSON after every
episode so learning survives restarts.

## 7. Baselines for evaluation (Phase 5)

| Policy | Description | Role |
|---|---|---|
| `STATIC` | Always `ALLOW` | A Cowrie-equivalent honeypot — the control |
| `RANDOM` | Uniform over $\mathcal{A}$ | Sanity floor |
| `BANDIT` | $\varepsilon$-greedy over actions, ignoring state | Tests whether *state* matters |
| `QLEARN` | Section 6 | The proposed method |
| `SARSA` | On-policy TD control, same state/action | Algorithmic comparison |

**Metrics per episode:** commands captured $T$, total intel value
$\sum_t v(\kappa_t)$, session duration, attacker time wasted, fraction of sessions
reaching `download`/`persist`. Report mean ± 95% CI over ≥ 10 seeds × 1000 episodes.

## 8. Extensions (not required for the base project)

- Add `last_action` or a short history window to the state (increases $|\mathcal{S}|$).
- Add attacker-type belief (bot vs. human) estimated from inter-command timing.
- Function approximation (linear or small DQN) if state is enriched.
- Learn the attacker transition matrix from captured data and run value iteration as a
  model-based comparison.

## 9. What the honeypot must therefore log per command

`session_id, seq, timestamp, raw_command, category, phase, action, reward, epsilon,
q_values_before, q_values_after, response_latency_ms, continued (bool)` — this is the
`session_actions` table in `db/init.sql`.
