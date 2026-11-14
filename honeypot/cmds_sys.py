"""System, identity and package-management commands."""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from .shell import Shell, command, files_of, flags_of


def _uptime(sh: Shell) -> str:
    up = datetime.now() - sh.fs.boot_time
    return f"up {up.days} days, {up.seconds // 3600:2d}:{(up.seconds % 3600) // 60:02d},  1 user,  load average: 0.08, 0.03, 0.01"


@command("whoami")
def cmd_whoami(sh: Shell, args: list[str]) -> str:
    return sh.user + "\n"


@command("id")
def cmd_id(sh: Shell, args: list[str]) -> str:
    if sh.is_root:
        return "uid=0(root) gid=0(root) groups=0(root)\n"
    uid = {"deploy": 1000, "ubuntu": 1001}.get(sh.user, 1002)
    extra = ",4(adm),27(sudo)" if sh.user == "deploy" else ""
    return f"uid={uid}({sh.user}) gid={uid}({sh.user}) groups={uid}({sh.user}){extra}\n"


@command("hostname")
def cmd_hostname(sh: Shell, args: list[str]) -> str:
    return ("10.0.12.37\n" if "-I" in args or "-i" in args else sh.host + "\n")


@command("uname")
def cmd_uname(sh: Shell, args: list[str]) -> str:
    flags = flags_of(args)
    parts = {"s": "Linux", "n": sh.host, "r": "5.15.0-91-generic", "v": "#101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023",
             "m": "x86_64", "p": "x86_64", "i": "x86_64", "o": "GNU/Linux"}
    if "a" in flags or "--all" in args:
        return f"Linux {sh.host} 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux\n"
    if not flags:
        return "Linux\n"
    return " ".join(parts[f] for f in "snrvmpio" if f in flags) + "\n"


@command("arch")
def cmd_arch(sh: Shell, args: list[str]) -> str:
    return "x86_64\n"


@command("uptime")
def cmd_uptime(sh: Shell, args: list[str]) -> str:
    return f" {datetime.now():%H:%M:%S} {_uptime(sh)}\n"


@command("w")
def cmd_w(sh: Shell, args: list[str]) -> str:
    return (f" {datetime.now():%H:%M:%S} {_uptime(sh)}\n"
            "USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT\n"
            f"{sh.user:<8} pts/0    {sh.src_ip:<16} {datetime.now():%H:%M}    0.00s  0.03s  0.00s w\n")


@command("who", "users")
def cmd_who(sh: Shell, args: list[str]) -> str:
    return f"{sh.user:<8} pts/0        {datetime.now():%Y-%m-%d %H:%M} ({sh.src_ip})\n"


@command("last")
def cmd_last(sh: Shell, args: list[str]) -> str:
    now = datetime.now()
    rows = [f"{sh.user:<8} pts/0        {sh.src_ip:<16} {now:%a %b %d %H:%M}   still logged in\n"]
    for i in range(1, 8):
        t = now - timedelta(days=i * 2 + sh.rng.randint(0, 1), hours=sh.rng.randint(1, 20))
        end = t + timedelta(minutes=sh.rng.randint(3, 90))
        rows.append(f"{'root':<8} pts/0        10.0.12.{sh.rng.randint(2, 60):<12} {t:%a %b %d %H:%M} - {end:%H:%M}  "
                    f"(00:{sh.rng.randint(3, 59):02d})\n")
    rows.append(f"reboot   system boot  5.15.0-91-generic {sh.fs.boot_time:%a %b %d %H:%M}   still running\n\n"
                f"wtmp begins {sh.fs.boot_time - timedelta(days=40):%a %b %d %H:%M:%S %Y}\n")
    return "".join(rows)


@command("lastlog")
def cmd_lastlog(sh: Shell, args: list[str]) -> str:
    fmt = "%a %b %d %H:%M:%S +0000 %Y"
    return ("Username         Port     From                             Latest\n"
            f"root             pts/0    10.0.12.14                       {datetime.now() - timedelta(days=2):{fmt}}\n"
            f"deploy           pts/1    10.0.12.21                       {datetime.now() - timedelta(days=5):{fmt}}\n"
            f"{sh.user:<16} pts/0    {sh.src_ip:<32} {datetime.now():{fmt}}\n")


# ----------------------------------------------------------------- processes
def processes(sh: Shell) -> list[tuple]:
    b = sh.pid_base
    procs = [
        ("root", 1, 0.0, 0.1, 167744, 11932, "?", "Ss", "/sbin/init"),
        ("root", 2, 0.0, 0.0, 0, 0, "?", "S", "[kthreadd]"),
        ("root", 3, 0.0, 0.0, 0, 0, "?", "I<", "[rcu_gp]"),
        ("root", 12, 0.0, 0.0, 0, 0, "?", "S", "[ksoftirqd/0]"),
        ("root", 13, 0.0, 0.0, 0, 0, "?", "I", "[rcu_sched]"),
        ("root", 98, 0.0, 0.0, 0, 0, "?", "S", "[kswapd0]"),
        ("root", 412, 0.0, 0.3, 48960, 24312, "?", "S<s", "/lib/systemd/systemd-journald"),
        ("root", 445, 0.0, 0.1, 26116, 7044, "?", "Ss", "/lib/systemd/systemd-udevd"),
        ("systemd+", 612, 0.0, 0.1, 25532, 13200, "?", "Ss", "/lib/systemd/systemd-resolved"),
        ("root", 650, 0.0, 0.0, 9492, 2644, "?", "Ss", "/usr/sbin/cron -f -P"),
        ("messagebus", 651, 0.0, 0.0, 8616, 4672, "?", "Ss", "@dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only"),
        ("syslog", 655, 0.0, 0.0, 222400, 5736, "?", "Ssl", "/usr/sbin/rsyslogd -n -iNONE"),
        ("root", 668, 0.0, 0.1, 15336, 7416, "?", "Ss", "/lib/systemd/systemd-logind"),
        ("root", 812, 0.0, 0.1, 15432, 8928, "?", "Ss", "sshd: /usr/sbin/sshd -D [listener] 0 of 10-100 startups"),
        ("root", 870, 0.0, 0.0, 5828, 1016, "tty1", "Ss+", "/sbin/agetty -o -p -- \\u --noclear tty1 linux"),
        ("root", 901, 0.0, 0.0, 55204, 1620, "?", "Ss", "nginx: master process /usr/sbin/nginx -g daemon on; master_process on;"),
        ("www-data", 903, 0.0, 0.1, 55868, 5796, "?", "S", "nginx: worker process"),
        ("www-data", 904, 0.0, 0.1, 55868, 5796, "?", "S", "nginx: worker process"),
        ("mysql", 1104, 0.4, 5.1, 2306240, 416564, "?", "Ssl", "/usr/sbin/mysqld"),
        ("root", b, 0.0, 0.1, 17064, 10852, "?", "Ss", f"sshd: {sh.user} [priv]"),
        (sh.user, b + 2, 0.0, 0.0, 17064, 7220, "?", "S", f"sshd: {sh.user}@pts/0"),
        (sh.user, b + 3, 0.0, 0.0, 8392, 5264, "pts/0", "Ss", "-bash"),
    ]
    if sh.decoy:
        procs.append(("root", b - 300, 0.2, 0.3, 11280, 6128, "?", "S",
                      "/bin/bash /opt/scripts/db_backup.sh --user=backup --password=<decoy:backup>"))
    return procs


@command("ps")
def cmd_ps(sh: Shell, args: list[str]) -> str:
    joined = " ".join(args)
    b = sh.pid_base
    if not args:
        return f"    PID TTY          TIME CMD\n{b + 3:>7} pts/0    00:00:00 bash\n{b + 4:>7} pts/0    00:00:00 ps\n"
    if "-ef" in joined or ("-e" in joined and "f" in joined):
        out = ["UID          PID    PPID  C STIME TTY          TIME CMD\n"]
        for u, pid, cpu, mem, vsz, rss, tty, stat, cmd in processes(sh):
            ppid = 0 if pid in (1, 2) else 2 if cmd.startswith("[") else 1 if pid < b else b
            out.append(f"{u:<8} {pid:>7} {ppid:>7}  {int(cpu)} {sh.fs.boot_time:%b%d} {tty:<12} 00:00:{sh.rng.randint(0, 59):02d} {cmd}\n")
        out.append(f"{sh.user:<8} {b + 4:>7} {b + 3:>7}  0 {datetime.now():%H:%M} pts/0        00:00:00 ps {joined}\n")
        return "".join(out)
    out = ["USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"]
    for u, pid, cpu, mem, vsz, rss, tty, stat, cmd in processes(sh):
        start = f"{sh.fs.boot_time:%b%d}" if pid < b else f"{datetime.now():%H:%M}"
        t = "0:00" if pid >= b else f"{sh.rng.randint(0, 12)}:{sh.rng.randint(0, 59):02d}"
        out.append(f"{u:<10} {pid:>5} {cpu:4.1f} {mem:4.1f} {vsz:6d} {rss:5d} {tty:<8} {stat:<4} {start:<6} {t:>6} {cmd}\n")
    out.append(f"{sh.user:<10} {b + 4:>5}  0.0  0.1  10072  1620 pts/0    R+   {datetime.now():%H:%M}   0:00 ps {joined}\n")
    return "".join(out)


@command("top", "htop")
def cmd_top(sh: Shell, args: list[str]) -> str:
    head = (f"top - {datetime.now():%H:%M:%S} {_uptime(sh)}\n"
            "Tasks: 118 total,   1 running, 117 sleeping,   0 stopped,   0 zombie\n"
            "%Cpu(s):  0.3 us,  0.2 sy,  0.0 ni, 99.3 id,  0.2 wa,  0.0 hi,  0.0 si,  0.0 st\n"
            "MiB Mem :   7957.6 total,   2921.1 free,   1048.4 used,   3988.1 buff/cache\n"
            "MiB Swap:   2048.0 total,   2048.0 free,      0.0 used.   6606.3 avail Mem\n\n"
            "    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND\n")
    rows = []
    for u, pid, cpu, mem, vsz, rss, tty, stat, cmd in sorted(processes(sh), key=lambda p: -p[2])[:12]:
        name = cmd.split()[0].split("/")[-1][:15]
        rows.append(f"{pid:>7} {u[:8]:<9} 20   0 {vsz:>7} {rss:>6} {rss // 3:>6} {stat[0]} {cpu:5.1f} {mem:5.1f} "
                    f"{sh.rng.randint(0, 40):3d}:{sh.rng.randint(0, 59):02d}.{sh.rng.randint(0, 99):02d} {name}\n")
    return head + "".join(rows)


@command("free")
def cmd_free(sh: Shell, args: list[str]) -> str:
    hdr = "               total        used        free      shared  buff/cache   available\n"
    if "-h" in args:
        return hdr + "Mem:           7.8Gi       1.0Gi       2.9Gi        12Mi       3.9Gi       6.5Gi\nSwap:          2.0Gi          0B       2.0Gi\n"
    if "-m" in args:
        return hdr + "Mem:            7957        1048        2921          12        3988        6606\nSwap:           2047           0        2047\n"
    return hdr + "Mem:         8148564     1073592     2991244       12984     4083728     6764012\nSwap:        2097148           0     2097148\n"


@command("df")
def cmd_df(sh: Shell, args: list[str]) -> str:
    if "-h" in args:
        return ("Filesystem      Size  Used Avail Use% Mounted on\ntmpfs           796M  1.1M  795M   1% /run\n"
                "/dev/vda1        78G   24G   51G  33% /\ntmpfs           3.9G     0  3.9G   0% /dev/shm\n"
                "tmpfs           5.0M     0  5.0M   0% /run/lock\n/dev/vda15      105M  6.1M   99M   6% /boot/efi\n"
                "tmpfs           796M  4.0K  796M   1% /run/user/0\n")
    return ("Filesystem     1K-blocks     Used Available Use% Mounted on\ntmpfs             814860     1124    813736   1% /run\n"
            "/dev/vda1       81106868 24530236  53158524  32% /\ntmpfs            4074280        0   4074280   0% /dev/shm\n"
            "tmpfs               5120        0      5120   0% /run/lock\n/dev/vda15        106858     6182    100677   6% /boot/efi\n"
            "tmpfs             814856        4    814852   1% /run/user/0\n")


@command("mount")
def cmd_mount(sh: Shell, args: list[str]) -> str:
    return ("sysfs on /sys type sysfs (rw,nosuid,nodev,noexec,relatime)\nproc on /proc type proc (rw,nosuid,nodev,noexec,relatime)\n"
            "udev on /dev type devtmpfs (rw,nosuid,relatime,size=4043996k,nr_inodes=1010999,mode=755,inode64)\n"
            "devpts on /dev/pts type devpts (rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000)\n"
            "tmpfs on /run type tmpfs (rw,nosuid,nodev,noexec,relatime,size=814860k,mode=755,inode64)\n"
            "/dev/vda1 on / type ext4 (rw,relatime,discard,errors=remount-ro)\n"
            "/dev/vda15 on /boot/efi type vfat (rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=iso8859-1,shortname=mixed,errors=remount-ro)\n")


@command("lsblk")
def cmd_lsblk(sh: Shell, args: list[str]) -> str:
    return ("NAME    MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS\nloop0     7:0    0 63.9M  1 loop /snap/core20/2105\n"
            "vda     252:0    0   80G  0 disk \n├─vda1  252:1    0 79.9G  0 part /\n├─vda14 252:14   0    4M  0 part \n"
            "└─vda15 252:15   0  106M  0 part /boot/efi\n")


@command("lscpu")
def cmd_lscpu(sh: Shell, args: list[str]) -> str:
    return ("Architecture:            x86_64\n  CPU op-mode(s):        32-bit, 64-bit\n  Address sizes:         46 bits physical, 48 bits virtual\n"
            "  Byte Order:            Little Endian\nCPU(s):                  4\n  On-line CPU(s) list:   0-3\nVendor ID:               GenuineIntel\n"
            "  Model name:            Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\n    CPU family:          6\n    Model:               85\n"
            "    Thread(s) per core:  2\n    Core(s) per socket:  2\n    Socket(s):           1\n    Stepping:            7\n"
            "    BogoMIPS:            4999.99\nVirtualization features: \n  Hypervisor vendor:     KVM\n  Virtualization type:   full\n")


@command("nproc")
def cmd_nproc(sh: Shell, args: list[str]) -> str:
    return "4\n"


@command("lsmod")
def cmd_lsmod(sh: Shell, args: list[str]) -> str:
    return ("Module                  Size  Used by\ntls                   114688  0\nvirtio_net             61440  0\n"
            "net_failover           24576  1 virtio_net\next4                 1024000  1\njbd2                  180224  1 ext4\n"
            "virtio_blk             20480  3\nvirtio_pci             24576  0\n")


@command("lspci")
def cmd_lspci(sh: Shell, args: list[str]) -> str:
    return ("00:00.0 Host bridge: Intel Corporation 440FX - 82441FX PMC [Natoma] (rev 02)\n"
            "00:01.0 ISA bridge: Intel Corporation 82371SB PIIX3 ISA [Natoma/Triton II]\n"
            "00:02.0 VGA compatible controller: Cirrus Logic GD 5446\n"
            "00:03.0 Ethernet controller: Red Hat, Inc. Virtio network device\n"
            "00:04.0 SCSI storage controller: Red Hat, Inc. Virtio block device\n")


@command("dmesg")
def cmd_dmesg(sh: Shell, args: list[str]) -> str:
    if not sh.is_root:
        return "dmesg: read kernel buffer failed: Operation not permitted\n"
    return ("[    0.000000] Linux version 5.15.0-91-generic (buildd@lcy02-amd64-045) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils for Ubuntu) 2.38) #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023\n"
            "[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz-5.15.0-91-generic root=UUID=3f1a2b4c-5d6e-7f80-91a2-b3c4d5e6f708 ro console=tty1 console=ttyS0\n"
            "[    0.000000] KERNEL supported cpus:\n[    0.000000]   Intel GenuineIntel\n[    0.000000]   AMD AuthenticAMD\n"
            "[    1.204531] virtio_net virtio0 eth0: renamed from ens3\n"
            "[    2.118836] EXT4-fs (vda1): mounted filesystem with ordered data mode. Opts: (null). Quota mode: none.\n")


@command("journalctl")
def cmd_journalctl(sh: Shell, args: list[str]) -> str:
    return (f"-- Journal begins at {sh.fs.boot_time - timedelta(days=30):%a %Y-%m-%d %H:%M:%S} UTC, ends at {datetime.now():%a %Y-%m-%d %H:%M:%S} UTC. --\n"
            + "".join(f"{datetime.now() - timedelta(minutes=i * 7):%b %d %H:%M:%S} {sh.host} systemd[1]: Started Session {4800 + i} of User root.\n"
                      for i in range(9, 0, -1)))


@command("lsb_release")
def cmd_lsb_release(sh: Shell, args: list[str]) -> str:
    return "No LSB modules are available.\nDistributor ID:\tUbuntu\nDescription:\tUbuntu 22.04.3 LTS\nRelease:\t22.04\nCodename:\tjammy\n"


@command("date")
def cmd_date(sh: Shell, args: list[str]) -> str:
    if args and args[0].startswith("+"):
        fmt = args[0][1:].replace("%F", "%Y-%m-%d").replace("%T", "%H:%M:%S")
        try:
            return datetime.now().strftime(fmt) + "\n"
        except ValueError:
            return ""
    return datetime.now().strftime("%a %b %d %I:%M:%S %p UTC %Y\n")


@command("cal")
def cmd_cal(sh: Shell, args: list[str]) -> str:
    return calendar.month(datetime.now().year, datetime.now().month)


@command("getconf")
def cmd_getconf(sh: Shell, args: list[str]) -> str:
    return "64\n"


@command("ulimit")
def cmd_ulimit(sh: Shell, args: list[str]) -> str:
    return "unlimited\n"


# ------------------------------------------------------- privilege & users
@command("sudo")
def cmd_sudo(sh: Shell, args: list[str]) -> str:
    inner = [a for a in args if not a.startswith("-")]
    if sh.is_root:
        return sh._run_statement(" ".join(inner))[0] if inner else ""
    return f"{sh.user} is not in the sudoers file.  This incident will be reported.\n"


@command("su")
def cmd_su(sh: Shell, args: list[str]) -> str:
    return "" if sh.is_root else "su: Authentication failure\n"


@command("passwd")
def cmd_passwd(sh: Shell, args: list[str]) -> str:
    return "passwd: Authentication token manipulation error\npasswd: password unchanged\n"


@command("useradd", "adduser")
def cmd_useradd(sh: Shell, args: list[str]) -> str:
    names = files_of(args)
    if not names:
        return "Usage: useradd [options] LOGIN\n"
    if not sh.is_root:
        return "useradd: Permission denied.\nuseradd: cannot lock /etc/passwd; try again later.\n"
    name = names[-1]
    if name + ":" in sh.fs.read("/etc/passwd"):
        return f"useradd: user '{name}' already exists\n"
    sh.fs.write("/etc/passwd", f"{name}:x:1003:1003::/home/{name}:/bin/sh\n", append=True)
    sh.fs.mkdir(f"/home/{name}", parents=True, owner=name)
    return ""


@command("pkexec", "doas")
def cmd_pkexec(sh: Shell, args: list[str]) -> str:
    return "-bash: pkexec: command not found\n"


@command("crontab")
def cmd_crontab(sh: Shell, args: list[str]) -> str:
    path = f"/var/spool/cron/crontabs/{sh.user}"
    if "-l" in args:
        return sh.fs.read(path) if sh.fs.exists(path) else f"no crontab for {sh.user}\n"
    if "-r" in args:
        if sh.fs.exists(path):
            sh.fs.remove(path)
        return ""
    if "-e" in args:
        return "Error opening terminal: unknown.\n"
    files = files_of(args)
    if files and files[0] != "-" and sh.fs.exists(files[0]):
        sh.fs.mkdir("/var/spool/cron/crontabs", parents=True)
        sh.fs.write(path, sh.fs.read(files[0]))
    return ""


@command("systemctl")
def cmd_systemctl(sh: Shell, args: list[str]) -> str:
    sub = args[0] if args else "list-units"
    unit = args[1] if len(args) > 1 else ""
    if sub == "status":
        svc = unit.replace(".service", "") or "ssh"
        return (f"● {svc}.service - {svc} daemon\n     Loaded: loaded (/lib/systemd/system/{svc}.service; enabled; vendor preset: enabled)\n"
                f"     Active: active (running) since {sh.fs.boot_time:%a %Y-%m-%d %H:%M:%S} UTC; {(datetime.now() - sh.fs.boot_time).days} days ago\n"
                f"   Main PID: {sh.rng.randint(600, 1200)} ({svc})\n      Tasks: 1 (limit: 9389)\n     Memory: 4.2M\n        CPU: 1.204s\n")
    if sub in ("start", "stop", "restart", "reload", "enable", "disable", "daemon-reload"):
        return "" if sh.is_root else f"Failed to {sub} {unit}: Access denied\n"
    return ("  UNIT                         LOAD   ACTIVE SUB     DESCRIPTION\n  cron.service                 loaded active running Regular background program processing daemon\n"
            "  mysql.service                loaded active running MySQL Community Server\n  nginx.service                loaded active running A high performance web server and a reverse proxy server\n"
            "  rsyslog.service              loaded active running System Logging Service\n  ssh.service                  loaded active running OpenBSD Secure Shell server\n"
            "  systemd-journald.service     loaded active running Journal Service\n  systemd-logind.service       loaded active running User Login Management\n")


@command("service")
def cmd_service(sh: Shell, args: list[str]) -> str:
    if len(args) >= 2:
        return cmd_systemctl(sh, [args[1], args[0]])
    return "Usage: service < option > | --status-all | [ service_name [ command | --full-restart ] ]\n"


@command("apt", "apt-get")
def cmd_apt(sh: Shell, args: list[str]) -> str:
    sub = args[0] if args else ""
    if not sh.is_root:
        return "E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)\nE: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), are you root?\n"
    if sub == "update":
        return ("Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease\nGet:2 http://security.ubuntu.com/ubuntu jammy-security InRelease [110 kB]\n"
                "Get:3 http://archive.ubuntu.com/ubuntu jammy-updates InRelease [119 kB]\nFetched 229 kB in 1s (201 kB/s)\n"
                "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n3 packages can be upgraded. Run 'apt list --upgradable' to see them.\n")
    if sub == "install":
        pkgs = [a for a in args[1:] if not a.startswith("-")]
        return ("Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n"
                + "".join(f"{p} is already the newest version.\n" for p in pkgs) + "0 upgraded, 0 newly installed, 0 to remove and 3 not upgraded.\n")
    return "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n"


@command("yum", "dnf", "rpm", "pacman", "apk", "docker", "nvidia-smi", "nmap", "wipe")
def cmd_notfound(sh: Shell, args: list[str]) -> str:
    return ""  # resolved by caller's name via REGISTRY lookup; emulate missing tool


@command("dpkg")
def cmd_dpkg(sh: Shell, args: list[str]) -> str:
    if "-l" in args:
        return ("Desired=Unknown/Install/Remove/Purge/Hold\n| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n"
                "||/ Name                 Version                Architecture Description\n+++-====================-======================-============-=================================\n"
                "ii  bash                 5.1-6ubuntu1           amd64        GNU Bourne Again SHell\nii  coreutils            8.32-4.1ubuntu1        amd64        GNU core utilities\n"
                "ii  curl                 7.81.0-1ubuntu1.14     amd64        command line tool for transferring data with URL syntax\n"
                "ii  mysql-server         8.0.35-0ubuntu0.22.04.1 all         MySQL database server (metapackage depending on the latest version)\n"
                "ii  nginx                1.18.0-6ubuntu14.4     amd64        small, powerful, scalable web/proxy server\n"
                "ii  openssh-server       1:8.9p1-3ubuntu0.4     amd64        secure shell (SSH) server, for secure access from remote machines\n"
                "ii  python3              3.10.6-1~22.04         amd64        interactive high-level object-oriented language (default python3 version)\n"
                "ii  wget                 1.21.2-2ubuntu1        amd64        retrieves files from the web\n")
    return ""


@command("pip", "pip3")
def cmd_pip(sh: Shell, args: list[str]) -> str:
    return "WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour.\n" if sh.is_root else ""


@command("python", "python3", "perl", "php", "ruby", "node")
def cmd_interpreter(sh: Shell, args: list[str]) -> str:
    if not args:
        return ""  # interactive REPL not emulated; behave as if it exited
    if args[0] in ("-c", "-e"):
        return ""
    if args[0] in ("-V", "--version"):
        return "Python 3.10.12\n"
    if sh.fs.exists(args[0]):
        return ""
    return f"python3: can't open file '{sh.fs.resolve(args[0])}': [Errno 2] No such file or directory\n"


@command("gcc", "cc", "make")
def cmd_gcc(sh: Shell, args: list[str]) -> str:
    return "-bash: gcc: command not found\n" if sh.rng.random() < 0.5 else "make: *** No targets specified and no makefile found.  Stop.\n"


@command("sh", "bash")
def cmd_sh(sh: Shell, args: list[str]) -> str:
    if args and args[0] == "-c" and len(args) > 1:
        return sh._run_statement(args[1])[0]
    files = files_of(args)
    if files:
        node = sh.fs.get(files[0])
        if node is None:
            return f"sh: 0: cannot open {files[0]}: No such file\n"
        return sh.run_script(node)
    return ""


@command("busybox")
def cmd_busybox(sh: Shell, args: list[str]) -> str:
    if not args:
        return "BusyBox v1.30.1 (Ubuntu 1:1.30.1-7ubuntu3) multi-call binary.\nBusyBox is copyrighted by many authors between 1998-2015.\n"
    return sh._run_statement(" ".join(args))[0]


@command("nohup", "setsid", "timeout")
def cmd_nohup(sh: Shell, args: list[str]) -> str:
    inner = [a for a in args if not a.startswith("-") and not a.isdigit()]
    return sh._run_statement(" ".join(inner))[0] if inner else ""


@command("reboot", "shutdown", "poweroff", "halt")
def cmd_reboot(sh: Shell, args: list[str]) -> str:
    return "" if sh.is_root else "Failed to set wall message, ignoring: Interactive authentication required.\nFailed to reboot system via logind: Interactive authentication required.\n"


@command("help")
def cmd_help(sh: Shell, args: list[str]) -> str:
    return ("GNU bash, version 5.1.16(1)-release (x86_64-pc-linux-gnu)\nThese shell commands are defined internally.  Type `help' to see this list.\n"
            "Type `help name' to find out more about the function `name'.\n")


@command("mysql", "mysqldump")
def cmd_mysql(sh: Shell, args: list[str]) -> str:
    return "ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: " + ("YES" if any(a.startswith("-p") for a in args) else "NO") + ")\n"
