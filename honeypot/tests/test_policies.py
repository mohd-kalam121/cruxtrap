import random

import pytest

from honeypot.config import RLParams, RewardWeights
from honeypot.rl.policies import (
    ACTIONS, TERMINAL, Action, BanditPolicy, QLearningPolicy, SarsaPolicy, StaticPolicy,
    compute_reward, make_policy, make_state,
)


def test_reward_rewards_continuation_and_penalises_friction():
    w = RewardWeights()
    cont = compute_reward(Action.ALLOW, True, "recon", "early", "download", w)
    assert cont == pytest.approx(1.0 + 0.5 * 4)
    left = compute_reward(Action.ALLOW, False, "recon", "early", None, w)
    assert left == 0.0
    tarpit_left = compute_reward(Action.TARPIT, False, "recon", "early", None, w)
    assert tarpit_left < left


def test_justified_block_bonus_only_late_cleanup():
    w = RewardWeights()
    assert compute_reward(Action.BLOCK, False, "cleanup", "late", None, w) == pytest.approx(w.block_bonus)
    assert compute_reward(Action.BLOCK, False, "cleanup", "early", None, w) == 0.0
    assert compute_reward(Action.BLOCK, False, "recon", "late", None, w) == 0.0


def test_static_always_allows():
    p = StaticPolicy()
    assert all(p.choose(make_state(c, "mid")) is Action.ALLOW for c in ("recon", "download"))


def test_warm_start_prefers_allow():
    p = QLearningPolicy(RLParams(epsilon0=0.0))
    assert p.choose("recon|early") is Action.ALLOW


def test_qlearning_learns_the_better_action():
    """In a toy world where FAKE on cred_access always continues and ALLOW never does,
    the agent must end up preferring FAKE."""
    rng = random.Random(0)
    p = QLearningPolicy(RLParams(epsilon0=0.3, epsilon_min=0.0, epsilon_decay=0.99), rng)
    s = make_state("cred_access", "mid")
    for _ in range(500):
        a = p.choose(s)
        if a is Action.FAKE:
            p.update(s, a, 3.0, s)
        else:
            p.update(s, a, 0.0, TERMINAL)
        p.end_episode()
    assert p.greedy(s) is Action.FAKE
    assert p.q_values(s)["FAKE"] > p.q_values(s)["ALLOW"]


def test_sarsa_and_bandit_update_without_error():
    for cls in (SarsaPolicy, BanditPolicy):
        p = cls(RLParams(), random.Random(1))
        s = make_state("recon", "early")
        a = p.choose(s)
        p.update(s, a, 1.0, make_state("recon", "early"), a)
        p.end_episode()
        assert set(p.q_values(s)) == {x.value for x in ACTIONS}


def test_epsilon_decays_to_floor():
    p = QLearningPolicy(RLParams(epsilon0=0.5, epsilon_min=0.05, epsilon_decay=0.5))
    for _ in range(10):
        p.end_episode()
    assert p.epsilon == pytest.approx(0.05)


def test_save_and_load_roundtrip(tmp_path):
    p = QLearningPolicy(RLParams())
    p.update("recon|early", Action.DELAY, 2.0, "download|mid")
    p.end_episode()
    path = tmp_path / "q.json"
    p.save(str(path))
    q = QLearningPolicy(RLParams())
    assert q.load(str(path))
    assert q.q == p.q and q.episodes == 1 and q.epsilon == pytest.approx(p.epsilon)


def test_make_policy_rejects_unknown():
    with pytest.raises(ValueError):
        make_policy("dqn")
