"""Network and download commands. No real network I/O happens here."""
from __future__ import annotations

import posixpath
import re

from . import command, n_arg, operands

LOCAL_IP = "10.0.12.37"


def _url(args: list[str]) -> str | None:
    for a in args:
        if re.match(r"^(https?|ftp|tftp)://", a) or (not a.startswith("-") and "." in a and "/" in a):
            return a if "://" in a else "http://" + a
    for a in args:
        if not a.startswith("-") and re.match(r"^[\w.-]+\.[a-z]{2,}$", a, re.I):
            return "http://" + a
    return None


def _filename(url: str, args: list[str]) -> str:
    for flag in ("-O", "-o"):
        if flag in args and args.index(flag) + 1 < len(args):
            return args[args.index(flag) + 1]
    name = posixpath.basename(url.split("?")[0].rstrip("/"))
    return name or "index.html"


@command("ifconfig")
def ifconfig(sh, args, stdin=None):
    return (f"eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
            f"        inet {LOCAL_IP}  netmask 255.255.255.0  broadcast 10.0.12.255\n"
            "        inet6 fe80::5054:ff:fe12:3456  prefixlen 64  scopeid 0x20<link>\n"
            "        ether 52:54:00:12:34:56  txqueuelen 1000  (Ethernet)\n"
            "        RX packets 48213911  bytes 61004832001 (61.0 GB)\n        RX errors 0  dropped 0  overruns 0  frame 0\n"
            "        TX packets 21398711  bytes 9834117652 (9.8 GB)\n        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0\n\n"
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n        inet 127.0.0.1  netmask 255.0.0.0\n"
            "        inet6 ::1  prefixlen 128  scopeid 0x10<host>\n        loop  txqueuelen 1000  (Local Loopback)\n"
            "        RX packets 1198233  bytes 184123311 (184.1 MB)\n        RX errors 0  dropped 0  overruns 0  frame 0\n"
            "        TX packets 1198233  bytes 184123311 (184.1 MB)\n        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0\n")


@command("ip")
def ip(sh, args, stdin=None):
    sub = args[0] if args else ""
    if sub.startswith("a"):
        return ("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000\n"
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n    inet 127.0.0.1/8 scope host lo\n"
                "       valid_lft forever preferred_lft forever\n    inet6 ::1/128 scope host \n       valid_lft forever preferred_lft forever\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000\n"
                f"    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff\n    inet {LOCAL_IP}/24 brd 10.0.12.255 scope global eth0\n"
                "       valid_lft forever preferred_lft forever\n    inet6 fe80::5054:ff:fe12:3456/64 scope link \n       valid_lft forever preferred_lft forever\n")
    if sub.startswith("r"):
        return f"default via 10.0.12.1 dev eth0 proto static \n10.0.12.0/24 dev eth0 proto kernel scope link src {LOCAL_IP} \n"
    if sub.startswith("l"):
        return ("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000\n"
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000\n"
                "    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff\n")
    if sub.startswith("n"):
        return "10.0.12.1 dev eth0 lladdr 52:54:00:aa:bb:01 REACHABLE\n10.0.12.10 dev eth0 lladdr 52:54:00:aa:bb:10 STALE\n"
    return "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\nwhere  OBJECT := { address | link | route | neigh }\n"


@command("route")
def route(sh, args, stdin=None):
    return ("Kernel IP routing table\nDestination     Gateway         Genmask         Flags Metric Ref    Use Iface\n"
            "default         10.0.12.1       0.0.0.0         UG    0      0        0 eth0\n"
            "10.0.12.0       0.0.0.0         255.255.255.0   U     0      0        0 eth0\n")


@command("arp")
def arp(sh, args, stdin=None):
    return ("Address                  HWtype  HWaddress           Flags Mask            Iface\n"
            "10.0.12.1                ether   52:54:00:aa:bb:01   C                     eth0\n"
            "10.0.12.10               ether   52:54:00:aa:bb:10   C                     eth0\n")


@command("netstat")
def netstat(sh, args, stdin=None):
    joined = "".join(args)
    client = sh.env["SSH_CLIENT"].split()[1]
    rows = [("tcp", "0.0.0.0:22", "0.0.0.0:*", "LISTEN", "812/sshd: /usr/sbin"),
            ("tcp", "0.0.0.0:80", "0.0.0.0:*", "LISTEN", "901/nginx: master p"),
            ("tcp", "127.0.0.1:3306", "0.0.0.0:*", "LISTEN", "1104/mysqld"),
            ("tcp", "127.0.0.53:53", "0.0.0.0:*", "LISTEN", "612/systemd-resolve"),
            ("tcp", f"{LOCAL_IP}:22", f"{sh.src_ip}:{client}", "ESTABLISHED", f"{sh.pid_base}/sshd: {sh.user}"),
            ("tcp6", ":::22", ":::*", "LISTEN", "812/sshd: /usr/sbin"),
            ("tcp6", ":::80", ":::*", "LISTEN", "901/nginx: master p"),
            ("udp", "127.0.0.53:53", "0.0.0.0:*", "", "612/systemd-resolve")]
    if "l" in joined:
        rows = [r for r in rows if r[3] != "ESTABLISHED"]
    out = [f"Active Internet connections ({'only servers' if 'l' in joined else 'servers and established'})\n",
           "Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name    \n"]
    for proto, loc, rem, st, prog in rows:
        out.append(f"{proto:<5} {0:>6} {0:>6} {loc:<23} {rem:<23} {st:<11} {prog if 'p' in joined and sh.user == 'root' else '-'}\n")
    return "".join(out)


@command("ss")
def ss(sh, args, stdin=None):
    return ("Netid State  Recv-Q Send-Q Local Address:Port   Peer Address:Port Process\n"
            "udp   UNCONN 0      0      127.0.0.53%lo:53        0.0.0.0:*     users:((\"systemd-resolve\",pid=612,fd=13))\n"
            "tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*     users:((\"sshd\",pid=812,fd=3))\n"
            "tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*     users:((\"nginx\",pid=903,fd=6),(\"nginx\",pid=901,fd=6))\n"
            "tcp   LISTEN 0      151        127.0.0.1:3306      0.0.0.0:*     users:((\"mysqld\",pid=1104,fd=23))\n"
            "tcp   LISTEN 0      128             [::]:22           [::]:*     users:((\"sshd\",pid=812,fd=4))\n")


@command("lsof")
def lsof(sh, args, stdin=None):
    return ("COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\nsshd     812 root    3u  IPv4  21488      0t0  TCP *:ssh (LISTEN)\n"
            "nginx    901 root    6u  IPv4  23017      0t0  TCP *:http (LISTEN)\nmysqld  1104 mysql  23u  IPv4  24101      0t0  TCP localhost:mysql (LISTEN)\n")


@command("ping")
def ping(sh, args, stdin=None):
    host = next((a for a in args if not a.startswith("-") and not a.isdigit()), None)
    if not host:
        return "ping: usage error: Destination address required\n"
    ip_ = host if re.match(r"^\d+\.\d+\.\d+\.\d+$", host) else f"142.250.{sh.rng.randint(1, 200)}.{sh.rng.randint(1, 254)}"
    n = n_arg([a for a in args if a.startswith("-c") or a.isdigit()], 4) if "-c" in " ".join(args) else 4
    n = min(n, 10)
    rtts = [round(sh.rng.uniform(9.8, 14.2), 1) for _ in range(n)]
    out = [f"PING {host} ({ip_}) 56(84) bytes of data.\n"]
    out += [f"64 bytes from {ip_}: icmp_seq={i + 1} ttl=117 time={r} ms\n" for i, r in enumerate(rtts)]
    out.append(f"\n--- {host} ping statistics ---\n{n} packets transmitted, {n} received, 0% packet loss, time {1000 * (n - 1) + 3}ms\n"
               f"rtt min/avg/max/mdev = {min(rtts)}/{sum(rtts) / n:.3f}/{max(rtts)}/0.{sh.rng.randint(100, 999)} ms\n")
    return "".join(out)


@command("wget")
def wget(sh, args, stdin=None):
    url = _url(args)
    if not url:
        return "wget: missing URL\nUsage: wget [OPTION]... [URL]...\n\nTry `wget --help' for more options.\n"
    name = _filename(url, args)
    size = sh.rng.randint(1200, 980000)
    host = re.sub(r"^\w+://", "", url).split("/")[0]
    ip_ = host if re.match(r"^\d+\.\d+\.\d+\.\d+(:\d+)?$", host) else f"{sh.rng.randint(23, 203)}.{sh.rng.randint(1, 254)}.{sh.rng.randint(1, 254)}.{sh.rng.randint(1, 254)}"
    sh.fs.write(name, "", size_override=size)
    if "-q" in args or "--quiet" in args:
        return ""
    return (f"--{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}--  {url}\n"
            f"Resolving {host.split(':')[0]} ({host.split(':')[0]})... {ip_.split(':')[0]}\n"
            f"Connecting to {host.split(':')[0]} ({host.split(':')[0]})|{ip_.split(':')[0]}|:{'443' if url.startswith('https') else '80'}... connected.\n"
            f"HTTP request sent, awaiting response... 200 OK\nLength: {size} ({size // 1024}K) [application/octet-stream]\n"
            f"Saving to: ‘{name}’\n\n{name:<20} 100%[===================>] {size / 1024:7.2f}K  --.-KB/s    in 0.{sh.rng.randint(1, 9)}s\n\n"
            f"{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S} ({sh.rng.randint(2, 9)}.{sh.rng.randint(10, 99)} MB/s) - ‘{name}’ saved [{size}/{size}]\n\n")


@command("curl")
def curl(sh, args, stdin=None):
    url = _url(args)
    if not url:
        return "curl: try 'curl --help' or 'curl --manual' for more information\n"
    if "-O" in args or "-o" in args:
        name = _filename(url, args)
        sh.fs.write(name, "", size_override=sh.rng.randint(1200, 980000))
        if "-s" in args or "-sS" in args or "--silent" in args:
            return ""
        return ("  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n"
                "                                 Dload  Upload   Total   Spent    Left  Speed\n"
                f"100  {sh.rng.randint(10, 900)}k  100  {sh.rng.randint(10, 900)}k    0     0   {sh.rng.randint(100, 999)}k      0 --:--:-- --:--:-- --:--:--  {sh.rng.randint(100, 999)}k\n")
    # Plain GET printed to stdout: a bare page body, so `curl url | sh` has something to pipe.
    return "<!DOCTYPE html>\n<html><head><title>Index</title></head><body></body></html>\n"


@command("tftp", "ftp", "sftp", "rsync")
def tftp(sh, args, stdin=None):
    return "" if args else f"{sh.current_cmd}: usage error\n"


@command("nc", "ncat", "netcat", "socat", "telnet")
def nc(sh, args, stdin=None):
    name = sh.current_cmd or "nc"
    if name in ("socat", "telnet"):
        return f"-bash: {name}: command not found\n"
    if "-l" in args or "-lvp" in "".join(args):
        return ""
    host = next((a for a in args if not a.startswith("-") and not a.isdigit()), None)
    if not host:
        return "usage: nc [-46CDdFhklNnrStUuvZz] [-I length] [-i interval] [-M ttl]\n\t  [-m minttl] [-O length] [-P proxy_username] [-p source_port]\n"
    return f"nc: connect to {host} port {next((a for a in args if a.isdigit()), '0')} (tcp) failed: Connection timed out\n"


@command("scp")
def scp(sh, args, stdin=None):
    return "ssh: connect to host port 22: Connection timed out\nlost connection\n" if len(operands(args)) >= 2 else "usage: scp [-346ABCOpqRrsTv] [-c cipher] [-D sftp_server_path] [-F ssh_config] source ... target\n"


@command("ssh")
def ssh(sh, args, stdin=None):
    target = next((a for a in args if not a.startswith("-")), None)
    if not target:
        return "usage: ssh [-46AaCfGgKkMNnqsTtVvXxYy] [-B bind_interface] [-b bind_address] destination [command [argument ...]]\n"
    return f"ssh: connect to host {target.split('@')[-1]} port 22: Connection timed out\n"


@command("ssh-keygen")
def sshkeygen(sh, args, stdin=None):
    path = args[args.index("-f") + 1] if "-f" in args and args.index("-f") + 1 < len(args) else f"{sh.fs.home}/.ssh/id_rsa"
    sh.fs.mkdir(posixpath.dirname(path), parents=True)
    sh.fs.write(path, "<generated-key-placeholder>\n", mode="-rw-------")
    sh.fs.write(path + ".pub", f"ssh-rsa <generated-key-placeholder> {sh.user}@{sh.host}\n")
    return (f"Generating public/private rsa key pair.\nYour identification has been saved in {path}\nYour public key has been saved in {path}.pub\n"
            f"The key fingerprint is:\nSHA256:<fingerprint-placeholder> {sh.user}@{sh.host}\n")


@command("git")
def git(sh, args, stdin=None):
    if args and args[0] == "clone":
        url = next((a for a in args[1:] if not a.startswith("-")), "")
        name = posixpath.basename(url.rstrip("/")).removesuffix(".git") or "repo"
        sh.fs.mkdir(name)
        sh.fs.write(f"{name}/README.md", f"# {name}\n")
        return f"Cloning into '{name}'...\nremote: Enumerating objects: 42, done.\nremote: Total 42 (delta 0), reused 0 (delta 0), pack-reused 42\nReceiving objects: 100% (42/42), 12.40 KiB | 1.24 MiB/s, done.\n"
    if args and args[0] == "--version":
        return "git version 2.34.1\n"
    return "fatal: not a git repository (or any of the parent directories): .git\n"


@command("pip", "pip3")
def pip(sh, args, stdin=None):
    if args and args[0] == "install":
        pkgs = [a for a in args[1:] if not a.startswith("-")]
        return "".join(f"Collecting {p}\n  Downloading {p}-1.0.0-py3-none-any.whl (24 kB)\n" for p in pkgs) + f"Installing collected packages: {', '.join(pkgs)}\nSuccessfully installed {' '.join(p + '-1.0.0' for p in pkgs)}\n"
    return "pip 22.0.2 from /usr/lib/python3/dist-packages/pip (python 3.10)\n"


@command("mysql", "mysqldump", "psql")
def mysql(sh, args, stdin=None):
    name = sh.current_cmd or "mysql"
    if name == "psql":
        return "-bash: psql: command not found\n"
    if "-p" in " ".join(args) and not any(a.startswith("-p") and len(a) > 2 for a in args):
        return "Enter password: \nERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)\n"
    return f"ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)\n"


@command("iptables", "ip6tables", "nft")
def iptables(sh, args, stdin=None):
    if sh.user != "root":
        return "iptables v1.8.7 (nf_tables): can't initialize iptables table `filter': Permission denied (you must be root)\n"
    if "-L" in args or "-S" in args:
        return "-P INPUT ACCEPT\n-P FORWARD ACCEPT\n-P OUTPUT ACCEPT\n" if "-S" in args else \
            "Chain INPUT (policy ACCEPT)\ntarget     prot opt source               destination         \n\nChain FORWARD (policy ACCEPT)\ntarget     prot opt source               destination         \n\nChain OUTPUT (policy ACCEPT)\ntarget     prot opt source               destination         \n"
    return ""


@command("ufw")
def ufw(sh, args, stdin=None):
    return "Status: inactive\n" if sh.user == "root" else "ERROR: You need to be root to run this script\n"


@command("tcpdump", "nmap", "masscan", "docker", "kubectl", "nvidia-smi", "wipe")
def notfound(sh, args, stdin=None):
    return f"-bash: {sh.current_cmd}: command not found\n"
