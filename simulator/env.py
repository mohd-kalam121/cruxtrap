"""Monte-Carlo environment: runs one attacker episode against any honeypot Policy.

The agent sees exactly what the real honeypot sees, the state "category|phase", and is
updated with exactly the same rule (deferred TD update when the next command arrives,
terminal update at session end), using the same compute_reward() as the live system.
"""
from __future__ import annotations

import bisect
import itertools
import random
from dataclasses import dataclass

from honeypot.classify import CATEGORIES, phase_for
from honeypot.config import RewardWeights
from honeypot.rl.policies import ACTION_COST, ACTIONS, TERMINAL, Policy, compute_reward, make_state

from .model import ACT, CAT, INTEL_VALUE, Population


@dataclass
class EpisodeResult:
    attacker: str
    commands: int
    ret: float            # discounted return  sum_t gamma^t r_t  (the agent's objective)
    reward: float         # undiscounted sum of rewards
    intel: float          # sum of v(category) over observed commands
    attacker_time: float  # sum of action costs chi(a): seconds of attacker time consumed
    reached_payload: bool  # saw download/execute/persist


class Sampler:
    """Fast categorical sampling from the compiled arrays (cumulative tables + bisect)."""

    def __init__(self, pop: Population):
        self.pop = pop
        self.type_cdf = list(itertools.accumulate(pop.weights.tolist()))
        self.init_cdf = [list(itertools.accumulate(row.tolist())) for row in pop.init]
        self.next_cdf = [[[list(itertools.accumulate(pop.nxt[k, c, a].tolist())) for a in range(pop.nxt.shape[2])]
                          for c in range(pop.nxt.shape[1])] for k in range(pop.K)]
        self.cont = pop.cont.tolist()

    @staticmethod
    def draw(cdf: list[float], u: float) -> int:
        return min(bisect.bisect_right(cdf, u * cdf[-1]), len(cdf) - 1)


PAYLOAD = {CAT["download"], CAT["execute"], CAT["persist"]}


def run_episode(policy: Policy, sampler: Sampler, rng: random.Random, w: RewardWeights, gamma: float,
                learn: bool = True, max_steps: int = 1000) -> EpisodeResult:
    k = sampler.draw(sampler.type_cdf, rng.random())
    c = sampler.draw(sampler.init_cdf[k], rng.random())
    t = 1
    state = make_state(CATEGORIES[c], phase_for(t))
    action = policy.choose(state)
    ret = total = intel = wasted = 0.0
    disc = 1.0
    payload = c in PAYLOAD
    while True:
        a = ACT[action]
        intel += INTEL_VALUE[CATEGORIES[c]]
        wasted += ACTION_COST[action]
        continued = rng.random() < sampler.cont[k][c][a] and t < max_steps
        c2 = sampler.draw(sampler.next_cdf[k][c][a], rng.random()) if continued else None
        r = compute_reward(action, continued, CATEGORIES[c], phase_for(t), CATEGORIES[c2] if continued else None, w)
        ret += disc * r
        total += r
        disc *= gamma
        if not continued:
            if learn:
                policy.update(state, action, r, TERMINAL, None)
            break
        t += 1
        payload = payload or c2 in PAYLOAD
        state2 = make_state(CATEGORIES[c2], phase_for(t))
        action2 = policy.choose(state2)
        if learn:
            policy.update(state, action, r, state2, action2)
        state, action, c = state2, action2, c2
    if learn:
        policy.end_episode()
    return EpisodeResult(sampler.pop.names[k], t, ret, total, intel, wasted, payload)


def greedy_table(policy: Policy) -> dict[str, str]:
    """Deterministic greedy action for each of the 30 observable states. Ties resolve to
    the earliest action in ACTIONS order (ALLOW first), i.e. towards the static honeypot."""
    from honeypot.classify import PHASES
    table = {}
    for c in CATEGORIES:
        for ph in PHASES:
            s = make_state(c, ph)
            q = policy.q_values(s)
            if not q:
                table[s] = ACTIONS[0].value
                continue
            best = max(q.values())
            table[s] = next(a.value for a in ACTIONS if q.get(a.value, float("-inf")) == best)
    return table
