"""Command classifier: maps a shell line to one of the MDP command categories.

See docs/02-mdp-formulation.md, section 2. Rule-based and deterministic so that every
RL decision can be explained on the dashboard.
"""
from __future__ import annotations

import re

CATEGORIES: tuple[str, ...] = (
    "recon", "fs_browse", "cred_access", "download", "execute",
    "persist", "privesc", "cleanup", "benign", "unknown",
)

# Intel value v(kappa) of observing a command of each category.
INTEL_VALUE: dict[str, int] = {
    "recon": 1, "fs_browse": 1, "cred_access": 3, "download": 4, "execute": 4,
    "persist": 5, "privesc": 3, "cleanup": 4, "benign": 0, "unknown": 1,
}

PHASES: tuple[str, ...] = ("early", "mid", "late")


def phase_for(command_index: int) -> str:
    """Session phase from the 1-based index of the command within the session."""
    if command_index <= 3:
        return "early"
    if command_index <= 10:
        return "mid"
    return "late"


# Ordered rules; first match wins, so intent-revealing categories come first.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("cleanup", re.compile(
        r"history\s+-c|unset\s+HISTFILE|HISTFILE=|HISTSIZE=0|shred\b|truncate\b|"
        r"rm\s+(-\S+\s+)*(/var/log|~?/?\.bash_history)|>\s*/var/log|cat\s+/dev/null\s*>", re.I)),
    ("persist", re.compile(
        r"crontab(?!\s+-l\b)|authorized_keys|useradd|adduser|usermod|systemctl\s+(enable|daemon-reload)|"
        r"rc\.local|/etc/init\.d|update-rc\.d|\.bashrc|\.profile|/etc/systemd|setsid\b|disown\b", re.I)),
    ("privesc", re.compile(
        r"^(sudo\s*(-i|-s|su)?\s*$|su\b|passwd\b|pkexec\b|doas\b|chmod\s+[ug]\+s|chmod\s+[0-7]?[4267][0-7]{3}\b)", re.I)),
    ("download", re.compile(
        r"^(wget|curl|tftp|ftp|scp|sftp|git\s+clone|pip3?\s+install|rsync)\b|\b(wget|curl)\s", re.I)),
    ("execute", re.compile(
        r"^(chmod\s+(\+x|a\+x|u\+x|[0-7]*7[0-7]*)|\./\S+|sh\s|bash\s|python\d?(\s|$)|perl\s|php\s|gcc\s|"
        r"nc\b|ncat\b|netcat\b|busybox\b|socat\b|nohup\s|base64\s+-d)", re.I)),
    ("cred_access", re.compile(
        r"/etc/shadow|/etc/passwd|/etc/sudoers|id_rsa|id_ed25519|id_dsa|\.ssh/|\.bash_history|\.env\b|"
        r"\bpassword|credentials|secret|\.aws|\.netrc|\.git-credentials|wp-config|\.my\.cnf|\.pgpass|"
        r"mysql\b.*\s-p|/etc/ssh/ssh_host", re.I)),
    ("recon", re.compile(
        r"^(uname|id|whoami|hostname|uptime|w|who|last|lastlog|ps|top|htop|free|df|du|lscpu|nproc|lsblk|"
        r"cat\s+/proc|ifconfig|ip\s|netstat|ss|arp|route|env|printenv|dmesg|lsb_release|lsmod|lspci|"
        r"cat\s+/etc/(os-release|issue|hostname|hosts|resolv\.conf|crontab|fstab)|mount|lsof|which|whereis|"
        r"dpkg|rpm|apt|yum|docker|systemctl\s+(status|list)|service\s+\S+\s+status|getconf|ulimit|date|"
        r"cat\s+/sys|nvidia-smi|crontab\s+-l)\b", re.I)),
    ("fs_browse", re.compile(
        r"^(ls|ll|la|cd|pwd|cat|find|locate|head|tail|less|more|file|stat|tree|grep|egrep|wc|mkdir|touch|cp|mv|"
        r"rm|rmdir|ln|vi|vim|nano|tar|gzip|gunzip|unzip|zip|cut|sort|uniq|awk|sed|strings|md5sum|sha256sum)\b", re.I)),
    ("benign", re.compile(
        r"^(echo|clear|help|cal|true|false|exit|logout|sleep|alias|set|export|unset|type|man|reset|:)\b", re.I)),
]

_SUDO_PREFIX = re.compile(r"^sudo\s+(?:-\S+\s+)*", re.I)


def classify(command: str) -> str:
    """Return the category of a single shell command."""
    line = command.strip()
    if not line:
        return "benign"
    # `sudo <cmd>` is classified by the inner command; bare `sudo` / `sudo -i` / `su` is privesc.
    m = _SUDO_PREFIX.match(line)
    if m and m.end() < len(line) and not re.match(r"^(-i|-s|su)\b", line[m.end():]):
        return classify(line[m.end():])
    for cat, pat in _RULES:
        if pat.search(line):
            return cat
    return "unknown"


def classify_line(line: str) -> str:
    """Classify an input line that may chain commands with ; && || or |.

    The line takes the highest-value category among its parts, since that is the
    intent the attacker revealed.
    """
    parts = [p for p in re.split(r"\s*(?:;|&&|\|\||\|)\s*", line) if p.strip()]
    if not parts:
        return "benign"
    return max((classify(p) for p in parts), key=lambda c: (INTEL_VALUE[c], c != "unknown"))
