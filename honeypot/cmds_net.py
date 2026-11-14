"""Network commands. Nothing here opens a real socket; downloads create an empty
placeholder file in the fake filesystem so that chmod/execute chains continue."""
from __future__ import annotations

import posixpath
import re

from .shell import Shell, command, files_of, n_arg

_URL = re.compile(r"^(https?|ftp)://", re.I)


def _url_of(args: list[str]) -> str | None:
    for a in args:
        if _URL.match(a) or ("." in a and not a.startswith("-") and "/" in a):
            return a if _URL.match(a) else "http://" + a
    return next(("http://" + a for a in args if "." in a and not a.startswith("-")), None)


@command("ifconfig")
def cmd_ifconfig(sh: Shell, args: list[str]) -> str:
    return ("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
            "        inet 10.0.12.37  netmask 255.255.255.0  broadcast 10.0.12.255\n"
            "        inet6 fe80::5054:ff:fe12:3456  prefixlen 64  scopeid 0x20<link>\n"
            "        ether 52:54:00:12:34:56  txqueuelen 1000  (Ethernet)\n"
            "        RX packets 48213911  bytes 61004832001 (61.0 GB)\n        RX errors 0  dropped 0  overruns 0  frame 0\n"
            "        TX packets 21398711  bytes 9834117652 (9.8 GB)\n        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0\n\n"
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n        inet 127.0.0.1  netmask 255.0.0.0\n"
            "        inet6 ::1  prefixlen 128  scopeid 0x10<host>\n        loop  txqueuelen 1000  (Local Loopback)\n"
            "        RX packets 1198233  bytes 184123311 (184.1 MB)\n        RX errors 0  dropped 0  overruns 0  frame 0\n"
            "        TX packets 1198233  bytes 184123311 (184.1 MB)\n        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0\n")


@command("ip")
def cmd_ip(sh: Shell, args: list[str]) -> str:
    sub = args[0] if args else ""
    if sub.startswith("a"):
        return ("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000\n"
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n    inet 127.0.0.1/8 scope host lo\n"
                "       valid_lft forever preferred_lft forever\n    inet6 ::1/128 scope host \n       valid_lft forever preferred_lft forever\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000\n"
                "    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff\n    inet 10.0.12.37/24 brd 10.0.12.255 scope global eth0\n"
                "       valid_lft forever preferred_lft forever\n    inet6 fe80::5054:ff:fe12:3456/64 scope link \n       valid_lft forever preferred_lft forever\n")
    if sub.startswith("r"):
        return "default via 10.0.12.1 dev eth0 proto static \n10.0.12.0/24 dev eth0 proto kernel scope link src 10.0.12.37 \n"
    if sub.startswith("l"):
        return ("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000\n"
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n"
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000\n"
                "    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff\n")
    if sub.startswith("n"):
        return "10.0.12.1 dev eth0 lladdr 52:54:00:aa:bb:01 REACHABLE\n10.0.12.10 dev eth0 lladdr 52:54:00:aa:bb:10 STALE\n"
    return "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\nwhere  OBJECT := { address | link | route | neigh }\n"


@command("route")
def cmd_route(sh: Shell, args: list[str]) -> str:
    return ("Kernel IP routing table\nDestination     Gateway         Genmask         Flags Metric Ref    Use Iface\n"
            "default         10.0.12.1       0.0.0.0         UG    0      0        0 eth0\n"
            "10.0.12.0       0.0.0.0         255.255.255.0   U     0      0        0 eth0\n")


@command("arp")
def cmd_arp(sh: Shell, args: list[str]) -> str:
    return ("Address                  HWtype  HWaddress           Flags Mask            Iface\n"
            "10.0.12.1                ether   52:54:00:aa:bb:01   C                     eth0\n"
            "10.0.12.10               ether   52:54:00:aa:bb:10   C                     eth0\n")


@command("netstat")
def cmd_netstat(sh: Shell, args: list[str]) -> str:
    client = sh.env["SSH_CLIENT"].split()[1]
    rows = [("tcp", "0.0.0.0:22", "0.0.0.0:*", "LISTEN", "812/sshd: /usr/sbin"),
            ("tcp", "0.0.0.0:80", "0.0.0.0:*", "LISTEN", "901/nginx: master p"),
            ("tcp", "127.0.0.1:3306", "0.0.0.0:*", "LISTEN", "1104/mysqld"),
            ("tcp", "127.0.0.53:53", "0.0.0.0:*", "LISTEN", "612/systemd-resolve"),
            ("tcp", "10.0.12.37:22", f"{sh.src_ip}:{client}", "ESTABLISHED", f"{sh.pid_base}/sshd: {sh.user}"),
            ("tcp6", ":::22", ":::*", "LISTEN", "812/sshd: /usr/sbin"),
            ("tcp6", ":::80", ":::*", "LISTEN", "901/nginx: master p"),
            ("udp", "127.0.0.53:53", "0.0.0.0:*", "", "612/systemd-resolve")]
    joined = "".join(args)
    if "l" in joined:
        rows = [r for r in rows if r[3] != "ESTABLISHED"]
    out = ["Active Internet connections (" + ("only servers" if "l" in joined else "servers and established") + ")\n",
           "Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name    \n"]
    for proto, loc, rem, st, prog in rows:
        out.append(f"{proto:<5} {0:>6} {0:>6} {loc:<23} {rem:<23} {st:<11} {prog if 'p' in joined or sh.is_root else '-'}\n")
    return "".join(out)


@command("ss")
def cmd_ss(sh: Shell, args: list[str]) -> str:
    return ("Netid State  Recv-Q Send-Q Local Address:Port   Peer Address:Port Process\n"
            "udp   UNCONN 0      0      127.0.0.53%lo:53        0.0.0.0:*     users:((\"systemd-resolve\",pid=612,fd=13))\n"
            "tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*     users:((\"sshd\",pid=812,fd=3))\n"
            "tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*     users:((\"nginx\",pid=903,fd=6),(\"nginx\",pid=901,fd=6))\n"
            "tcp   LISTEN 0      151        127.0.0.1:3306      0.0.0.0:*     users:((\"mysqld\",pid=1104,fd=23))\n"
            "tcp   LISTEN 0      128             [::]:22           [::]:*     users:((\"sshd\",pid=812,fd=4))\n")


@command("lsof")
def cmd_lsof(sh: Shell, args: list[str]) -> str:
    return ("COMMAND  PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\nsshd     812 root    3u  IPv4  21488      0t0  TCP *:ssh (LISTEN)\n"
            "nginx    901 root    6u  IPv4  23017      0t0  TCP *:http (LISTEN)\nmysqld  1104 mysql  23u  IPv4  24101      0t0  TCP localhost:mysql (LISTEN)\n")


@command("ping")
def cmd_ping(sh: Shell, args: list[str]) -> str:
    host = next((a for a in args if not a.startswith("-") and not a.isdigit()), None)
    if not host:
        return "ping: usage error: Destination address required\n"
    ip = host if re.match(r"^\d+\.\d+\.\d+\.\d+$", host) else f"142.250.{sh.rng.randint(1, 200)}.{sh.rng.randint(1, 254)}"
    n = n_arg(args, 4) if any(a.startswith("-c") for a in args) else 4
    rtts = [round(sh.rng.uniform(9.8, 14.2), 1) for _ in range(n)]
    out = [f"PING {host} ({ip}) 56(84) bytes of data.\n"]
    out += [f"64 bytes from {ip}: icmp_seq={i + 1} ttl=117 time={r} ms\n" for i, r in enumerate(rtts)]
    out.append(f"\n--- {host} ping statistics ---\n{n} packets transmitted, {n} received, 0% packet loss, time {1000 * (n - 1) + 3}ms\n"
               f"rtt min/avg/max/mdev = {min(rtts)}/{sum(rtts) / n:.3f}/{max(rtts)}/0.{sh.rng.randint(100, 999)} ms\n")
    return "".join(out)


def _save_download(sh: Shell, url: str, name: str) -> int:
    size = sh.rng.randint(1200, 98000)
    sh.fs.write(name, "", size_override=size)
    return size


@command("wget")
def cmd_wget(sh: Shell, args: list[str]) -> str:
    url = _url_of(args)
    if not url:
        return "wget: missing URL\nUsage: wget [OPTION]... [URL]...\n\nTry `wget --help' for more options.\n"
    name = posixpath.basename(url.split("?")[0]) or "index.html"
    for i, a in enumerate(args):
        if a == "-O" and i + 1 < len(args):
            name = args[i + 1]
        elif a.startswith("-O") and len(a) > 2:
            name = a[2:]
    host = re.sub(r"^\w+://", "", url).split("/")[0]
    size = _save_download(sh, url, name)
    if "-q" in args or "-nv" in args:
        return ""
    return (f"--{sh.rng.randint(2024, 2025)}-01-01 00:00:00--  {url}\nResolving {host} ({host})... {sh.rng.randint(1, 223)}.{sh.rng.randint(0, 255)}.{sh.rng.randint(0, 255)}.{sh.rng.randint(1, 254)}\n"
            f"Connecting to {host} ({host})|...|:80... connected.\nHTTP request sent, awaiting response... 200 OK\n"
            f"Length: {size} ({size // 1024}K) [application/octet-stream]\nSaving to: '{name}'\n\n"
            f"{name:<20} 100%[===================>] {size / 1024:6.2f}K  --.-KB/s    in 0.01s\n\n"
            f"({size // 100}.{size % 100:02d} KB/s) - '{name}' saved [{size}/{size}]\n")


@command("curl")
def cmd_curl(sh: Shell, args: list[str]) -> str:
    url = _url_of(args)
    if not url:
        return "curl: try 'curl --help' or 'curl --manual' for more information\n"
    name = None
    for i, a in enumerate(args):
        if a in ("-o", "--output") and i + 1 < len(args):
            name = args[i + 1]
        elif a in ("-O", "--remote-name"):
            name = posixpath.basename(url.split("?")[0]) or "index.html"
    if name:
        size = _save_download(sh, url, name)
        return "" if "-s" in args else (f"  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n"
                                        f"                                 Dload  Upload   Total   Spent    Left  Speed\n"
