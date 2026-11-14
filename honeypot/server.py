"""AsyncSSH server: accepts connections, applies the login policy, hands sessions to SessionRunner."""
from __future__ import annotations

import asyncio
import logging
import os
import random

import asyncssh

from .config import Settings
from .emitter import Emitter, make_emitter
from .rl.policies import Policy, make_policy
from .session import SessionRunner

log = logging.getLogger("honeypot")


class HoneypotContext:
    """State shared by every connection: settings, the single learning policy, the emitter."""

    def __init__(self, settings: Settings, policy: Policy, emitter: Emitter, time_scale: float = 1.0):
        self.settings = settings
        self.policy = policy
        self.emitter = emitter
        self.time_scale = time_scale          # <1 speeds up DELAY/TARPIT (tests)
        self.rng = random.Random()
        self.thresholds: dict[str, int] = {}  # src_ip -> attempt number that succeeds
        self.attempts: dict[str, int] = {}    # src_ip -> password attempts so far
        self.authenticated: set[str] = set()
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def should_accept(self, src_ip: str) -> tuple[bool, int]:
        if src_ip not in self.thresholds:
            s = self.settings
            self.thresholds[src_ip] = self.rng.randint(s.login_attempts_min, s.login_attempts_max)
        self.attempts[src_ip] = self.attempts.get(src_ip, 0) + 1
        n = self.attempts[src_ip]
        ok = src_ip in self.authenticated or n >= self.thresholds[src_ip]
        if ok:
            self.authenticated.add(src_ip)
        return ok, n


class HoneypotSSHServer(asyncssh.SSHServer):
    def __init__(self, ctx: HoneypotContext):
        self.ctx = ctx
        self.src_ip, self.src_port = "0.0.0.0", 0
        self.username = self.password = ""
        self.authenticated = False

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        peer = conn.get_extra_info("peername") or ("0.0.0.0", 0)
        self.src_ip, self.src_port = peer[0], peer[1]
        conn.set_extra_info(honeypot=self)
        log.info("connection from %s:%s", self.src_ip, self.src_port)
        self.ctx.spawn(self.ctx.emitter.emit("connection", src_ip=self.src_ip, src_port=self.src_port,
                                             client_version=conn.get_extra_info("client_version")))

    def connection_lost(self, exc: Exception | None) -> None:
        if not self.authenticated:
            self.ctx.spawn(self.ctx.emitter.emit("disconnect", src_ip=self.src_ip, src_port=self.src_port,
                                                 authenticated=False, error=str(exc) if exc else None))

    def begin_auth(self, username: str) -> bool:
        self.username = username
        return True  # always require authentication

    def password_auth_supported(self) -> bool:
        return True

    async def validate_password(self, username: str, password: str) -> bool:
        ok, attempt = self.ctx.should_accept(self.src_ip)
        await self.ctx.emitter.emit("login_attempt", src_ip=self.src_ip, src_port=self.src_port, username=username,
                                    password=password, attempt=attempt, success=ok)
        if ok:
            self.authenticated = True
            self.username, self.password = username, password
        return ok

    def public_key_auth_supported(self) -> bool:
        return False


def make_process_handler(ctx: HoneypotContext):
    async def handle(process: asyncssh.SSHServerProcess) -> None:
        srv: HoneypotSSHServer = process.channel.get_connection().get_extra_info("honeypot")
        if process.subsystem:
            process.stderr.write("This service allows sftp connections only.\n")
            process.exit(1)
            return
        await SessionRunner(process, ctx, srv.src_ip, srv.src_port, srv.username, srv.password).run()
    return handle


def load_host_keys(path: str) -> list[asyncssh.SSHKey]:
    """Load (or generate once) RSA + Ed25519 host keys. Old bots only speak ssh-rsa."""
    keys = []
    for suffix, algo in (("", "ssh-rsa"), ("_ed25519", "ssh-ed25519")):
        p = path + suffix
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            key = asyncssh.generate_private_key(algo, key_size=2048) if algo == "ssh-rsa" else asyncssh.generate_private_key(algo)
            key.write_private_key(p)
            log.info("generated host key %s", p)
        keys.append(asyncssh.read_private_key(p))
    return keys


async def start_server(settings: Settings, policy: Policy | None = None, emitter: Emitter | None = None,
                       host: str | None = None, port: int | None = None, time_scale: float = 1.0):
    """Start listening. Returns (acceptor, ctx). Use acceptor.get_port() for an ephemeral port."""
    policy = policy or make_policy(settings.rl.policy, settings.rl)
    if policy.load(settings.qtable_path):
        log.info("loaded Q-table from %s (%d episodes, epsilon=%.3f)", settings.qtable_path, policy.episodes, policy.epsilon)
    emitter = emitter or make_emitter(settings.redis_url, settings.redis_stream)
    ctx = HoneypotContext(settings, policy, emitter, time_scale)
    acceptor = await asyncssh.listen(
        host if host is not None else settings.host,
        port if port is not None else settings.port,
        server_host_keys=load_host_keys(settings.host_key_path),
        server_factory=lambda: HoneypotSSHServer(ctx),
        process_factory=make_process_handler(ctx),
        server_version=settings.server_version,
        encoding="utf-8",
        line_editor=True,
        login_timeout=90,
        keepalive_interval=30,
    )
    return acceptor, ctx
