"""Response policies: the proposed Q-learning agent and the baselines it is compared to.

All policies share one interface so the honeypot and the simulator can swap them:

    action = policy.choose(state)
    policy.update(state, action, reward, next_state, next_action=None)
    policy.end_episode()

State is the string "category|phase" (docs/02-mdp-formulation.md).
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from dataclasses import asdict
from enum import Enum

from ..classify import INTEL_VALUE
from ..config import RLParams, RewardWeights


class Action(str, Enum):
    ALLOW = "ALLOW"      # faithful emulated output
    DELAY = "DELAY"      # pause 1-4 s, then faithful output
    FAKE = "FAKE"        # decoy output with placeholder honeytokens
    TARPIT = "TARPIT"    # dribble the output over ~10-15 s
    BLOCK = "BLOCK"      # close the connection (terminal)


ACTIONS: tuple[Action, ...] = tuple(Action)

# Expected attacker-time cost chi(a) in seconds (MDP section 3).
ACTION_COST: dict[Action, float] = {
    Action.ALLOW: 0.0, Action.DELAY: 2.5, Action.FAKE: 0.0, Action.TARPIT: 15.0, Action.BLOCK: 0.0,
}

TERMINAL = "__terminal__"


def make_state(category: str, phase: str) -> str:
    return f"{category}|{phase}"


def compute_reward(action: Action, continued: bool, category: str, phase: str,
                   next_category: str | None, w: RewardWeights) -> float:
    """Reward for taking `action` in state (category, phase) given what happened next.

    r = 1[continue] * (w_e + w_v * v(next)) - w_c * chi(a) + w_b * 1[justified block]
    """
    r = -w.cost * ACTION_COST[action]
    if continued and next_category is not None:
        r += w.engagement + w.value * INTEL_VALUE.get(next_category, 1)
    if action is Action.BLOCK and category == "cleanup" and phase == "late":
        r += w.block_bonus
    return r


class Policy:
    """Base class. Non-learning by default."""
    name = "base"

    def __init__(self, params: RLParams | None = None, rng: random.Random | None = None):
        self.params = params or RLParams()
        self.rng = rng or random.Random()
        self.episodes = 0
        self.epsilon = self.params.epsilon0

    def choose(self, state: str) -> Action:
        raise NotImplementedError

    def update(self, state: str, action: Action, reward: float,
               next_state: str | None, next_action: Action | None = None) -> None:
        return None

    def end_episode(self) -> None:
        self.episodes += 1

    def q_values(self, state: str) -> dict[str, float]:
        return {}

    def save(self, path: str) -> None:
        return None

    def load(self, path: str) -> bool:
        return False


class StaticPolicy(Policy):
    """Always ALLOW: a conventional (Cowrie-like) honeypot. The control."""
    name = "static"

    def choose(self, state: str) -> Action:
        return Action.ALLOW


class RandomPolicy(Policy):
    name = "random"

    def choose(self, state: str) -> Action:
        return self.rng.choice(ACTIONS)


class TabularPolicy(Policy):
    """Shared machinery for Q-table based policies: epsilon-greedy, persistence."""

    def __init__(self, params: RLParams | None = None, rng: random.Random | None = None):
        super().__init__(params, rng)
        self.q: dict[str, dict[str, float]] = {}

    def _row(self, state: str) -> dict[str, float]:
        if state not in self.q:
            self.q[state] = {a.value: (self.params.warm_start_allow if a is Action.ALLOW else 0.0) for a in ACTIONS}
        return self.q[state]

    def greedy(self, state: str) -> Action:
        row = self._row(state)
        best = max(row.values())
        # tie-break randomly among the best so early learning is not order-biased
        return Action(self.rng.choice([a for a, v in row.items() if v == best]))

    def choose(self, state: str) -> Action:
        if self.rng.random() < self.epsilon:
            return self.rng.choice(ACTIONS)
        return self.greedy(state)

    def end_episode(self) -> None:
        super().end_episode()
        self.epsilon = max(self.params.epsilon_min, self.epsilon * self.params.epsilon_decay)

    def q_values(self, state: str) -> dict[str, float]:
        return dict(self._row(state))

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {"policy": self.name, "episodes": self.episodes, "epsilon": self.epsilon,
                   "params": asdict(self.params), "q": self.q}
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=1)
        os.replace(tmp, path)  # atomic on POSIX and Windows

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path) as f:
            payload = json.load(f)
        self.q = payload.get("q", {})
        self.episodes = int(payload.get("episodes", 0))
        self.epsilon = float(payload.get("epsilon", self.params.epsilon0))
        return True


class BanditPolicy(TabularPolicy):
    """Epsilon-greedy over actions ignoring state. Tests whether state matters."""
    name = "bandit"
    _ONE = "*"

    def choose(self, state: str) -> Action:
        return super().choose(self._ONE)

    def update(self, state, action, reward, next_state, next_action=None) -> None:
        row = self._row(self._ONE)
        row[action.value] += self.params.alpha * (reward - row[action.value])

    def q_values(self, state: str) -> dict[str, float]:
        return dict(self._row(self._ONE))


class QLearningPolicy(TabularPolicy):
    """Off-policy TD control: Q(s,a) += alpha [r + gamma max_a' Q(s',a') - Q(s,a)]."""
    name = "qlearn"

    def update(self, state, action, reward, next_state, next_action=None) -> None:
        row = self._row(state)
        target = reward
        if next_state is not None and next_state != TERMINAL:
            target += self.params.gamma * max(self._row(next_state).values())
        row[action.value] += self.params.alpha * (target - row[action.value])


class SarsaPolicy(TabularPolicy):
    """On-policy TD control: Q(s,a) += alpha [r + gamma Q(s',a') - Q(s,a)]."""
    name = "sarsa"

    def update(self, state, action, reward, next_state, next_action=None) -> None:
        row = self._row(state)
        target = reward
        if next_state is not None and next_state != TERMINAL:
            a2 = next_action or self.greedy(next_state)
            target += self.params.gamma * self._row(next_state)[a2.value]
        row[action.value] += self.params.alpha * (target - row[action.value])


POLICIES: dict[str, type[Policy]] = {
    p.name: p for p in (StaticPolicy, RandomPolicy, BanditPolicy, QLearningPolicy, SarsaPolicy)
}


def make_policy(name: str, params: RLParams | None = None, rng: random.Random | None = None) -> Policy:
    try:
        return POLICIES[name](params, rng)
    except KeyError:
        raise ValueError(f"unknown policy {name!r}; choose from {sorted(POLICIES)}") from None
