"""File and text commands."""
from __future__ import annotations

import fnmatch
import posixpath
import re
from datetime import datetime

from ..fakefs import Node
from . import command, flags, human, join, lines, ls_time, n_arg, operands


@command("ls", "dir", "ll", "la")
def ls(sh, args, stdin=None):
    fl = flags(args)
    paths = operands(args) or ["."]
    long_, all_, almost, human_, one, classify = "l" in fl, "a" in fl, "A" in fl, "h" in fl, "1" in fl, "F" in fl
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
        is_dir = sh.fs.is_dir(p)
        if is_dir:
            if all_:
                here = sh.fs.get(p)
                parent = sh.fs.get(posixpath.dirname(sh.fs.resolve(p))) or here
                nodes = [Node(".", True, mode=here.perms, owner=here.owner, group=here.group, mtime=here.mtime),
                         Node("..", True, mode=parent.perms, owner=parent.owner, group=parent.group, mtime=parent.mtime)] + nodes
            elif not almost:
                nodes = [n for n in nodes if not n.name.startswith(".")]
        if len(paths) > 1 and is_dir:
            out.append(("" if i == 0 else "\n") + f"{p}:\n")
        names = [((n.name if is_dir else p) + ("/" if n.is_dir and classify else "*" if n.executable and classify else ""), n)
                 for n in nodes]
        if long_:
            out.append(f"total {sum((n.size + 4095) // 4096 * 4 for _, n in names)}\n")
            for name, n in names:
                nlink = 1 if not n.is_dir else 2 + sum(1 for c in n.children.values() if c.is_dir)
                size = human(n.size) if human_ else str(n.size)
                out.append(f"{n.perms} {nlink:>2} {n.owner:<8} {n.group:<8} {size:>8} {ls_time(n.mtime)} {name}\n")
        elif names:
            just = [nm for nm, _ in names]
            if one:
                out.append(join(just))
            else:
                width = max(len(nm) for nm in just) + 2
                cols = max(1, 80 // width)
                rows = (len(just) + cols - 1) // cols
                for r in range(rows):
                    out.append("".join(just[c * rows + r].ljust(width) for c in range(cols) if c * rows + r < len(just)).rstrip() + "\n")
    return "".join(out)


@command("cd")
def cd(sh, args, stdin=None):
    target = args[0] if args else sh.fs.home
    if target == "-":
        target = sh.env.get("OLDPWD", sh.fs.cwd)
    try:
        old = sh.fs.cwd
        sh.fs.chdir(target)
        sh.env["OLDPWD"], sh.env["PWD"] = old, sh.fs.cwd
        return ""
    except FileNotFoundError:
        return f"-bash: cd: {target}: No such file or directory\n"
    except NotADirectoryError:
        return f"-bash: cd: {target}: Not a directory\n"


@command("pwd")
def pwd(sh, args, stdin=None):
    return sh.fs.cwd + "\n"


@command("cat", "less", "more", "strings")
def cat(sh, args, stdin=None):
    fs_ = operands(args)
    if not fs_:
        return stdin or ""
    out = []
    for f in fs_:
        if f == "/proc/uptime":
            secs = (datetime.now() - sh.fs.boot_time).total_seconds()
            out.append(f"{secs:.2f} {secs * 3.7:.2f}\n")
            continue
        try:
            c = sh.fs.read(f)
            out.append(c if not c or c.endswith("\n") else c + "\n")
        except FileNotFoundError:
            out.append(f"cat: {f}: No such file or directory\n")
        except IsADirectoryError:
            out.append(f"cat: {f}: Is a directory\n")
        except PermissionError:
            out.append(f"cat: {f}: Permission denied\n")
    return "".join(out)


@command("echo")
def echo(sh, args, stdin=None):
    if args and args[0] == "-n":
        return " ".join(args[1:])
    if args and args[0] == "-e":
        return " ".join(args[1:]).replace("\\n", "\n").replace("\\t", "\t") + "\n"
    return " ".join(args) + "\n"


@command("mkdir")
def mkdir(sh, args, stdin=None):
    out = []
    for d in operands(args):
        try:
            sh.fs.mkdir(d, parents="-p" in args)
        except FileNotFoundError:
            out.append(f"mkdir: cannot create directory '{d}': No such file or directory\n")
    return "".join(out)


@command("rm", "rmdir")
def rm(sh, args, stdin=None):
    fl = flags(args)
    out = []
    for f in operands(args):
        try:
            sh.fs.remove(f, recursive="r" in fl or "R" in fl)
        except FileNotFoundError:
            if "f" not in fl:
                out.append(f"rm: cannot remove '{f}': No such file or directory\n")
        except IsADirectoryError:
            out.append(f"rm: cannot remove '{f}': Is a directory\n")
        except PermissionError:
            out.append("rm: it is dangerous to operate recursively on '/'\nrm: use --no-preserve-root to override this failsafe\n")
    return "".join(out)


@command("touch")
def touch(sh, args, stdin=None):
    for f in operands(args):
        try:
            sh.fs.touch(f)
        except FileNotFoundError:
            return f"touch: cannot touch '{f}': No such file or directory\n"
    return ""


def _cp_mv(sh, args, name):
    fs_ = operands(args)
    if len(fs_) < 2:
        return f"{name}: missing file operand\nTry '{name} --help' for more information.\n"
    try:
        (sh.fs.copy if name == "cp" else sh.fs.move)(fs_[0], fs_[1])
    except FileNotFoundError:
        return f"{name}: cannot stat '{fs_[0]}': No such file or directory\n"
    return ""


@command("cp")
def cp(sh, args, stdin=None):
    return _cp_mv(sh, args, "cp")


@command("mv")
def mv(sh, args, stdin=None):
    return _cp_mv(sh, args, "mv")


@command("chmod")
def chmod(sh, args, stdin=None):
    fs_ = operands(args)
    if len(fs_) < 2:
        return "chmod: missing operand\nTry 'chmod --help' for more information.\n"
    mode, out = fs_[0], []
    for t in fs_[1:]:
        node = sh.fs.get(t)
        if node is None:
            out.append(f"chmod: cannot access '{t}': No such file or directory\n")
            continue
        if "x" in mode or re.match(r"^[0-7]*[1357][0-7]*$", mode):
            node.executable = True
            if not node.is_dir:
                node.mode = "-rwxrwxrwx" if mode == "777" else "-rwxr-xr-x"
    return "".join(out)


@command("chown", "chgrp", "chattr", "ln", "gzip", "gunzip", "unzip", "zip", "shred", "sync", "kill", "killall", "pkill")
def ok(sh, args, stdin=None):
    return ""


@command("find", "locate")
def find(sh, args, stdin=None):
    start = args[0] if args and not args[0].startswith("-") else "."
    name_pat = type_f = perm = None
    for i, a in enumerate(args[:-1]):
        if a in ("-name", "-iname"):
            name_pat = args[i + 1]
        elif a == "-type":
            type_f = args[i + 1]
        elif a == "-perm":
            perm = args[i + 1]
    if not sh.fs.exists(start):
        return f"find: '{start}': No such file or directory\n"
    out = []
    setuid = ("/usr/bin/sudo", "/usr/bin/su", "/usr/bin/passwd", "/usr/bin/mount", "/usr/bin/umount")
    for p, n in sh.fs.walk(start):
        if (type_f == "f" and n.is_dir) or (type_f == "d" and not n.is_dir):
            continue
        if name_pat and not fnmatch.fnmatch(n.name, name_pat):
            continue
        if perm and ("4000" in perm or "u=s" in perm or "u+s" in perm) and p not in setuid:
            continue
        if start == ".":
            p = "." if p == sh.fs.cwd else "./" + p[len(sh.fs.cwd):].lstrip("/")
        out.append(p)
        if len(out) >= 500:
            break
    return join(out)


@command("grep", "egrep")
def grep(sh, args, stdin=None):
    fl = [a for a in args if a.startswith("-")]
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        return "Usage: grep [OPTION]... PATTERNS [FILE]...\nTry 'grep --help' for more information.\n"
    pat, targets = rest[0], rest[1:]
    ci = any("i" in f for f in fl)
    inv = "-v" in fl
    try:
        rx = re.compile(re.escape(pat) if "-F" in fl else pat, re.I if ci else 0)
    except re.error:
        return f"grep: Invalid regular expression\n"
    sources: list[tuple[str, str]] = []
    if not targets:
        sources.append(("", stdin or ""))
    for t in targets:
        if any("r" in f.lower() for f in fl) and sh.fs.is_dir(t):
            sources += [(p, n.content) for p, n in sh.fs.walk(t) if not n.is_dir]
        else:
            node = sh.fs.get(t)
            if node is None:
                return f"grep: {t}: No such file or directory\n"
            if node.is_dir:
                return f"grep: {t}: Is a directory\n"
            sources.append((t, node.content))
    many = len(sources) > 1
    hits = [(f"{src}:" if many else "") + l for src, text in sources for l in lines(text) if (rx.search(l) is not None) != inv]
    if "-c" in fl:
        return f"{len(hits)}\n"
    return join(hits)


@command("head")
def head(sh, args, stdin=None):
    n = n_arg(args, 10)
    srcs = operands(args) or [None]
    return "".join(join(lines(cat(sh, [f], None) if f else (stdin or ""))[:n]) for f in srcs)


@command("tail")
def tail(sh, args, stdin=None):
    n = n_arg(args, 10)
    srcs = [f for f in operands(args) if not f.isdigit()] or [None]
    return "".join(join(lines(cat(sh, [f], None) if f else (stdin or ""))[-n:]) for f in srcs)


@command("wc")
def wc(sh, args, stdin=None):
    srcs = operands(args) or [None]
    out = []
    for f in srcs:
        if f and sh.fs.get(f) is None:
            out.append(f"wc: {f}: No such file or directory\n")
            continue
        text = sh.fs.get(f).content if f else (stdin or "")
        l, w, c = text.count("\n"), len(text.split()), len(text.encode())
        label = f" {f}" if f else ""
        out.append(f"{l}{label}\n" if "-l" in args else f"{w}{label}\n" if "-w" in args else f"{c}{label}\n" if "-c" in args else f"{l:7d} {w:7d} {c:7d}{label}\n")
    return "".join(out)


@command("sort")
def sort(sh, args, stdin=None):
    text = cat(sh, operands(args), None) if operands(args) else (stdin or "")
    ls_ = sorted(set(lines(text)) if "-u" in args else lines(text), reverse="-r" in args)
    return join(ls_)


@command("uniq")
def uniq(sh, args, stdin=None):
    text = cat(sh, operands(args), None) if operands(args) else (stdin or "")
    out: list[str] = []
    counts: list[int] = []
    for l in lines(text):
        if out and out[-1] == l:
            counts[-1] += 1
        else:
            out.append(l)
            counts.append(1)
    return join([f"{c:7d} {l}" for c, l in zip(counts, out)] if "-c" in args else out)


@command("cut")
def cut(sh, args, stdin=None):
    delim, fields = "\t", None
    rest = []
    it = iter(args)
    for a in it:
        if a.startswith("-d"):
            delim = a[2:] or next(it, "\t")
        elif a.startswith("-f"):
            fields = a[2:] or next(it, "1")
        elif not a.startswith("-"):
            rest.append(a)
    text = cat(sh, rest, None) if rest else (stdin or "")
    if not fields:
        return text
    idx = [int(x) - 1 for x in fields.split(",") if x.isdigit()]
    return join([delim.join(p[i] for i in idx if i < len(p)) for p in (l.split(delim) for l in lines(text))])


@command("awk")
def awk(sh, args, stdin=None):
    prog = next((a for a in args if "{" in a), "")
    rest = [a for a in args if "{" not in a and not a.startswith("-")]
    text = cat(sh, rest, None) if rest else (stdin or "")
    m = re.search(r"print\s+\$(\d+)", prog)
    if not m:
        return text
    i = int(m.group(1)) - 1
    return join([(l.split()[i] if 0 <= i < len(l.split()) else "") for l in lines(text)])


@command("sed", "tr", "xargs", "base64")
def passthrough(sh, args, stdin=None):
    rest = [a for a in args if not a.startswith("-") and not re.match(r"^s[/|#]", a)]
    if rest and stdin is None:
        return cat(sh, rest, None)
    return stdin or ""


@command("tee")
def tee(sh, args, stdin=None):
    for f in operands(args):
        try:
            sh.fs.write(f, stdin or "", append="-a" in args)
        except (FileNotFoundError, IsADirectoryError):
            pass
    return stdin or ""


@command("which")
def which(sh, args, stdin=None):
    out = []
    for a in args:
        for d in ("/usr/bin", "/usr/sbin", "/usr/local/bin"):
            if sh.fs.exists(f"{d}/{a}"):
                out.append(f"{d}/{a}")
                break
    return join(out)


@command("whereis")
def whereis(sh, args, stdin=None):
    return join([f"{a}: /usr/bin/{a} /usr/share/man/man1/{a}.1.gz" if sh.fs.exists(f"/usr/bin/{a}") else f"{a}:" for a in args])


@command("type", "command")
def type_(sh, args, stdin=None):
    return join([f"{a} is /usr/bin/{a}" if a in sh.handlers else f"-bash: type: {a}: not found" for a in args if not a.startswith("-")])


@command("file")
def file_(sh, args, stdin=None):
    out = []
    for f in operands(args):
        n = sh.fs.get(f)
        if n is None:
            out.append(f"{f}: cannot open `{f}' (No such file or directory)")
        elif n.is_dir:
            out.append(f"{f}: directory")
        elif n.executable and not n.content:
            out.append(f"{f}: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, "
                       "interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0, stripped")
        elif n.content.startswith("#!"):
            out.append(f"{f}: Bourne-Again shell script, ASCII text executable")
        elif not n.content:
            out.append(f"{f}: empty")
        else:
            out.append(f"{f}: ASCII text")
    return join(out)


@command("stat")
def stat(sh, args, stdin=None):
    out = []
    for f in operands(args):
        n = sh.fs.get(f)
        if n is None:
            out.append(f"stat: cannot statx '{f}': No such file or directory\n")
            continue
        kind = "directory" if n.is_dir else "regular file" if n.content or n.size else "regular empty file"
        octal = "0755" if n.is_dir or n.executable else "0600" if n.perms.startswith("-rw-------") else "0644"
        t = f"{n.mtime:%Y-%m-%d %H:%M:%S}.000000000 +0000"
        out.append(f"  File: {f}\n  Size: {n.size:<10}\tBlocks: {(n.size + 511) // 512:<10} IO Block: 4096   {kind}\n"
                   f"Device: fd01h/64769d\tInode: {sh.rng.randint(100000, 999999)}     Links: 1\n"
                   f"Access: ({octal}/{n.perms})  Uid: (    0/    {n.owner})   Gid: (    0/    {n.group})\n"
                   f"Access: {t}\nModify: {t}\nChange: {t}\n Birth: -\n")
    return "".join(out)


@command("du")
def du(sh, args, stdin=None):
    out = []
    for p in operands(args) or ["."]:
        total = sum(n.size for _, n in sh.fs.walk(p) if not n.is_dir)
        out.append(f"{human(total) if 'h' in flags(args) else total // 1024}\t{p}")
    return join(out)


@command("tar")
def tar(sh, args, stdin=None):
    if args and "x" in args[0]:
        fs_ = operands(args)
        name = fs_[-1] if fs_ else ""
        if not sh.fs.exists(name):
            return f"tar: {name}: Cannot open: No such file or directory\ntar: Error is not recoverable: exiting now\n"
        base = re.sub(r"\.(tar\.gz|tgz|tar|tar\.xz)$", "", posixpath.basename(name))
        sh.fs.mkdir(base)
        sh.fs.write(f"{base}/README", "")
    return ""


@command("truncate")
def truncate(sh, args, stdin=None):
    for f in operands(args):
        if sh.fs.exists(f):
            sh.fs.write(f, "")
    return ""


@command("md5sum", "sha256sum", "sha1sum")
def hashsum(sh, args, stdin=None):
    import hashlib
    algo = {"md5sum": "md5", "sha256sum": "sha256", "sha1sum": "sha1"}.get(sh.current_cmd, "md5")
    out = []
    for f in operands(args):
        n = sh.fs.get(f)
        if n is None:
            out.append(f"{algo}sum: {f}: No such file or directory")
        else:
            out.append(f"{hashlib.new(algo, n.content.encode()).hexdigest()}  {f}")
    return join(out)


@command("history")
def history(sh, args, stdin=None):
    if "-c" in args:
        sh.history.clear()
        return ""
    hist_file = f"{sh.fs.home}/.bash_history"
    prior = sh.fs.read(hist_file) if sh.fs.exists(hist_file) else ""
    return join([f"{i + 1:5d}  {l}" for i, l in enumerate(lines(prior) + sh.history)])


@command("env", "printenv", "set")
def env(sh, args, stdin=None):
    e = dict(sh.env, PWD=sh.fs.cwd)
    if sh.decoy:
        e.update(DB_PASSWORD="<decoy:db-app>", AWS_ACCESS_KEY_ID="<decoy:aws-id>", AWS_SECRET_ACCESS_KEY="<decoy:aws-secret>")
    if args and not args[0].startswith("-"):
        return e.get(args[0], "") + "\n"
    return "".join(f"{k}={v}\n" for k, v in e.items())


@command("export")
def export(sh, args, stdin=None):
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            sh.env[k] = v
    return ""


@command("unset")
def unset(sh, args, stdin=None):
    for a in args:
        sh.env.pop(a, None)
    return ""


@command("alias")
def alias(sh, args, stdin=None):
    return "" if args else "alias l='ls -CF'\nalias la='ls -A'\nalias ll='ls -alF'\nalias ls='ls --color=auto'\n"


@command("nano", "vi", "vim", "visudo", "emacs", "pico")
def editor(sh, args, stdin=None):
    return "Error opening terminal: unknown.\n"


@command("man")
def man(sh, args, stdin=None):
    return f"No manual entry for {args[0]}\n" if args else "What manual page do you want?\nFor example, try 'man man'.\n"


@command("help")
def help_(sh, args, stdin=None):
    return ("GNU bash, version 5.1.16(1)-release (x86_64-pc-linux-gnu)\n"
            "These shell commands are defined internally.  Type `help' to see this list.\n"
            "Type `help name' to find out more about the function `name'.\n")
