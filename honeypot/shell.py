"""Shell: parses attacker input and dispatches to emulated commands.

Supports `;`, `&&`, `||`, pipes, `>` / `>>` redirection, `VAR=value` assignments and
`$VAR` expansion. Everything is interpreted; nothing is executed on the host.
`execute(line, decoy=True)` is the FAKE action: honeytokens are planted and
information commands include decoy entries.
"""
from __future__ import annotations

import posixpath
import random
import re
import shlex

from .cmds import ExitSession, load
from .fakefs import FakeFileSystem, Node

STDIN_COMMANDS = {"grep", "egrep", "head", "tail", "wc", "sort", "uniq", "cut", "awk", "tee", "cat", "sh", "bash",
                  "python", "python3", "perl", "base64", "xargs", "tr", "less", "more", "strings", "sed", "crontab"}
FAILURE_SUFFIXES = ("No such file or directory", "Permission denied", "command not found", "Not a directory",
                    "Is a directory", "Operation not permitted", "Authentication failure")


class Shell:
    def __init__(self, fs: FakeFileSystem, username: str, hostname: str, src_ip: str = "10.0.12.44",
                 seed: int | None = None):
        self.fs = fs
        self.user = username
        self.host = hostname
        self.src_ip = src_ip
        self.rng = random.Random(seed)
        self.handlers = load()
        self.history: list[str] = []
        self.current_cmd = ""
        self.decoy = False
        self.pid_base = self.rng.randint(1500, 3000)
        port = self.rng.randint(40000, 60000)
        self.env: dict[str, str] = {
            "SHELL": "/bin/bash", "PWD": fs.cwd, "LOGNAME": username, "HOME": fs.home, "LANG": "C.UTF-8",
            "TERM": "xterm-256color", "USER": username, "SSH_TTY": "/dev/pts/0", "_": "/usr/bin/env",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/snap/bin",
            "MAIL": f"/var/mail/{username}", "SSH_CLIENT": f"{src_ip} {port} 22",
            "SSH_CONNECTION": f"{src_ip} {port} 10.0.12.37 22",
        }

    # -------------------------------------------------------------- public
    def prompt(self) -> str:
        return f"{self.user}@{self.host}:{self.fs.display_cwd()}{'#' if self.user == 'root' else '$'} "

    def execute(self, line: str, decoy: bool = False) -> str:
        self.decoy = decoy
        if decoy:
            self.fs.plant_decoys()
        line = line.strip()
        if not line or line.startswith("#"):
            return ""
        self.history.append(line)
        out: list[str] = []
        last_ok = True
        for stmt, op in self.split_statements(line):
            if (op == "&&" and not last_ok) or (op == "||" and last_ok):
                continue
            text, last_ok = self.run_statement(stmt)
            out.append(text)
        return "".join(out)

    def run_script(self, node: Node) -> str:
        out = []
        for ln in node.content.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                out.append(self.run_statement(ln)[0])
        return "".join(out)

    # ------------------------------------------------------------- parsing
    @staticmethod
    def split_statements(line: str) -> list[tuple[str, str]]:
        """Split on ; && || & outside quotes -> [(statement, operator_before_it)]."""
        parts: list[tuple[str, str]] = []
        buf: list[str] = []
        quote: str | None = None
        op = ""
        i = 0
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
                parts.append(("".join(buf).strip(), op))
                op, buf = line[i:i + 2], []
                i += 1
            elif ch in ";&":
                parts.append(("".join(buf).strip(), op))
                op, buf = ";", []
            else:
                buf.append(ch)
            i += 1
        parts.append(("".join(buf).strip(), op))
        return [(s, o) for s, o in parts if s]

    @staticmethod
    def split_pipes(stmt: str) -> list[str]:
        segs: list[str] = []
        buf: list[str] = []
        quote: str | None = None
        for ch in stmt:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
                buf.append(ch)
            elif ch == "|":
                segs.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        segs.append("".join(buf).strip())
        return [s for s in segs if s]

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
    def run_statement(self, stmt: str) -> tuple[str, bool]:
        stmt = re.sub(r"\s*2>\s*/dev/null|\s*2>&1|\s*</dev/null", "", stmt)
        redirect = None
        m = re.match(r"^(.*?)\s*(>>|>)\s*(\S+)\s*$", stmt)
        if m:
            stmt, redirect = m.group(1), (m.group(2), m.group(3))
        segments = self.split_pipes(stmt)
        if not segments:
            return "", True
        text, ok = self.run_simple(segments[0], None)
        for seg in segments[1:]:
            text, ok = self.run_simple(seg, text)
        if redirect:
            op, target = redirect
            if target != "/dev/null":
                try:
                    self.fs.write(target, text, append=(op == ">>"))
                except (FileNotFoundError, IsADirectoryError):
                    return f"-bash: {target}: No such file or directory\n", False
            return "", ok
        return text, ok

    def run_simple(self, stmt: str, stdin: str | None) -> tuple[str, bool]:
        m = re.match(r"^([A-Za-z_]\w*)=(\S*)\s*(.*)$", stmt)
        if m:
            self.env[m.group(1)] = m.group(2).strip("\"'")
            if not m.group(3):
                return "", True
            stmt = m.group(3)
        argv = self.parse(stmt)
        if not argv:
            return stdin or "", True
        cmd, args = argv[0], argv[1:]
        if "/" in cmd:
            base = posixpath.basename(cmd)
            if cmd.startswith(("/usr/bin/", "/bin/", "/usr/sbin/", "/sbin/", "/usr/local/bin/")) and base in self.handlers:
                cmd = base
            else:
                return self.run_path(cmd, args)
        handler = self.handlers.get(cmd)
        if handler is None:
            return f"-bash: {cmd}: command not found\n", False
        self.current_cmd = cmd
        try:
            text = handler(self, args, stdin if cmd in STDIN_COMMANDS else None) or ""
            ok = cmd != "false" and not text.rstrip().endswith(FAILURE_SUFFIXES)
            return text, ok
        except ExitSession:
            raise
        except Exception:  # noqa: BLE001 - an emulation bug must never crash a session
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
        return "", True  # a downloaded binary "runs" silently, as a dropper would expect
