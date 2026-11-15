"""Redis Streams consumer: XREADGROUP -> parse -> GeoIP -> PostgreSQL -> XACK.

Delivery semantics: at-least-once. A message is acknowledged only after its database
transaction commits; on restart, un-acked messages (the PEL) are replayed first. Malformed
messages are copied to a dead-letter stream and acknowledged so they cannot wedge the group.
"""
from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
import redis.asyncio as aioredis
from redis.exceptions import RedisError, ResponseError

from .config import PipelineSettings
from .db import Database
from .geoip import GeoIP

log = logging.getLogger("pipeline")


class Pipeline:
    def __init__(self, settings: PipelineSettings):
        self.s = settings
        # The socket timeout must outlast the XREADGROUP BLOCK window, or every idle wait
        # ends in a client-side TimeoutError.
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True,
                                       socket_timeout=settings.block_ms / 1000 + 10,
                                       socket_connect_timeout=5, health_check_interval=30)
        self.db = Database(settings.database_url)
        self.geo = GeoIP(settings.geoip_db)
        self.processed = 0
        self.failed = 0
        self._stop = asyncio.Event()

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        while True:
            try:
                await self.db.connect(self.s.schema_path)
                break
            except (OSError, asyncpg.PostgresError) as e:
                log.warning("database not ready (%s); retrying in %.0fs", e, self.s.db_retry_seconds)
                await asyncio.sleep(self.s.db_retry_seconds)
        while True:
            try:
                await self.ensure_group()
                break
            except (RedisError, OSError) as e:
                log.warning("redis not ready (%s); retrying", e)
                await asyncio.sleep(2.0)
        log.info("consumer %s ready (group=%s stream=%s)", self.s.consumer, self.s.group, self.s.stream)

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.s.stream, self.s.group, id="0", mkstream=True)
            log.info("created consumer group %s on %s", self.s.group, self.s.stream)
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def close(self) -> None:
        await self.db.close()
        await self.redis.aclose()
        self.geo.close()

    def stop(self) -> None:
        self._stop.set()

    # --------------------------------------------------------------- loop
    async def run(self) -> None:
        """Recover orphaned and own pending messages, then follow new ones until stop()."""
        await self.claim_orphans()
        await self.drain(pending_only=True)
        while not self._stop.is_set():
            await self.read_batch(">", block_ms=self.s.block_ms)

    async def claim_orphans(self, min_idle_ms: int = 60_000) -> int:
        """XAUTOCLAIM messages left pending by consumers that died (e.g. a previous process
        with a different name) and process them. Returns the number recovered."""
        start, n = "0-0", 0
        while True:
            resp = await self.redis.xautoclaim(self.s.stream, self.s.group, self.s.consumer,
                                               min_idle_time=min_idle_ms, start_id=start, count=self.s.batch_size)
            start, messages = resp[0], resp[1]
            for msg_id, fields in messages:
                if fields is not None:
                    await self.handle(msg_id, fields)
                    n += 1
            if start in ("0-0", b"0-0") or not messages:
                break
        if n:
            log.info("recovered %d orphaned messages", n)
        return n

    async def drain(self, pending_only: bool = False) -> int:
        """Process everything currently available and return the count. Used by tests."""
        n = 0
        while True:
            got = await self.read_batch("0", block_ms=None)
            n += got
            if got == 0:
                break
        if pending_only:
            return n
        while True:
            got = await self.read_batch(">", block_ms=None)
            n += got
            if got == 0:
                return n

    async def read_batch(self, start_id: str, block_ms: int | None) -> int:
        try:
            entries = await self.redis.xreadgroup(self.s.group, self.s.consumer, {self.s.stream: start_id},
                                                  count=self.s.batch_size, block=block_ms)
        except ResponseError as e:
            if "NOGROUP" in str(e):  # stream/group deleted (e.g. Redis data wiped): recreate
                log.warning("consumer group missing; recreating")
                await self.ensure_group()
            else:
                log.warning("redis error (%s); retrying", e)
            await asyncio.sleep(1.0)
            return 0
        except (RedisError, OSError) as e:  # connection refused/reset, timeouts: Redis restarting
            log.warning("redis unavailable (%s: %s); retrying", type(e).__name__, e)
            await asyncio.sleep(2.0)
            return 0
        count = 0
        for _stream, messages in entries or []:
            for msg_id, fields in messages:
                await self.handle(msg_id, fields)
                count += 1
        return count

    async def handle(self, msg_id: str, fields: dict) -> None:
        try:
            event = json.loads(fields.get("data", ""))
            if not isinstance(event, dict):
                raise ValueError("event is not an object")
        except (ValueError, TypeError) as e:
            await self.dead_letter(msg_id, fields, f"parse error: {e}")
            return
        geo = self.geo.lookup(event.get("src_ip", "")) if event.get("src_ip") else {}
        attempt = 0
        while True:
            try:
                known = await self.db.apply(event, geo)
                break
            except (asyncpg.PostgresConnectionError, OSError, asyncpg.InterfaceError) as e:
                attempt += 1
                log.warning("database write failed (%s); retry %d", e, attempt)
                await asyncio.sleep(min(30.0, self.s.db_retry_seconds * attempt))
            except (asyncpg.PostgresError, KeyError, ValueError, TypeError) as e:
                # Not transient: bad data or a bug. Park it rather than crash ingestion.
                await self.dead_letter(msg_id, fields, f"{type(e).__name__}: {e}")
                return
        if not known:
            log.debug("ignoring unknown event type %r", event.get("type"))
        await self.redis.xack(self.s.stream, self.s.group, msg_id)
        self.processed += 1
        if self.processed % 500 == 0:
            log.info("processed=%d failed=%d", self.processed, self.failed)

    async def dead_letter(self, msg_id: str, fields: dict, reason: str) -> None:
        self.failed += 1
        log.error("dead-lettering %s: %s", msg_id, reason)
        try:
            await self.redis.xadd(self.s.dead_letter_stream, {**fields, "reason": reason, "source_id": msg_id})
        finally:
            await self.redis.xack(self.s.stream, self.s.group, msg_id)
