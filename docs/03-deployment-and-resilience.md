# CruxTrap — Deployment, Hardening and Resilience

## 1. Deployment

```
docker compose up -d --build
```

| Service | Image | Host port (default) | Networks | Purpose |
|---|---|---|---|---|
| honeypot | `cruxtrap/honeypot` | 127.0.0.1:2222 | ingest | AsyncSSH honeypot + RL agent |
| redis | `redis:7-alpine` | 127.0.0.1:6379 | ingest | Event bus (Streams, AOF persistence) |
| pipeline | `cruxtrap/pipeline` | — | ingest, storage | Redis → GeoIP → PostgreSQL |
| postgres | `postgres:16-alpine` | 127.0.0.1:55432 | storage | System of record |
| dashboard | `cruxtrap/dashboard` | 127.0.0.1:8000 | storage | SOC UI (read-only) |

Every port binds to localhost by default. A real deployment exposes **only the honeypot**:
`HONEYPOT_BIND=0.0.0.0 HONEYPOT_PORT=22 docker compose up -d` (move the host's real sshd
to another port first). The dashboard has no authentication; reach it through an SSH tunnel.

Persistent volumes: `pg-data` (database), `redis-data` (stream, AOF), `honeypot-data`
(SSH host keys, so the server fingerprint is stable, and the learned Q-table).

## 2. Hardening of the exposed component

The honeypot is the only container that talks to attackers. Defence in depth, innermost first:

1. **Emulation, not execution.** Commands are interpreted by Python handlers against an
   in-memory filesystem; no attacker input reaches a real shell, `exec` or `subprocess`.
2. **Unprivileged process.** Runs as UID 10001 with an effective capability set of 0.
3. **Immutable container.** Read-only root filesystem; a 16 MB `tmpfs` at `/tmp`;
   `no-new-privileges`; limits of 256 processes, 512 MB RAM and 1 CPU.
4. **Network segmentation.** Attached only to the `ingest` network with Redis. The name
   `postgres` does not even resolve from inside the honeypot container.

Verified on the running stack (2026-11-15):

| Check | Result |
|---|---|
| `id` inside honeypot | `uid=10001(cruxtrap)` |
| `touch /app/x` | `Read-only file system` |
| `CapEff` in `/proc/self/status` | `0000000000000000` |
| connect `postgres:5432` from honeypot | `Name or service not known` |
| connect `redis:6379` from honeypot | ok |
| host listeners on 2222/6379/8000/55432 | all `127.0.0.1` |

## 3. Failure behaviour

Design goal: **attack capture must never depend on anything downstream of the honeypot.**

- The honeypot's event emitter is *store-and-forward*: `emit()` appends to a bounded
  in-memory buffer (50,000 events) and returns immediately; a background task forwards to
  Redis in order with exponential backoff. If an outage outlasts the buffer, the oldest
  events are dropped and counted.
- The pipeline acknowledges a message only after its PostgreSQL transaction commits
  (at-least-once). All writes are idempotent, so redelivery is harmless. On start it
  reclaims messages left pending by a dead consumer (`XAUTOCLAIM`) and replays its own.
- Malformed or unprocessable events go to `honeypot:dead` instead of blocking the stream.

Measured on the running stack (SSH sessions opened during the outage, then the
service restored):

| Outage | Honeypot accepts attackers? | Sessions recovered after restore | Notes |
|---|---|---|---|
| Redis stopped | yes | all | honeypot log: `buffering events` → `forwarding 23 buffered events` |
| PostgreSQL stopped | yes (4/4) | 4/4 | events wait in the stream; dashboard returns 503 |
| Pipeline stopped | yes (4/4) | 4/4 | resumes from its consumer-group position |
| Pipeline idle (no traffic) | — | — | 0 restarts over 40 s (regression test for a socket-timeout crash) |

After all scenarios: 0 dead-lettered events, 0 commands without a recorded reward.

**Limits:** the emitter buffer lives in memory, so events emitted during a Redis outage
are lost if the honeypot process itself also dies before Redis returns. A disk-backed
spool would close that gap; it is listed as future work.

## 4. Bugs found by running the system (not by unit tests)

| Symptom | Cause | Fix |
|---|---|---|
| Pipeline crashed on the first unauthenticated scanner | `disconnect` event upserted an attacker with no counters → invalid SQL | Correct SQL generation; non-transient DB errors now dead-letter instead of crashing |
| Pipeline container restarted every ~5 s when idle | Client socket timeout shorter than the `XREADGROUP BLOCK` window; handler caught Python's `ConnectionError`, not redis-py's | Socket timeout > block window; catch `RedisError`; recreate the group on `NOGROUP` |
| Every attacker disconnected while Redis was down | Emitter awaited `XADD` inside the SSH auth/session path | Store-and-forward emitter |
| Dashboard charts blank | CSP `style-src 'self'` blocked inline `style` attributes used for bar widths | Allow inline styles only (scripts remain same-origin only) |
