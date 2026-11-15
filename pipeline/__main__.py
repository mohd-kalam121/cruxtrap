"""Run the pipeline:  python -m pipeline   (settings from environment, see config.py)."""
from __future__ import annotations

import asyncio
import logging
import sys

from .config import PipelineSettings
from .consumer import Pipeline


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    pipeline = Pipeline(PipelineSettings.from_env())
    await pipeline.start()
    try:
        await pipeline.run()
    finally:
        await pipeline.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
