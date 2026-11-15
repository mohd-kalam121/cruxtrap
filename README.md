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
- [x] Phase 1 — honeypot core (standalone, no infra)
- [x] Phase 2 — pipeline + PostgreSQL
- [ ] Phase 3 — dashboard
- [ ] Phase 4 — Docker Compose, end-to-end
- [ ] Phase 5 — attacker simulator + experiments
- [ ] Phase 6 — report, slides

## Run the honeypot standalone (no Docker)

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; use bin/activate on Linux
pip install -r honeypot/requirements.txt
python -m honeypot                                  # listens on :2222, events as JSON on stdout
ssh -p 2222 root@localhost                          # any password; the N-th attempt succeeds
```

Environment variables (all optional): `HONEYPOT_PORT`, `HONEYPOT_HOSTNAME`, `REDIS_URL`,
`RL_POLICY` (`qlearn|sarsa|bandit|random|static`), `RL_ALPHA`, `RL_GAMMA`, `RL_EPSILON0`,
`LOGIN_ATTEMPTS_MIN/MAX`, `QTABLE_PATH`. See `honeypot/config.py`.

## Run with the data pipeline (Redis + PostgreSQL in Docker)

```bash
docker compose up -d                                 # redis :6379, postgres :55432 (localhost only)
pip install -r pipeline/requirements.txt
python -m pipeline                                   # terminal 1: Redis Streams -> PostgreSQL
REDIS_URL=redis://127.0.0.1:6379/0 python -m honeypot   # terminal 2 (PowerShell: $env:REDIS_URL="...")
```

Postgres is published on host port **55432** because 5432/5433 are commonly taken by a
native install or other projects; override with `POSTGRES_PORT` and `DATABASE_URL`.

GeoIP: drop a MaxMind `GeoLite2-City.mmdb` into `data/` for country/city of public IPs.
Without it, loopback/private ranges are still labelled and public IPs show as unknown.

Tests: `python -m pytest` (pipeline tests use a separate `cruxtrap_test` database and
skip if Docker services are down).

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
