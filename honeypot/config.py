"""Runtime settings, read from environment variables with sensible defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class RewardWeights:
    """Weights of the reward function (docs/02-mdp-formulation.md, section 5)."""
    engagement: float = 1.0    # w_e: each further command is worth this
    value: float = 0.5         # w_v: multiplier on the intel value of the next command
    cost: float = 0.02         # w_c: multiplier on the friction cost (seconds) of an action
    block_bonus: float = 2.0   # w_b: bonus for a justified BLOCK


@dataclass(frozen=True)
class RLParams:
    policy: str = "qlearn"          # qlearn | sarsa | bandit | random | static
    alpha: float = 0.1              # learning rate (alpha_schedule="constant")
    # visit: alpha_n = max(alpha_min, n^-omega) per (state, action). Default since Phase 5: with
    # constant alpha the greedy policy was noise-driven and lost to the static honeypot
    # (docs/04-evaluation.md). Set RL_ALPHA_MIN > 0 to keep tracking a drifting population.
    alpha_schedule: str = "visit"   # visit | constant
    alpha_omega: float = 0.7
    alpha_min: float = 0.0
    gamma: float = 0.9              # discount factor
    epsilon0: float = 0.3           # initial exploration rate
    epsilon_min: float = 0.05
    epsilon_decay: float = 0.995    # multiplicative, per episode
    warm_start_allow: float = 0.5   # initial Q(s, ALLOW)


@dataclass(frozen=True)
class Settings:
    # Localhost by default so a dev run never exposes the honeypot by accident.
    # The container sets HONEYPOT_HOST=0.0.0.0; exposure is then decided by the port mapping.
    host: str = "127.0.0.1"
    port: int = 2222
    hostname: str = "ubuntu-srv01"
    host_key_path: str = "data/ssh_host_key"
    server_version: str = "OpenSSH_8.9p1 Ubuntu-3ubuntu0.4"

    # Login policy: the N-th password attempt from a source IP succeeds, N ~ U{min..max}.
    login_attempts_min: int = 1
    login_attempts_max: int = 3

    # Session limits
    max_commands: int = 200
    max_session_seconds: int = 1800
    idle_timeout_seconds: int = 300

    # Event transport; None means JSON lines on stdout.
    redis_url: str | None = None
    redis_stream: str = "honeypot:events"

    # RL
    qtable_path: str = "data/qtable.json"
    rl: RLParams = field(default_factory=RLParams)
    reward: RewardWeights = field(default_factory=RewardWeights)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=_env("HONEYPOT_HOST", "127.0.0.1"),
            port=int(_env("HONEYPOT_PORT", "2222")),
            hostname=_env("HONEYPOT_HOSTNAME", "ubuntu-srv01"),
            host_key_path=_env("HONEYPOT_HOST_KEY", "data/ssh_host_key"),
            login_attempts_min=int(_env("LOGIN_ATTEMPTS_MIN", "1")),
            login_attempts_max=int(_env("LOGIN_ATTEMPTS_MAX", "3")),
            max_commands=int(_env("MAX_COMMANDS", "200")),
            max_session_seconds=int(_env("MAX_SESSION_SECONDS", "1800")),
            idle_timeout_seconds=int(_env("IDLE_TIMEOUT_SECONDS", "300")),
            redis_url=os.getenv("REDIS_URL") or None,
            redis_stream=_env("REDIS_STREAM", "honeypot:events"),
            qtable_path=_env("QTABLE_PATH", "data/qtable.json"),
            rl=RLParams(
                policy=_env("RL_POLICY", "qlearn"),
                alpha=float(_env("RL_ALPHA", "0.1")),
                alpha_schedule=_env("RL_ALPHA_SCHEDULE", "visit"),
                alpha_omega=float(_env("RL_ALPHA_OMEGA", "0.7")),
                alpha_min=float(_env("RL_ALPHA_MIN", "0.0")),
                gamma=float(_env("RL_GAMMA", "0.9")),
                epsilon0=float(_env("RL_EPSILON0", "0.3")),
                epsilon_min=float(_env("RL_EPSILON_MIN", "0.05")),
                epsilon_decay=float(_env("RL_EPSILON_DECAY", "0.995")),
            ),
            reward=RewardWeights(
                engagement=float(_env("REWARD_W_ENGAGEMENT", "1.0")),
                value=float(_env("REWARD_W_VALUE", "0.5")),
                cost=float(_env("REWARD_W_COST", "0.02")),
                block_bonus=float(_env("REWARD_W_BLOCK", "2.0")),
            ),
        )

    def with_overrides(self, **kwargs) -> "Settings":
        return replace(self, **kwargs)
