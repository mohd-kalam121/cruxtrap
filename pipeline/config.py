"""Pipeline settings from environment variables."""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PipelineSettings:
    redis_url: str = "redis://127.0.0.1:6379/0"
    stream: str = "honeypot:events"
    group: str = "pipeline"
    consumer: str = f"{socket.gethostname()}-{os.getpid()}"
    dead_letter_stream: str = "honeypot:dead"
    database_url: str = "postgresql://cruxtrap:cruxtrap@127.0.0.1:55432/cruxtrap"
    schema_path: str = os.path.join(os.path.dirname(__file__), "..", "db", "init.sql")
    geoip_db: str = "data/GeoLite2-City.mmdb"
    batch_size: int = 100
    block_ms: int = 5000
    db_retry_seconds: float = 3.0

    @classmethod
    def from_env(cls) -> "PipelineSettings":
        d = cls()
        return cls(
            redis_url=os.getenv("REDIS_URL", d.redis_url),
            stream=os.getenv("REDIS_STREAM", d.stream),
            group=os.getenv("REDIS_GROUP", d.group),
            consumer=os.getenv("CONSUMER_NAME", d.consumer),
            database_url=os.getenv("DATABASE_URL", d.database_url),
            schema_path=os.getenv("SCHEMA_PATH", d.schema_path),
            geoip_db=os.getenv("GEOIP_DB", d.geoip_db),
            batch_size=int(os.getenv("BATCH_SIZE", d.batch_size)),
            block_ms=int(os.getenv("BLOCK_MS", d.block_ms)),
        )

    def with_overrides(self, **kw) -> "PipelineSettings":
        return replace(self, **kw)
