"""RedisEmitter must never block or fail a session, and must not lose or reorder events
across a Redis outage (up to its buffer size)."""
import asyncio
import json

import pytest

from honeypot.emitter import RedisEmitter


class FlakyRedis:
    """Fake async Redis: raises while `down` is True, records XADDs otherwise."""
    def __init__(self, down=False, delay=0.0):
        self.down = down
        self.delay = delay
        self.added: list[dict] = []
        self.calls = 0

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.down:
            raise ConnectionError("Connection refused")
        self.added.append(json.loads(fields["data"]))

    async def aclose(self):
        pass


async def test_forwards_in_order():
    r = FlakyRedis()
    e = RedisEmitter(client=r)
    for i in range(50):
        await e.emit("command", seq=i)
    assert await e.flush(2)
    assert [x["seq"] for x in r.added] == list(range(50))
    await e.close()


async def test_emit_never_blocks_on_slow_redis():
    r = FlakyRedis(delay=1.0)
    e = RedisEmitter(client=r)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    for i in range(20):
        await e.emit("command", seq=i)
    assert loop.time() - t0 < 0.1
    e._closing = True
    await e.close()


async def test_outage_buffers_then_delivers_everything_in_order():
    r = FlakyRedis(down=True)
    e = RedisEmitter(client=r)
    for i in range(30):
        await e.emit("command", seq=i)          # must not raise while Redis is down
    await asyncio.sleep(0.2)
    assert e.backlog == 30 and r.added == []
    r.down = False                               # Redis comes back
    assert await e.flush(5)
    assert [x["seq"] for x in r.added] == list(range(30))
    assert e.dropped == 0
    await e.close()


async def test_bounded_buffer_drops_oldest():
    r = FlakyRedis(down=True)
    e = RedisEmitter(client=r, buffer_size=10)
    for i in range(25):
        await e.emit("command", seq=i)
    assert e.backlog == 10 and e.dropped == 15
    r.down = False
    assert await e.flush(5)
    assert [x["seq"] for x in r.added] == list(range(15, 25))
    await e.close()
