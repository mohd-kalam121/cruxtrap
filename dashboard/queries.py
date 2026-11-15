"""All SQL used by the dashboard. Read-only."""
from __future__ import annotations

import json
import uuid

import asyncpg

CATEGORIES = ("recon", "fs_browse", "cred_access", "download", "execute", "persist", "privesc", "cleanup", "benign", "unknown")
PHASES = ("early", "mid", "late")
ACTIONS = ("ALLOW", "DELAY", "FAKE", "TARPIT", "BLOCK")


async def init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=init_conn)


# ------------------------------------------------------------------ overview
async def stats(pool) -> dict:
    row = await pool.fetchrow("""
        SELECT (SELECT count(*) FROM attackers)                                        AS attackers,
               (SELECT count(*) FROM sessions)                                         AS sessions,
               (SELECT count(*) FROM session_actions)                                  AS commands,
               (SELECT count(*) FROM login_attempts)                                   AS login_attempts,
               (SELECT count(*) FROM sessions WHERE started_at > now() - interval '24 hours') AS sessions_24h,
               (SELECT count(*) FROM session_actions WHERE decoys_planted AND category = 'cred_access') AS decoy_reads,
               (SELECT round(avg(command_count)::numeric, 2) FROM sessions WHERE ended_at IS NOT NULL) AS avg_commands,
               (SELECT epsilon  FROM sessions WHERE epsilon IS NOT NULL ORDER BY started_at DESC LIMIT 1) AS epsilon,
               (SELECT episode  FROM sessions WHERE episode IS NOT NULL ORDER BY started_at DESC LIMIT 1) AS episodes
    """)
    d = dict(row)
    d["avg_commands"] = float(d["avg_commands"]) if d["avg_commands"] is not None else None
    return d


async def sessions_per_hour(pool, hours: int = 24) -> list[dict]:
    rows = await pool.fetch("""
        SELECT h AS hour, count(s.session_id) AS n
        FROM generate_series(date_trunc('hour', now()) - ($1 - 1) * interval '1 hour', date_trunc('hour', now()), interval '1 hour') h
        LEFT JOIN sessions s ON date_trunc('hour', s.started_at) = h
        GROUP BY h ORDER BY h""", hours)
    return [dict(r) for r in rows]


async def top(pool, column: str, table: str, limit: int = 8) -> list[dict]:
    allowed = {("username", "login_attempts"), ("password", "login_attempts"), ("command", "session_actions"),
               ("category", "session_actions"), ("action", "session_actions"), ("country", "attackers")}
    if (column, table) not in allowed:
        raise ValueError("column not allowed")
    rows = await pool.fetch(f"""SELECT {column} AS label, count(*) AS n FROM {table}
                                WHERE {column} IS NOT NULL GROUP BY {column} ORDER BY n DESC, label LIMIT $1""", limit)
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ sessions
async def list_sessions(pool, q: str = "", min_commands: int = 0, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    where = "WHERE s.command_count >= $1 AND ($2 = '' OR host(s.src_ip) LIKE $2 || '%' OR s.username ILIKE '%' || $2 || '%')"
    total = await pool.fetchval(f"SELECT count(*) FROM sessions s {where}", min_commands, q)
    rows = await pool.fetch(f"""
        SELECT s.*, host(s.src_ip) AS ip, a.country_code, a.country
        FROM sessions s JOIN attackers a USING (src_ip) {where}
        ORDER BY s.started_at DESC LIMIT $3 OFFSET $4""", min_commands, q, limit, offset)
    return [dict(r) for r in rows], total


async def get_session(pool, session_id: str) -> dict | None:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return None
    row = await pool.fetchrow("""SELECT s.*, host(s.src_ip) AS ip, a.country_code, a.country, a.city
                                 FROM sessions s JOIN attackers a USING (src_ip) WHERE s.session_id = $1""", sid)
    if row is None:
        return None
    actions = await pool.fetch("SELECT * FROM session_actions WHERE session_id = $1 ORDER BY seq", sid)
    session = dict(row)
    session["actions"] = [dict(a) for a in actions]
    return session


# ----------------------------------------------------------------- attackers
async def list_attackers(pool, q: str = "", limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    where = "WHERE ($1 = '' OR host(src_ip) LIKE $1 || '%' OR country ILIKE '%' || $1 || '%')"
    total = await pool.fetchval(f"SELECT count(*) FROM attackers {where}", q)
    rows = await pool.fetch(f"SELECT *, host(src_ip) AS ip FROM attackers {where} ORDER BY last_seen DESC LIMIT $2 OFFSET $3",
                            q, limit, offset)
    return [dict(r) for r in rows], total


async def get_attacker(pool, ip: str) -> dict | None:
    try:
        row = await pool.fetchrow("SELECT *, host(src_ip) AS ip FROM attackers WHERE src_ip = $1::inet", ip)
    except (asyncpg.DataError, asyncpg.InvalidTextRepresentationError):
        return None
    if row is None:
        return None
    a = dict(row)
    a["sessions"] = [dict(r) for r in await pool.fetch(
        "SELECT * FROM sessions WHERE src_ip = $1::inet ORDER BY started_at DESC LIMIT 100", ip)]
    a["logins"] = [dict(r) for r in await pool.fetch(
        "SELECT * FROM login_attempts WHERE src_ip = $1::inet ORDER BY ts DESC LIMIT 100", ip)]
    a["categories"] = [dict(r) for r in await pool.fetch(
        """SELECT category AS label, count(*) AS n FROM session_actions sa JOIN sessions s USING (session_id)
           WHERE s.src_ip = $1::inet GROUP BY category ORDER BY n DESC""", ip)]
    return a


# ------------------------------------------------------------------------ RL
async def q_table(pool) -> dict[str, dict]:
    """Latest Q-values per state, reconstructed from rl_update rows (q_after), plus visit counts
    and mean reward per (state, action)."""
    latest = await pool.fetch("""SELECT DISTINCT ON (state) state, q_after FROM session_actions
                                 WHERE q_after IS NOT NULL ORDER BY state, ts DESC, seq DESC""")
    visits = await pool.fetch("""SELECT state, action, count(*) AS n, avg(reward) AS r FROM session_actions
                                 WHERE state IS NOT NULL GROUP BY state, action""")
    table: dict[str, dict] = {}
    for r in latest:
        table.setdefault(r["state"], {"q": {}, "visits": {}, "reward": {}})["q"] = r["q_after"] or {}
    for r in visits:
        t = table.setdefault(r["state"], {"q": {}, "visits": {}, "reward": {}})
        t["visits"][r["action"]] = r["n"]
        t["reward"][r["action"]] = float(r["r"]) if r["r"] is not None else None
    return table


async def learning_curve(pool, bucket: int = 20) -> list[dict]:
    """Per block of `bucket` consecutive finished sessions: mean commands, mean return, epsilon."""
    rows = await pool.fetch("""
        WITH s AS (SELECT command_count, total_reward, epsilon,
                          (row_number() OVER (ORDER BY started_at) - 1) / $1 AS b
                   FROM sessions WHERE ended_at IS NOT NULL)
        SELECT b, count(*) AS n, avg(command_count) AS commands, avg(total_reward) AS reward, avg(epsilon) AS epsilon
        FROM s GROUP BY b ORDER BY b""", bucket)
    return [{k: (float(v) if v is not None and k != "b" and k != "n" else v) for k, v in dict(r).items()} for r in rows]


async def action_mix(pool, bucket: int = 20) -> list[dict]:
    rows = await pool.fetch("""
        WITH s AS (SELECT session_id, (row_number() OVER (ORDER BY started_at) - 1) / $1 AS b FROM sessions)
        SELECT s.b, sa.action, count(*) AS n FROM session_actions sa JOIN s USING (session_id)
        GROUP BY s.b, sa.action ORDER BY s.b""", bucket)
    out: dict[int, dict] = {}
    for r in rows:
        out.setdefault(r["b"], {a: 0 for a in ACTIONS})[r["action"]] = r["n"]
    return [{"b": b, **counts} for b, counts in sorted(out.items())]
