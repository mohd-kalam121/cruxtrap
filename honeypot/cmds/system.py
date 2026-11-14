"""System, identity, process and package commands."""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from . import ExitSession, command, flags, join

KERNEL = "5.15.0-91-generic"
KVER = "#101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023"


def _uptime(sh) -> str:
    up = datetime.now() - sh.fs.boot_time
    return f"up {up.days} days, {up.seconds // 3600:2d}:{(up.seconds % 3600) // 60:02d}"


@command("exit", "logout")
def exit_(sh, args, stdin=None):
    raise ExitSession()


@command("clear", "reset")
def clear(sh, args, stdin=None):
    return "\x1b[H\x1b[2J"


@command("whoami")
def whoami(sh, args, stdin=None):
    return sh.user + "\n"


@command("hostname")
def hostname(sh, args, stdin=None):
    return ("10.0.12.37\n" if "-I" in args or "-i" in args else sh.host + "\n")


@command("id")
def id_(sh, args, stdin=None):
    if sh.user == "root":
        return "uid=0(root) gid=0(root) groups=0(root)\n"
    uid = {"deploy": 1000, "ubuntu": 1001}.get(sh.user, 1002)
    extra = ",4(adm),27(sudo)" if sh.user == "deploy" else ""
    return f"uid={uid}({sh.user}) gid={uid}({sh.user}) groups={uid}({sh.user}){extra}\n"


@command("uname")
def uname(sh, args, stdin=None):
    fl = flags(args)
    if "a" in fl or "--all" in args:
        return f"Linux {sh.host} {KERNEL} {KVER} x86_64 x86_64 x86_64 GNU/Linux\n"
    parts = {"s": "Linux", "n": sh.host, "r": KERNEL, "v": KVER, "m": "x86_64", "p": "x86_64", "i": "x86_64", "o": "GNU/Linux"}
    return (" ".join(parts[f] for f in "snrvmpio" if f in fl) or "Linux") + "\n"


@command("arch")
def arch(sh, args, stdin=None):
    return "x86_64\n"


@command("nproc")
def nproc(sh, args, stdin=None):
    return "4\n"


@command("uptime")
def uptime(sh, args, stdin=None):
    return f" {datetime.now():%H:%M:%S} {_uptime(sh)},  1 user,  load average: 0.08, 0.03, 0.01\n"


@command("w")
def w(sh, args, stdin=None):
    return (f" {datetime.now():%H:%M:%S} {_uptime(sh)},  1 user,  load average: 0.08, 0.03, 0.01\n"
            "USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT\n"
            f"{sh.user:<8} pts/0    {sh.src_ip:<16} {datetime.now():%H:%M}    0.00s  0.03s  0.00s w\n")


@command("who")
def who(sh, args, stdin=None):
    return f"{sh.user:<8} pts/0        {datetime.now():%Y-%m-%d %H:%M} ({sh.src_ip})\n"


@command("last")
def last(sh, args, stdin=None):
    now = datetime.now()
    rows = [f"{sh.user:<8} pts/0        {sh.src_ip:<16} {now:%a %b %d %H:%M}   still logged in"]
    for i in range(1, 8):
        t = now - timedelta(days=i * 2, hours=sh.rng.randint(1, 20))
        mins = sh.rng.randint(3, 90)
        rows.append(f"{'root':<8} pts/0        10.0.12.{sh.rng.randint(2, 60):<12} {t:%a %b %d %H:%M} - "
                    f"{t + timedelta(minutes=mins):%H:%M}  ({mins // 60:02d}:{mins % 60:02d})")
    rows.append(f"reboot   system boot  {KERNEL} {sh.fs.boot_time:%a %b %d %H:%M}   still running")
    rows.append(f"\nwtmp begins {sh.fs.boot_time - timedelta(days=40):%a %b %d %H:%M:%S %Y}")
    return join(rows)


@command("lastlog")
def lastlog(sh, args, stdin=None):
    now = datetime.now()
    return ("Username         Port     From                             Latest\n"
            f"root             pts/0    10.0.12.14                       {now - timedelta(days=2):%a %b %d %H:%M:%S +0000 %Y}\n"
            f"deploy           pts/1    10.0.12.21                       {now - timedelta(days=5):%a %b %d %H:%M:%S +0000 %Y}\n")


def processes(sh) -> list[tuple]:
    """(user, pid, %cpu, %mem, vsz, rss, tty, stat, command)"""
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
def ps(sh, args, stdin=None):
    joined = " ".join(args)
    b = sh.pid_base
    if not args:
        return f"    PID TTY          TIME CMD\n{b + 3:>7} pts/0    00:00:00 bash\n{b + 4:>7} pts/0    00:00:00 ps\n"
    procs = processes(sh)
    if "-e" in joined or "-A" in joined:
        out = ["UID          PID    PPID  C STIME TTY          TIME CMD"]
        for u, pid, cpu, mem, vsz, rss, tty, st, cmd in procs:
            ppid = 0 if pid in (1, 2) else 2 if cmd.startswith("[") else 1 if pid < b else b
            out.append(f"{u:<8} {pid:>7} {ppid:>7}  {int(cpu)} {sh.fs.boot_time:%b%d} {tty:<12} 00:00:{sh.rng.randint(0, 59):02d} {cmd}")
        out.append(f"{sh.user:<8} {b + 4:>7} {b + 3:>7}  0 {datetime.now():%H:%M} pts/0        00:00:00 ps {joined}")
        return join(out)
    out = ["USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"]
    for u, pid, cpu, mem, vsz, rss, tty, st, cmd in procs:
        start = f"{sh.fs.boot_time:%b%d}" if pid < b - 400 else f"{datetime.now():%H:%M}"
        t = "0:00" if pid >= b - 400 else f"{sh.rng.randint(0, 12)}:{sh.rng.randint(0, 59):02d}"
        out.append(f"{u:<10} {pid:>5} {cpu:4.1f} {mem:4.1f} {vsz:6d} {rss:5d} {tty:<8} {st:<4} {start:<6} {t:>6} {cmd}")
    out.append(f"{sh.user:<10} {b + 4:>5}  0.0  0.1  10072  1620 pts/0    R+   {datetime.now():%H:%M}   0:00 ps {joined}")
    return join(out)


@command("top", "htop")
def top(sh, args, stdin=None):
    head = (f"top - {datetime.now():%H:%M:%S} {_uptime(sh)},  1 user,  load average: 0.08, 0.03, 0.01\n"
            "Tasks: 118 total,   1 running, 117 sleeping,   0 stopped,   0 zombie\n"
            "%Cpu(s):  0.3 us,  0.2 sy,  0.0 ni, 99.3 id,  0.2 wa,  0.0 hi,  0.0 si,  0.0 st\n"
            "MiB Mem :   7957.6 total,   2921.1 free,   1048.4 used,   3988.1 buff/cache\n"
            "MiB Swap:   2048.0 total,   2048.0 free,      0.0 used.   6606.3 avail Mem\n\n"
            "    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND\n")
    rows = []
    for u, pid, cpu, mem, vsz, rss, tty, st, cmd in sorted(processes(sh), key=lambda p: -p[2])[:12]:
        name = cmd.split()[0].split("/")[-1].strip("[]")[:15]
        rows.append(f"{pid:>7} {u[:8]:<9} 20   0 {vsz:>7} {rss:>6} {rss // 3:>6} {st[0]} {cpu:5.1f} {mem:5.1f} "
                    f"{sh.rng.randint(0, 40):3d}:{sh.rng.randint(0, 59):02d}.{sh.rng.randint(0, 99):02d} {name}")
    return head + join(rows)


@command("free")
def free(sh, args, stdin=None):
    hdr = "               total        used        free      shared  buff/cache   available\n"
    if "-h" in args:
        return hdr + "Mem:           7.8Gi       1.0Gi       2.9Gi        12Mi       3.9Gi       6.5Gi\nSwap:          2.0Gi          0B       2.0Gi\n"
    if "-m" in args:
        return hdr + "Mem:            7957        1048        2921          12        3988        6606\nSwap:           2047           0        2047\n"
    return hdr + "Mem:         8148564     1073592     2991244       12984     4083728     6764012\nSwap:        2097148           0     2097148\n"


@command("df")
def df(sh, args, stdin=None):
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
def mount(sh, args, stdin=None):
    return ("sysfs on /sys type sysfs (rw,nosuid,nodev,noexec,relatime)\nproc on /proc type proc (rw,nosuid,nodev,noexec,relatime)\n"
            "udev on /dev type devtmpfs (rw,nosuid,relatime,size=4043996k,nr_inodes=1010999,mode=755,inode64)\n"
            "devpts on /dev/pts type devpts (rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000)\n"
            "tmpfs on /run type tmpfs (rw,nosuid,nodev,noexec,relatime,size=814860k,mode=755,inode64)\n"
            "/dev/vda1 on / type ext4 (rw,relatime,discard,errors=remount-ro)\n"
            "/dev/vda15 on /boot/efi type vfat (rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=iso8859-1,shortname=mixed,errors=remount-ro)\n")


@command("lsblk")
def lsblk(sh, args, stdin=None):
    return ("NAME    MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS\nloop0     7:0    0 63.9M  1 loop /snap/core20/2105\n"
            "vda     252:0    0   80G  0 disk \n├─vda1  252:1    0 79.9G  0 part /\n├─vda14 252:14   0    4M  0 part \n"
            "└─vda15 252:15   0  106M  0 part /boot/efi\n")


@command("lscpu")
def lscpu(sh, args, stdin=None):
    return ("Architecture:            x86_64\n  CPU op-mode(s):        32-bit, 64-bit\n  Address sizes:         46 bits physical, 48 bits virtual\n"
            "  Byte Order:            Little Endian\nCPU(s):                  4\n  On-line CPU(s) list:   0-3\nVendor ID:               GenuineIntel\n"
            "  Model name:            Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\n    CPU family:          6\n    Model:               85\n"
            "    Thread(s) per core:  2\n    Core(s) per socket:  2\n    Socket(s):           1\n    Stepping:            7\n"
            "    BogoMIPS:            4999.99\nVirtualization features: \n  Hypervisor vendor:     KVM\n  Virtualization type:   full\n")


@command("lsmod")
def lsmod(sh, args, stdin=None):
    return ("Module                  Size  Used by\ntls                   114688  0\nvirtio_net             61440  0\n"
            "net_failover           24576  1 virtio_net\nfailover               16384  1 net_failover\next4                 1024000  1\n"
            "crc16                  16384  1 ext4\nmbcache                16384  1 ext4\njbd2                  180224  1 ext4\n"
            "virtio_blk             20480  3\nvirtio_pci             24576  0\n")


@command("lspci")
def lspci(sh, args, stdin=None):
    return ("00:00.0 Host bridge: Intel Corporation 440FX - 82441FX PMC [Natoma] (rev 02)\n"
            "00:01.0 ISA bridge: Intel Corporation 82371SB PIIX3 ISA [Natoma/Triton II]\n"
            "00:02.0 VGA compatible controller: Cirrus Logic GD 5446\n"
            "00:03.0 Ethernet controller: Red Hat, Inc. Virtio network device\n"
            "00:04.0 SCSI storage controller: Red Hat, Inc. Virtio block device\n")


@command("lsb_release")
def lsb_release(sh, args, stdin=None):
    return "No LSB modules are available.\nDistributor ID:\tUbuntu\nDescription:\tUbuntu 22.04.3 LTS\nRelease:\t22.04\nCodename:\tjammy\n"


@command("dmesg")
def dmesg(sh, args, stdin=None):
    if sh.user != "root":
        return "dmesg: read kernel buffer failed: Operation not permitted\n"
    return (f"[    0.000000] Linux version {KERNEL} (buildd@lcy02-amd64-045) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0) {KVER}\n"
            f"[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz-{KERNEL} root=UUID=3f1a2b4c-5d6e-7f80-91a2-b3c4d5e6f708 ro console=tty1 console=ttyS0\n"
            "[    0.000000] KERNEL supported cpus:\n[    0.000000]   Intel GenuineIntel\n[    0.000000]   AMD AuthenticAMD\n"
            "[    0.000000] BIOS-provided physical RAM map:\n[    0.000000] BIOS-e820: [mem 0x0000000000000000-0x000000000009fbff] usable\n"
            "[    1.204531] virtio_net virtio0 eth0: renamed from ens3\n"
            "[    2.118836] EXT4-fs (vda1): mounted filesystem with ordered data mode. Opts: (null). Quota mode: none.\n")


@command("journalctl")
def journalctl(sh, args, stdin=None):
    now = datetime.now()
    return (f"-- Journal begins at {sh.fs.boot_time - timedelta(days=30):%a %Y-%m-%d %H:%M:%S} UTC, ends at {now:%a %Y-%m-%d %H:%M:%S} UTC. --\n"
            + join([f"{now - timedelta(minutes=i * 7):%b %d %H:%M:%S} {sh.host} systemd[1]: Started Session {4800 + i} of User root." for i in range(9, 0, -1)]))


@command("date")
def date(sh, args, stdin=None):
    if args and args[0].startswith("+"):
        fmt = args[0][1:].replace("%F", "%Y-%m-%d").replace("%T", "%H:%M:%S")
        try:
            return datetime.now().strftime(fmt) + "\n"
        except ValueError:
            return ""
    return datetime.now().strftime("%a %b %d %I:%M:%S %p UTC %Y\n")


@command("cal")
def cal(sh, args, stdin=None):
    return calendar.month(datetime.now().year, datetime.now().month)


@command("sleep", "true", "false", "test", "[", ":", "jobs", "bg", "fg", "disown", "chroot", "ulimit", "timeout", "nice", "ionice")
def noop(sh, args, stdin=None):
    return ""


@command("getconf")
def getconf(sh, args, stdin=None):
    return "64\n"


@command("yes")
def yes(sh, args, stdin=None):
    return ((args[0] if args else "y") + "\n") * 20


@command("seq")
def seq(sh, args, stdin=None):
    nums = [int(a) for a in args if a.lstrip("-").isdigit()]
    if not nums:
        return ""
    lo, hi = (1, nums[0]) if len(nums) == 1 else (nums[0], nums[-1])
    return join([str(i) for i in range(lo, hi + 1)][:1000])


# ------------------------------------------------------------- privilege
@command("sudo")
def sudo(sh, args, stdin=None):
    if not args or args[0] in ("-i", "-s", "su"):
        return "" if sh.user == "root" else f"[sudo] password for {sh.user}: \nSorry, try again.\nsudo: 3 incorrect password attempts\n"
    if sh.user == "root":
        return sh.run_statement(" ".join(args))[0]
    return f"{sh.user} is not in the sudoers file.  This incident will be reported.\n"


@command("su")
def su(sh, args, stdin=None):
    return "" if sh.user == "root" else "Password: \nsu: Authentication failure\n"


@command("passwd")
def passwd(sh, args, stdin=None):
    target = args[0] if args and not args[0].startswith("-") else sh.user
    if sh.user != "root" and target != sh.user:
        return "passwd: You may not view or modify password information for other users.\n"
    return f"New password: \nRetype new password: \npasswd: password updated successfully\n"


@command("pkexec", "doas")
def pkexec(sh, args, stdin=None):
    return f"-bash: {sh.current_cmd}: command not found\n"


@command("useradd", "adduser")
def useradd(sh, args, stdin=None):
    name = next((a for a in args if not a.startswith("-")), None)
    if sh.user != "root":
        return "useradd: Permission denied.\nuseradd: cannot lock /etc/passwd; try again later.\n"
    if not name:
        return "Usage: useradd [options] LOGIN\n"
    if f"\n{name}:" in "\n" + sh.fs.read("/etc/passwd"):
        return f"useradd: user '{name}' already exists\n"
    uid = 1000 + sh.fs.read("/etc/passwd").count(":/home/")
    sh.fs.write("/etc/passwd", f"{name}:x:{uid}:{uid}::/home/{name}:/bin/sh\n", append=True)
    sh.fs.write("/etc/shadow", f"{name}:!:19680:0:99999:7:::\n", append=True)
    if "-m" in args:
        sh.fs.mkdir(f"/home/{name}", owner=name)
    return ""


@command("usermod", "userdel", "groupadd", "gpasswd")
def usermod(sh, args, stdin=None):
    return "" if sh.user == "root" else f"{sh.current_cmd}: Permission denied.\n"


@command("crontab")
def crontab(sh, args, stdin=None):
    if "-l" in args:
        node = sh.fs.get(f"/var/spool/cron/crontabs/{sh.user}")
        if node is None:
            return f"no crontab for {sh.user}\n"
        return node.content
    if "-r" in args:
        return ""
    if "-e" in args:
        return "Error opening terminal: unknown.\n"
    # `crontab -` or `crontab file`: install
    content = stdin if stdin is not None else (sh.fs.read(args[-1]) if args and sh.fs.exists(args[-1]) else "")
    sh.fs.mkdir("/var/spool/cron/crontabs", parents=True, owner="root")
    sh.fs.write(f"/var/spool/cron/crontabs/{sh.user}", content or "")
    return ""


@command("systemctl")
def systemctl(sh, args, stdin=None):
    sub = args[0] if args else "list-units"
    unit = next((a for a in args[1:] if not a.startswith("-")), "")
    if sub == "status":
        if not unit:
            return f"● {sh.host}\n    State: running\n     Jobs: 0 queued\n   Failed: 0 units\n    Since: {sh.fs.boot_time:%a %Y-%m-%d %H:%M:%S} UTC\n"
        svc = unit.replace(".service", "")
        pid = {"ssh": 812, "sshd": 812, "nginx": 901, "mysql": 1104, "cron": 650, "rsyslog": 655}.get(svc)
        if pid is None:
            return f"Unit {unit}.service could not be found.\n"
        return (f"● {svc}.service - {svc}\n     Loaded: loaded (/lib/systemd/system/{svc}.service; enabled; vendor preset: enabled)\n"
                f"     Active: active (running) since {sh.fs.boot_time:%a %Y-%m-%d %H:%M:%S} UTC; {(datetime.now() - sh.fs.boot_time).days} days ago\n"
                f"   Main PID: {pid} ({svc})\n      Tasks: 2 (limit: 9389)\n     Memory: 6.1M\n        CPU: 1.204s\n     CGroup: /system.slice/{svc}.service\n")
    if sub in ("start", "stop", "restart", "reload", "enable", "disable", "daemon-reload", "mask", "unmask"):
        if sh.user != "root":
            return f"Failed to {sub} {unit}: Access denied\nSee system logs and 'systemctl status {unit}' for details.\n"
        if sub == "enable" and unit:
            return f"Created symlink /etc/systemd/system/multi-user.target.wants/{unit} → /lib/systemd/system/{unit}.\n"
        return ""
    if sub.startswith("list") or sub == "":
        return ("  UNIT                       LOAD   ACTIVE SUB     DESCRIPTION\n"
                "  cron.service               loaded active running Regular background program processing daemon\n"
                "  mysql.service              loaded active running MySQL Community Server\n"
                "  nginx.service              loaded active running A high performance web server and a reverse proxy server\n"
                "  rsyslog.service            loaded active running System Logging Service\n"
                "  ssh.service                loaded active running OpenBSD Secure Shell server\n"
                "  systemd-journald.service   loaded active running Journal Service\n"
                "  systemd-logind.service     loaded active running User Login Management\n")
    return ""


@command("service")
def service(sh, args, stdin=None):
    if len(args) >= 2:
        return systemctl(sh, [args[1], args[0]], None)
    if "--status-all" in args:
        return " [ + ]  cron\n [ + ]  mysql\n [ + ]  nginx\n [ + ]  rsyslog\n [ + ]  ssh\n [ - ]  ufw\n"
    return "Usage: service < option > | --status-all | [ service_name [ command | --full-restart ] ]\n"


@command("apt", "apt-get")
def apt(sh, args, stdin=None):
    sub = args[0] if args else ""
    if sh.user != "root":
        return "E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)\nE: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), are you root?\n"
    if sub == "update":
        return ("Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease\nGet:2 http://archive.ubuntu.com/ubuntu jammy-updates InRelease [119 kB]\n"
                "Get:3 http://security.ubuntu.com/ubuntu jammy-security InRelease [110 kB]\nFetched 229 kB in 1s (201 kB/s)\n"
                "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n"
                "12 packages can be upgraded. Run 'apt list --upgradable' to see them.\n")
    if sub == "install":
        pkgs = [a for a in args[1:] if not a.startswith("-")]
        if not pkgs:
            return "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n0 upgraded, 0 newly installed, 0 to remove and 12 not upgraded.\n"
        out = "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n"
        for p in pkgs:
            sh.fs.write(f"/usr/bin/{p}", "", executable=True, size_override=sh.rng.randint(20000, 900000))
        return out + f"The following NEW packages will be installed:\n  {' '.join(pkgs)}\n0 upgraded, {len(pkgs)} newly installed, 0 to remove and 12 not upgraded.\n" \
            + "".join(f"Get:{i+1} http://archive.ubuntu.com/ubuntu jammy/main amd64 {p} amd64 [{sh.rng.randint(40, 900)} kB]\n" for i, p in enumerate(pkgs)) \
            + "".join(f"Selecting previously unselected package {p}.\nUnpacking {p} ...\nSetting up {p} ...\n" for p in pkgs) \
            + "Processing triggers for man-db (2.10.2-1) ...\n"
    if sub in ("upgrade", "dist-upgrade", "full-upgrade"):
        return "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\nCalculating upgrade... Done\n0 upgraded, 0 newly installed, 0 to remove and 12 not upgraded.\n"
    if sub in ("remove", "purge", "autoremove", "clean", "autoclean"):
        return "Reading package lists... Done\nBuilding dependency tree... Done\nReading state information... Done\n0 upgraded, 0 newly installed, 0 to remove and 12 not upgraded.\n"
    if sub == "list":
        return "Listing... Done\ncurl/jammy-updates,now 7.81.0-1ubuntu1.15 amd64 [installed]\nnginx/jammy-updates,now 1.18.0-6ubuntu14.4 amd64 [installed]\nopenssh-server/jammy-updates,now 1:8.9p1-3ubuntu0.4 amd64 [installed]\n"
    return "apt 2.4.11 (amd64)\nUsage: apt [options] command\n\napt is a commandline package manager and provides commands for\nsearching and managing as well as querying information about packages.\n"


@command("yum", "dnf", "pacman", "apk", "zypper")
def yum(sh, args, stdin=None):
    return f"-bash: {sh.current_cmd}: command not found\n"


@command("dpkg")
def dpkg(sh, args, stdin=None):
    if "-l" in args:
        return ("Desired=Unknown/Install/Remove/Purge/Hold\n| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n"
                "||/ Name                 Version                  Architecture Description\n"
                "ii  bash                 5.1-6ubuntu1             amd64        GNU Bourne Again SHell\n"
                "ii  curl                 7.81.0-1ubuntu1.15       amd64        command line tool for transferring data with URL syntax\n"
                "ii  nginx                1.18.0-6ubuntu14.4       amd64        small, powerful, scalable web/proxy server\n"
                "ii  openssh-server       1:8.9p1-3ubuntu0.4       amd64        secure shell (SSH) server, for secure access from remote machines\n"
                "ii  mysql-server         8.0.35-0ubuntu0.22.04.1  amd64        MySQL database server (metapackage depending on the latest version)\n")
    return "dpkg: error: need an action option\n\nType dpkg --help for help about installing and deinstalling packages;\n"


@command("python", "python3", "perl", "php", "ruby", "node")
def interpreter(sh, args, stdin=None):
    name = sh.current_cmd or "python3"
    if name == "python":
        return "-bash: python: command not found\n"
    if name in ("php", "ruby", "node"):
        return f"-bash: {name}: command not found\n"
    if "-c" in args or "-e" in args or stdin is not None:
        return ""
    if "--version" in args or "-V" in args:
        return "Python 3.10.12\n" if name == "python3" else "This is perl 5, version 34, subversion 0 (v5.34.0) built for x86_64-linux-gnu-thread-multi\n"
    script = next((a for a in args if not a.startswith("-")), None)
    if script:
        if not sh.fs.exists(script):
            return f"{name}: can't open file '{sh.fs.resolve(script)}': [Errno 2] No such file or directory\n"
        return ""
    return ""  # bare interpreter: pretend the REPL was opened and closed


@command("gcc", "cc", "g++", "make", "cmake")
def gcc(sh, args, stdin=None):
    name = sh.current_cmd or "gcc"
    if name in ("make", "cmake"):
        return f"{name}: *** No targets specified and no makefile found.  Stop.\n"
    src = next((a for a in args if a.endswith(".c") or a.endswith(".cpp")), None)
    if src and not sh.fs.exists(src):
        return f"{name}: error: {src}: No such file or directory\n{name}: fatal error: no input files\ncompilation terminated.\n"
    out = args[args.index("-o") + 1] if "-o" in args and args.index("-o") + 1 < len(args) else "a.out"
    sh.fs.write(out, "", executable=True, size_override=16696)
    return ""


@command("busybox")
def busybox(sh, args, stdin=None):
    if not args:
        return ("BusyBox v1.30.1 (Ubuntu 1:1.30.1-7ubuntu3) multi-call binary.\nBusyBox is copyrighted by many authors between 1998-2015.\n"
                "Licensed under GPLv2. See source distribution for detailed\ncopyright notices.\n\nUsage: busybox [function [arguments]...]\n")
    return sh.run_statement(" ".join(args))[0]


@command("nohup", "setsid")
def nohup(sh, args, stdin=None):
    name = sh.current_cmd
    if not args:
        return f"{name}: missing operand\nTry '{name} --help' for more information.\n"
    sh.run_statement(" ".join(args))
    return "nohup: ignoring input and appending output to 'nohup.out'\n" if name == "nohup" else ""


@command("reboot", "shutdown", "poweroff", "halt", "init")
def reboot(sh, args, stdin=None):
    if sh.user != "root":
        return "Failed to set wall message, ignoring: Interactive authentication required.\nFailed to reboot system via logind: Interactive authentication required.\n"
    raise ExitSession()


@command("sh", "bash", "dash", "zsh")
def subshell(sh, args, stdin=None):
    """`sh -c CMD` runs CMD; `sh script` runs the script; piped-in text is "run" silently
    (we cannot fetch the real payload, and a dropper expects no output)."""
    if "-c" in args and args.index("-c") + 1 < len(args):
        return sh.run_statement(args[args.index("-c") + 1])[0]
    script = next((a for a in args if not a.startswith("-")), None)
    if script:
        node = sh.fs.get(script)
        if node is None:
            return f"{sh.current_cmd}: 0: cannot open {script}: No such file\n"
        return sh.run_script(node)
    return ""
