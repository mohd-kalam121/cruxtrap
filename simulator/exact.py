"""Exact analysis of the simulator by dynamic programming.

Because the attacker model is known, the process can be written as a finite MDP on the
*augmented* state x = (k, c, t): attacker type k, current category c, and command index t
(capped at T = 11, from which the phase is 'late' forever). From x, under action a:

    with prob  cont[k,c,a] * nxt[k,c,a,c']   ->  (k, c', min(t+1, T))
    with prob  1 - cont[k,c,a]               ->  terminal

and the expected immediate reward is

    r(x,a) = cont[k,c,a] * sum_c' nxt[k,c,a,c'] (w_e + w_v v(c'))  -  w_c chi(a)
             + w_b 1[a = BLOCK, c = cleanup, t >= T]

which is exactly E[compute_reward(...)] in the live honeypot. The honeypot only observes
(c, phase(t)); a policy over that observation induces a Markov chain on x, so its value
solves the linear system (I - gamma P_pi) V = r_pi. Expected commands per session, intel
captured, and attacker time follow from the same system with gamma = 1 (the chain is
absorbing because every continue-probability is <= 0.98).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from honeypot.classify import CATEGORIES, PHASES
from honeypot.config import RewardWeights
from honeypot.rl.policies import ACTIONS

from .model import A, ACT, C, CAT, COST, VALUE, Population

T = 11                                    # t >= 11 is 'late' (phase_for)
PHASE_OF_T = np.array([0, 0, 0] + [1] * 7 + [2])  # t = 1..11 -> early, mid, late


@dataclass
class MDP:
    pop: Population
    gamma: float
    P: np.ndarray        # (A, X, X)
    r: np.ndarray        # (A, X) expected immediate reward
    mu0: np.ndarray      # (X,) start distribution
    obs: np.ndarray      # (X,) observable-state index  c*3 + phase
    cat: np.ndarray      # (X,) category index

    @property
    def X(self) -> int:
        return self.mu0.shape[0]


def idx(k: int, c: int, t: int) -> int:
    return (k * C + c) * T + (t - 1)


def build(pop: Population, w: RewardWeights, gamma: float) -> MDP:
    X = pop.K * C * T
    P = np.zeros((A, X, X))
    r = np.zeros((A, X))
    mu0 = np.zeros(X)
    obs = np.zeros(X, dtype=int)
    cat = np.zeros(X, dtype=int)
    gain = w.engagement + w.value * VALUE                     # reward for continuing into c'
    for k in range(pop.K):
        for c in range(C):
            mu0[idx(k, c, 1)] = pop.weights[k] * pop.init[k, c]
            for t in range(1, T + 1):
                x = idx(k, c, t)
                obs[x] = c * 3 + PHASE_OF_T[t - 1]
                cat[x] = c
                t2 = min(t + 1, T)
                for a in range(A):
                    q = pop.cont[k, c, a]
                    P[a, x, idx(k, 0, t2):idx(k, C - 1, t2) + 1:T] = q * pop.nxt[k, c, a]
                    r[a, x] = q * pop.nxt[k, c, a] @ gain - w.cost * COST[a]
                    if ACTIONS[a].value == "BLOCK" and c == CAT["cleanup"] and t == T:
                        r[a, x] += w.block_bonus
    return MDP(pop, gamma, P, r, mu0, obs, cat)


def _induced(mdp: MDP, pi: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """pi: (30, A) action probabilities per observable state. Returns P_pi, r_pi, chi_pi."""
    probs = pi[mdp.obs]                                      # (X, A)
    P_pi = np.einsum("xa,axy->xy", probs, mdp.P)
    r_pi = np.einsum("xa,ax->x", probs, mdp.r)
    chi_pi = probs @ COST
    return P_pi, r_pi, chi_pi


def evaluate(mdp: MDP, pi: np.ndarray) -> dict:
    """Exact expected per-session metrics of a (possibly stochastic) observable policy."""
    P_pi, r_pi, chi_pi = _induced(mdp, pi)
    I = np.eye(mdp.X)
    V = np.linalg.solve(I - mdp.gamma * P_pi, r_pi)
    N = np.linalg.inv(I - P_pi)                              # fundamental matrix (expected visits)
    visits = mdp.mu0 @ N                                     # expected visits to each augmented state
    per_type = {}
    for k, name in enumerate(mdp.pop.names):
        mu_k = np.zeros(mdp.X)
        sl = slice(k * C * T, (k + 1) * C * T)
        mu_k[sl] = mdp.mu0[sl] / mdp.pop.weights[k]
        per_type[name] = {"commands": float(mu_k @ N @ np.ones(mdp.X)), "return": float(mu_k @ V)}
    return {
        "return": float(mdp.mu0 @ V),
        "commands": float(visits.sum()),
        "intel": float(visits @ VALUE[mdp.cat]),
        "attacker_time": float(visits @ chi_pi),
        "per_type": per_type,
    }


def deterministic(table: dict[str, str]) -> np.ndarray:
    """{'recon|early': 'ALLOW', ...} -> (30, A) one-hot policy."""
    pi = np.zeros((C * 3, A))
    for c_i, c in enumerate(CATEGORIES):
        for p_i, ph in enumerate(PHASES):
            pi[c_i * 3 + p_i, ACT[next(a for a in ACTIONS if a.value == table[f"{c}|{ph}"])]] = 1.0
    return pi


def constant(action: str) -> np.ndarray:
    pi = np.zeros((C * 3, A))
    pi[:, [a.value for a in ACTIONS].index(action)] = 1.0
    return pi


def uniform() -> np.ndarray:
    return np.full((C * 3, A), 1.0 / A)


def value_iteration(mdp: MDP, tol: float = 1e-10, max_iter: int = 100_000) -> tuple[float, np.ndarray]:
    """Optimal value when the attacker TYPE IS OBSERVED (full information). This is an upper
    bound for every policy the honeypot can actually run, since it sees only (c, phase)."""
    V = np.zeros(mdp.X)
    for _ in range(max_iter):
        Q = mdp.r + mdp.gamma * np.einsum("axy,y->ax", mdp.P, V)
        V2 = Q.max(axis=0)
        if np.max(np.abs(V2 - V)) < tol:
            V = V2
            break
        V = V2
    return float(mdp.mu0 @ V), Q


def best_observable(mdp: MDP, restarts: int = 8, seed: int = 0) -> tuple[np.ndarray, float]:
    """Best deterministic policy over the honeypot's own observation (c, phase).

    Finding the optimal memoryless policy of a POMDP is NP-hard in general, so this uses
    exact policy evaluation inside coordinate ascent (change one observable state's action
    at a time, keep strict improvements) with random restarts. With 30 states and 5 actions
    this converges in a few sweeps; the result is a strong benchmark, not a proof of optimality.
    """
    rng = np.random.default_rng(seed)
    best_pi, best_v = None, -np.inf
    starts = [np.zeros(C * 3, dtype=int)] + [rng.integers(0, A, C * 3) for _ in range(restarts - 1)]
    for choice in starts:
        choice = choice.copy()
        v = _value_of(mdp, choice)
        improved = True
        while improved:
            improved = False
            for o in range(C * 3):
                for a in range(A):
                    if a == choice[o]:
                        continue
                    old = choice[o]
                    choice[o] = a
                    v2 = _value_of(mdp, choice)
                    if v2 > v + 1e-12:
                        v, improved = v2, True
                    else:
                        choice[o] = old
        if v > best_v:
            best_v, best_pi = v, choice.copy()
    pi = np.zeros((C * 3, A))
    pi[np.arange(C * 3), best_pi] = 1.0
    return pi, float(best_v)


def _value_of(mdp: MDP, choice: np.ndarray) -> float:
    """Value of a deterministic observable policy (choice[o] = action index)."""
    a_x = choice[mdp.obs]                                    # action taken in each augmented state
    rows = np.arange(mdp.X)
    P_pi, r_pi = mdp.P[a_x, rows], mdp.r[a_x, rows]
    return float(mdp.mu0 @ np.linalg.solve(np.eye(mdp.X) - mdp.gamma * P_pi, r_pi))


def table_of(pi: np.ndarray) -> dict[str, str]:
    return {f"{c}|{ph}": ACTIONS[int(pi[c_i * 3 + p_i].argmax())].value
            for c_i, c in enumerate(CATEGORIES) for p_i, ph in enumerate(PHASES)}


def type_posterior_by_t(mdp: MDP, pi: np.ndarray) -> np.ndarray:
    """P(type | session reached command t) for t = 1..T under policy pi: shows how the
    phase carries information about the hidden attacker type."""
    P_pi, _, _ = _induced(mdp, pi)
    dist = mdp.mu0.copy()
    out = np.zeros((T, mdp.pop.K))
    for t in range(T):
        mass = dist.reshape(mdp.pop.K, C, T).sum(axis=(1, 2))
        out[t] = mass / mass.sum() if mass.sum() > 0 else mass
        dist = dist @ P_pi
        if t < T - 1:  # keep only mass that has just moved to index t+1
            keep = np.zeros_like(dist).reshape(mdp.pop.K, C, T)
            keep[:, :, t + 1] = dist.reshape(mdp.pop.K, C, T)[:, :, t + 1]
            dist = keep.ravel()
    return out
