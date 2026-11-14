# CruxTrap — Revised Problem Statement

## 1. Background

SSH is the most widely exposed remote-administration service on the Internet and is
continuously brute-forced by automated bots and, less frequently, by human operators.
Conventional defences (firewalls, fail2ban, IDS) *block* this traffic. Blocking is
correct for production systems but discards the most valuable information an attacker
offers: **what they do after they get in** — which credentials they try, which
reconnaissance they run, what they download, how they attempt persistence.

A *honeypot* inverts the defensive posture: it deliberately admits the attacker into a
decoy environment and records everything. The dominant open-source SSH honeypot,
Cowrie, does this with a **static** policy — every attacker, every command, every
time, receives the same emulated response.

## 2. The gap

A static honeypot has two weaknesses:

1. **It is fingerprintable.** Automated tooling detects Cowrie-style honeypots from
   fixed responses, and a detected honeypot yields no further intelligence.
2. **It cannot trade off between goals.** Sometimes the best move is to answer a
   command truthfully (keep the attacker engaged); sometimes it is to feed a decoy
   credential (bait them into revealing a second-stage tool); sometimes it is to slow
   the connection (waste a bot's time); sometimes it is to disconnect (a session has
   stopped producing new information). A fixed policy makes none of these choices.

## 3. Problem statement

> **Design, implement and evaluate an SSH honeypot whose per-command response is
> chosen by a reinforcement-learning policy, with the objective of maximising the
> quantity and value of attacker behaviour captured per session, while remaining
> safe (no attacker input is ever executed on the host).**

Formally, attacker interaction is modelled as a Markov Decision Process in which the
honeypot is the agent, the attacker session is the environment, the state summarises
the attacker's current command and progress through the session, the action is the
honeypot's response strategy, and the reward measures captured intelligence
(see `02-mdp-formulation.md`). The policy is learned online by tabular Q-learning.

## 4. Objectives

| # | Objective | Deliverable |
|---|---|---|
| O1 | Safe medium-interaction SSH honeypot emulating Ubuntu | `honeypot/` — AsyncSSH server, in-memory filesystem, ~50 emulated commands |
| O2 | Formal MDP model of honeypot–attacker interaction | `docs/02-mdp-formulation.md` |
| O3 | Online Q-learning response policy | `honeypot/rl/` |
| O4 | Event-driven telemetry pipeline with GeoIP enrichment | Redis Streams → `pipeline/` → PostgreSQL |
| O5 | SOC-style analyst dashboard with session replay | `dashboard/` |
| O6 | Attacker simulator for training and controlled evaluation | `simulator/` |
| O7 | Quantitative comparison of learned policy vs. baselines | experiments + results chapter |
| O8 | Reproducible one-command deployment | `docker-compose.yml` |

## 5. Scope and limitations

**In scope:** SSH password authentication, interactive shell sessions, command
emulation, RL policy, telemetry, dashboard, simulated-attacker evaluation, optional
short Internet-facing deployment for real-traffic data.

**Out of scope:** SFTP/SCP file capture, malware sandboxing of downloaded payloads,
dashboard authentication and HTTPS (noted as future work), other protocols (Telnet,
HTTP).

## 6. Research questions

- **RQ1.** Does a Q-learning response policy capture more commands per session than a
  static (always-allow) honeypot against a simulated attacker population?
- **RQ2.** How sensitive is the result to the reward weights and to the attacker mix
  (bot-heavy vs. human-heavy)?
- **RQ3.** Does the learned policy transfer: trained in simulation, does it hold up on
  real captured sessions?

## 7. Differences from the original synopsis

| Original | Revised | Reason |
|---|---|---|
| Action `INSULT` | Action `TARPIT` (slow, dribbled output) | Insulting reveals the honeypot and has no defensible objective; tarpitting wastes bot time, a recognised deception goal |
| Accept every login on first attempt | Accept on the *N*-th attempt (N drawn per source IP) | First-try success is a known honeypot fingerprint |
| "AI-driven" with no evaluation | Formal MDP + simulator + baselines + metrics | Required for the project to make a defensible claim |
| Synopsis title "AI-Driven" | "with a Reinforcement-Learning Response Policy" | Precise about what the learning component is |
