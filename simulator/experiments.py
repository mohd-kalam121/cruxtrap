"""Phase 5 experiments.

    python -m simulator.experiments                       # full run (~1-2 min on 8 cores)
    python -m simulator.experiments --episodes 1000 --seeds 4 --quick

E1  Learning:  5 policies x S seeds x N episodes on the balanced population. Online
    (with exploration) learning curves, and the exact value of each final greedy policy.
E2  Benchmarks: oracle (type observed, value iteration) and best observable policy.
E3  Sensitivity: attacker mix (3) x defender objective (intel / attrition).
E4  Validation: Monte-Carlo vs exact for the learned policies (sanity of the analysis).
E5  Type posterior P(type | session reached command t): why phase matters.

Outputs: docs/results/results.json, docs/results/summary.md, docs/figures/*.png
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import simulator  # noqa: F401  (pins BLAS threads before numpy is used)
import numpy as np
from scipy import stats

from honeypot.classify import CATEGORIES, PHASES
from honeypot.config import RewardWeights, RLParams
from honeypot.rl.policies import ACTIONS, make_policy

from . import exact
from .env import Sampler, greedy_table, run_episode
from .model import MIXES, compile_population

POLICIES = ["qlearn", "sarsa", "bandit", "static", "random"]
ABLATION = {
    "constant α=0.1": {"alpha_schedule": "constant", "alpha": 0.1},
    "αₙ=n^-0.6": {"alpha_schedule": "visit", "alpha_omega": 0.6},
    "αₙ=n^-0.7 (main)": {"alpha_schedule": "visit", "alpha_omega": 0.7},
    "αₙ=n^-0.85": {"alpha_schedule": "visit", "alpha_omega": 0.85},
    "αₙ=1/n": {"alpha_schedule": "visit", "alpha_omega": 1.0},
}
LABEL = {"qlearn": "Q-learning", "sarsa": "SARSA", "bandit": "ε-greedy bandit", "static": "Static (always ALLOW)",
         "random": "Random", "best_obs": "Best observable policy", "oracle": "Oracle (type known)"}
OBJECTIVES = {"intel": RewardWeights(), "attrition": RewardWeights(cost=-0.05)}
GAMMA = 0.9
ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------- one run
def train(task: dict) -> dict:
    import simulator  # noqa: F401  (worker processes need the BLAS pin too)
    pop = compile_population(MIXES[task["mix"]])
    w = OBJECTIVES[task["objective"]]
    rng = random.Random(task["seed"] * 7919 + POLICIES.index(task["policy"]))
    policy = make_policy(task["policy"], RLParams(**task.get("params", {})), rng)
    sampler = Sampler(pop)
    n = task["episodes"]
    ret = np.empty(n, dtype=np.float32)
    cmds = np.empty(n, dtype=np.float32)
    for i in range(n):
        r = run_episode(policy, sampler, rng, w, GAMMA, learn=True)
        ret[i], cmds[i] = r.ret, r.commands
    mdp = exact.build(pop, w, GAMMA)
    if task["policy"] == "random":
        pi, table = exact.uniform(), None
    else:
        table = greedy_table(policy)
        pi = exact.deterministic(table)
    ev = exact.evaluate(mdp, pi)
    return {**task, "online_return": ret, "online_commands": cmds, "table": table, "final": ev,
            "epsilon": getattr(policy, "epsilon", None)}


def ci95(x) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 2 or np.allclose(x, x[0]):
        return float(x.mean()), 0.0
    return float(x.mean()), float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)))


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=20000)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--sens-seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--block", type=int, default=400, help="episodes per point on the learning curve")
    ap.add_argument("--out", default=str(ROOT / "docs" / "results"))
    ap.add_argument("--figures", default=str(ROOT / "docs" / "figures"))
    args = ap.parse_args()
    out, figdir = Path(args.out), Path(args.figures)
    out.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ---- E1: learning on the balanced population, intel objective
    tasks = [{"policy": p, "seed": s, "mix": "balanced", "objective": "intel", "episodes": args.episodes}
             for p in POLICIES for s in range(args.seeds)]
    # ---- E3: sensitivity (Q-learning only; benchmarks are exact)
    sens = [{"policy": "qlearn", "seed": 1000 + s, "mix": m, "objective": o, "episodes": args.episodes}
            for m in MIXES for o in OBJECTIVES for s in range(args.sens_seeds)]
    # ---- E6: step-size ablation (Q-learning, own seeds), at two training lengths
    abl = [{"policy": "qlearn", "seed": 2000 + s, "mix": "balanced", "objective": "intel", "episodes": n,
            "params": params, "variant": name}
           for name, params in ABLATION.items() for n in (args.episodes // 4, args.episodes)
           for s in range(args.sens_seeds)]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        runs = list(ex.map(train, tasks + sens + abl, chunksize=1))
    main_runs = [r for r in runs if r["seed"] < 1000]
    sens_runs = [r for r in runs if 1000 <= r["seed"] < 2000]
    abl_runs = [r for r in runs if r["seed"] >= 2000]
    print(f"training done in {time.time() - t0:.1f}s ({len(runs)} runs)")

    # ---- E2: exact benchmarks for every scenario
    bench = {}
    for m in MIXES:
        for o, w in OBJECTIVES.items():
            mdp = exact.build(compile_population(MIXES[m]), w, GAMMA)
            pi_b, _ = exact.best_observable(mdp)
            v_or, _ = exact.value_iteration(mdp)
            bench[(m, o)] = {"static": exact.evaluate(mdp, exact.constant("ALLOW")),
                             "random": exact.evaluate(mdp, exact.uniform()),
                             "best_obs": exact.evaluate(mdp, pi_b), "best_obs_table": exact.table_of(pi_b),
                             "oracle_return": v_or}
    b = bench[("balanced", "intel")]

    # ---- E1 summary
    summary = {}
    for p in POLICIES:
        rs = [r for r in main_runs if r["policy"] == p]
        summary[p] = {k: ci95([r["final"][k] for r in rs]) for k in ("return", "commands", "intel", "attacker_time")}
        summary[p]["per_type_commands"] = {t: ci95([r["final"]["per_type"][t]["commands"] for r in rs])
                                           for t in rs[0]["final"]["per_type"]}
        last = [float(r["online_return"][-1000:].mean()) for r in rs]
        summary[p]["online_return_last1000"] = ci95(last)
        if p in ("qlearn", "sarsa", "bandit"):
            matches = [sum(r["table"][s] == b["best_obs_table"][s] for s in r["table"]) / len(r["table"]) for r in rs]
            summary[p]["agreement_with_best_obs"] = ci95(matches)
            gap = b["best_obs"]["return"] - b["static"]["return"]
            summary[p]["fraction_of_achievable_gain"] = ci95([(r["final"]["return"] - b["static"]["return"]) / gap for r in rs])
    q_final = [r["final"]["return"] for r in main_runs if r["policy"] == "qlearn"]
    tt = stats.ttest_1samp(q_final, b["static"]["return"], alternative="greater")
    s_final = [r["final"]["return"] for r in main_runs if r["policy"] == "sarsa"]
    tw = stats.ttest_ind(q_final, s_final, equal_var=False)

    # ---- E4: Monte-Carlo validation of exact numbers for seed-0 Q-learning
    pop_b = compile_population(MIXES["balanced"])
    r0 = next(r for r in main_runs if r["policy"] == "qlearn" and r["seed"] == 0)
    agent = make_policy("qlearn", RLParams(epsilon0=0.0, epsilon_min=0.0), random.Random(0))
    for s, a in r0["table"].items():  # an agent whose greedy table is r0's
        agent.q[s] = {x.value: (1.0 if x.value == a else 0.0) for x in ACTIONS}
    agent.epsilon = 0.0
    rng, smp = random.Random(99), Sampler(pop_b)
    mc = [run_episode(agent, smp, rng, OBJECTIVES["intel"], GAMMA, learn=False) for _ in range(50_000)]
    mc_ret, mc_cmd = np.array([x.ret for x in mc]), np.array([x.commands for x in mc])
    validation = {"exact_return": r0["final"]["return"], "mc_return": ci95(mc_ret),
                  "exact_commands": r0["final"]["commands"], "mc_commands": ci95(mc_cmd), "episodes": len(mc)}

    # ---- E5: type posterior under static policy
    mdp_b = exact.build(pop_b, OBJECTIVES["intel"], GAMMA)
    posterior = exact.type_posterior_by_t(mdp_b, exact.constant("ALLOW"))

    # ---- E3 summary
    sensitivity = []
    for m in MIXES:
        for o in OBJECTIVES:
            bb = bench[(m, o)]
            rs = [r for r in sens_runs if r["mix"] == m and r["objective"] == o]
            base = bb["static"]["return"]
            sensitivity.append({
                "mix": m, "objective": o, "static_return": base, "best_obs_return": bb["best_obs"]["return"],
                "oracle_return": bb["oracle_return"], "qlearn_return": ci95([r["final"]["return"] for r in rs]),
                "static_commands": bb["static"]["commands"], "best_obs_commands": bb["best_obs"]["commands"],
                "qlearn_commands": ci95([r["final"]["commands"] for r in rs]),
                "static_attacker_time": bb["static"]["attacker_time"],
                "best_obs_attacker_time": bb["best_obs"]["attacker_time"],
                "best_obs_deviations": {s: a for s, a in bb["best_obs_table"].items() if a != "ALLOW"},
            })

    # modal Q-learning policy and agreement per state
    q_tables = [r["table"] for r in main_runs if r["policy"] == "qlearn"]
    policy_map = {}
    for s in q_tables[0]:
        votes = {a.value: sum(t[s] == a.value for t in q_tables) for a in ACTIONS}
        mode = max(votes, key=votes.get)
        policy_map[s] = {"action": mode, "agreement": votes[mode] / len(q_tables), "best_obs": b["best_obs_table"][s]}

    ablation = []
    for name in ABLATION:
        for n in (args.episodes // 4, args.episodes):
            vals = [r["final"]["return"] for r in abl_runs if r["variant"] == name and r["episodes"] == n]
            ablation.append({"variant": name, "episodes": n, "return": ci95(vals),
                             "beats_static": int(sum(v > b["static"]["return"] for v in vals)), "n": len(vals),
                             "gain_captured": (float(np.mean(vals)) - b["static"]["return"])
                             / (b["best_obs"]["return"] - b["static"]["return"])})

    results = {
        "ablation_step_size": ablation,
        "config": {"episodes": args.episodes, "seeds": args.seeds, "sens_seeds": args.sens_seeds, "gamma": GAMMA,
                   "rl": asdict(RLParams()), "reward_intel": asdict(OBJECTIVES["intel"]),
                   "reward_attrition": asdict(OBJECTIVES["attrition"]), "mixes": MIXES},
        "benchmarks_balanced": {"static": b["static"], "random": b["random"], "best_obs": b["best_obs"],
                                "oracle_return": b["oracle_return"], "best_obs_table": b["best_obs_table"]},
        "policies": summary,
        "tests": {"qlearn_vs_static_one_sample": {"t": float(tt.statistic), "p": float(tt.pvalue), "n": len(q_final)},
                  "qlearn_vs_sarsa_welch": {"t": float(tw.statistic), "p": float(tw.pvalue)}},
        "validation": validation, "sensitivity": sensitivity, "policy_map": policy_map,
        "type_posterior": {"types": pop_b.names, "by_t": posterior.tolist()},
        "runtime_s": round(time.time() - t0, 1),
    }
    (out / "results.json").write_text(json.dumps(results, indent=1, default=float), encoding="utf-8")
    write_summary(out / "summary.md", results)

    from . import figures
    curves = {p: np.stack([r["online_return"] for r in main_runs if r["policy"] == p]) for p in POLICIES}
    figures.learning_curves(curves, args.block, b["best_obs"]["return"], b["oracle_return"], figdir / "fig_learning_curves.png")
    figures.final_performance(summary, b, figdir / "fig_final_performance.png")
    figures.policy_map(policy_map, figdir / "fig_policy_map.png")
    figures.sensitivity(sensitivity, figdir / "fig_sensitivity.png")
    figures.type_posterior(pop_b.names, posterior, figdir / "fig_type_posterior.png")
    figures.ablation(ablation, b["static"]["return"], b["best_obs"]["return"], figdir / "fig_ablation_step_size.png")
    print(f"done in {time.time() - t0:.1f}s -> {out}, {figdir}")


def write_summary(path: Path, R: dict) -> None:
    f = lambda m, d=3: f"{m[0]:.{d}f} ± {m[1]:.{d}f}"  # noqa: E731
    b = R["benchmarks_balanced"]
    L = ["# Phase 5 results (auto-generated)", "",
         f"{R['config']['seeds']} seeds × {R['config']['episodes']} episodes, balanced population, γ = {R['config']['gamma']}. "
         "Values are exact expectations of each run's final greedy policy (mean ± 95% CI over seeds).", "",
         "| Policy | Return | Commands / session | Intel / session | Attacker time (s) | Agreement with best |",
         "|---|---|---|---|---|---|"]
    for p in POLICIES:
        s = R["policies"][p]
        agr = f(s["agreement_with_best_obs"], 2) if "agreement_with_best_obs" in s else "—"
        L.append(f"| {LABEL[p]} | {f(s['return'])} | {f(s['commands'])} | {f(s['intel'], 2)} | {f(s['attacker_time'], 2)} | {agr} |")
    L.append(f"| {LABEL['best_obs']} | {b['best_obs']['return']:.3f} | {b['best_obs']['commands']:.3f} | {b['best_obs']['intel']:.2f} | {b['best_obs']['attacker_time']:.2f} | 1.00 |")
    L.append(f"| {LABEL['oracle']} | {b['oracle_return']:.3f} | — | — | — | — |")
    t = R["tests"]
    L += ["", f"Q-learning > static: one-sample t = {t['qlearn_vs_static_one_sample']['t']:.2f}, "
              f"p = {t['qlearn_vs_static_one_sample']['p']:.2g} (n = {t['qlearn_vs_static_one_sample']['n']}).",
          f"Q-learning vs SARSA: Welch t = {t['qlearn_vs_sarsa_welch']['t']:.2f}, p = {t['qlearn_vs_sarsa_welch']['p']:.2g}.",
          f"Q-learning reaches {f(R['policies']['qlearn']['fraction_of_achievable_gain'], 2)} of the gain available to the best observable policy.",
          "", "## Validation (Monte Carlo vs exact, seed-0 Q-learning policy)", "",
          f"Return: exact {R['validation']['exact_return']:.4f}, MC {f(R['validation']['mc_return'], 4)}; "
          f"commands: exact {R['validation']['exact_commands']:.4f}, MC {f(R['validation']['mc_commands'], 4)} "
          f"({R['validation']['episodes']:,} episodes).", "",
          "## Step-size ablation (Q-learning, separate seeds)", "",
          "| Step size | Episodes | Return | Beats static | Share of achievable gain |", "|---|---|---|---|---|"]
    L += [f"| {a['variant']} | {a['episodes']:,} | {f(a['return'])} | {a['beats_static']}/{a['n']} | {a['gain_captured']:+.0%} |"
          for a in R["ablation_step_size"]]
    L += ["", "## Sensitivity", "", "| Mix | Objective | Static | Q-learning | Best observable | Oracle | Best-policy changes |",
          "|---|---|---|---|---|---|---|"]
    for s in R["sensitivity"]:
        dev = ", ".join(f"{k}→{v}" for k, v in s["best_obs_deviations"].items()) or "none"
        L.append(f"| {s['mix']} | {s['objective']} | {s['static_return']:.3f} | {f(s['qlearn_return'])} | "
                 f"{s['best_obs_return']:.3f} | {s['oracle_return']:.3f} | {dev} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
