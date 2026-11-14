import pytest

from honeypot.fakefs import DECOY_FILES, FakeFileSystem


@pytest.fixture
def fs():
    return FakeFileSystem("root", "testhost", seed=1)


def test_ubuntu_layout_exists(fs):
    for p in ("/etc/passwd", "/etc/shadow", "/etc/os-release", "/root/.bash_history", "/home/deploy", "/proc/cpuinfo",
              "/usr/bin/ls", "/var/log/auth.log"):
        assert fs.exists(p), p
    assert fs.is_dir("/etc") and not fs.is_dir("/etc/passwd")


def test_home_and_prompt_for_non_root_user():
    fs = FakeFileSystem("admin", "h", seed=2)
    assert fs.home == "/home/admin" and fs.cwd == "/home/admin"
    assert "admin:x:1002:" in fs.read("/etc/passwd")
    assert fs.display_cwd() == "~"
    fs.chdir("/etc")
    assert fs.display_cwd() == "/etc"


def test_path_resolution(fs):
    fs.chdir("/var/log")
    assert fs.resolve("../www/../log/./syslog") == "/var/log/syslog"
    assert fs.resolve("~/.ssh") == "/root/.ssh"
    assert fs.resolve("/../..") == "/"


def test_write_read_append_remove(fs):
    fs.write("/tmp/x.sh", "#!/bin/sh\n")
    fs.write("/tmp/x.sh", "echo hi\n", append=True)
    assert fs.read("/tmp/x.sh") == "#!/bin/sh\necho hi\n"
    with pytest.raises(FileNotFoundError):
        fs.write("/nope/x", "")
    with pytest.raises(IsADirectoryError):
        fs.read("/tmp")
    fs.remove("/tmp/x.sh")
    assert not fs.exists("/tmp/x.sh")
    with pytest.raises(PermissionError):
        fs.remove("/")


def test_permission_model_for_non_root():
    fs = FakeFileSystem("deploy", "h", seed=3)
    with pytest.raises(PermissionError):
        fs.read("/root/.bash_history")
    with pytest.raises(PermissionError):
        fs.listdir("/root")
    assert fs.read("/home/deploy/.bash_history")
    assert fs.get("/etc/passwd").owner == "root"
    fs.write("/tmp/mine", "x")
    assert fs.get("/tmp/mine").owner == "deploy"


def test_sessions_are_isolated():
    a, b = FakeFileSystem(seed=1), FakeFileSystem(seed=1)
    a.write("/tmp/evil", "x")
    assert not b.exists("/tmp/evil")


def test_decoys_are_placeholders_and_idempotent(fs):
    assert not fs.decoys_planted
    planted = fs.plant_decoys()
    assert set(planted) == set(DECOY_FILES)
    assert fs.plant_decoys() == []
    for p in DECOY_FILES:
        assert "<decoy:" in fs.read(p)
    assert "mysql -h db-primary" in fs.read("/root/.bash_history")


def test_walk_covers_tree(fs):
    paths = [p for p, _ in fs.walk("/etc")]
    assert "/etc" in paths and "/etc/ssh/sshd_config" in paths
