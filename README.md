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

## Quick start

Requires Docker Desktop.

```bash
docker compose up -d --build
ssh -p 2222 root@127.0.0.1           # the honeypot: any password, the N-th attempt succeeds
# dashboard: http://127.0.0.1:8000
```

Generate demo traffic (needs a local Python venv with `asyncssh`):

```bash
HONEYPOT_TIME_SCALE=0.15 docker compose up -d honeypot     # shorten DELAY/TARPIT for demos
python scripts/demo_traffic.py --sessions 60
```

PowerShell: `$env:HONEYPOT_TIME_SCALE="0.15"; docker compose up -d honeypot`.

All ports bind to `127.0.0.1`. To expose **only the honeypot** on a real server:
`HONEYPOT_BIND=0.0.0.0 HONEYPOT_PORT=22 docker compose up -d`. See
[docs/03-deployment-and-resilience.md](docs/03-deployment-and-resilience.md) for hardening,
network segmentation and measured failure behaviour.

## Repository layout

| Path | Purpose |
|---|---|
| `docs/` | Problem statement, MDP formulation, deployment & resilience, synopsis, viva guide |
| `honeypot/` | AsyncSSH server, fake filesystem, command emulation, RL agent, event emitter |
| `pipeline/` | Redis Streams consumer → GeoIP enrichment → PostgreSQL |
| `dashboard/` | FastAPI + Jinja2 SOC dashboard with session replay and Q-table view |
| `simulator/` | Attacker population model, exact DP solver, experiments, figures (`python -m simulator.experiments`) |
| `db/` | PostgreSQL schema |
| `scripts/` | Demo traffic generator |
| `geoip/` | Optional MaxMind GeoLite2-City database (not committed) |
| `docker-compose.yml` | All five services |

## Status

- [x] Phase 0 — repository, problem statement, MDP formulation
- [x] Phase 1 — honeypot core
- [x] Phase 2 — pipeline + PostgreSQL
- [x] Phase 3 — dashboard
- [x] Phase 4 — Docker Compose, hardening, failure testing
- [x] Phase 5 — attacker simulator, exact analysis, experiments ([docs/04-evaluation.md](docs/04-evaluation.md))
- [ ] Phase 6 — report, slides

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `HONEYPOT_BIND` / `HONEYPOT_PORT` | `127.0.0.1` / `2222` | Host address/port for the honeypot |
| `HONEYPOT_HOSTNAME` | `ubuntu-srv01` | Hostname shown to attackers |
| `RL_POLICY` | `qlearn` | `qlearn`, `sarsa`, `bandit`, `random`, `static` |
| `RL_ALPHA_SCHEDULE`, `RL_ALPHA_OMEGA`, `RL_ALPHA_MIN` | `visit`, `0.7`, `0` | Step size αₙ = max(α_min, n^−ω) per (state, action); `constant` uses `RL_ALPHA` |
| `RL_GAMMA`, `RL_EPSILON0` | `0.9`, `0.3` | Discount, initial exploration |
| `LOGIN_ATTEMPTS_MIN/MAX` | `1` / `3` | The N-th password attempt succeeds, N uniform in range |
| `HONEYPOT_TIME_SCALE` | `1` | Multiplier for DELAY/TARPIT durations (demos only) |
| `POSTGRES_PORT` | `55432` | Host port for PostgreSQL (5432/5433 are often taken) |
| `DASHBOARD_PORT` | `8000` | Host port for the dashboard |

## Development without Docker

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; bin/activate on Linux
pip install -r honeypot/requirements.txt -r pipeline/requirements.txt -r dashboard/requirements.txt pytest pytest-asyncio httpx
python -m honeypot                                  # localhost:2222, events as JSON on stdout
```

With Redis and PostgreSQL from compose (`docker compose up -d redis postgres`):

```bash
python -m pipeline
REDIS_URL=redis://127.0.0.1:6379/0 python -m honeypot
uvicorn dashboard.app:app --host 127.0.0.1 --port 8000
```

Experiments: `pip install numpy scipy matplotlib threadpoolctl`, then `python -m simulator.experiments` (about 1 minute; writes `docs/results/` and `docs/figures/`).

Tests: `python -m pytest` (111 tests; pipeline and dashboard tests use a separate
`cruxtrap_test` database and skip if PostgreSQL/Redis are not running).

## Safety

The honeypot never executes attacker input. Every command is interpreted against an
in-memory filesystem that is discarded when the session ends, inside a non-root,
read-only, capability-free container that cannot reach the database. Captured
credentials are attacker-supplied and are stored in plaintext by design. Decoy
"credentials" planted by the FAKE action are visibly fake placeholders.
