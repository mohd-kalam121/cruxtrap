"""SessionRunner: one attacker's shell session, from banner to disconnect.

Per command:  classify -> state -> policy.choose -> apply action -> emit `command`.
The reward for command t is only known once we see whether the attacker continues,
so the TD update for (s_t, a_t) happens when command t+1 arrives (or at session end).
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from datetime import datetime

import asyncssh

from .classify import classify_line, phase_for
from .cmds import ExitSession
from .fakefs import FakeFileSystem
from .rl.policies import TERMINAL, Action, compute_reward, make_state
from .shell import Shell

BANNER = (
    "Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\n\n"
    " * Documentation:  https://help.ubuntu.com\n"
    " * Management:     https://landscape.canonical.com\n"
    " * Support:        https://ubuntu.com/advantage\n\n"
    "  System information as of {now}\n\n"
    "  System load:  0.08              Processes:             118\n"
    "  Usage of /:   32.1% of 77.35GB  Users logged in:       0\n"
    "  Memory usage: 13%               IPv4 address for eth0: 10.0.12.37\n"
    "  Swap usage:   0%\n\n"
    "12 updates can be applied immediately.\n"
    "To see these additional updates run: apt list --upgradable\n\n\n"
    "Last login: {last} from 10.0.12.14\n"
)


class SessionRunner:
    def __init__(self, process: asyncssh.SSHServerProcess, ctx, src_ip: str, src_port: int,
                 username: str, password: str):
        self.process = process
        self.ctx = ctx
        self.settings = ctx.settings
        self.policy = ctx.policy
        self.emitter = ctx.emitter
        self.src_ip, self.src_port = src_ip, src_port
        self.username, self.password = username, password
        self.session_id = str(uuid.uuid4())
        self.pty = process.get_terminal_type() is not None
        self.nl = "\r\n" if self.pty else "\n"
        self.rng = random.Random()
        seed = self.rng.randrange(1 << 30)
        self.fs = FakeFileSystem(username, self.settings.hostname, seed=seed)
        self.shell = Shell(self.fs, username, self.settings.hostname, src_ip, seed=seed)
        self.seq = 0
        self.pending: tuple[str, Action, str, str, int] | None = None  # (state, action, category, phase, seq)
        self.total_reward = 0.0
        self.started = time.monotonic()
        self.end_reason = "disconnect"

    # ---------------------------------------------------------------- I/O
    def write(self, text: str) -> None:
        if text:
            try:
                self.process.stdout.write(text.replace("\n", self.nl) if self.pty else text)
            except (BrokenPipeError, ConnectionError, asyncssh.Error):
                pass

    async def emit(self, event_type: str, **fields) -> None:
        await self.emitter.emit(event_type, session_id=self.session_id, src_ip=self.src_ip, src_port=self.src_port, **fields)

    # --------------------------------------------------------------- main
    async def run(self) -> None:
        await self.emit("session_start", username=self.username, password=self.password, pty=self.pty,
                        term=self.process.get_terminal_type(), exec_command=self.process.command)
        try:
            if self.process.command:                       # `ssh host 'cmd'` — non-interactive
                await self.handle_command(self.process.command)
                self.end_reason = "exec_done"
            else:
                await self.interactive_loop()
        except (asyncssh.Error, ConnectionError, BrokenPipeError):
            self.end_reason = "connection_lost"
        finally:
            await self.finish()

    async def interactive_loop(self) -> None:
        last = datetime.now().replace(microsecond=0)
        self.write(BANNER.format(now=f"{last:%a %b %d %H:%M:%S} UTC {last.year}", last=f"{last:%a %b %d %H:%M:%S %Y}"))
        while True:
            if self.seq >= self.settings.max_commands or time.monotonic() - self.started > self.settings.max_session_seconds:
                self.end_reason = "limit"
                return
            self.write(self.shell.prompt())
            try:
                line = await asyncio.wait_for(self.process.stdin.readline(), self.settings.idle_timeout_seconds)
            except asyncio.TimeoutError:
                self.write("\ntimed out waiting for input: auto-logout\n")
                self.end_reason = "idle_timeout"
                return
            except (asyncssh.BreakReceived, asyncssh.SignalReceived, asyncssh.TerminalSizeChanged):
                self.write("\n")
                continue
            if not line:                                   # EOF / Ctrl-D
                self.end_reason = "eof"
                return
            line = line.rstrip("\r\n")
            if "\x03" in line:
                self.write("^C\n")
                continue
            if await self.handle_command(line):
                return

    # ------------------------------------------------------------ command
    async def handle_command(self, line: str) -> bool:
        """Process one line. Returns True when the session must end."""
        if not line.strip():
            return False
        self.seq += 1
        category = classify_line(line)
        phase = phase_for(self.seq)
        state = make_state(category, phase)
        action = self.policy.choose(state)
        if self.pending:
            await self.learn(continued=True, next_state=state, next_category=category, next_action=action)
        q_before = self.policy.q_values(state)

        t0 = time.monotonic()
        exited = False
        try:
            output = self.shell.execute(line, decoy=(action is Action.FAKE))
        except ExitSession:
            output, exited = "logout\n", True
        await self.deliver(action, output)
        latency_ms = int((time.monotonic() - t0) * 1000)

        await self.emit("command", seq=self.seq, command=line, category=category, phase=phase, state=state,
                        action=action.value, epsilon=round(self.policy.epsilon, 4), q_values=q_before,
                        latency_ms=latency_ms, output_bytes=len(output.encode()), decoys_planted=self.fs.decoys_planted)
        self.pending = (state, action, category, phase, self.seq)

        if action is Action.BLOCK:
            self.end_reason = "blocked"
            return True
        if exited:
            self.end_reason = "exit"
            return True
        return False

    async def deliver(self, action: Action, output: str) -> None:
        if action is Action.BLOCK:
            return
        if action is Action.DELAY:
            await asyncio.sleep(self.rng.uniform(1.0, 4.0) * self.ctx.time_scale)
            self.write(output)
            return
        if action is Action.TARPIT:
            await asyncio.sleep(self.rng.uniform(4.0, 7.0) * self.ctx.time_scale)
            budget = 10.0 * self.ctx.time_scale
            chunks = [output[i:i + 8] for i in range(0, len(output), 8)] or [""]
            pause = min(0.3 * self.ctx.time_scale, budget / max(1, len(chunks)))
            for chunk in chunks:
                self.write(chunk)
                await asyncio.sleep(pause)
            return
        self.write(output)  # ALLOW and FAKE

    # ----------------------------------------------------------------- RL
    async def learn(self, continued: bool, next_state: str | None, next_category: str | None,
                    next_action: Action | None = None) -> None:
        state, action, category, phase, seq = self.pending
        reward = compute_reward(action, continued, category, phase, next_category, self.settings.reward)
        self.policy.update(state, action, reward, next_state or TERMINAL, next_action)
        self.total_reward += reward
        self.pending = None
        await self.emit("rl_update", seq=seq, state=state, action=action.value, reward=round(reward, 4),
                        continued=continued, next_state=next_state or TERMINAL, q_values=self.policy.q_values(state))

    async def finish(self) -> None:
        if self.pending:
            await self.learn(continued=False, next_state=None, next_category=None)
        self.policy.end_episode()
        try:
            self.policy.save(self.settings.qtable_path)
        except OSError:
            pass
        await self.emit("session_end", username=self.username, commands=self.seq, reason=self.end_reason,
                        duration_s=round(time.monotonic() - self.started, 3), total_reward=round(self.total_reward, 4),
                        epsilon=round(self.policy.epsilon, 4), episodes=self.policy.episodes)
        try:
            self.process.exit(0)
        except (OSError, asyncssh.Error):
            pass
