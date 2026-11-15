"""Event emitters: the honeypot's only output channel.

Every attacker-visible happening becomes one JSON event. With REDIS_URL set, events go
to a Redis Stream (XADD); otherwise they are printed as JSON lines so the honeypot runs
standalone. A MemoryEmitter collects events for tests.

Event types: connection, login_attempt, session_start, command, rl_update, session_end.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("honeypot.emitter")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Emitter:
    async def emit(self, event_type: str, **fields: Any) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None

    @staticmethod
    def build(event_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        return {"type": event_type, "ts": _now(), **fields}


class StdoutEmitter(Emitter):
    def __init__(self, stream=None):
        self.stream = stream or sys.stdout

    async def emit(self, event_type: str, **fields: Any) -> None:
        self.stream.write(json.dumps(self.build(event_type, fields), default=str) + "\n")
        self.stream.flush()


class MemoryEmitter(Emitter):
    def __init__(self):
        self.events: list[dict[str, Any]] = []

    async def emit(self, event_type: str, **fields: Any) -> None:
        self.events.append(self.build(event_type, fields))

    def of_type(self, event_type: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == event_type]


class RedisEmitter(Emitter):
    """Store-and-forward to a Redis Stream (XADD, one `data` field holding JSON).

    `emit()` never awaits Redis: it appends to a bounded in-memory buffer and returns, so a
    slow or unavailable Redis can never delay or break an attacker's session. A background
    task forwards the buffer in order, retrying with exponential backoff during outages.
    If an outage outlasts the buffer, the oldest events are dropped and counted.
    """

    def __init__(self, url: str | None = None, stream: str = "honeypot:events", maxlen: int = 100_000,
                 buffer_size: int = 50_000, client=None):
        if client is None:
            import redis.asyncio as aioredis  # lazy: stdout mode needs no redis
            client = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5)
        self.redis = client
        self.stream = stream
        self.maxlen = maxlen
        self.buffer: deque[str] = deque()
        self.buffer_size = buffer_size
        self.dropped = 0
        self.sent = 0
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._closing = False

    @property
    def backlog(self) -> int:
        return len(self.buffer)

    async def emit(self, event_type: str, **fields: Any) -> None:
        if len(self.buffer) >= self.buffer_size:
            self.buffer.popleft()
            self.dropped += 1
            if self.dropped % 1000 == 1:
                log.error("event buffer full; dropped %d oldest events so far", self.dropped)
        self.buffer.append(json.dumps(self.build(event_type, fields), default=str))
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._forward())
        self._wake.set()

    async def _forward(self) -> None:
        backoff = 0.5
        outage = False
        while True:
            while self.buffer:
                try:
                    await self.redis.xadd(self.stream, {"data": self.buffer[0]}, maxlen=self.maxlen, approximate=True)
                except Exception as e:  # noqa: BLE001 - any failure: keep the event, back off, retry
                    if self._closing:
                        return
                    if not outage:
                        log.warning("redis unavailable (%s: %s); buffering events", type(e).__name__, e)
                        outage = True
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue
                self.buffer.popleft()
                self.sent += 1
                if outage:
                    log.info("redis back; forwarding %d buffered events", len(self.buffer))
                    outage, backoff = False, 0.5
            if self._closing:
                return
            self._wake.clear()
            await self._wake.wait()

    async def flush(self, timeout: float = 5.0) -> bool:
        """Wait until the buffer is empty (or timeout). Returns True if fully flushed."""
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while self.buffer and loop.time() < end:
            self._wake.set()
            await asyncio.sleep(0.02)
        return not self.buffer

    async def close(self) -> None:
        await self.flush(timeout=5.0)
        self._closing = True
        self._wake.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self.buffer:
            log.error("closing with %d unsent events", len(self.buffer))
        await self.redis.aclose()


def make_emitter(redis_url: str | None, stream: str = "honeypot:events") -> Emitter:
    return RedisEmitter(redis_url, stream) if redis_url else StdoutEmitter()
