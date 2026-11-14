"""Emulated command registry.

Each handler has the signature `fn(sh, args, stdin) -> str` where `sh` is the Shell,
`args` the argv after the command name, and `stdin` the text piped in (or None).
Handlers never touch the host; they only read/write the session's FakeFileSystem.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

Handler = Callable[..., str]
REGISTRY: dict[str, Handler] = {}


class ExitSession(Exception):
    """Raised by `exit` / `logout` to end the shell loop."""


def command(*names: str):
    def deco(fn: Handler) -> Handler:
        for n in names:
            REGISTRY[n] = fn
        return fn
    return deco


def load() -> dict[str, Handler]:
    import importlib
    for mod in ("files", "system", "network"):
        importlib.import_module(f"{__name__}.{mod}")  # registration side effect
    return REGISTRY


# ---------------------------------------------------------------- helpers
def operands(args: list[str]) -> list[str]:
    """Positional arguments (everything that is not a -flag)."""
    return [a for a in args if not a.startswith("-")]


def flags(args: list[str]) -> str:
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def n_arg(args: list[str], default: int) -> int:
    for i, a in enumerate(args):
        if a.startswith("-n") and a[2:].isdigit():
            return int(a[2:])
        if a == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
            return int(args[i + 1])
        if a[1:].isdigit() and a.startswith("-"):
            return int(a[1:])
    return default


def human(n: int) -> str:
    size = float(n)
    for unit in ("", "K", "M", "G", "T"):
        if size < 1024 or unit == "T":
            return f"{int(size)}" if unit == "" else f"{size:.1f}{unit}".replace(".0", "")
        size /= 1024
    return f"{n}"


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def ls_time(dt: datetime) -> str:
    if datetime.now() - dt < timedelta(days=180):
        return f"{_MONTHS[dt.month - 1]} {dt.day:2d} {dt:%H:%M}"
    return f"{_MONTHS[dt.month - 1]} {dt.day:2d}  {dt.year}"


def lines(text: str) -> list[str]:
    return text.splitlines()


def join(ls: list[str]) -> str:
    return "".join(l + "\n" for l in ls)
