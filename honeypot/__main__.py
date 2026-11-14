"""Run the honeypot:  python -m honeypot   (settings from environment, see config.py)."""
from __future__ import annotations

import asyncio
import logging
import sys

from .config import Settings
from .server import start_server


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    settings = Settings.from_env()
    acceptor, ctx = await start_server(settings)
    logging.getLogger("honeypot").info(
        "listening on %s:%d  policy=%s  events=%s", settings.host, acceptor.get_port(), ctx.policy.name,
        settings.redis_url or "stdout")
    try:
        await asyncio.Event().wait()
    finally:
        acceptor.close()
        await ctx.emitter.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
