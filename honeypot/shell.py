"""Shell emulator: parses attacker input and dispatches to emulated commands.

Supports `;`, `&&`, `||`, pipes into a few filters (grep/head/tail/wc/sort/uniq/cut/awk),
`>` / `>>` redirection into the fake filesystem, `$VAR` expansion and `VAR=value`.
Nothing is ever executed on the host.

Commands live in cmds_fs.py, cmds_sys.py and cmds_net.py and register themselves with
the `@command(...)` decorator. `Shell.execute(line, decoy=True)` is used by the FAKE
action: decoy files are planted and info commands include placeholder honeytokens.
"""
from __future__ import annotations

import posixpath
import random
import re
import shlex
from collections.abc import Callable

from .fakefs import FakeFileSystem, Node

Handler = Callable[["Shell", list[str]], str]
REGISTRY: dict[str, Handler] = {}


def command(*names: str):
    def deco(fn: Handler) -> Handler:
        for n in names:
            REGISTRY[n] = fn
        return fn
    return deco


class ExitSession(Exception):
    """Raised by exit/logout to end the shell loop."""


class Shell:
    def __init__(self, fs: FakeFileSystem, username: str, hostname: str, src_ip: str = "10.0.12.44",
                 seed: int | None = None):
        # import for side effects: registers the handlers
        from . import cmds_fs, cmds_net, cmds_sys  # noqa: F401
        self.fs = fs
        self.user = username
        self.host = hostname
        self.src_ip = src_ip
        self.rng = random.Random(seed)
        self.history: list[str] = []
        self.decoy = False
        self.pid_base = self.rng.randint(1500, 3000)
        client_port = self.rng.randint(40000, 60000)
        self.env: dict[str, str] = {
            "SHELL": "/bin/bash", "PWD": fs.cwd, "LOGNAME": username, "HOME": fs.home, "LANG": "C.UTF-8",
            "TERM": "xterm-256color", "USER": username, "MAIL": f"/var/mail/{username}",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/snap/bin",
            "SSH_CLIENT": f"{src_ip} {client_port} 22", "SSH_CONNECTION": f"{src_ip} {client_port} 10.0.12.37 22",
            "SSH_TTY": "/dev/pts/0", "_": "/usr/bin/env",
        }

    # ------------------------------------------------------------------ API
    @property
    def is_root(self) -> bool:
        return self.user == "root"

    def prompt(self) -> str:
        return f"{self.user}@{self.host}:{self.fs.display_cwd()}{'#' if self.is_root else '$'} "

    def execute(self, line: str, decoy: bool = False) -> str:
        """Run one input line; returns the output text (\\n newlines)."""
        self.decoy = decoy
        if decoy:
            self.fs.plant_decoys()
        line = line.strip()
        if not line or line.startswith("#"):
            return ""
        self.history.append(line)
        out, last_ok = [], True
        for stmt, op in self._split_statements(line):
            if (op == "&&" and not last_ok) or (op == "||" and last_ok):
                continue
            text, last_ok = self._run_statement(stmt)
            out.append(text)
        return "".join(out)

    # ------------------------------------------------------------- parsing
    @staticmethod
    def _split_statements(line: str) -> list[tuple[str, str]]:
        """Split on ; && || & outside quotes -> [(statement, operator_before_it)]."""
        parts, buf, quote, op, i = [], [], None, "", 0
        while i < len(line):
            ch = line[i]
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
                buf.append(ch)
            elif line.startswith("&&", i) or line.startswith("||", i):
                parts.append(("".join(buf), op))
                op, buf = line[i:i + 2], []
                i += 1
            elif ch in ";&":
                parts.append(("".join(buf), op))
                op, buf = ";", []
            else:
                buf.append(ch)
            i += 1
        parts.append(("".join(buf), op))
        return [(s.strip(), o) for s, o in parts if s.strip()]

    @staticmethod
    def _split_pipes(stmt: str) -> list[str]:
        segs, buf, quote = [], [], None
        for ch in stmt:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
                buf.append(ch)
            elif ch == "|":
                segs.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        segs.append("".join(buf))
        return [s.strip() for s in segs if s.strip()]

    def parse(self, stmt: str) -> list[str]:
        try:
            argv = shlex.split(stmt)
        except ValueError:
            argv = stmt.split()
        return [self.expand(a) for a in argv]

    def expand(self, token: str) -> str:
        token = re.sub(r"\$\{(\w+)\}|\$(\w+)", lambda m: self.env.get(m.group(1) or m.group(2), ""), token)
        if token == "~" or token.startswith("~/"):
            token = self.fs.home + token[1:]
        return token

    # ----------------------------------------------------------- execution
    def _run_statement(self, stmt: str) -> tuple[str, bool]:
        stmt = re.sub(r"\s*2>\s*/dev/null|\s*2>&1", "", stmt)
        redirect = None
        m = re.match(r"^(.*?)\s*(>>|>)\s*(\S+)\s*$", stmt)
        if m:
            stmt, redirect = m.group(1), (m.group(2), m.group(3))
        segments = self._split_pipes(stmt)
        if not segments:
            return "", True
        text, ok = self._run_simple(segments[0])
        for seg in segments[1:]:
            text, ok = self._run_filter(seg, text)
        if redirect:
            op, target = redirect
            if target != "/dev/null":
                try:
                    self.fs.write(self.expand(target), text, append=(op == ">>"))
                except (FileNotFoundError, IsADirectoryError):
                    return f"-bash: {target}: No such file or directory\n", False
            return "", ok
        return text, ok

    def _run_simple(self, stmt: str) -> tuple[str, bool]:
        m = re.match(r"^([A-Za-z_]\w*)=(\S*)\s*(.*)$", stmt)
        if m:  # VAR=value [command]
            self.env[m.group(1)] = m.group(2).strip("\"'")
            if not m.group(3):
                return "", True
            stmt = m.group(3)
        argv = self.parse(stmt)
        if not argv:
            return "", True
        cmd, args = argv[0], argv[1:]
        if cmd.startswith(("./", "../", "/")) and not re.match(r"^/(usr/)?s?bin/", cmd):
            return self.run_path(cmd, args)
        cmd = posixpath.basename(cmd) if "/" in cmd else cmd
        handler = REGISTRY.get(cmd)
        if handler is None:
            return f"-bash: {cmd}: command not found\n", False
        try:
            return handler(self, args) or "", True
        except ExitSession:
            raise
        except Exception:  # noqa: BLE001 — an emulation bug must never crash the session
            return "", False

    def run_path(self, path: str, args: list[str]) -> tuple[str, bool]:
        node = self.fs.get(path)
        if node is None:
            return f"-bash: {path}: No such file or directory\n", False
        if node.is_dir:
            return f"-bash: {path}: Is a directory\n", False
        if not node.executable:
            return f"-bash: {path}: Permission denied\n", False
        if node.content.startswith("#!") or node.name.endswith(".sh"):
            return self.run_script(node), True
        return "", True  # a downloaded binary: pretend it ran silently, as droppers expect

    def run_script(self, node: Node) -> str:
        out = []
        for ln in node.content.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                out.append(self._run_statement(ln)[0])
        return "".join(out)

    # -------------------------------------------------------------- filters
    def _run_filter(self, seg: str, text: str) -> tuple[str, bool]:
        argv = self.parse(seg)
        if not argv:
            return text, True
        cmd, args = argv[0], argv[1:]
        lines = text.splitlines()
        flags = [a for a in args if a.startswith("-")]
        rest = [a for a in args if not a.startswith("-")]
        if cmd in ("grep", "egrep"):
            if not rest:
                return "", False
            pat = rest[0]
            try:
                rx = re.compile(pat, re.I if "-i" in flags else 0)
            except re.error:
                rx = re.compile(re.escape(pat))
            kept = [l for l in lines if (rx.search(l) is not None) != ("-v" in flags)]
            if "-c" in flags:
                return f"{len(kept)}\n", True
            return "".join(l + "\n" for l in kept), bool(kept)
        if cmd == "head":
            return "".join(l + "\n" for l in lines[:n_arg(args, 10)]), True
        if cmd == "tail":
            return "".join(l + "\n" for l in lines[-n_arg(args, 10):]), True
        if cmd == "wc":
            if "-l" in flags:
                return f"{len(lines)}\n", True
            if "-c" in flags:
                return f"{len(text.encode())}\n", True
            if "-w" in flags:
                return f"{len(text.split())}\n", True
            return f"{len(lines):8d}{len(text.split()):8d}{len(text.encode()):8d}\n", True
        if cmd == "sort":
            src = set(lines) if "-u" in flags else lines
            return "".join(l + "\n" for l in sorted(src, reverse="-r" in flags)), True
        if cmd == "uniq":
            outl, counts = [], []
            for l in lines:
                if outl and l == outl[-1]:
                    counts[-1] += 1
                else:
                    outl.append(l)
                    counts.append(1)
            if "-c" in flags:
                return "".join(f"{c:7d} {l}\n" for c, l in zip(counts, outl)), True
            return "".join(l + "\n" for l in outl), True
        if cmd == "cut":
            return cut_text(args, text), True
        if cmd == "awk":
            return awk_text(args, text), True
        if cmd == "tee":
            for f in rest:
                try:
                    self.fs.write(f, text, append="-a" in flags)
                except Exception:  # noqa: BLE001
                    pass
            return text, True
        if cmd in ("sh", "bash", "python", "python3", "perl", "xargs"):
            return "", True  # `curl ... | sh`: the dropper "ran"
        return text, True


# ------------------------------------------------------------------ helpers
def n_arg(args: list[str], default: int) -> int:
    for i, a in enumerate(args):
        if a.startswith("-n") and a[2:].isdigit():
            return int(a[2:])
        if a == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
            return int(args[i + 1])
        if re.match(r"^-\d+$", a):
            return int(a[1:])
    return default


def files_of(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def flags_of(args: list[str]) -> str:
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def cut_text(args: list[str], text: str) -> str:
    delim, fields = "\t", None
    for i, a in enumerate(args):
        if a.startswith("-d"):
            delim = a[2:] or (args[i + 1] if i + 1 < len(args) else "\t")
        if a.startswith("-f"):
            fields = a[2:] or (args[i + 1] if i + 1 < len(args) else "1")
    if not fields:
        return text
    idx = [int(x) - 1 for x in fields.split(",") if x.isdigit()]
    out = []
    for line in text.splitlines():
        parts = line.split(delim)
        out.append(delim.join(parts[i] for i in idx if i < len(parts)) + "\n")
    return "".join(out)


def awk_text(args: list[str], text: str) -> str:
    prog = next((a for a in args if "{" in a), "")
    m = re.search(r"print\s+\$(\d+)", prog)
    if not m:
        return text
    i = int(m.group(1)) - 1
    return "".join(((ln.split()[i] if 0 <= i < len(ln.split()) else "") + "\n") for ln in text.splitlines())
