"""Correctness of the simulator and the exact solver.

The key test is that Monte-Carlo estimates agree with the exact linear-algebra values:
if they do, the MDP construction in exact.py is the same process as the simulator, and
the exact numbers in the report can be trusted.
"""
import math
import random

import numpy as np
import pytest

from honeypot.config import RLParams, RewardWeights
from honeypot.rl.policies import QLearningPolicy, StaticPolicy, make_policy
from simulator import exact
from simulator.env import Sampler, greedy_table, run_episode
from simulator.fit import fit_chain
from simulator.model import ACT, CAT, MIXES, MAX_CONTINUE, compile_population

W = RewardWeights()
GAMMA = 0.9


@pytest.fixture(scope="module")
def pop():
    return compile_population(MIXES["balanced"])


@pytest.fixture(scope="module")
def mdp(pop):
    return exact.build(pop, W, GAMMA)


def test_population_is_stochastic(pop):
    assert np.allclose(pop.init.sum(axis=1), 1)
    assert np.allclose(pop.nxt.sum(axis=3), 1)
    assert (pop.cont >= 0).all() and (pop.cont <= MAX_CONTINUE).all()
    assert (pop.cont[:, :, ACT[next(a for a in ACT if a.value == "BLOCK")]] == 0).all()


def test_transition_rows_substochastic(mdp):
    rows = mdp.P.sum(axis=2)
    assert (rows <= MAX_CONTINUE + 1e-12).all() and (rows >= 0).all()
    assert math.isclose(mdp.mu0.sum(), 1.0)


def mc(policy, pop, n, seed):
    s = Sampler(pop)
    rng = random.Random(seed)
    res = [run_episode(policy, s, rng, W, GAMMA, learn=False) for _ in range(n)]
    return np.array([r.ret for r in res]), np.array([r.commands for r in res]), np.array([r.intel for r in res])


@pytest.mark.parametrize("name", ["static", "random"])
def test_monte_carlo_matches_exact(pop, mdp, name):
    """MC mean must lie within 4 standard errors of the exact expectation."""
    policy = make_policy(name, RLParams(epsilon0=0.0), random.Random(1))
    pi = exact.constant("ALLOW") if name == "static" else exact.uniform()
    ex = exact.evaluate(mdp, pi)
    rets, cmds, intel = mc(policy, pop, 30_000, seed=2)
    for sample, key in ((rets, "return"), (cmds, "commands"), (intel, "intel")):
        se = sample.std(ddof=1) / math.sqrt(len(sample))
        assert abs(sample.mean() - ex[key]) < 4 * se, (key, sample.mean(), ex[key], se)


def test_exact_learned_policy_matches_mc(pop, mdp):
    """Same check for a non-trivial deterministic policy (a briefly trained Q-learner)."""
    rng = random.Random(3)
    agent = QLearningPolicy(RLParams(), rng)
    s = Sampler(pop)
    for _ in range(500):
        run_episode(agent, s, rng, W, GAMMA)
    table = greedy_table(agent)
    agent.epsilon = 0.0
    ex = exact.evaluate(mdp, exact.deterministic(table))
    rets, cmds, _ = mc(agent, pop, 30_000, seed=4)
    for sample, key in ((rets, "return"), (cmds, "commands")):
        se = sample.std(ddof=1) / math.sqrt(len(sample))
        assert abs(sample.mean() - ex[key]) < 4 * se, (key, sample.mean(), ex[key])


def test_benchmark_ordering(mdp):
    """oracle (type observed) >= best observable >= static, and BLOCK-always is terrible."""
    oracle, _ = exact.value_iteration(mdp)
    pi_best, v_best = exact.best_observable(mdp, restarts=3)
    v_static = exact.evaluate(mdp, exact.constant("ALLOW"))["return"]
    v_block = exact.evaluate(mdp, exact.constant("BLOCK"))["return"]
    assert oracle >= v_best - 1e-9 >= v_static - 1e-9 > v_block
    assert math.isclose(exact.evaluate(mdp, pi_best)["return"], v_best, rel_tol=1e-9)


def test_value_iteration_satisfies_bellman(mdp):
    v, Q = exact.value_iteration(mdp)
    V = Q.max(axis=0)
    resid = Q - (mdp.r + mdp.gamma * np.einsum("axy,y->ax", mdp.P, V))
    assert np.abs(resid).max() < 1e-8


def test_fit_recovers_chain():
    """Sessions from a single attacker type under ALLOW: MLE recovers its chain."""
    p1 = compile_population({"operator": 1.0})
    s = Sampler(p1)
    rng = random.Random(5)
    seqs = []
    from honeypot.classify import CATEGORIES
    for _ in range(20_000):
        c = s.draw(s.init_cdf[0], rng.random())
        seq = [CATEGORIES[c]]
        while rng.random() < s.cont[0][c][ACT[next(a for a in ACT if a.value == "ALLOW")]]:
            c = s.draw(s.next_cdf[0][c][0], rng.random())
            seq.append(CATEGORIES[c])
        seqs.append(seq)
    fit = fit_chain(seqs)
    allow = ACT[next(a for a in ACT if a.value == "ALLOW")]
    seen = fit["visits"] > 2000
    assert np.abs(fit["P"][seen] - p1.nxt[0, :, allow][seen]).max() < 0.02
    assert np.abs(fit["exit"][seen] - (1 - p1.cont[0, :, allow][seen])).max() < 0.02
    assert np.abs(fit["init"] - p1.init[0]).max() < 0.02


def test_posterior_shifts_toward_patient_attackers(mdp, pop):
    post = exact.type_posterior_by_t(mdp, exact.constant("ALLOW"))
    op = pop.names.index("operator")
    assert np.allclose(post.sum(axis=1), 1)
    assert post[-1, op] > post[0, op] * 2      # operators dominate long sessions


def test_static_policy_table_is_all_allow():
    assert set(greedy_table(StaticPolicy()).values()) == {"ALLOW"}
