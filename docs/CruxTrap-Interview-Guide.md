# CruxTrap: Viva and Interview Guide

This guide matches the system as built and the numbers in the report
(`docs/CruxTrap_Project_Report.pdf`). Every number below is reproduced by
`python -m simulator.experiments`.

**How to use it.** Learn the three pitches in Part 0 word for word. Part 1 is the system, Part 2
is the mathematics (where an M&C panel will spend most of its time), Part 3 is the results, and
Part 4 is the hard questions. Part 5 lists the derivations you must be able to do on a whiteboard.

---

## The team

| Member | Roll number | Main ownership *(fill in before the viva)* |
|---|---|---|
| Mohd Kalam | 23/MC/090 | |
| Mayank Jha | 23/MC/087 | |
| Krish | 23/MC/076 | |

In a group viva, examiners usually ask each member **"what did *you* do?"** and then ask that
person a deep question about it. Agree on the split before the viva and fill in the table. A natural
split for this project:

- **Honeypot and emulation:** the SSH server, shell, fake filesystem, decoys (Batch 3)
- **RL and evaluation:** the MDP, learning theory, simulator, exact evaluation, experiments
  (Batches 4–7, Part 5)
- **Data platform:** Redis Streams, the pipeline, PostgreSQL, the dashboard, Docker, failure testing
  (Batches 8–10)

Rules for the room:
1. Say **"we"** for the project and **"I"** only for your own part. The answers below use "we".
2. **Every member must know Part 0, the numbers table, and Q55 (why constant α failed).** These
   are the questions most likely to be put to any of you.
3. Split the three-minute pitch: one person gives points 1–2, the next 3–4, the last 5, then
   hand over to the demo.
4. Don't answer for a teammate who was asked directly. Add to their answer only if they invite you.

---

## Unlearn these (the earlier version of this guide was wrong)

The first version of this guide was written before any code existed. If you studied it, correct
these answers:

| Old answer | Correct answer |
|---|---|
| Actions: Allow, Delay, Fake, **Insult**, Block | **TARPIT** replaced INSULT. An insult tells the attacker it's a honeypot. |
| Accepts every password | Accepts the **N-th attempt** per source IP, N uniform in {1, 2, 3}. Accepting the first try is a known honeypot tell. |
| Constant learning rate α | **α = n^(−0.7) per (state, action)**. Constant α = 0.1 lost to the static honeypot. |
| 3 tables | **4 tables**: attackers, login_attempts, sessions, session_actions |
| If Redis is down, events are lost / publishing fails | The honeypot **buffers** events in memory (store-and-forward) and sends them when Redis returns. Verified: "forwarding 23 buffered events". |
| Commands read character by character | AsyncSSH's **line editor** handles echo, backspace and Ctrl+C. The session reads whole lines with an idle timeout. |
| "CommandProcessor", around 50 commands | `Shell` emulator with **206 command names**, pipes, `;`, `&&`, `\|\|`, redirection, variables and scripts |
| Only SSH 2222 and dashboard 8000 exposed | **Every port binds to 127.0.0.1** by default. A real deployment exposes only the honeypot. |
| PostgreSQL on 5432 | Host port **55432** (5432 and 5433 were already taken on the development machine). Inside Docker it is still 5432. |
| JSON parse failure → empty object | Malformed events go to a **dead-letter stream** (`honeypot:dead`) and are acknowledged. |
| The pipeline retries Postgres "according to its retry strategy" | Transient errors are retried with backoff. Non-transient errors are dead-lettered, so one bad event cannot block the group. |
| RL updates once at session end | Q-learning is a **TD update after every command**. It is deferred by one command because the reward depends on the attacker's next move. |
| No evaluation | Simulator plus **exact** evaluation (linear algebra on a 330-state chain), oracle and best-observable benchmarks, and t-tests over 20 seeds |

---

# Part 0: The Pitches

## One line

> CruxTrap is an SSH honeypot that uses reinforcement learning to choose how to answer each
> attacker command, together with an exact mathematical method to measure how much that adaptation
> actually helps.

## One minute

> CruxTrap emulates an Ubuntu 22.04 server over SSH. Nothing the attacker types is ever executed:
> every session gets its own in-memory fake filesystem and a shell emulator with 206 commands. For
> each command, a Q-learning agent picks one of five responses: allow, delay, fake (plant decoy
> credentials), tarpit, or block. Every event goes through Redis Streams to a pipeline that adds
> GeoIP and writes to PostgreSQL. A FastAPI dashboard shows session replays and the learned policy.
> Everything runs as five hardened Docker containers.
>
> The mathematical part: We modelled the problem as an MDP, which is really a POMDP because the
> attacker's type is hidden. We built an attacker model, and we evaluate policies *exactly* by solving
> Bellman equations instead of simulating. Q-learning beats the static honeypot with
> p = 6 × 10⁻⁶ and gets 60% of the achievable gain, but only with a Robbins–Monro step size. With
> the usual constant learning rate it did *worse* than static, and we can explain why from theory.

## Three minutes (add these after the one-minute version)

1. **The problem with static honeypots:** they cannot make trade-offs, and they are easy to fingerprint.
2. **The gap in prior work** (Heliza, RASSH, QRASSH): those systems were deployed and reported
   engagement statistics, but they never asked *how much better than static* the learned policy is,
   or how far it is from the best achievable.
3. **What we measured:** Q-learning 5.686 ± 0.051 vs static 5.542 vs best observable 5.783 vs oracle
   5.935. What the agent learns is to serve decoy credentials to attackers who are looking for
   credentials.
4. **The negative result:** constant α = 0.1 lost to static. The variance of a constant-step
   estimate never shrinks (it stays at σ²·α/(2−α), a standard deviation of about 0.23σ), and that
   is larger than the true differences between actions. Switching to α = n^(−0.7) fixed it, and an
   ablation confirmed the explanation.
5. **When it pays:** +0.5% against bots (not significant), +3.5% on the balanced mix, +5.2% against
   human-heavy traffic. Adaptation pays where attackers adapt.

## Numbers to memorise

| What | Value |
|---|---|
| Code | ≈ 4,900 lines of Python (+ ≈ 500 template/CSS/JS), **111 tests**, **206** command names |
| States / actions / Q-entries | 10 categories × 3 phases = **30** states; **5** actions; **150** entries |
| Phases | early t ≤ 3, mid 4–10, late ≥ 11 |
| Reward weights | w_e = 1, w_v = 0.5, w_c = 0.02, w_b = 2; γ = 0.9 |
| Exploration | ε = max(0.05, 0.3 × 0.995^k) after k episodes |
| Step size | α_n = n^(−0.7) per (s, a); warm start Q(s, ALLOW) = 0.5 |
| Augmented chain | 3 types × 10 categories × 11 time steps = **330** states; one evaluation ≈ 3 ms |
| Main experiment | 20 seeds × 20,000 episodes; all experiments ≈ 1 minute on 8 cores |
| Q-learning | **5.686 ± 0.051** (95% CI) |
| SARSA / bandit / static / random | 5.702 ± 0.026 / 5.503 ± 0.021 / 5.542 / 1.949 |
| Best observable / oracle | 5.783 / 5.935 |
| Test vs static | t = 5.88, **p = 5.8 × 10⁻⁶**, n = 20; Q vs SARSA Welch p = 0.57 |
| Share of achievable gain | **60% ± 21%**; agrees with the best policy in 68% of states |
| Constant α = 0.1 | 5.343 ± 0.154 at 5,000 episodes (only 2 of 10 seeds beat static) |
| Sensitivity (gain over static) | bot-heavy +0.5%, balanced +3.5%, human-heavy +5.2% |
| Monte Carlo check | exact 5.464 vs simulated 5.442 ± 0.043 (50,000 episodes) |
| Type posterior | bots 60% → 16%, operators 15% → 54% between t = 1 and t ≥ 11 |
| Ports (all on 127.0.0.1) | SSH 2222, dashboard 8000, Redis 6379, Postgres 55432 |

---

# Part 1: The System

## Batch 1: Overview and Motivation

**Q1. What is a honeypot?**
A decoy system with no production value. It has no legitimate users, so every interaction with it
is suspicious, which gives it a very low false-positive rate. It deliberately lets attackers in and
records what they do (Spitzner's definition: a resource whose value lies in its unauthorised use).

**Q2. Low, medium or high interaction? Which is CruxTrap?**
Low interaction records a connection or a login and nothing more. High interaction gives the
attacker a real (virtual) operating system: realistic, but risky and expensive. **Medium interaction**
emulates the shell and filesystem in software, so attackers can run commands but nothing is executed.
CruxTrap is medium interaction, the same design point as Kippo and Cowrie.

**Q3. Why SSH?**
SSH is one of the most attacked services on the internet. A server with port 22 open gets
password-guessing attempts within minutes. SSH also gives an interactive shell, so you see what the
attacker does *after* login, which is the valuable part.

**Q4. What problem does the project solve?**
Two problems. (1) Static honeypots always give the same response, so they cannot trade
off engagement against deception, and they are easy to fingerprint. (2) Previous *adaptive* honeypots
were never evaluated against a proper baseline. Our problem statement: design, implement and evaluate
an SSH honeypot whose response to each command is chosen by an RL policy, to maximise the amount
and value of attacker behaviour captured, without ever executing attacker input.

**Q5. What are your research questions?**
RQ1: Does a learned response policy capture more attacker behaviour than a static honeypot?
RQ2: How does the answer depend on the attacker population and on what the defender values?

**Q6. Why not just block attackers?**
Blocking is right for a production server, but it throws away the most informative part of an
attack: the commands, the download URLs, the persistence tricks. A honeypot exists to observe.

**Q7. What is your contribution compared with Cowrie?**
Be honest. Cowrie is far more mature: SFTP/SCP capture, saving downloaded files, a bigger emulation.
Our contributions are (i) a per-command **adaptive response policy**, (ii) a **formal model** and an
**exact evaluation method** that says how much adaptation helps compared with what is achievable,
(iii) the finding that it only works with a Robbins–Monro step size, and (iv) a full pipeline and
dashboard that records every RL decision (Q-values before and after) for each command.

**Q8. And compared with RASSH / Heliza / QRASSH?**
They showed that adaptive honeypots are feasible: Heliza used allow/block/substitute/insult with RL,
RASSH used SARSA on Kippo, QRASSH used a deep Q-network. They were evaluated by deploying for some
weeks and reporting engagement. That cannot compare policies fairly, because different policies meet
different attackers on different days, and it cannot say how far you are from optimal. Our
evaluation can do both. We also replaced *insult* with *tarpit*, because an insult gives the
honeypot away.

**Q9. What technologies did you use and why?**
Python 3.12 with AsyncIO (everything is I/O-bound), AsyncSSH (an SSH *server* library built on
asyncio), Redis 7 Streams (a durable event log with consumer groups), PostgreSQL 16 with asyncpg
(the data is relational), FastAPI + Jinja2 (an async dashboard rendered on the server),
NumPy/SciPy/Matplotlib (exact evaluation and statistics), Docker Compose (reproducible five-service
deployment), and pytest.

**Q10. Which part are you most proud of?**
The evaluation. Anyone can wire Q-learning into a honeypot. Being able to say "60% of the
achievable gain, p = 6 × 10⁻⁶, and here is why the textbook learning rate fails" is the
mathematics-and-computing part of the project.

**Q11. What is in scope and what is out of scope?**
In scope: SSH password authentication, interactive and `exec` sessions, emulation, the policy,
telemetry, the dashboard, deployment, and simulation-based evaluation. Out of scope: SFTP/SCP file
capture, sandboxed payload analysis, other protocols, and dashboard authentication (all listed as
future work).

**Q12. Did you deploy it on the internet?**
No. Everything was tested in the lab with scripted attacker traffic over real SSH
(`scripts/demo_traffic.py`), plus the simulator. We also found that on Docker Desktop
(Windows/macOS) published ports go through a user-space proxy, so the honeypot sees every client as
the Docker gateway. A real deployment must run on a Linux host or use host networking. A live
deployment with an A/B comparison is the first item of future work.

---

## Batch 2: Architecture and Data Flow

**Q13. Draw the architecture.**
```
Attacker ──SSH──▶ Honeypot ──XADD──▶ Redis Streams ──XREADGROUP/XACK──▶ Pipeline ──SQL──▶ PostgreSQL ◀──SQL── Dashboard ◀──HTTP── Analyst
                 (AsyncSSH, shell,                                     (GeoIP, upserts)
                  fake FS, RL agent)
        └────────── network "ingest" ──────────┘          └──────────── network "storage" ────────────┘
```
The pipeline is the only service on both networks.

**Q14. Why five services instead of one program?**
Each has one job and its own way of failing. Most importantly, **capture must not depend on
anything downstream**: if Redis, the pipeline or Postgres fails, attackers are still served. That
is requirement NFR2, and we tested it.

**Q15. Why put Redis between the honeypot and the database?**
To decouple capture from storage. The honeypot never waits for a database write, and a database
outage cannot reach an attacker's session. We chose Streams over Pub/Sub because streams are durable:
a message stays in the stream, and in the consumer's pending list until it is acknowledged, so a
crashed consumer loses nothing. Pub/Sub drops messages when no one is listening.

**Q16. Why is the RL agent inside the honeypot and not in the pipeline?**
The action has to be chosen *before* the response is sent, so it is on the critical path.
Enrichment is not, so it lives in the pipeline.

**Q17. Walk us through one session from start to finish.**
1. TCP connect. AsyncSSH sends the version `OpenSSH_8.9p1 Ubuntu-3ubuntu0.4` and RSA + Ed25519
   host keys.
2. Password attempts. Each becomes a `login_attempt` event. The N-th attempt from that IP
   succeeds (N ∈ {1, 2, 3}).
3. `SessionRunner` creates a UUID4 session ID and a fresh `FakeFileSystem` (seeded,
   procedural), emits `session_start`, and prints the Ubuntu banner and prompt.
4. For each command: classify it into a category → state = (category, phase) → **apply the
   deferred TD update for the previous command** → the policy chooses an action → the emulator runs
   the line (with decoys if FAKE) → the output is delivered according to the action → `command` and
   `rl_update` events are emitted.
5. Exit, disconnect, idle timeout (300 s), 200 commands or 30 minutes → terminal update,
   ε decays, the Q-table is checkpointed atomically, and `session_end` is emitted.
6. The pipeline consumes the events, adds GeoIP, upserts in one transaction, then XACKs. The
   dashboard reads Postgres.

**Q18. What event types are there?**
`connection`, `login_attempt`, `session_start`, `command`, `rl_update`, `session_end`, `disconnect`.
Each is JSON with `type`, an ISO-8601 timestamp, the source IP and port, and the session UUID where
there is one. A `command` event also carries the category, phase, state, action, ε, the Q-values at
decision time, latency, output size and whether decoys were planted.

**Q19. Why does the dashboard read Postgres and not Redis?**
Redis is transport. Postgres is the system of record. Investigative queries need joins,
aggregation and indexes.

**Q20. Why is the architecture loosely coupled?**
The only contract between the honeypot and the rest is the JSON event schema on one stream. The
honeypot does not know the database exists. It cannot even resolve `postgres` on its network.

**Q21. Which service is the bottleneck, and how would you scale?**
For throughput, the pipeline, because each event is a transaction. Scale it by running more
consumers in the same consumer group; Redis shares the messages between them. Scale the honeypot by
running several sensors that all publish to the same stream. The dashboard is stateless. Postgres
would need partitioning of `session_actions` by time and read replicas long before sharding.

**Q22. Which metric would you monitor first?**
Consumer lag: the stream length and the size of the pending list. It tells you whether events are
arriving faster than they are stored. Also the emitter's dropped-event counter.

---

## Batch 3: The Honeypot (AsyncSSH, Shell, Fake Filesystem)

**Q23. Why AsyncSSH and not Paramiko?**
AsyncSSH is built on asyncio and designed for servers as well as clients. It gives us
authentication callbacks, PTY handling and a line editor, so one thread serves many sessions.
Paramiko is synchronous and mostly used for clients.

**Q24. Why accept the N-th password and not the first?**
A server that accepts any password on the first try is a well-known honeypot tell. A per-IP
threshold N drawn uniformly from {1, 2, 3} looks like a real server with a weak password. Every
attempt is recorded anyway.

**Q25. Why keep host keys in a volume?**
If the fingerprint changed on every restart, a returning bot would notice (and SSH clients warn
about it). The keys are generated once and persisted.

**Q26. How is input read?**
`line_editor=True` in AsyncSSH handles echo, backspace and line editing. `SessionRunner` reads whole
lines with `asyncio.wait_for(..., idle_timeout)`. Ctrl+C clears the line, as Bash does.

**Q27. How does the shell work?**
`Shell` splits a line into statements on `;`, `&&`, `||` and `&`, and tracks the exit status, so
`false || echo x` behaves as in Bash. It also handles quoting, pipes, `>` and `>>` into the fake
filesystem, `$VAR` expansion and `VAR=value`. A file with a shebang that has been made executable has
its lines interpreted, so the classic `wget …; chmod +x …; ./…` sequence works end to end.

**Q28. How are commands implemented?**
As plain functions registered with a `@command("name")` decorator into a table of **206 names**,
grouped into files/text, system/identity and network. A handler gets `(shell, args, stdin)` and
returns text. Unknown commands print Bash's `command not found`. **An exception in any handler is
caught and gives empty output, so an emulation bug can never end a session.**

**Q29. Does `wget` really download anything? Can the honeypot be used to attack others?**
No. `wget`, `curl`, `ping`, `ssh` and `nc` are emulated: they print realistic output, `wget`
writes a placeholder file into the *fake* filesystem, and no network request is made. The URL is
captured, and it is an indicator of compromise. Fetching and sandboxing the payload is future work.

**Q30. Can `rm -rf /` hurt the host?**
No. It only changes that session's in-memory tree, which is discarded at disconnect. There is no
`exec`, `subprocess` or shell anywhere in the command path.

**Q31. What does the fake filesystem contain?**
A procedurally generated (seeded) Ubuntu 22.04 web/database server: the standard hierarchy;
`/etc/passwd`, `shadow`, `group`, `os-release`, `sshd_config`, `crontab`, nginx and mysql configs;
`/proc/cpuinfo`, `meminfo`, `version`, and an `uptime` computed live; a 60-line `auth.log` of failed
logins, `syslog`, a nightly backup script and its log, `.bash_history` for three users, binaries
with realistic sizes, and timestamps spread over the past year. Unix permissions apply: a non-root
user cannot read `/etc/shadow` or list `/root`.

**Q32. Is it the same filesystem for every attacker?**
No. Every session gets its own `FakeFileSystem` object. Changes are never visible to another
session (there is a test for this).

**Q33. What exactly does FAKE do?**
It calls `plant_decoys()`, which idempotently adds honeytoken files (`/root/backup_credentials.txt`,
`/root/.our.cnf`, `/home/deploy/.env`, `/var/www/html/wp-config.php`), appends `.bash_history` lines
that point to them, and adds decoy entries to `ps` and `env` output.

**Q34. Why are the decoy values visible placeholders like `<decoy:mysql-root>`?**
So the repository contains nothing that looks like a real secret. The experiment measures *whether*
attackers go after decoys, and that does not depend on how convincing the values look. A real
deployment would generate unique, plausible honeytokens and alert when one is used.

**Q35. What do DELAY, TARPIT and BLOCK do?**
DELAY waits U(1, 4) s, then sends the faithful output. TARPIT waits 4–7 s, then sends the output in
8-byte chunks with pauses (≈ 10–15 s in total); it targets bots with timeouts. BLOCK closes the
channel and ends the episode.

**Q36. Why TARPIT instead of INSULT?**
An insult tells the attacker it's a honeypot, which ruins every later observation. A tarpit is an
established deception against automated tools and looks like a slow server.

**Q37. Why AsyncIO and not threads?**
Every session spends nearly all its time waiting on the network or on deliberate delays. One event
loop serves many sessions without a thread per connection, and a TARPIT sleeping for 15 s costs
nothing.

**Q38. What limits protect the honeypot itself?**
Per session: 200 commands, 30 minutes, 300 s idle timeout. Per container: 256 processes, 512 MB of
memory, 1 CPU.

---

# Part 2: The Mathematics

## Batch 4: The MDP Formulation

**Q39. Where is the mathematics in this project?**
In four places. (1) Modelling: the honeypot's problem as an MDP, which is really a POMDP. (2)
Learning theory: Q-learning, and the Robbins–Monro conditions for its convergence. (3) Exact
evaluation: absorbing Markov chains, Bellman equations, fundamental matrices, value iteration,
Bayesian type posteriors, and MLE for Markov chains. (4) Statistics: confidence intervals,
one-sample and Welch t-tests, seed hygiene, and an ablation study.

**Q40. Define your MDP.**
M = (S, A, P, R, γ), plus a terminal state s⊥.
- S = K × Φ: 10 command categories × 3 phases = 30 states.
- A = {ALLOW, DELAY, FAKE, TARPIT, BLOCK}.
- P(s′ | s, a) is induced by the attacker. It is unknown to the agent.
- R is the reward below, and γ = 0.9.
One SSH session is one episode. Each command is one time step.

**Q41. What are the categories and why do they have values?**

| Category | Examples | v(κ) |
|---|---|---|
| recon | `uname -a`, `id`, `ps aux` | 1 |
| fs_browse | `ls`, `cd`, `find`, non-sensitive `cat` | 1 |
| cred_access | `cat /etc/shadow`, `cat ~/.ssh/id_rsa`, `cat .env` | 3 |
| download | `wget`, `curl`, `tftp`, `git clone` | 4 |
| execute | `chmod +x`, `./payload`, `sh script.sh` | 4 |
| persist | `crontab -`, `>> authorized_keys`, `useradd` | 5 |
| privesc | `sudo -i`, `su`, `passwd` | 3 |
| cleanup | `history -c`, `rm /var/log/*`, `unset HISTFILE` | 4 |
| benign | `echo`, `clear`, `exit` | 0 |
| unknown | anything unmatched | 1 |

v(κ) is how much an analyst learns from seeing that kind of command: a persistence technique is
worth more than another `ls`. The classifier is rule-based and deterministic. A chained line takes
the **highest-value** category among its parts, because that is the intent the attacker revealed.

**Q42. Why phases, and why those boundaries (≤ 3, 4–10, ≥ 11)?**
The same command means different things early and late in a session. More importantly, the phase
carries information about the *hidden attacker type*: bots leave early, so long sessions are mostly
humans (Q63). The boundaries roughly match a bot script (about 3 commands), a short human session,
and a long one.

**Q43. Why such a small state space?**
On purpose. 150 Q-entries can be learned from thousands of sessions rather than millions, each one
can be shown and inspected on the dashboard, and the exact evaluation stays tractable. Richer state
(previous action, command history, timing) is future work.

**Q44. Write the reward.**
r_t = 1[cont_t] · (w_e + w_v · v(κ_{t+1})) − w_c · χ(a_t) + w_b · 1[a_t = BLOCK, κ_t = cleanup, φ_t = late]

with w_e = 1, w_v = 0.5, w_c = 0.02 and w_b = 2. χ(a) is the expected friction in seconds: 0 for
ALLOW, FAKE and BLOCK, 2.5 for DELAY, 15 for TARPIT. In words: each further command is worth 1, a
high-value next command is worth more, friction costs a little, and blocking earns a bonus only when
a late session is covering its tracks.

**Q45. Why is the reward for command t based on command t+1?**
Because the outcome of the response to command t is whether the attacker carries on, and with what.
That is why the TD update is **deferred**: (s_t, a_t) is updated when command t+1 arrives, or when
the session ends.

**Q46. Isn't the reward arbitrary?**
The weights are a modelling choice, so we do three things. (1) We also report reward-independent
measures: expected commands per session and expected intelligence per session. (2) We test a second
objective, *attrition* (w_c = −0.05, so wasting the attacker's time is rewarded). (3) The
qualitative conclusions hold across all six population × objective scenarios.

**Q47. Why γ = 0.9?**
The effective horizon is 1/(1−γ) = 10 commands, which is longer than a typical session (about 4
commands on average), so the agent values the rest of the session without the values blowing up.
Also, γ < 1 together with continuation probability ≤ 0.98 makes every value finite.

**Q48. Is the state Markov?**
No, and saying so is important. What the attacker does next depends on *who they are* (bot, script
kiddie, operator), and the honeypot cannot see that. The true process is a POMDP; (category, phase)
is an observation, not a state. Q55 covers what that breaks.

## Batch 5: Learning Theory

**Q49. Write the Q-learning update and explain each term.**
Q(s,a) ← Q(s,a) + α_n(s,a) · [ r + γ · max_{a′} Q(s′,a′) − Q(s,a) ],  with Q(s⊥, ·) = 0.
The term in brackets is the TD error δ: the target r + γ·max Q(s′,·) minus the current estimate.
α is the step size. It is **off-policy**: it learns the value of the greedy policy while behaving
ε-greedily.

**Q50. SARSA vs Q-learning?**
SARSA uses Q(s′, a′) for the action actually taken next, instead of the max. It is on-policy: it
learns the value of the ε-greedy policy it follows, and is more conservative near costly
exploratory actions. In our results they are indistinguishable (5.702 vs 5.686, Welch p = 0.57),
because by the end ε = 0.05 and the two targets differ very little.

**Q51. What is ε-greedy and what is your schedule?**
With probability ε pick a uniformly random action, otherwise the greedy one. ε_k =
max(0.05, 0.3 × 0.995^k) after k episodes. It reaches the 0.05 floor after about 360 episodes
(0.995^k = 1/6 ⇒ k = ln 6 / 0.005 ≈ 358).

**Q52. What is the warm start and why?**
Q(s, ALLOW) = 0.5 and everything else 0, so an untrained honeypot behaves like a normal honeypot
and doesn't block or tarpit people at random. Note: with α₁ = 1 the first real update replaces the
initial value completely, so the warm start only matters for pairs not yet tried.

**Q53. State the convergence theorem.**
Watkins and Dayan (1992): in a finite MDP with bounded rewards, if every (s, a) is updated infinitely
often and the step sizes satisfy the **Robbins–Monro conditions**
Σ_n α_n = ∞ and Σ_n α_n² < ∞,
then Q_n → Q* with probability 1.
Intuition: the first sum lets you travel arbitrarily far from a bad starting value. The second makes
the accumulated noise have finite variance, so the estimate settles.

**Q54. For which ω does α_n = n^(−ω) satisfy them?**
They are p-series. Σ n^(−ω) diverges iff ω ≤ 1. Σ n^(−2ω) converges iff 2ω > 1. So
**½ < ω ≤ 1**. We use ω = 0.7. A constant α satisfies the first and fails the second.

**Q55. Why did constant α = 0.1 lose to the static honeypot?** *(Be ready to derive this. See D2.)*
With a constant step size the estimate is an exponentially weighted average:
Q_∞ = Σ_j α(1−α)^j X_{n−j}. For i.i.d. targets with variance σ²,
Var = σ² α² Σ_j (1−α)^{2j} = σ² α² / (1 − (1−α)²) = **σ² α / (2 − α)**.
With α = 0.1 that is 0.0526σ², a standard deviation of **0.23σ, and it never goes down**. In
the most-visited states, for example `recon|early`, bots barely react to the response, so the true
differences between actions are about that size. The greedy choice is then decided by noise:
half of the seeds picked a non-ALLOW action there, and the policy lost to static (5.343 ± 0.154,
only 2 of 10 seeds better).

**Q56. Why not α = 1/n, the "sample average"?**
It satisfies Robbins–Monro, but Even-Dar and Mansour (2003) showed that it can converge
exponentially slowly in Q-learning: the early bootstrapped targets are wrong, and 1/n keeps giving
them weight for too long. In our ablation 1/n was the weakest decaying schedule (5.611). The
conclusion: the step size must decay, and **more slowly than 1/n**.

**Q57. How did you choose ω = 0.7 without cheating?**
In a pilot on **disjoint seeds**, and it was fixed before the reported runs. Main, sensitivity,
ablation and diagnostics all use separate seed ranges (0–19, 1000+, 2000+, 50,000+/70,000+). The
differences among ω ∈ {0.6, 0.7, 0.85} are not significant with 10 seeds, and we say so.

**Q58. Your MDP isn't Markov. Does the convergence theorem still apply?**
No, and we say so. Singh, Jaakkola and Jordan (1994) showed that TD methods on observations of a
POMDP need not converge to the best memoryless policy, and the best memoryless policy may even need
to be stochastic. So we don't *assume* the agent is optimal, we *measure* the gap: Q-learning 5.686
vs best observable 5.783.

**Q59. If α decays to zero, how does the agent track attackers whose behaviour changes?**
It doesn't, and that is a real trade-off. Convergence and tracking conflict. The code supports a
floor α_n ≥ α_min (`RL_ALPHA_MIN`), which accepts a small, bounded noise level in exchange for
tracking. For a long deployment we would use a small floor, or reset the counts periodically.

**Q60. Why tabular and not a DQN?**
30 discrete states. A table is exact, has convergence theory, needs no GPU, and every entry can be
inspected on the dashboard. A DQN becomes appropriate past a few hundred states, for example with
command history or timing features. QRASSH did that.

**Q61. You have a terminal action. How does BLOCK's update work?**
Its target is r + γ·0, because the episode ends: no bootstrapping. That turns out to matter for the
residual bias (Q78).

## Batch 6: Attacker Model and Exact Evaluation

**Q62. How do you model attackers?**
A mixture of three types, each a Markov chain over categories, where the continuation probability
depends on the action:
- start: Pr(κ₁ = c | k) = μ_k(c)
- continue: q_k(c, a) = min(0.98, (1 − e_k(c)) · m_k(c, a)), where e_k is the attacker's own exit
  probability, m_k is a reaction multiplier, and m_k(c, BLOCK) = 0
- next category: N_k(c, a, ·), the base transition row. After FAKE on cred_access it is mixed
  50/50 with a "chase the honeytoken" distribution.

| Type | Balanced weight | Behaviour |
|---|---|---|
| bot | 0.60 | recon → download → execute, quick exit; DELAY ×0.90, TARPIT ×0.35 |
| script kiddie | 0.25 | browses and hunts credentials, impatient; FAKE on cred_access ×1.15 |
| operator | 0.15 | patient; TARPIT ×0.60; FAKE on cred_access ×1.20 and steers to download/persist/privesc; FAKE on recon/browse ×0.85 (fabricated data looks inconsistent) |

Bot-heavy weights are (0.85, 0.10, 0.05); human-heavy weights are (0.30, 0.35, 0.35).

**Q63. Where do these numbers come from?**
They are **modelling assumptions** based on qualitative findings about SSH attackers (mostly
automated scripts, with rarer and longer human sessions), not measurements. That is why we (a)
report a sensitivity analysis over three mixes, and (b) derived the MLE that fits the model to
captured sessions (Q69). Say this before the examiner does.

**Q64. What is the augmented chain?**
x = (k, c, t) with t capped at T = 11 (from 11 on, the phase is always late). |X| = 3 × 10 × 11 =
**330**. Under action a: P_a((k,c,t), (k,c′, min(t+1, T))) = q_k(c,a) · N_k(c,a,c′), and with
probability 1 − q_k(c,a) the chain is absorbed. Including k makes it Markov. Including t makes the
phase a function of the state.

**Q65. How do you evaluate a policy exactly?**
A policy π(a | c, φ) sees only the category and phase. It induces P_π and r_π on the 330 states.
Then:
- **Return:** V_π = (I − γP_π)⁻¹ r_π, and the expected return is μ₀ᵀ V_π. This is the Bellman
  equation for a fixed policy, solved directly.
- **Commands per session:** N_π = (I − P_π)⁻¹ is the fundamental matrix of the absorbing chain;
  (N_π)_{xy} is the expected number of visits to y starting from x. Expected commands = μ₀ᵀ N_π 1.
- **Intelligence per session:** μ₀ᵀ N_π v.
Each evaluation is one 330 × 330 linear solve, about 3 ms.

**Q66. Why are those matrices invertible?**
Each row of P_π sums to at most 0.98, so ‖P_π‖_∞ ≤ 0.98 and the spectral radius ρ(P_π) ≤ 0.98 < 1.
Then I − P_π and I − γP_π are invertible, and the Neumann series Σ_k P_π^k converges to (I − P_π)⁻¹.
That is also why the expected number of visits is finite: every session ends with probability 1.

**Q67. Why exact evaluation instead of simulation?**
(1) No evaluation noise: the spread across seeds is pure *learning* variability. (2) It is fast
enough to use inside an optimiser. (3) It gives benchmarks that simulation cannot: the oracle and
the best observable policy. We used Monte Carlo only to *validate* the evaluator: 5.464 exact vs
5.442 ± 0.043 from 50,000 simulated episodes, and the unit tests check three more policies within 4
standard errors.

**Q68. What are the oracle and the best observable policy?**
- **Oracle:** the optimal policy if the honeypot could see x, including the type k. Solved by value
  iteration on V*(x) = max_a [r_a(x) + γ P_a(x,·)V*] (a contraction with modulus γ, so it converges
  geometrically; the test checks a Bellman residual < 10⁻⁸). No honeypot can beat 5.935.
- **Best observable:** the best *deterministic* policy over (c, φ), searched over 5³⁰ ≈ 9 × 10²⁰
  candidates. Optimising memoryless POMDP policies is NP-hard in general, so we use **coordinate
  ascent** with exact evaluation inside: change one state's action at a time, keep strict
  improvements, 8 restarts. All restarts reach the same policy: FAKE on cred_access in all three
  phases, ALLOW everywhere else. Value 5.783.

**Q69. Is the best observable policy really optimal?**
It is a strong local optimum, not a proven one. Coordinate ascent can get stuck, and a stochastic
memoryless policy could in principle do better (Singh et al.). So 5.783 is a *realistic ceiling*,
and the oracle 5.935 is a hard upper bound. We list this under threats to validity.

**Q70. What does the type posterior show?**
Propagate μ₀ through P_π one step at a time and normalise the mass at time t by type: that gives
Pr(type = k | session reached command t). Under the static policy, bots are 60% at t = 1 but only
16% of sessions that reach t ≥ 11; operators rise from 15% to 54%. So the phase is a cheap estimate
of the hidden type. That is the formal justification for having phase in the state.

**Q71. How would you fit the model to real data?**
Maximum likelihood for a Markov chain with exits:
L = Π_sessions μ(c₁) Π_i (1 − e(c_i)) P(c_i, c_{i+1}) · e(c_n).
The likelihood factorises into one multinomial for μ, one multinomial per row of P, and one
Bernoulli per e(c). Maximising each one (with Lagrange multipliers for the sum-to-one constraints)
gives normalised counts:
μ̂(c) = #starts at c / #sessions, P̂(c,c′) = #(c→c′) / #(c→·), ê(c) = #ends at c / #visits to c.
We add Laplace smoothing for unseen transitions. A test checks that the fitter recovers a known chain.
Reaction multipliers m_k(c,a) can only be identified from sessions where *different* actions were
taken, and the live learner's exploration provides those.

**Q72. Can you recover the *types* from data?**
Not with the per-type MLE above, because the type is hidden. That would need a mixture of Markov
chains fitted with EM, which is a natural extension. The current fitter estimates a single chain,
which describes the population as a whole.

---

# Part 3: Results

## Batch 7: Results and Statistics

**Q73. Give the main result.**
Balanced population, 20 seeds × 20,000 episodes, final greedy policy evaluated exactly, 95% CI:

| Policy | Return | Commands/session | Intel/session |
|---|---|---|---|
| Q-learning | **5.686 ± 0.051** | 4.056 | 9.91 |
| SARSA | 5.702 ± 0.026 | 4.064 | 9.93 |
| ε-greedy bandit | 5.503 ± 0.021 | 3.982 | 9.58 |
| Static (always ALLOW) | 5.542 | 4.034 | 9.64 |
| Random | 1.949 | 2.015 | 3.91 |
| Best observable | 5.783 | 4.157 | 10.22 |
| Oracle | 5.935 | – | – |

Q-learning beats static by 2.6% (t = 5.88, p = 5.8 × 10⁻⁶) and recovers 60% ± 21% of the gap
to the best observable policy.

**Q74. Which test, and why?**
A **one-sample, one-sided t-test** of the 20 Q-learning returns against 5.542. Static is
deterministic and evaluated exactly, so it is a constant, not a sample. Q-learning vs SARSA uses
**Welch's t-test** (two samples, unequal variances). The CI is mean ± t_{0.975,19} · s/√20, with
t_{0.975,19} ≈ 2.09.
*Follow-up, "is normality justified?":* with n = 20 the t-test is fairly robust, and p is tiny.
A Wilcoxon signed-rank test would be a sensible non-parametric check. We did not run it, so don't
claim it.

**Q75. 2.6% is small. Why should anyone care?**
Because the ceiling is small too. The best policy available to *any* honeypot with this state is
only 4.3% above static (5.783 vs 5.542), and Q-learning gets 60% of that. The small headroom is a
finding in itself: against mostly-bot traffic, a static honeypot is already near-optimal. The gain
grows to 5.2% against human-heavy traffic. And the oracle shows that a further 2.6% needs
information the honeypot doesn't have, the attacker's type.

**Q76. What did the agent learn?**
**FAKE on credential access, in every phase**: when someone runs `cat /etc/shadow` or looks for keys,
plant decoy credentials. Humans chase the decoy and reveal their next tools; bots don't care.
Q-learning finds this in 100% of seeds for early and mid, and 80% for late. Overall it agrees with
the best policy in 68% of states. Most disagreements are in states where the actions are nearly
equivalent (bots barely react) or that are rarely visited, so they cost almost nothing.

**Q77. Why does the bandit do worse than static?**
A bandit ignores the state, so it has to pick one action for all situations. FAKE helps on
cred_access but hurts operators on recon/browse (×0.85), and nothing beats ALLOW everywhere, so the
best single action is ALLOW. Exploration noise sometimes settles the bandit on something else.
The lesson: **the state matters**.

**Q78. What is the residual bias?**
In 95% of runs Q-learning chooses BLOCK in `cleanup|late`, where the best policy keeps ALLOW. A
diagnostic on fresh seeds showed that the learned Q(ALLOW) there is 1.18 against a true 2.04, while
Q(BLOCK) is exact (2.00 vs 2.00). The reason: late states are rarely visited, so the values ALLOW
bootstraps from are still near their initial levels, while BLOCK's target is terminal and does not
bootstrap. Once BLOCK is greedy, ALLOW gets about half the updates (109 vs 199), so the
underestimate persists. Cost in return: 0.0017 (0.03%). Standard remedies, left as future work:
optimistic initial values or double Q-learning.

**Q79. What does online performance look like during learning?**
All three learners stay *below* static online (≈ 5.42 vs 5.55 at the end), even though their
greedy policies beat it. With ε ≥ 0.05, about 1 action in 20 is random, and 1 in 100 is a random
session-ending BLOCK. **Exploration costs about as much as adaptation gains.** In a deployment ε
should go to zero once the policy has settled (a GLIE schedule), or you serve the greedy policy and
learn off-policy from logged sessions.

**Q80. Explain the step-size ablation table.**

| Step size | 5,000 ep. | 20,000 ep. |
|---|---|---|
| constant α = 0.1 | 5.343 ± 0.154 (2/10) | 5.479 ± 0.150 (4/10) |
| n^(−0.6) | 5.662 ± 0.080 (9/10) | 5.618 ± 0.138 (7/10) |
| **n^(−0.7)** | 5.608 ± 0.155 (8/10) | **5.710 ± 0.043 (10/10)** |
| n^(−0.85) | 5.610 ± 0.092 (7/10) | 5.676 ± 0.067 (8/10) |
| 1/n | 5.513 ± 0.087 (4/10) | 5.611 ± 0.083 (6/10) |

(In parentheses: seeds whose final policy beats static.) Every Robbins–Monro schedule beats
static. Constant α never does on average. 1/n is the weakest decaying schedule (Even-Dar and
Mansour). The ω values in between are not significantly different.

**Q81. RQ2: how does it depend on the population and the objective?**

| Mix | Objective | Static | Q-learning | Best obs. | Oracle |
|---|---|---|---|---|---|
| balanced | intel | 5.542 | 5.736 ± 0.012 | 5.783 | 5.935 |
| bot-heavy | intel | 5.133 | 5.159 ± 0.039 | 5.222 | 5.281 |
| human-heavy | intel | 6.273 | 6.600 ± 0.060 | 6.740 | 6.953 |
| balanced | attrition | 5.542 | 5.659 ± 0.076 | 5.783 | 5.937 |
| bot-heavy | attrition | 5.133 | 5.135 ± 0.038 | 5.222 | 5.282 |
| human-heavy | attrition | 6.273 | 6.634 ± 0.055 | 6.740 | 6.957 |

- **Adaptation pays in proportion to how adaptive the attackers are**: +0.5% (bots, not
  significant), +3.5% (balanced), +5.2% (human-heavy).
- **The learned structure is stable:** FAKE on cred_access appears in every scenario. With many bots
  the best policy also fakes during file browsing. Under attrition it uses DELAY on late cleanup.
- **TARPIT is never chosen**, even when wasting time is rewarded. The sessions it ends are worth
  more than the time it wastes.

**Q82. The main table says 5.686 for balanced, the sensitivity table says 5.736. Why?**
Same configuration, different seeds: the sensitivity runs use 10 seeds from a separate range (1000+).
The intervals overlap (5.686 ± 0.051 reaches 5.737). The headline number is the 20-seed main
experiment, and the difference is a good illustration of why we report CIs over seeds.

**Q83. What are the threats to validity?**
1. **Model dependence:** effect sizes depend on the assumed reactions. The qualitative conclusions
   hold in all six scenarios, and the MLE fitting is how to tighten them.
2. **Abstraction:** the simulator generates categories, not command strings, so classifier errors
   on real input are not modelled.
3. **Stationarity:** real populations drift; mine is a fixed mixture.
4. **Reward design:** mitigated by reporting commands and intelligence too.
5. **Benchmark optimality:** the best observable policy is a local optimum of an NP-hard problem.

---

# Part 1 (continued): Pipeline, Database, Dashboard, Deployment

## Batch 8: Redis Streams and the Pipeline

**Q84. How does the honeypot publish events without ever blocking?**
**Store-and-forward.** `emit()` serialises the event into a bounded in-memory deque (50,000 events)
and returns immediately. A background task forwards it to Redis with `XADD`, in order, retrying
with exponential backoff (0.5 s to 30 s) during an outage. If an outage outlasts the buffer, the
*oldest* events are dropped and **counted**, never silently.

**Q85. Why did you build it that way? What was there before?**
The first version awaited `XADD` inline. During a Redis-outage test it **disconnected every attacker**
(defect D3), because the emit was inside SSH authentication. That broke the architecture's central
claim, so we replaced it. There is now a regression test.

**Q86. What if Redis dies *and* the honeypot crashes?**
The buffered events are lost, because the buffer is in memory. That is a known limitation, and the
fix is a disk-backed spool. Redis itself runs with append-only-file persistence on a volume.

**Q87. Explain XADD, XREADGROUP, XACK, the PEL and XAUTOCLAIM.**
- `XADD` appends an entry to the stream; Redis assigns a monotonically increasing ID.
- `XREADGROUP GROUP pipeline <consumer> … >` delivers new entries to one consumer in the group, and
  blocks for up to 5 s when the stream is idle.
- Delivered but unacknowledged entries sit in that consumer's **Pending Entries List**.
- `XACK` removes an entry from the PEL once it has been processed.
- `XAUTOCLAIM` transfers entries that have been pending for too long on *another* (dead) consumer
  to this one.

**Q88. What does the pipeline do on startup?**
Three steps: (1) create the group if it is missing (`MKSTREAM`; ignore `BUSYGROUP`); (2) **reclaim
orphans** of dead consumers with XAUTOCLAIM; (3) replay its own pending entries (read from ID `0`).
Only then does it read new ones (`>`). We added XAUTOCLAIM because consumer names used to include the
PID, so a restart left the old consumer's messages stuck.

**Q89. What delivery guarantee do you give, and how do you avoid duplicates?**
**At-least-once**: each event is applied to Postgres in one transaction, and only *then* XACKed. A
crash in between means redelivery, so every write is **idempotent**:
- attackers: `INSERT … ON CONFLICT (src_ip) DO UPDATE`, with counters incremented in the same
  statement;
- commands: `ON CONFLICT (session_id, seq) DO NOTHING`, and the session's command count is
  incremented only if a row was actually inserted;
- a command that arrives before its `session_start` creates a placeholder session row, so the
  foreign key holds.
"Exactly-once" processing = at-least-once delivery + idempotent effects.

**Q90. Why not ACK before processing?**
Then a crash after the ACK would lose the event: at-most-once.

**Q91. What happens to a bad event?**
Malformed JSON, and non-transient database errors (`PostgresError`, `KeyError`, `ValueError`,
`TypeError`), are copied to the dead-letter stream `honeypot:dead` with the reason and the original
ID, then acknowledged, so a single bad message cannot block the group. Transient errors (connection
lost) are retried with backoff.

**Q92. Tell us about a bug you found in the pipeline.**
D1: the first scanner that disconnected *without logging in* crashed the pipeline, because the
attacker upsert had no counters to increment and generated invalid SQL. Fixed the SQL generation,
and now non-transient errors are dead-lettered instead of crashing the service.
D2: the pipeline container restarted every few seconds when idle. The Redis client's socket timeout
was shorter than the 5 s `BLOCK` window, and the code caught Python's `ConnectionError` instead of
redis-py's `RedisError`. Fix: socket timeout = block window + 10 s, catch `RedisError`, and recreate
the group on `NOGROUP`.

**Q93. How does GeoIP work?**
MaxMind GeoLite2 when the database file is mounted (it is optional, read-only and cached per IP).
Without it, loopback and private ranges are labelled and public addresses stay unknown. GeoIP gives
a location for the *IP*, not the person: it is often a VPS or a compromised machine.

**Q94. Can multiple pipelines run?**
Yes. Several consumers in the `pipeline` group split the stream between them. Because writes are
idempotent, redelivery during a rebalance is harmless. Ordering *within* a session could then be
broken across consumers, which the placeholder-session logic tolerates.

**Q95. Why not Kafka?**
For one sensor and a few thousand events per hour, Redis Streams gives the same semantics we need
(durable log, consumer groups, ACKs) with far less to operate. With many sensors and long retention
We would move to Kafka.

## Batch 9: PostgreSQL

**Q96. Describe the schema.**
Four tables:
```
attackers (1) ──< sessions (1) ──< session_actions
attackers (1) ──< login_attempts
```
- `attackers`: PK `src_ip INET`. first/last seen, counters (connections, login attempts, sessions,
  commands), last username, country, city, coordinates, ASN.
- `login_attempts`: PK `BIGSERIAL`. ts, IP, username, password, attempt number, success.
- `sessions`: PK `session_id UUID`. IP, credentials, PTY/term, start/end, duration, command count,
  end reason, total reward, ε, episode.
- `session_actions`: PK `(session_id, seq)`. ts, command, category, phase, state, action, ε,
  **q_before (JSONB)**, latency, output bytes, decoys planted, and from the `rl_update` event:
  **reward, continued, next_state, q_after (JSONB)**.
Foreign keys cascade on delete.

**Q97. Why UUID and not the IP for a session?**
One IP can open many sessions, at the same time or later.

**Q98. Which normal form?**
3NF, with one deliberate denormalisation: the per-attacker counters are stored redundantly for
dashboard speed, and they are kept correct by the idempotent upserts.

**Q99. Why JSONB for Q-values?**
It is a small map of 5 action → value pairs that is always read and written as a whole and never
filtered on. JSONB keeps it in one column. The RL heatmap is rebuilt from the latest `q_after` per
state.

**Q100. What indexes, and why?**
`attackers(last_seen DESC)`, `login_attempts(src_ip, ts DESC)` and `(ts DESC)`,
`sessions(src_ip, started_at DESC)` and `(started_at DESC)`, `session_actions(category)`,
`(state, action)` and `(ts DESC)`. Each one serves a dashboard query: recent activity, per-attacker
pages, category mix, and the Q-table/action mix.

**Q101. Are passwords hashed?**
No. Captured passwords are *attacker-supplied* data, and they are the intelligence. They are not
user secrets. That is exactly why the dashboard must be protected (Q109).

**Q102. 10 million actions: what breaks?**
Aggregations over `session_actions`. Fixes: partition by time, pre-aggregate hourly counts,
archive old partitions, and add read replicas for the dashboard.

## Batch 10: Dashboard, Security, Deployment, Testing

**Q103. What does the dashboard show?**
Five views. **Overview**: counters refreshed every 10 s from `/api/stats`, sessions per hour, top
usernames/passwords/commands/countries, category mix, and the agent's action mix. **Sessions** and
**session detail**: a terminal replay plus a per-command timeline (category, phase, action, reward,
continued, greedy action before the decision). **Attackers**: a per-IP profile. **RL**: learning
curves, action mix over time, and the Q-table heatmap. Routes: `/`, `/sessions`, `/sessions/{id}`,
`/attackers`, `/attackers/{ip}`, `/rl`, `/api/stats`, `/healthz`.

**Q104. Why server-side SVG instead of a chart library?**
No JavaScript dependency, it works with a strict CSP, the charts are tiny, and they render in tests.

**Q105. The dashboard displays attacker-typed text. What's the risk?**
**Stored XSS against the analyst.** A username like `<script>…` would run in the analyst's browser.
Defences: Jinja2 autoescaping for all text, `tojson` for data passed to JavaScript, no inline
scripts, and a CSP with `script-src 'self'`. A test injects `<script>` as a username, password and
command and asserts that it never appears unescaped.

**Q106. Your CSP allows `'unsafe-inline'` styles. Why?**
The bar charts set widths with inline `style` attributes, and the stricter CSP blanked them (defect
D4). Inline *styles* cannot run code, so we allowed only those. Scripts are still restricted to the
same origin.

**Q107. What happens if Postgres is down when someone opens the dashboard?**
A 503 page (or JSON for the API) that explains that capture continues, not a raw 500.

**Q108. Why FastAPI + asyncpg?**
The whole stack is async. asyncpg gives a connection pool (1–10 connections), so requests borrow a
connection instead of opening one, and the event loop is never blocked waiting for a query.

**Q109. Is the dashboard secure enough for production?**
Not yet: there is no authentication or HTTPS. Mitigation: it binds to 127.0.0.1 and is meant to be
reached over an SSH tunnel or VPN. Authentication is the first item of operational future work.

**Q110. How is the honeypot container hardened?**

| Layer | Measure |
|---|---|
| Application | emulation only: no exec/subprocess in the command path |
| Process | UID 10001, `cap_drop: ALL` (CapEff = 0), `no-new-privileges` |
| Filesystem | read-only root, 16 MB tmpfs at /tmp |
| Resources | 256 PIDs, 512 MB, 1 CPU |
| Network | `ingest` network only: Redis reachable, **Postgres not even resolvable** |
| Health check | reads `/proc/net/tcp` instead of connecting, so probes aren't recorded as attackers |

We *verified* each of these inside the running container: `id`, `touch` → read-only, `CapEff`
all zeros, `postgres` → "Name or service not known".

**Q111. Why split the network in two?**
Defence in depth. If someone broke out of the emulator into the Python process, the database still
would not be reachable from there. The pipeline is the only bridge.

**Q112. How does startup order work?**
`depends_on` with `condition: service_healthy`. Redis is checked with `redis-cli ping`, Postgres
with `pg_isready`. The honeypot waits for Redis, the pipeline for Redis and Postgres, the dashboard
for Postgres. Startup order alone isn't enough, because a started container may not be accepting
connections yet.

**Q113. What volumes are there?**
Three: the Postgres data, the Redis append-only file, and `honeypot-data` (SSH host keys plus the
Q-table checkpoint).

**Q114. How is the Q-table saved safely?**
At the end of each episode it is written to a temporary file and **renamed** over the old one (an
atomic rename), so a crash mid-write can't corrupt it. It stores Q, the visit counts n(s,a) (needed
for α_n), the episode count and ε, so learning resumes exactly where it stopped.

**Q115. How did you test it?**
111 automated tests: classifier (25), fake FS (8), shell (15), policies (12), emitter (4), real SSH
server (5), pipeline (12, including a full SSH → honeypot → Redis → pipeline → Postgres test), dashboard (20,
including XSS and 503), simulator (10, including Monte Carlo within 4 standard errors of exact,
oracle ≥ best observable ≥ static, Bellman residual < 10⁻⁸, MLE recovery). Pipeline and dashboard
tests use a separate `cruxtrap_test` database and Redis DB 15.

**Q116. What did the failure experiments show?**
We stopped each downstream component during live SSH sessions:

| Outage | Attackers served | Events recovered |
|---|---|---|
| Redis | yes | all ("forwarding 23 buffered events") |
| PostgreSQL | 4/4 | 4/4 (waited in the stream; dashboard 503) |
| Pipeline | 4/4 | 4/4 (resumed from its group position) |

After every scenario: no dead-lettered events, and no command without a recorded reward.

**Q117. What's the lesson from the five defects?**
Unit tests checked each component in its steady state. D1–D3 only appeared at **boundaries**: an
unauthenticated client, an idle period, a dependency outage. Running the real system under failure
found what the tests could not. D5 was a performance defect: the exact solver was about 100× slower
than expected because of multi-threaded OpenBLAS overhead on small 330 × 330 solves. Fix: pin BLAS
to one thread and parallelise across processes instead.

---

# Part 4: Hard Questions

**Q118. You designed the attacker model and then showed your agent does well in it. Isn't that circular?**
The model decides *which* deviations from static could help, but the agent never sees the model. It
learns model-free from sampled sessions. The question is whether such a learner finds the useful
deviation, and how close it gets to the best possible: 60%. It is not rigged in our favour: the
textbook configuration (constant α) *lost*, the bandit lost, and against bots there is almost no
gain. The qualitative conclusions hold across six scenarios, and the MLE fitter is the route to
replacing assumptions with data.

**Q119. Then why should we believe it works on real attackers?**
You should believe the *methodology* and the *qualitative* findings; the exact percentages need
real data. The next step is to deploy on Linux, fit the chain to sessions served by the static
policy, and run an interleaved A/B comparison between learned and static on live traffic.

**Q120. Look at the per-type numbers. Does Q-learning help every attacker type?**
No. In expected commands per session, the learned policies get more from script kiddies than
static does (4.66 vs 4.26) but fewer from operators (6.09 vs 6.57). The best observable policy
improves both (4.52 and 6.97). The likely cause is the late-state disagreements, mainly the biased
BLOCK in `cleanup|late`: most sessions that reach late phase are operators (54%), so ending them
early costs operator commands, while the reward rates that BLOCK almost the same as ALLOW (2.00 vs
2.04). This is why we report reward-independent measures, and why fixing the late-state bias
(optimistic initialisation, double Q-learning) is listed as future work.

**Q121. Couldn't a hand-written rule ("fake on cred_access") do just as well?**
Yes, *now that we know it*. The best observable policy is exactly that rule plus ALLOW elsewhere.
The point is that the agent *discovered* it without supervision, and under other populations the
right rule is different (for example, also fake on browsing when bots dominate; DELAY on late
cleanup under attrition). The evaluation framework is also how you would *validate* any rule.

**Q122. Why not include the attacker type in the state, then?**
The honeypot can't observe it. You could *estimate* it, for example from inter-command timing
(bots type instantly) or a belief state over types. The posterior result suggests that would help,
and the oracle gap (2.6%) is the most it could be worth. That is the main future-work direction.

**Q123. Is the attacker really an "environment"? Attackers adapt to the honeypot too.**
Correct. A strategic attacker who learns to detect the honeypot makes this a game, not an MDP.
Heliza framed it as a game. Our model treats attackers as non-strategic within a session, which is
fair for bots and less so for skilled operators. Non-stationarity across sessions is why a step-size
floor exists (Q59).

**Q124. Does the 60% ± 21% mean anything with such a wide interval?**
It is a ratio of a small difference (0.144) to another small difference (0.241), so it is noisy.
The robust statement is "between about 40% and 80% of the achievable gain, and significantly
above zero".

**Q125. Why should exploration cost so much?**
Five actions, ε = 0.05: each command has a 1% chance of a random BLOCK, plus random TARPITs that
kill bot sessions (×0.35). With about 4 commands per session, a few percent of sessions are
damaged, which is the same order as the 2.6% gain. A practical deployment should explore less once
it has settled.

**Q126. What would you do with two more months?**
(1) A real-traffic study with an A/B comparison. (2) Richer state: previous action, timing-based
type belief. (3) A disk-backed emitter spool. (4) Fixing the late-state bias with double
Q-learning. (5) Dashboard authentication. In that order: the first two answer the scientific
question, the rest harden the system.

**Q127. What did you learn?**
Technically: async systems, stream processing with at-least-once semantics, container hardening,
and an evaluation that actually shows a difference between policies. The most valuable lesson was
the negative result: the default learning rate failed, and stochastic-approximation theory both
predicted it and told us how to fix it. Also, most real bugs were at component boundaries,
under failure, not inside components.

**Q128. What was the hardest part?**
Making the evaluation honest: separating learning noise from evaluation noise (hence exact
evaluation), keeping tuning seeds separate from reporting seeds, and finding the right benchmark
(best observable, not the oracle). On the systems side, the Redis-outage defect (D3), because it
contradicted the design's main claim.

---

# Part 5: Whiteboard Derivations

You should be able to write each of these from memory in under two minutes.

**D1. Q-learning update and TD error.** (Q49)

**D2. Variance of constant-α estimates.**
Q_n = (1−α)Q_{n−1} + αX_n ⇒ Q_∞ = Σ_{j≥0} α(1−α)^j X_{n−j}.
Independence ⇒ Var = σ² α² Σ_j (1−α)^{2j} = σ² α² / (1 − (1−α)²) = σ² α² / (α(2−α)) = σ² α/(2−α).
α = 0.1 ⇒ 0.0526σ² ⇒ standard deviation ≈ 0.23σ. Compare α = 1/n: the sample mean, with variance σ²/n → 0.

**D3. Robbins–Monro for n^(−ω).** p-series: Σ n^(−p) < ∞ iff p > 1. Need ω ≤ 1 (divergence) and
2ω > 1 (square-summable) ⇒ ½ < ω ≤ 1.

**D4. Policy evaluation.** V = r_π + γP_πV ⇒ (I − γP_π)V = r_π. Invertible since
‖γP_π‖_∞ ≤ 0.9 × 0.98 < 1 ⇒ V = Σ_k (γP_π)^k r_π (Neumann series).

**D5. Fundamental matrix.** N = I + P + P² + … = (I − P)⁻¹. (P^k)_{xy} = Pr(at y after k steps | start
x), so N_{xy} = Σ_k Pr(…) = E[visits to y]. Expected commands = μ₀ᵀ N 1.

**D6. Value iteration converges.** The Bellman optimality operator T is a γ-contraction in the
sup-norm: ‖TV − TU‖_∞ ≤ γ‖V − U‖_∞. By Banach's fixed-point theorem it has a unique fixed point V*,
and the iterates converge geometrically.

**D7. MLE for a Markov chain.** Maximise Σ_{c′} n(c,c′) log P(c,c′) subject to Σ_{c′} P(c,c′) = 1.
Lagrangian ⇒ n(c,c′)/P(c,c′) = λ ⇒ P̂(c,c′) = n(c,c′)/Σ n(c,·). The same argument gives μ̂, and the
Bernoulli MLE gives ê.

**D8. Type posterior (Bayes).** Pr(k | reached t) = w_k Pr(reach t | k) / Σ_j w_j Pr(reach t | j).
Bots have small Pr(reach t | bot) for large t, so their posterior collapses.

**D9. ε floor timing.** 0.3 × 0.995^k = 0.05 ⇒ k = ln 6 / (−ln 0.995) ≈ 358 episodes.

**D10. Confidence interval and t statistic.** x̄ ± t_{0.975, n−1} s/√n, and t = (x̄ − μ₀)/(s/√n).
Check: half-width 0.051 ⇒ s/√20 ≈ 0.0244 ⇒ t ≈ 0.144 / 0.0244 ≈ 5.9.

---

## Study Plan

*(Each member does every day; spend extra time on your own batches.)*

1. **Day 1:** Part 0. Say the one-minute and three-minute pitches aloud until they flow. Memorise the
   numbers table.
2. **Day 2:** Part 2, Batches 4–5. Derive D1–D3 on paper without notes.
3. **Day 3:** Part 2, Batch 6. Derive D4–D8. Be able to draw the augmented chain and explain why it
   is Markov.
4. **Day 4:** Part 3 and Part 4. Practise Q75, Q118, Q120 and Q121 out loud; these are where
   examiners push.
5. **Day 5:** Part 1. Draw the architecture and the session sequence from memory, and walk through
   Q17 and the failure table (Q116).
6. **Before the viva:** run `docker compose up -d`, open the dashboard, and have one session
   replay and the RL page ready to show. Re-read "Unlearn these" at the top.

## Tips

1. **Lead with the evaluation**, not the tech stack. The panel is Mathematics & Computing.
2. **Volunteer the limitations** before they are pointed out (model assumptions, no live
   deployment, the residual bias). It reads as understanding, not weakness.
3. **Don't overstate.** Say "2.6% better, with high confidence, 60% of what is achievable" and never
   "much better". Say "the model assumes", not "attackers do".
4. **Use the negative result.** "The textbook learning rate failed, and here is the theorem that
   explains why" is the strongest moment of the viva. Rehearse it.
5. **If you don't know, say what you would do to find out.** For example: "We didn't run a
   Wilcoxon test; with 20 seeds we would expect it to agree, and it would take one line to check."
