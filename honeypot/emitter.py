"""Event emitters: the honeypot's only output channel.

Every attacker-visible happening becomes one JSON event. With REDIS_URL set, events go
to a Redis Stream (XADD); otherwise they are printed as JSON lines so the honeypot runs
standalone. A MemoryEmitter collects events for tests.

Event types: connection, login_attempt, session_start, command, rl_update, session_end.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


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
    """XADD each event to a Redis Stream as a single `data` field holding JSON."""

    def __init__(self, url: str, stream: str = "honeypot:events", maxlen: int = 100_000):
        import redis.asyncio as aioredis  # imported lazily so stdout mode needs no redis
        self.redis = aioredis.from_url(url, decode_responses=True)
        self.stream = stream
        self.maxlen = maxlen

    async def emit(self, event_type: str, **fields: Any) -> None:
        payload = json.dumps(self.build(event_type, fields), default=str)
        await self.redis.xadd(self.stream, {"data": payload}, maxlen=self.maxlen, approximate=True)

    async def close(self) -> None:
        await self.redis.aclose()


def make_emitter(redis_url: str | None, stream: str = "honeypot:events") -> Emitter:
    return RedisEmitter(redis_url, stream) if redis_url else StdoutEmitter()
