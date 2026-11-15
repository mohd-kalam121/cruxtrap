"""Maximum-likelihood estimation of an attacker Markov chain from captured sessions.

Given category sequences c_1..c_n (one per session), the likelihood of a first-order
chain with initial distribution pi, transition matrix P and exit probabilities e is

    L = prod_sessions  pi(c_1) * prod_i (1 - e(c_i)) P(c_i, c_{i+1}) * e(c_n)

whose maximiser is the normalised counts:
    pi(c)    = #sessions starting at c / #sessions
    P(c, c') = #(c -> c') / #(c -> anything)
    e(c)     = #sessions ending at c / #visits to c

Additive (Laplace) smoothing `alpha` keeps unseen transitions at a small non-zero value.
Note: the estimate describes attacker behaviour *under the policy that was running when the
data was captured*; to recover the attacker's own chain, fit sessions served by the static
(always-ALLOW) policy, or condition on action.
"""
from __future__ import annotations

import numpy as np

from honeypot.classify import CATEGORIES

from .model import C, CAT


def fit_chain(sequences: list[list[str]], alpha: float = 0.0) -> dict[str, np.ndarray]:
    starts = np.zeros(C)
    trans = np.zeros((C, C))
    ends = np.zeros(C)
    for seq in sequences:
        if not seq:
            continue
        ids = [CAT[c] for c in seq]
        starts[ids[0]] += 1
        for a, b in zip(ids, ids[1:]):
            trans[a, b] += 1
        ends[ids[-1]] += 1
    visits = trans.sum(axis=1) + ends
    P = (trans + alpha) / np.maximum(trans.sum(axis=1, keepdims=True) + alpha * C, 1e-12)
    exit_p = np.divide(ends, visits, out=np.full(C, np.nan), where=visits > 0)
    return {"init": (starts + alpha) / (starts.sum() + alpha * C), "P": P, "exit": exit_p, "visits": visits}


async def load_sequences(dsn: str, min_commands: int = 1) -> list[list[str]]:
    """Category sequences of finished sessions in the CruxTrap database."""
    import asyncpg
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch("""
            SELECT array_agg(sa.category ORDER BY sa.seq) AS cats
            FROM session_actions sa JOIN sessions s USING (session_id)
            WHERE s.ended_at IS NOT NULL AND sa.category IS NOT NULL
            GROUP BY sa.session_id HAVING count(*) >= $1""", min_commands)
    finally:
        await conn.close()
    return [[c for c in r["cats"] if c in CATEGORIES] for r in rows]
