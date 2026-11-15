"""Attacker population model (docs/02-mdp-formulation.md, section 4).

An attacker type k is a Markov chain over the 10 command categories with an exit
probability per category, plus a *response model*: how the honeypot's action changes
(i) the probability that the attacker issues another command and (ii) which category
comes next. The honeypot never observes k, so from its point of view the environment
is a mixture of chains: a partially observable problem.

All parameters below are modelling assumptions chosen to reflect qualitative findings
about SSH attackers (most traffic is short scripted bot sessions; human operators are
rarer, longer, and go after credentials). They are not fitted to data; `fit.py` estimates
them from captured sessions, and `experiments.py` tests sensitivity to the mix.

The compiled arrays are used by both the Monte-Carlo environment (env.py) and the exact
solver (exact.py), so the two are guaranteed to describe the same process.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from honeypot.classify import CATEGORIES, INTEL_VALUE
from honeypot.rl.policies import ACTION_COST, ACTIONS, Action

C = len(CATEGORIES)
A = len(ACTIONS)
CAT = {c: i for i, c in enumerate(CATEGORIES)}
ACT = {a: i for i, a in enumerate(ACTIONS)}
VALUE = np.array([INTEL_VALUE[c] for c in CATEGORIES], dtype=float)
COST = np.array([ACTION_COST[a] for a in ACTIONS], dtype=float)
MAX_CONTINUE = 0.98  # no response makes an attacker certain to stay


@dataclass(frozen=True)
class AttackerType:
    name: str
    init: dict[str, float]
    # category -> (next-category distribution, exit probability). "*" is the default row.
    trans: dict[str, tuple[dict[str, float], float]]
    # multiplier on the continue probability, per action
    action_mult: dict[str, float]
    # FAKE-specific multiplier per category (overrides action_mult["FAKE"])
    fake_mult: dict[str, float] = field(default_factory=dict)
    # after FAKE on these categories, next-category distribution is mixed with this one
    fake_shift: dict[str, dict[str, float]] = field(default_factory=dict)
    shift_weight: float = 0.5


BOT = AttackerType(
    name="bot",
    init={"recon": 0.5, "unknown": 0.3, "download": 0.2},
    trans={
        "recon": ({"recon": .35, "download": .35, "unknown": .15, "fs_browse": .10, "execute": .05}, .25),
        "unknown": ({"recon": .40, "unknown": .30, "download": .30}, .30),
        "download": ({"execute": .70, "download": .20, "cleanup": .10}, .15),
        "execute": ({"persist": .30, "cleanup": .30, "download": .20, "execute": .20}, .40),
        "persist": ({"cleanup": .50, "execute": .30, "persist": .20}, .40),
        "cleanup": ({"cleanup": .30, "recon": .20, "download": .50}, .70),
        "*": ({"recon": .40, "download": .40, "unknown": .20}, .40),
    },
    # Scripted: indifferent to content, but its timeouts cut it off under TARPIT.
    action_mult={"ALLOW": 1.0, "DELAY": 0.90, "FAKE": 1.0, "TARPIT": 0.35, "BLOCK": 0.0},
)

SCRIPT_KIDDIE = AttackerType(
    name="script_kiddie",
    init={"recon": 0.6, "fs_browse": 0.3, "benign": 0.1},
    trans={
        "recon": ({"recon": .35, "fs_browse": .30, "cred_access": .15, "download": .15, "privesc": .05}, .20),
        "fs_browse": ({"fs_browse": .35, "cred_access": .30, "recon": .20, "download": .15}, .20),
        "cred_access": ({"fs_browse": .30, "privesc": .25, "download": .25, "cred_access": .20}, .25),
        "download": ({"execute": .60, "download": .20, "fs_browse": .20}, .20),
        "execute": ({"persist": .30, "execute": .20, "recon": .20, "cleanup": .30}, .35),
        "privesc": ({"recon": .40, "fs_browse": .30, "download": .30}, .30),
        "persist": ({"cleanup": .50, "recon": .30, "persist": .20}, .35),
        "cleanup": ({"recon": .30, "benign": .70}, .75),
        "benign": ({"recon": .50, "fs_browse": .50}, .30),
        "*": ({"recon": .50, "fs_browse": .50}, .40),
    },
    # Impatient human: slowness drives them away; a juicy credential file excites them.
    action_mult={"ALLOW": 1.0, "DELAY": 0.80, "FAKE": 1.0, "TARPIT": 0.30, "BLOCK": 0.0},
    fake_mult={"cred_access": 1.15, "fs_browse": 1.10},
    fake_shift={"cred_access": {"cred_access": .5, "download": .3, "privesc": .2}},
)

OPERATOR = AttackerType(
    name="operator",
    init={"recon": 0.8, "fs_browse": 0.2},
    trans={
        "recon": ({"recon": .45, "fs_browse": .30, "cred_access": .15, "privesc": .10}, .10),
        "fs_browse": ({"fs_browse": .30, "cred_access": .40, "recon": .20, "download": .10}, .10),
        "cred_access": ({"cred_access": .30, "persist": .25, "privesc": .20, "fs_browse": .25}, .15),
        "privesc": ({"persist": .40, "recon": .30, "cred_access": .30}, .15),
        "download": ({"execute": .70, "download": .30}, .10),
        "execute": ({"persist": .50, "cleanup": .30, "execute": .20}, .15),
        "persist": ({"persist": .30, "cleanup": .50, "download": .20}, .15),
        "cleanup": ({"cleanup": .50, "benign": .50}, .60),
        "benign": ({"recon": 1.0}, .30),
        "*": ({"recon": .60, "fs_browse": .40}, .20),
    },
    # Skilled and suspicious: chases planted credentials, but fabricated system
    # information (FAKE on recon/fs_browse) is inconsistent and raises suspicion.
    action_mult={"ALLOW": 1.0, "DELAY": 0.97, "FAKE": 0.95, "TARPIT": 0.60, "BLOCK": 0.0},
    fake_mult={"cred_access": 1.20, "recon": 0.85, "fs_browse": 0.85},
    fake_shift={"cred_access": {"download": .4, "persist": .3, "privesc": .3}},
)

TYPES = {t.name: t for t in (BOT, SCRIPT_KIDDIE, OPERATOR)}

MIXES: dict[str, dict[str, float]] = {
    "balanced": {"bot": 0.60, "script_kiddie": 0.25, "operator": 0.15},
    "bot_heavy": {"bot": 0.85, "script_kiddie": 0.10, "operator": 0.05},
    "human_heavy": {"bot": 0.30, "script_kiddie": 0.35, "operator": 0.35},
}


def _vec(dist: dict[str, float], what: str) -> np.ndarray:
    v = np.zeros(C)
    for c, p in dist.items():
        if c not in CAT:
            raise ValueError(f"{what}: unknown category {c!r}")
        v[CAT[c]] = p
    if abs(v.sum() - 1.0) > 1e-9:
        raise ValueError(f"{what}: probabilities sum to {v.sum():.6f}, not 1")
    return v


@dataclass
class Population:
    """Compiled, array form of a mixture of attacker types.

    weights[k]        P(type k)
    init[k, c]        P(first category = c | k)
    cont[k, c, a]     P(attacker issues another command | k, current category c, action a)
    nxt[k, c, a, c']  P(next category = c' | k, c, a, continues)
    """
    names: list[str]
    weights: np.ndarray
    init: np.ndarray
    cont: np.ndarray
    nxt: np.ndarray

    @property
    def K(self) -> int:
        return len(self.names)


def compile_population(mix: dict[str, float], types: dict[str, AttackerType] | None = None) -> Population:
    types = types or TYPES
    names = [n for n, w in mix.items() if w > 0]
    weights = np.array([mix[n] for n in names], dtype=float)
    if abs(weights.sum() - 1.0) > 1e-9:
        raise ValueError("mix weights must sum to 1")
    K = len(names)
    init = np.zeros((K, C))
    cont = np.zeros((K, C, A))
    nxt = np.zeros((K, C, A, C))
    for k, n in enumerate(names):
        t = types[n]
        init[k] = _vec(t.init, f"{n}.init")
        for c in CATEGORIES:
            dist, exit_p = t.trans.get(c, t.trans["*"])
            base = _vec(dist, f"{n}.trans[{c}]")
            for a in ACTIONS:
                mult = t.fake_mult.get(c, t.action_mult["FAKE"]) if a is Action.FAKE else t.action_mult[a.value]
                cont[k, CAT[c], ACT[a]] = min(MAX_CONTINUE, (1.0 - exit_p) * mult)
                row = base
                if a is Action.FAKE and c in t.fake_shift:
                    row = (1 - t.shift_weight) * base + t.shift_weight * _vec(t.fake_shift[c], f"{n}.fake_shift[{c}]")
                nxt[k, CAT[c], ACT[a]] = row
    return Population(names, weights, init, cont, nxt)
