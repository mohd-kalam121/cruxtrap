"""Filesystem and text commands, emulated against the fake filesystem."""
from __future__ import annotations

import fnmatch
import posixpath
import re
from datetime import datetime, timedelta

from .fakefs import Node
from .shell import ExitSession, Shell, awk_text, command, cut_text, files_of, flags_of, n_arg

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def ls_time(dt: datetime) -> str:
    if datetime.now() - dt < timedelta(days=180):
        return f"{_MONTHS[dt.month - 1]} {dt.day:2d} {dt:%H:%M}"
    return f"{_MONTHS[dt.month - 1]} {dt.day:2d}  {dt.year}"


def human(n: int) -> str:
    for unit in ("", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n}{unit}" if unit == "" or n == int(n) else f"{n:.1f}{unit}"
        n = round(n / 1024, 1)
    return f"{n}P"


def _columns(names: list[str], width_total: int = 80) -> str:
    if not names:
        return ""
    width = max(len(n) for n in names) + 2
    cols = max(1, width_total // width)
    rows = (len(names) + cols - 1) // cols
    out = []
    for r in range(rows):
        row = [names[c * rows + r] for c in range(cols) if c * rows + r < len(names)]
        out.append("".join(n.ljust(width) for n in row).rstrip() + "\n")
    return "".join(out)


@command("ls", "dir", "ll", "la")
def cmd_ls(sh: Shell, args: list[str]) -> str:
    flags = flags_of(args)
    paths = files_of(args) or ["."]
    long_fmt, show_all = "l" in flags, "a" in flags or "A" in flags
    out = []
    for i, p in enumerate(paths):
        try:
            nodes = sh.fs.listdir(p)
        except FileNotFoundError:
            out.append(f"ls: cannot access '{p}': No such file or directory\n")
            continue
        except PermissionError:
            out.append(f"ls: cannot open directory '{p}': Permission denied\n")
            continue
        single = not sh.fs.is_dir(p)
        if single:
            nodes = [Node(p, False, mode=nodes[0].perms, owner=nodes[0].owner, group=nodes[0].group,
                          mtime=nodes[0].mtime, size_override=nodes[0].size)]
        elif "a" in flags:
            here = sh.fs.get(p)
            parent = sh.fs.get(posixpath.dirname(sh.fs.resolve(p))) or here
            nodes = [Node(".", True, mode=here.perms, owner=here.owner, group=here.group, mtime=here.mtime),
                     Node("..", True, mode=parent.perms, owner=parent.owner, group=parent.group, mtime=parent.mtime)] + nodes
        elif not show_all:
            nodes = [n for n in nodes if not n.name.startswith(".")]
        if len(paths) > 1 and not single:
            out.append(("" if i == 0 else "\n") + f"{p}:\n")
        suffix = (lambda n: "/" if n.is_dir and "F" in flags else "*" if n.executable and "F" in flags else "")
        if long_fmt:
            out.append(f"total {sum((n.size + 4095) // 4096 * 4 for n in nodes)}\n")
            for n in nodes:
                nlink = 2 + sum(1 for c in n.children.values() if c.is_dir) if n.is_dir else 1
                size = human(n.size) if "h" in flags else str(n.size)
                out.append(f"{n.perms} {nlink:>2} {n.owner:<8} {n.group:<8} {size:>8} {ls_time(n.mtime)} {n.name}{suffix(n)}\n")
        else:
            names = [n.name + suffix(n) for n in nodes]
            out.append("".join(n + "\n" for n in names) if "1" in flags else _columns(names))
    return "".join(out)


@command("cd")
def cmd_cd(sh: Shell, args: list[str]) -> str:
    target = args[0] if args else sh.fs.home
    if target == "-":
        target = sh.env.get("OLDPWD", sh.fs.cwd)
    try:
        old = sh.fs.cwd
        sh.fs.chdir(target)
        sh.env["OLDPWD"], sh.env["PWD"] = old, sh.fs.cwd
    except FileNotFoundError:
        return f"-bash: cd: {target}: No such file or directory\n"
    except NotADirectoryError:
        return f"-bash: cd: {target}: Not a directory\n"
    return ""


@command("pwd")
def cmd_pwd(sh: Shell, args: list[str]) -> str:
    return sh.fs.cwd + "\n"


@command("cat", "less", "more", "strings", "xxd")
def cmd_cat(sh: Shell, args: list[str]) -> str:
    out = []
    for f in files_of(args):
        if f == "/proc/uptime":
            secs = (datetime.now() - sh.fs.boot_time).total_seconds()
            out.append(f"{secs:.2f} {secs * 3.7:.2f}\n")
            continue
        try:
            content = sh.fs.read(f)
            out.append(content if not content or content.endswith("\n") else content + "\n")
        except FileNotFoundError:
            out.append(f"cat: {f}: No such file or directory\n")
        except IsADirectoryError:
            out.append(f"cat: {f}: Is a directory\n")
        except PermissionError:
            out.append(f"cat: {f}: Permission denied\n")
    return "".join(out)


@command("echo")
def cmd_echo(sh: Shell, args: list[str]) -> str:
    if args and args[0] == "-n":
        return " ".join(args[1:])
    if args and args[0] == "-e":
        return " ".join(args[1:]).replace("\\n", "\n").replace("\\t", "\t") + "\n"
    return " ".join(args) + "\n"


@command("mkdir")
def cmd_mkdir(sh: Shell, args: list[str]) -> str:
    out = []
    for d in files_of(args):
        try:
            sh.fs.mkdir(d, parents="-p" in args)
        except FileNotFoundError:
            out.append(f"mkdir: cannot create directory '{d}': No such file or directory\n")
    return "".join(out)


@command("rm", "rmdir")
def cmd_rm(sh: Shell, args: list[str]) -> str:
    flags = flags_of(args)
    out = []
    for f in files_of(args):
        try:
            sh.fs.remove(f, recursive="r" in flags or "R" in flags)
        except FileNotFoundError:
            if "f" not in flags:
                out.append(f"rm: cannot remove '{f}': No such file or directory\n")
        except IsADirectoryError:
            out.append(f"rm: cannot remove '{f}': Is a directory\n")
        except PermissionError:
            out.append("rm: it is dangerous to operate recursively on '/'\n"
                       "rm: use --no-preserve-root to override this failsafe\n")
    return "".join(out)


@command("touch")
def cmd_touch(sh: Shell, args: list[str]) -> str:
    for f in files_of(args):
        try:
            sh.fs.touch(f)
        except FileNotFoundError:
            return f"touch: cannot touch '{f}': No such file or directory\n"
    return ""


@command("cp")
def cmd_cp(sh: Shell, args: list[str]) -> str:
    files = files_of(args)
    if len(files) < 2:
        return "cp: missing file operand\nTry 'cp --help' for more information.\n"
    try:
        sh.fs.copy(files[0], files[1])
    except FileNotFoundError:
        return f"cp: cannot stat '{files[0]}': No such file or directory\n"
    return ""


@command("mv")
def cmd_mv(sh: Shell, args: list[str]) -> str:
    files = files_of(args)
    if len(files) < 2:
        return "mv: missing file operand\nTry 'mv --help' for more information.\n"
    try:
        sh.fs.move(files[0], files[1])
    except FileNotFoundError:
        return f"mv: cannot stat '{files[0]}': No such file or directory\n"
    return ""


@command("chmod")
def cmd_chmod(sh: Shell, args: list[str]) -> str:
    files = files_of(args)
    if len(files) < 2:
        return "chmod: missing operand\n"
    mode, out = files[0], []
    for t in files[1:]:
        node = sh.fs.get(t)
        if node is None:
            out.append(f"chmod: cannot access '{t}': No such file or directory\n")
            continue
        if "x" in mode or re.match(r"^[0-7]*[1357][0-7]*$", mode):
            node.executable = True
            if not node.is_dir:
                node.mode = "-rwxrwxrwx" if mode == "777" else "-rwxr-xr-x"
    return "".join(out)


@command("chown", "chattr", "ln", "gzip", "gunzip", "unzip", "shred", "kill", "killall", "pkill", "usermod")
def cmd_silent_ok(sh: Shell, args: list[str]) -> str:
    return ""


@command("find", "locate")
def cmd_find(sh: Shell, args: list[str]) -> str:
    start = args[0] if args and not args[0].startswith("-") else "."
    name_pat = type_f = perm = None
    for i, a in enumerate(args):
        if a in ("-name", "-iname") and i + 1 < len(args):
            name_pat = args[i + 1]
        elif a == "-type" and i + 1 < len(args):
            type_f = args[i + 1]
        elif a == "-perm" and i + 1 < len(args):
            perm = args[i + 1]
    if not sh.fs.exists(start):
        return f"find: '{start}': No such file or directory\n"
    setuid = {"/usr/bin/sudo", "/usr/bin/su", "/usr/bin/passwd", "/usr/bin/mount", "/usr/bin/umount"}
    out = []
    for p, n in sh.fs.walk(start):
        if p.startswith("/proc") and not start.startswith("/proc"):
            continue
        if (type_f == "f" and n.is_dir) or (type_f == "d" and not n.is_dir):
            continue
        if name_pat and not fnmatch.fnmatch(n.name, name_pat):
            continue
        if perm and ("4000" in perm or "u=s" in perm or "u+s" in perm) and p not in setuid:
            continue
        if start == ".":
            p = "." if p == sh.fs.cwd else "./" + p[len(sh.fs.cwd):].lstrip("/")
        out.append(p + "\n")
        if len(out) >= 500:
            break
    return "".join(out)


@command("grep", "egrep")
def cmd_grep(sh: Shell, args: list[str]) -> str:
    flags = [a for a in args if a.startswith("-")]
    rest = files_of(args)
    if len(rest) < 2:
        return "Usage: grep [OPTION]... PATTERNS [FILE]...\nTry 'grep --help' for more information.\n"
    pat, files = rest[0], rest[1:]
    recursive = any("r" in f.lower() for f in flags)
    targets = []
    for f in files:
        if recursive and sh.fs.is_dir(f):
            targets += [(p, n) for p, n in sh.fs.walk(f) if not n.is_dir]
        else:
            node = sh.fs.get(f)
            if node is None:
                return f"grep: {f}: No such file or directory\n"
            targets.append((f, node))
    try:
        rx = re.compile(pat, re.I if "-i" in flags else 0)
    except re.error:
        rx = re.compile(re.escape(pat))
    out, many = [], len(targets) > 1
    for p, n in targets:
        if n.is_dir:
            out.append(f"grep: {p}: Is a directory\n")
            continue
        out += [(f"{p}:" if many else "") + line + "\n" for line in n.content.splitlines() if rx.search(line)]
    return "".join(out)


@command("head")
def cmd_head(sh: Shell, args: list[str]) -> str:
    n = n_arg(args, 10)
    return "".join("".join(l + "\n" for l in cmd_cat(sh, [f]).splitlines()[:n]) for f in files_of(args) if not f.isdigit())


@command("tail")
def cmd_tail(sh: Shell, args: list[str]) -> str:
    n = n_arg(args, 10)
    return "".join("".join(l + "\n" for l in cmd_cat(sh, [f]).splitlines()[-n:]) for f in files_of(args) if not f.isdigit())


@command("wc")
def cmd_wc(sh: Shell, args: list[str]) -> str:
    out = []
    for f in files_of(args):
        node = sh.fs.get(f)
        if node is None:
            out.append(f"wc: {f}: No such file or directory\n")
            continue
        c = node.content
        lines, words, chars = c.count("\n"), len(c.split()), len(c.encode())
        if "-l" in args:
            out.append(f"{lines} {f}\n")
        elif "-c" in args:
            out.append(f"{chars} {f}\n")
        else:
            out.append(f"{lines:7d} {words:7d} {chars:7d} {f}\n")
    return "".join(out)


@command("sort", "uniq")
def cmd_sort_uniq(sh: Shell, args: list[str]) -> str:
    which = "sort" if sh.history and sh.history[-1].lstrip().startswith("sort") else "uniq"
    text = cmd_cat(sh, files_of(args))
    return sh._run_filter(which + " " + " ".join(a for a in args if a.startswith("-")), text)[0]


@command("cut")
def cmd_cut(sh: Shell, args: list[str]) -> str:
    skip = {a[2:] for a in args if a.startswith("-d") and len(a) > 2}
    return cut_text(args, cmd_cat(sh, [f for f in files_of(args) if f not in skip and not f.isdigit()]))


@command("awk")
def cmd_awk(sh: Shell, args: list[str]) -> str:
    return awk_text(args, cmd_cat(sh, [a for a in files_of(args) if "{" not in a]))


@command("sed")
def cmd_sed(sh: Shell, args: list[str]) -> str:
    return cmd_cat(sh, [a for a in files_of(args) if not re.match(r"^s[/|#]", a)])


@command("which")
def cmd_which(sh: Shell, args: list[str]) -> str:
    out = []
    for a in args:
        for d in ("/usr/bin", "/usr/sbin", "/usr/local/bin"):
            if sh.fs.exists(f"{d}/{a}"):
                out.append(f"{d}/{a}\n")
                break
    return "".join(out)


@command("whereis")
def cmd_whereis(sh: Shell, args: list[str]) -> str:
    return "".join(f"{a}: /usr/bin/{a} /usr/share/man/man1/{a}.1.gz\n" if sh.fs.exists(f"/usr/bin/{a}") else f"{a}:\n"
                   for a in args)


@command("type", "command")
def cmd_type(sh: Shell, args: list[str]) -> str:
    from .shell import REGISTRY
    return "".join(f"{a} is /usr/bin/{a}\n" if a in REGISTRY else f"-bash: type: {a}: not found\n"
                   for a in args if not a.startswith("-"))


@command("file")
def cmd_file(sh: Shell, args: list[str]) -> str:
    out = []
    for f in files_of(args):
        n = sh.fs.get(f)
        if n is None:
            out.append(f"{f}: cannot open `{f}' (No such file or directory)\n")
        elif n.is_dir:
            out.append(f"{f}: directory\n")
        elif n.executable and not n.content:
            out.append(f"{f}: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, "
                       "interpreter /lib64/ld-linux-x86-64.so.2, stripped\n")
        elif n.content.startswith("#!"):
            out.append(f"{f}: Bourne-Again shell script, ASCII text executable\n")
        else:
            out.append(f"{f}: ASCII text\n")
    return "".join(out)


@command("stat")
def cmd_stat(sh: Shell, args: list[str]) -> str:
    out = []
    for f in files_of(args):
        n = sh.fs.get(f)
        if n is None:
            out.append(f"stat: cannot statx '{f}': No such file or directory\n")
            continue
        kind = "directory" if n.is_dir else "regular file"
        octal = "0755" if n.is_dir or n.executable else "0644"
        ts = f"{n.mtime:%Y-%m-%d %H:%M:%S}.000000000 +0000"
        out.append(f"  File: {f}\n  Size: {n.size:<10}\tBlocks: {(n.size + 511) // 512:<10} IO Block: 4096   {kind}\n"
                   f"Device: fd01h/64769d\tInode: {sh.rng.randint(100000, 999999)}     Links: 1\n"
                   f"Access: ({octal}/{n.perms})  Uid: (    0/    {n.owner})   Gid: (    0/    {n.group})\n"
                   f"Access: {ts}\nModify: {ts}\nChange: {ts}\n Birth: -\n")
    return "".join(out)


@command("du")
def cmd_du(sh: Shell, args: list[str]) -> str:
    out = []
    for p in files_of(args) or ["."]:
        total = sum(n.size for _, n in sh.fs.walk(p) if not n.is_dir)
        out.append(f"{human(total) if 'h' in flags_of(args) else total // 1024}\t{p}\n")
    return "".join(out)


@command("tar")
def cmd_tar(sh: Shell, args: list[str]) -> str:
    if args and "x" in args[0]:
        files = files_of(args)
        name = files[-1] if files else ""
        if not sh.fs.exists(name):
            return f"tar: {name}: Cannot open: No such file or directory\ntar: Error is not recoverable: exiting now\n"
        base = re.sub(r"\.(tar\.gz|tgz|tar)$", "", posixpath.basename(name))
        sh.fs.mkdir(base)
        sh.fs.write(f"{base}/README", "")
    return ""


@command("truncate")
def cmd_truncate(sh: Shell, args: list[str]) -> str:
    for f in files_of(args):
        if sh.fs.exists(f):
            sh.fs.write(f, "")
    return ""


@command("history")
def cmd_history(sh: Shell, args: list[str]) -> str:
    if "-c" in args:
        sh.history.clear()
        return ""
    hist_file = f"{sh.fs.home}/.bash_history"
    prior = sh.fs.read(hist_file) if sh.fs.exists(hist_file) else ""
    lines = prior.splitlines() + sh.history
    return "".join(f"{i + 1:5d}  {l}\n" for i, l in enumerate(lines))


@command("env", "printenv", "set")
def cmd_env(sh: Shell, args: list[str]) -> str:
    env = dict(sh.env, PWD=sh.fs.cwd)
    if sh.decoy:
        env.update(DB_PASSWORD="<decoy:db-app>", AWS_ACCESS_KEY_ID="<decoy:aws-id>", AWS_SECRET_ACCESS_KEY="<decoy:aws-secret>")
    if args and not args[0].startswith("-"):
        return env.get(args[0], "") + "\n"
    return "".join(f"{k}={v}\n" for k, v in env.items())


@command("export")
def cmd_export(sh: Shell, args: list[str]) -> str:
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            sh.env[k] = v
    return ""


@command("unset")
def cmd_unset(sh: Shell, args: list[str]) -> str:
    for a in args:
        sh.env.pop(a, None)
    return ""


@command("alias")
def cmd_alias(sh: Shell, args: list[str]) -> str:
    return "" if args else "alias l='ls -CF'\nalias la='ls -A'\nalias ll='ls -alF'\nalias ls='ls --color=auto'\n"


@command("exit", "logout")
def cmd_exit(sh: Shell, args: list[str]) -> str:
    raise ExitSession()


@command("clear", "reset")
def cmd_clear(sh: Shell, args: list[str]) -> str:
    return "\x1b[H\x1b[2J"


@command("nano", "vi", "vim", "visudo")
def cmd_editor(sh: Shell, args: list[str]) -> str:
    return "Error opening terminal: unknown.\n"


@command("sleep", "true", "false", "test", "[", ":", "sync", "jobs", "bg", "fg", "disown", "xargs", "tr",
         "yes", "man", "base64", "md5sum", "sha256sum")
def cmd_noop(sh: Shell, args: list[str]) -> str:
    return ""
