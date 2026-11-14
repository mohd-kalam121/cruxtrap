"""In-memory fake Ubuntu filesystem. One instance per attacker session.

Nothing here touches the host filesystem. Decoy ("honeytoken") files are planted on
demand by the FAKE action; their contents are obvious placeholders of the form
`<decoy:name>` so that the repository never contains anything resembling a real
secret. What the experiments measure is whether the attacker *reads* them.
"""
from __future__ import annotations

import posixpath
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Node:
    name: str
    is_dir: bool
    content: str = ""
    mode: str = ""
    owner: str = "root"
    group: str = "root"
    mtime: datetime = field(default_factory=datetime.now)
    children: dict[str, "Node"] = field(default_factory=dict)
    size_override: int | None = None
    executable: bool = False

    @property
    def size(self) -> int:
        if self.size_override is not None:
            return self.size_override
        return 4096 if self.is_dir else len(self.content.encode())

    @property
    def perms(self) -> str:
        if self.mode:
            return self.mode
        if self.is_dir:
            return "drwxr-xr-x"
        return "-rwxr-xr-x" if self.executable else "-rw-r--r--"


BINARIES = (
    "bash sh ls cat cp mv rm mkdir rmdir chmod chown echo grep ps kill ping netstat ss ip mount umount "
    "dd df dmesg hostname login su sleep sync tar gzip gunzip uname date touch sed nano vi vim wget curl "
    "python3 perl find head tail less more which whoami id env sudo apt apt-get dpkg systemctl journalctl "
    "crontab top free uptime w who last lscpu nproc base64 md5sum sha256sum awk cut sort uniq wc xargs tee "
    "scp ssh ssh-keygen git gcc make nc mysql busybox chattr file stat"
).split()
SBINARIES = "sshd cron rsyslogd nginx mysqld useradd userdel usermod iptables ufw service reboot shutdown init ifconfig route visudo".split()

DECOY_FILES: dict[str, str] = {
    # path: content. Placeholders only; see module docstring.
    "/root/backup_credentials.txt": "# production access\nmysql db-primary root <decoy:mysql-root>\nvpn vpn.internal admin <decoy:vpn-admin>\n",
    "/home/deploy/.env": "APP_ENV=production\nDB_HOST=db-primary\nDB_USERNAME=app\nDB_PASSWORD=<decoy:db-app>\nAWS_ACCESS_KEY_ID=<decoy:aws-id>\nAWS_SECRET_ACCESS_KEY=<decoy:aws-secret>\n",
    "/root/.my.cnf": "[client]\nuser=root\npassword=<decoy:mysql-root>\nhost=db-primary\n",
    "/var/www/html/wp-config.php": "<?php\ndefine( 'DB_NAME', 'wordpress' );\ndefine( 'DB_USER', 'wpuser' );\ndefine( 'DB_PASSWORD', '<decoy:wp-db>' );\ndefine( 'DB_HOST', 'db-primary' );\n",
}
DECOY_HISTORY_LINES = [
    "mysql -h db-primary -u root -p production",
    "scp /var/backups/prod-latest.sql.gz backup@10.0.12.50:/srv/backups/",
]


class FakeFileSystem:
    def __init__(self, username: str = "root", hostname: str = "ubuntu-srv01", seed: int | None = None):
        self.username = username
        self.hostname = hostname
        self.rng = random.Random(seed)
        self.boot_time = datetime.now() - timedelta(days=self.rng.randint(11, 97), hours=self.rng.randint(0, 23))
        self.home = "/root" if username == "root" else f"/home/{username}"
        self.root = Node("", True)
        self.cwd = self.home
        self._decoys_planted = False
        self._building = True
        self._build()
        self._building = False

    # ---------------------------------------------------------------- paths
    def resolve(self, path: str, cwd: str | None = None) -> str:
        cwd = cwd or self.cwd
        if not path:
            return cwd
        if path == "~" or path.startswith("~/"):
            path = self.home + path[1:]
        if not path.startswith("/"):
            path = posixpath.join(cwd, path)
        norm = posixpath.normpath(path)
        return "/" if norm in ("", ".") else norm

    def display_cwd(self) -> str:
        if self.cwd == self.home:
            return "~"
        if self.cwd.startswith(self.home + "/"):
            return "~" + self.cwd[len(self.home):]
        return self.cwd

    def get(self, path: str) -> Node | None:
        node = self.root
        for part in [p for p in self.resolve(path).split("/") if p]:
            if not node.is_dir or part not in node.children:
                return None
            node = node.children[part]
        return node

    def exists(self, path: str) -> bool:
        return self.get(path) is not None

    def is_dir(self, path: str) -> bool:
        n = self.get(path)
        return n is not None and n.is_dir

    # ------------------------------------------------------------- mutation
    def mkdir(self, path: str, parents: bool = False, owner: str | None = None) -> Node:
        node = self.root
        parts = [p for p in self.resolve(path).split("/") if p]
        for i, part in enumerate(parts):
            if part not in node.children:
                if i < len(parts) - 1 and not parents:
                    raise FileNotFoundError(path)
                o = owner or self.username
                node.children[part] = Node(part, True, owner=o, group=o)
            node = node.children[part]
            if not node.is_dir:
                raise NotADirectoryError(path)
        return node

    def write(self, path: str, content: str, append: bool = False, **attrs) -> Node:
        abs_path = self.resolve(path)
        parent_path, name = posixpath.split(abs_path)
        parent = self.get(parent_path)
        if parent is None or not parent.is_dir:
            raise FileNotFoundError(path)
        node = parent.children.get(name)
        if node is None:
            o = "root" if self._building else self.username
            node = Node(name, False, owner=o, group=o)
            parent.children[name] = node
        elif node.is_dir:
            raise IsADirectoryError(path)
        node.content = node.content + content if append else content
        node.mtime = datetime.now()
        for k, v in attrs.items():
            setattr(node, k, v)
        return node

    def touch(self, path: str) -> Node:
        node = self.get(path)
        if node is None:
            return self.write(path, "")
        node.mtime = datetime.now()
        return node

    def read(self, path: str) -> str:
        node = self.get(path)
        if node is None:
            raise FileNotFoundError(path)
        if node.is_dir:
            raise IsADirectoryError(path)
        if node.mode.startswith("-rw-------") and node.owner != self.username and self.username != "root":
            raise PermissionError(path)
        return node.content

    def listdir(self, path: str = ".") -> list[Node]:
        node = self.get(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            return [node]
        if node.mode.startswith("drwx------") and node.owner != self.username and self.username != "root":
            raise PermissionError(path)
        return sorted(node.children.values(), key=lambda n: n.name)

    def remove(self, path: str, recursive: bool = False) -> None:
        abs_path = self.resolve(path)
        if abs_path == "/":
            raise PermissionError(path)
        parent_path, name = posixpath.split(abs_path)
        parent = self.get(parent_path)
        if parent is None or name not in parent.children:
            raise FileNotFoundError(path)
        node = parent.children[name]
        if node.is_dir and node.children and not recursive:
            raise IsADirectoryError(path)
        del parent.children[name]

    def copy(self, src: str, dst: str) -> None:
        node = self.get(src)
        if node is None:
            raise FileNotFoundError(src)
        if self.is_dir(dst):
            dst = posixpath.join(dst, node.name)
        self.write(dst, node.content, executable=node.executable)

    def move(self, src: str, dst: str) -> None:
        self.copy(src, dst)
        self.remove(src, recursive=True)

    def chdir(self, path: str) -> None:
        target = self.resolve(path)
        node = self.get(target)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            raise NotADirectoryError(path)
        self.cwd = target

    def walk(self, path: str = "/"):
        """Yield (absolute_path, node) depth-first, including the start node."""
        start = self.resolve(path)
        node = self.get(start)
        if node is None:
            return
        stack = [(start, node)]
        while stack:
            p, n = stack.pop()
            yield p, n
            if n.is_dir:
                for child in sorted(n.children.values(), key=lambda c: c.name, reverse=True):
                    stack.append(("/" + child.name if p == "/" else posixpath.join(p, child.name), child))

    # -------------------------------------------------------------- content
    def _build(self) -> None:
        r = self.rng
        for d in ("bin", "boot", "dev", "etc", "home", "lib", "lib64", "media", "mnt", "opt", "proc",
                  "root", "run", "sbin", "srv", "sys", "tmp", "usr", "var"):
            self.mkdir("/" + d, owner="root")
        for d in ("/etc/ssh", "/etc/cron.d", "/etc/apt", "/etc/nginx", "/etc/mysql", "/etc/systemd/system",
                  "/usr/bin", "/usr/sbin", "/usr/lib", "/usr/local/bin", "/usr/share", "/var/log", "/var/www/html",
                  "/var/lib/mysql", "/var/backups", "/var/tmp", "/opt/scripts", "/root/.ssh", "/home/deploy",
                  "/home/deploy/.ssh", "/home/ubuntu", "/dev/shm", "/proc/net", "/sys/class"):
            self.mkdir(d, parents=True, owner="root")
        self.get("/root").mode = "drwx------"
        self.get("/root/.ssh").mode = "drwx------"
        for p in ("/tmp", "/var/tmp", "/dev/shm"):
            self.get(p).mode = "drwxrwxrwt"
        for p in ("/bin", "/sbin", "/lib", "/lib64"):
            self.get(p).mode = "lrwxrwxrwx"
        for u in ("deploy", "ubuntu"):
            n = self.get(f"/home/{u}")
            n.owner = n.group = u
        users = ["deploy", "ubuntu"]
        if self.username not in ("root", "deploy", "ubuntu"):
            n = self.mkdir(self.home, parents=True, owner=self.username)
            self.mkdir(self.home + "/.ssh", owner=self.username)
            users.append(self.username)

        system_users = [
            ("root", 0, "root", "/root", "/bin/bash"), ("daemon", 1, "daemon", "/usr/sbin", "/usr/sbin/nologin"),
            ("bin", 2, "bin", "/bin", "/usr/sbin/nologin"), ("sys", 3, "sys", "/dev", "/usr/sbin/nologin"),
            ("sync", 4, "sync", "/bin", "/bin/sync"), ("games", 5, "games", "/usr/games", "/usr/sbin/nologin"),
            ("man", 6, "man", "/var/cache/man", "/usr/sbin/nologin"), ("lp", 7, "lp", "/var/spool/lpd", "/usr/sbin/nologin"),
            ("mail", 8, "mail", "/var/mail", "/usr/sbin/nologin"), ("news", 9, "news", "/var/spool/news", "/usr/sbin/nologin"),
            ("www-data", 33, "www-data", "/var/www", "/usr/sbin/nologin"), ("nobody", 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
            ("systemd-network", 100, "systemd Network Management,,,", "/run/systemd", "/usr/sbin/nologin"),
            ("systemd-resolve", 101, "systemd Resolver,,,", "/run/systemd", "/usr/sbin/nologin"),
            ("messagebus", 102, "", "/nonexistent", "/usr/sbin/nologin"), ("sshd", 106, "", "/run/sshd", "/usr/sbin/nologin"),
            ("mysql", 107, "MySQL Server,,,", "/nonexistent", "/bin/false"),
        ]
        passwd = "".join(f"{u}:x:{uid}:{uid if uid < 100 or uid == 65534 else uid + 2}:{g}:{h}:{s}\n" for u, uid, g, h, s in system_users)
        shadow = "".join(f"{u}:{'!' if u == 'root' else '*'}:19674:0:99999:7:::\n" for u, *_ in system_users)
        for i, u in enumerate(users):
            passwd += f"{u}:x:{1000+i}:{1000+i}:{u},,,:/home/{u}:/bin/bash\n"
            shadow += f"{u}:!:19680:0:99999:7:::\n"
        self.write("/etc/passwd", passwd)
        self.write("/etc/shadow", shadow, mode="-rw-r-----", group="shadow")
        self.write("/etc/group", "root:x:0:\ndaemon:x:1:\nbin:x:2:\nsys:x:3:\nadm:x:4:syslog,deploy\ntty:x:5:\n"
                   "sudo:x:27:deploy\nwww-data:x:33:\nshadow:x:42:\nssh:x:115:\nmysql:x:113:\n"
                   + "".join(f"{u}:x:{1000+i}:\n" for i, u in enumerate(users)))
        self.write("/etc/hostname", self.hostname + "\n")
        self.write("/etc/hosts", f"127.0.0.1\tlocalhost\n127.0.1.1\t{self.hostname}\n10.0.12.10\tdb-primary\n"
                   "10.0.12.11\tdb-replica\n\n::1     ip6-localhost ip6-loopback\nfe00::0 ip6-localnet\n"
                   "ff00::0 ip6-mcastprefix\nff02::1 ip6-allnodes\nff02::2 ip6-allrouters\n")
        self.write("/etc/os-release",
                   'PRETTY_NAME="Ubuntu 22.04.3 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"\n'
                   'VERSION="22.04.3 LTS (Jammy Jellyfish)"\nVERSION_CODENAME=jammy\nID=ubuntu\nID_LIKE=debian\n'
                   'HOME_URL="https://www.ubuntu.com/"\nSUPPORT_URL="https://help.ubuntu.com/"\n'
                   'BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"\nUBUNTU_CODENAME=jammy\n')
        self.write("/etc/issue", "Ubuntu 22.04.3 LTS \\n \\l\n\n")
        self.write("/etc/lsb-release", "DISTRIB_ID=Ubuntu\nDISTRIB_RELEASE=22.04\nDISTRIB_CODENAME=jammy\n"
                   'DISTRIB_DESCRIPTION="Ubuntu 22.04.3 LTS"\n')
        self.write("/etc/resolv.conf", "nameserver 127.0.0.53\noptions edns0 trust-ad\nsearch internal.local\n")
        self.write("/etc/fstab", "# /etc/fstab: static file system information.\n"
                   "UUID=3f1a2b4c-5d6e-7f80-91a2-b3c4d5e6f708 / ext4 errors=remount-ro 0 1\n"
                   "UUID=A1B2-C3D4 /boot/efi vfat umask=0077 0 1\n/swapfile none swap sw 0 0\n")
        self.write("/etc/crontab", "SHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin\n\n"
                   "17 *\t* * *\troot    cd / && run-parts --report /etc/cron.hourly\n"
                   "25 6\t* * *\troot\ttest -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )\n"
                   "30 2\t* * *\troot\t/opt/scripts/db_backup.sh >> /var/log/db_backup.log 2>&1\n")
        self.write("/etc/ssh/sshd_config", "Include /etc/ssh/sshd_config.d/*.conf\nPort 22\nPermitRootLogin yes\n"
                   "PasswordAuthentication yes\nKbdInteractiveAuthentication no\nUsePAM yes\nX11Forwarding yes\n"
                   "PrintMotd no\nAcceptEnv LANG LC_*\nSubsystem\tsftp\t/usr/lib/openssh/sftp-server\n")
        self.write("/etc/sudoers", "Defaults\tenv_reset\nDefaults\tmail_badpass\nroot\tALL=(ALL:ALL) ALL\n"
                   "%admin ALL=(ALL) ALL\n%sudo\tALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n", mode="-r--r-----")
        self.write("/etc/nginx/nginx.conf", "user www-data;\nworker_processes auto;\npid /run/nginx.pid;\n"
                   "include /etc/nginx/modules-enabled/*.conf;\n\nevents {\n\tworker_connections 768;\n}\n\n"
                   "http {\n\tsendfile on;\n\tinclude /etc/nginx/mime.types;\n\tinclude /etc/nginx/sites-enabled/*;\n}\n")
        self.write("/etc/mysql/my.cnf", "[client-server]\nsocket = /var/run/mysqld/mysqld.sock\n!includedir /etc/mysql/conf.d/\n")

        self.write("/proc/cpuinfo", "".join(
            f"processor\t: {i}\nvendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 85\n"
            f"model name\t: Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\nstepping\t: 7\ncpu MHz\t\t: 2499.998\n"
            f"cache size\t: 36608 KB\nphysical id\t: 0\nsiblings\t: 4\ncore id\t\t: {i // 2}\ncpu cores\t: 2\n"
            f"flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr "
            f"sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid "
            f"aperfmperf pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c "
            f"rdrand hypervisor lahf_lm abm 3dnowprefetch invpcid_single pti fsgsbase bmi1 avx2 smep bmi2 erms "
            f"invpcid avx512f avx512dq rdseed adx smap clflushopt clwb avx512cd avx512bw avx512vl xsaveopt xsavec "
            f"xgetbv1 xsaves ida arat pku ospke\nbogomips\t: 4999.99\n\n" for i in range(4)))
        self.write("/proc/meminfo", "MemTotal:        8148564 kB\nMemFree:         2991244 kB\nMemAvailable:    6120380 kB\n"
                   "Buffers:          166932 kB\nCached:          3062212 kB\nSwapCached:            0 kB\n"
                   "Active:          2735848 kB\nInactive:        1917944 kB\nSwapTotal:       2097148 kB\n"
                   "SwapFree:        2097148 kB\nDirty:               148 kB\nShmem:             12984 kB\n")
        self.write("/proc/version", "Linux version 5.15.0-91-generic (buildd@lcy02-amd64-045) "
                   "(gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils for Ubuntu) 2.38) "
                   "#101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023\n")
        self.write("/proc/uptime", "")  # rendered dynamically by the shell

        self.write("/var/log/auth.log", "".join(
            f"Nov {12 + i // 40:2d} {(i * 37) % 24:02d}:{(i * 11) % 60:02d}:{(i * 7) % 60:02d} {self.hostname} "
            f"sshd[{2100 + i}]: Failed password for {'root' if i % 3 else 'invalid user admin'} from "
            f"{r.choice(['185.224.128.', '45.155.205.', '103.154.77.', '194.165.16.'])}{r.randint(2, 254)} "
            f"port {r.randint(30000, 65000)} ssh2\n" for i in range(60)), owner="syslog", group="adm", mode="-rw-r-----")
        self.write("/var/log/syslog", "".join(
            f"Nov 1{3 + i // 30} {(i * 13) % 24:02d}:{(i * 17) % 60:02d}:{(i * 23) % 60:02d} {self.hostname} systemd[1]: "
            + r.choice(["Started Daily apt download activities.", "Starting Cleanup of Temporary Directories...",
                        "Finished Cleanup of Temporary Directories.", "Started Session 4821 of User root.",
                        "Starting Daily apt upgrade and clean activities..."]) + "\n"
            for i in range(40)), owner="syslog", group="adm", mode="-rw-r-----")
        self.write("/var/log/db_backup.log", "[2024-11-12 02:30:01] starting backup of production\n"
                   "[2024-11-12 02:31:47] backup complete (412 MB)\n[2024-11-13 02:30:01] starting backup of production\n"
                   "[2024-11-13 02:31:52] backup complete (414 MB)\n")
        for f in ("kern.log", "dpkg.log", "lastlog", "wtmp", "btmp", "faillog"):
            self.write(f"/var/log/{f}", "", size_override=r.randint(2000, 90000))
        self.write("/var/backups/prod-latest.sql.gz", "", size_override=434110464, mode="-rw-r-----")
        self.write("/var/backups/apt.extended_states.0", "", size_override=12931)
        self.write("/var/www/html/index.nginx-debian.html",
                   "<!DOCTYPE html>\n<html>\n<head>\n<title>Welcome to nginx!</title>\n</head>\n<body>\n"
                   "<h1>Welcome to nginx!</h1>\n<p>If you see this page, the nginx web server is successfully installed and\n"
                   "working. Further configuration is required.</p>\n</body>\n</html>\n", owner="www-data", group="www-data")

        bashrc = ("# ~/.bashrc: executed by bash(1) for non-login shells.\n[ -z \"$PS1\" ] && return\n"
                  "HISTSIZE=1000\nHISTFILESIZE=2000\nalias ls='ls --color=auto'\nalias ll='ls -alF'\nalias la='ls -A'\n"
                  "alias l='ls -CF'\nexport PATH=$PATH:/opt/scripts\n")
        profile = ("# ~/.profile: executed by Bourne-compatible login shells.\nif [ \"$BASH\" ]; then\n"
                   "  if [ -f ~/.bashrc ]; then\n    . ~/.bashrc\n  fi\nfi\nmesg n 2> /dev/null || true\n")
        self.write("/root/.bash_history",
                   "apt update && apt upgrade -y\nsystemctl status nginx\ncd /var/www/html\nls -la\n"
                   "vim /etc/nginx/sites-enabled/default\nsystemctl reload nginx\ntail -f /var/log/nginx/access.log\n"
                   "cd /opt/scripts\n./db_backup.sh\nls -la /var/backups\ndf -h\nfree -m\nhtop\ncrontab -e\nexit\n",
                   mode="-rw-------")
        self.write("/root/.bashrc", bashrc)
        self.write("/root/.profile", profile)
        self.write("/root/.ssh/authorized_keys", "", mode="-rw-------")
        self.write("/root/.ssh/known_hosts", "db-primary,10.0.12.10 ssh-ed25519 <host-key-placeholder>\n"
                   "db-replica,10.0.12.11 ssh-ed25519 <host-key-placeholder>\n")
        self.write("/root/.viminfo", "", size_override=r.randint(3000, 15000), mode="-rw-------")
        self.write("/home/deploy/.bash_history", "cd /var/www/html\ngit pull origin main\nsudo systemctl restart nginx\n"
                   "ls -la\ncat .env\nexit\n", owner="deploy", group="deploy", mode="-rw-------")
        self.write("/home/deploy/.bashrc", bashrc, owner="deploy", group="deploy")
        self.write("/home/deploy/.profile", profile, owner="deploy", group="deploy")
        self.write("/home/deploy/.ssh/authorized_keys", "", owner="deploy", group="deploy", mode="-rw-------")
        self.write("/home/ubuntu/.bash_history", "sudo apt update\nsudo apt install -y nginx\nexit\n",
                   owner="ubuntu", group="ubuntu", mode="-rw-------")
        self.write("/opt/scripts/db_backup.sh", "#!/bin/bash\n# Nightly backup of the production database\nset -euo pipefail\n"
                   "DATE=$(date +%Y%m%d)\nmysqldump --defaults-file=/root/.my.cnf production | gzip > /var/backups/prod-$DATE.sql.gz\n"
                   "find /var/backups -name 'prod-*.sql.gz' -mtime +14 -delete\n"
                   "echo \"[$(date '+%F %T')] backup complete\"\n", executable=True)
        self.write("/opt/scripts/rotate_logs.sh", "#!/bin/bash\nfind /var/log -name '*.gz' -mtime +30 -delete\n", executable=True)
        for name, size in (("vmlinuz-5.15.0-91-generic", 11607232), ("initrd.img-5.15.0-91-generic", 112563845),
                           ("config-5.15.0-91-generic", 261917), ("System.map-5.15.0-91-generic", 6126123)):
            self.write(f"/boot/{name}", "", size_override=size)
        for b in BINARIES:
            self.write(f"/usr/bin/{b}", "", size_override=r.randint(14000, 1400000), executable=True)
        for b in SBINARIES:
            self.write(f"/usr/sbin/{b}", "", size_override=r.randint(14000, 900000), executable=True)

        # Make timestamps look lived-in.
        now = datetime.now()
        for p, n in self.walk("/"):
            if p.startswith("/proc") or p.startswith("/sys"):
                n.mtime = now
            else:
                n.mtime = now - timedelta(days=r.randint(1, 400), hours=r.randint(0, 23), minutes=r.randint(0, 59))

    # --------------------------------------------------------------- decoys
    def plant_decoys(self) -> list[str]:
        """Plant honeytoken files. Idempotent; returns the paths planted on this call."""
        if self._decoys_planted:
            return []
        self._decoys_planted = True
        planted: list[str] = []
        for path, content in DECOY_FILES.items():
            owner = "deploy" if path.startswith("/home/deploy") else "www-data" if path.startswith("/var/www") else "root"
            mode = "-rw-------" if owner == "root" else "-rw-r--r--"
            self.write(path, content, owner=owner, group=owner, mode=mode)
            self.get(path).mtime = datetime.now() - timedelta(days=self.rng.randint(3, 60))
            planted.append(path)
        hist = self.read("/root/.bash_history").replace("crontab -e\n", "crontab -e\n" + "".join(l + "\n" for l in DECOY_HISTORY_LINES))
        self.write("/root/.bash_history", hist, mode="-rw-------")
        return planted

    @property
    def decoys_planted(self) -> bool:
        return self._decoys_planted
