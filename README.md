# CruxTrap — An Adaptive SSH Honeypot with a Reinforcement-Learning Response Policy

Final-year B.Tech project (Mathematics & Computing), Delhi Technological University.

CruxTrap is a medium-interaction SSH honeypot that emulates an Ubuntu server inside an
in-memory fake filesystem, records attacker credentials and commands, and uses a
tabular **Q-learning** agent to choose how to respond to each command so as to maximise
the amount of attacker behaviour it captures.

```
Attacker ──▶ SSH Honeypot ──▶ Redis Streams ──▶ Pipeline ──▶ PostgreSQL ──▶ FastAPI Dashboard
             (AsyncSSH + RL)   (event bus)      (+GeoIP)     (storage)      (SOC-style UI)
```

## Repository layout

| Path | Purpose |
|---|---|
| `docs/` | Problem statement, MDP formulation, synopsis, viva guide, report sources |
| `honeypot/` | AsyncSSH server, fake filesystem, command processor, RL agent, Redis emitter |
| `pipeline/` | Redis Streams consumer → GeoIP enrichment → PostgreSQL |
| `dashboard/` | FastAPI + Jinja2 SOC dashboard with session replay |
| `simulator/` | Markov-chain attacker simulator and RL experiments (baselines, learning curves) |
| `db/` | PostgreSQL schema |
| `docker-compose.yml` | One-command deployment of all five services |

## Status

- [x] Phase 0 — repository, problem statement, MDP formulation
- [ ] Phase 1 — honeypot core (standalone, no infra)
- [ ] Phase 2 — pipeline + PostgreSQL
- [ ] Phase 3 — dashboard
- [ ] Phase 4 — Docker Compose, end-to-end
- [ ] Phase 5 — attacker simulator + experiments
- [ ] Phase 6 — report, slides

## Quick start (after Phase 4)

```bash
docker compose up --build
ssh -p 2222 root@localhost          # the honeypot
open http://localhost:8000          # the dashboard
```

## Safety

The honeypot never executes attacker input on the host. Every command is interpreted
against an in-memory filesystem that is discarded when the session ends. Captured
credentials are attacker-supplied and are stored in plaintext by design.
