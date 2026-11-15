"""PostgreSQL writes. Every method is idempotent so a redelivered event is harmless."""
from __future__ import annotations

import ipaddress
import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

log = logging.getLogger("pipeline.db")


def ts_of(event: dict) -> datetime:
    t = event.get("ts")
    if not t:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(t)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ip_of(event: dict):
    return ipaddress.ip_address(event.get("src_ip") or "0.0.0.0")


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self, schema_path: str | None = None) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        if schema_path:
            with open(schema_path, encoding="utf-8") as f:
                await self.pool.execute(f.read())

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    # ----------------------------------------------------------- attackers
    async def ensure_attacker(self, conn, event: dict, geo: dict, **increments) -> None:
        sets = ", ".join(f"{k} = attackers.{k} + {int(v)}" for k, v in increments.items() if v) or "last_seen = EXCLUDED.last_seen"
        await conn.execute(
            f"""INSERT INTO attackers (src_ip, first_seen, last_seen, country_code, country, city, latitude, longitude,
                                       last_username, {", ".join(increments)})
                VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8, {", ".join(str(int(v)) for v in increments.values())})
                ON CONFLICT (src_ip) DO UPDATE SET
                    last_seen = GREATEST(attackers.last_seen, EXCLUDED.last_seen),
                    last_username = COALESCE(EXCLUDED.last_username, attackers.last_username),
                    country_code = COALESCE(attackers.country_code, EXCLUDED.country_code),
                    country = COALESCE(attackers.country, EXCLUDED.country),
                    city = COALESCE(attackers.city, EXCLUDED.city),
                    latitude = COALESCE(attackers.latitude, EXCLUDED.latitude),
                    longitude = COALESCE(attackers.longitude, EXCLUDED.longitude),
                    {sets}""",
            ip_of(event), ts_of(event), geo.get("country_code"), geo.get("country"), geo.get("city"),
            geo.get("latitude"), geo.get("longitude"), event.get("username"))

    # -------------------------------------------------------------- events
    async def on_connection(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn:
            await self.ensure_attacker(conn, event, geo, total_connections=1)

    async def on_login_attempt(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await self.ensure_attacker(conn, event, geo, total_login_attempts=1)
            await conn.execute(
                """INSERT INTO login_attempts (ts, src_ip, src_port, username, password, attempt, success)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                ts_of(event), ip_of(event), event.get("src_port"), event.get("username"), event.get("password"),
                event.get("attempt"), bool(event.get("success")))

    async def on_session_start(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await self.ensure_attacker(conn, event, geo, total_sessions=1)
            await conn.execute(
                """INSERT INTO sessions (session_id, src_ip, src_port, username, password, started_at, pty, term, exec_command)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   ON CONFLICT (session_id) DO NOTHING""",
                uuid.UUID(event["session_id"]), ip_of(event), event.get("src_port"), event.get("username"),
                event.get("password"), ts_of(event), event.get("pty"), event.get("term"), event.get("exec_command"))

    async def on_command(self, event: dict, geo: dict) -> None:
        sid = uuid.UUID(event["session_id"])
        async with self.pool.acquire() as conn, conn.transaction():
            await self.ensure_attacker(conn, event, geo, total_commands=1)
            # session_start may have been lost; keep the FK satisfied
            await conn.execute(
                """INSERT INTO sessions (session_id, src_ip, src_port, started_at) VALUES ($1, $2, $3, $4)
                   ON CONFLICT (session_id) DO NOTHING""", sid, ip_of(event), event.get("src_port"), ts_of(event))
            inserted = await conn.execute(
                """INSERT INTO session_actions (session_id, seq, ts, command, category, phase, state, action, epsilon,
                                                q_before, latency_ms, output_bytes, decoys_planted)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13)
                   ON CONFLICT (session_id, seq) DO NOTHING""",
                sid, event["seq"], ts_of(event), event.get("command", ""), event.get("category"), event.get("phase"),
                event.get("state"), event.get("action"), event.get("epsilon"), json.dumps(event.get("q_values")),
                event.get("latency_ms"), event.get("output_bytes"), event.get("decoys_planted"))
            if inserted.endswith("1"):
                await conn.execute("UPDATE sessions SET command_count = command_count + 1 WHERE session_id = $1", sid)

    async def on_rl_update(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE session_actions SET reward = $3, continued = $4, next_state = $5, q_after = $6::jsonb
                   WHERE session_id = $1 AND seq = $2""",
                uuid.UUID(event["session_id"]), event["seq"], event.get("reward"), event.get("continued"),
                event.get("next_state"), json.dumps(event.get("q_values")))

    async def on_session_end(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE sessions SET ended_at = $2, duration_s = $3, end_reason = $4, total_reward = $5,
                                       epsilon = $6, episode = $7,
                                       command_count = GREATEST(command_count, $8)
                   WHERE session_id = $1""",
                uuid.UUID(event["session_id"]), ts_of(event), event.get("duration_s"), event.get("reason"),
                event.get("total_reward"), event.get("epsilon"), event.get("episodes"), event.get("commands") or 0)

    async def on_disconnect(self, event: dict, geo: dict) -> None:
        async with self.pool.acquire() as conn:
            await self.ensure_attacker(conn, event, geo)

    HANDLERS = {
        "connection": on_connection, "login_attempt": on_login_attempt, "session_start": on_session_start,
        "command": on_command, "rl_update": on_rl_update, "session_end": on_session_end, "disconnect": on_disconnect,
    }

    async def apply(self, event: dict, geo: dict) -> bool:
        handler = self.HANDLERS.get(event.get("type"))
        if handler is None:
            return False
        await handler(self, event, geo)
        return True
