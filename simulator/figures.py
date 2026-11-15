"""Report figures (static PNG, light surface, for print).

Palette: the reference categorical palette in fixed slot order; each policy keeps its
colour in every figure. Benchmarks are reference lines in neutral ink, not series.
One y-axis per chart; hairline grids; legends always present for >= 2 series.
"""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from honeypot.classify import CATEGORIES, PHASES  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = {"qlearn": "#2a78d6", "sarsa": "#eb6834", "bandit": "#1baf7a", "static": "#eda100", "random": "#e87ba4"}
TYPE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]  # blue ramp, light -> dark
LABEL = {"qlearn": "Q-learning", "sarsa": "SARSA", "bandit": "ε-greedy bandit", "static": "Static (always ALLOW)",
         "random": "Random"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": AXIS, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
    "axes.titlesize": 11, "axes.titlelocation": "left", "legend.frameon": False,
})


def _save(fig, path):
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _band(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = data.mean(axis=0)
    n = data.shape[0]
    h = stats.t.ppf(0.975, n - 1) * data.std(axis=0, ddof=1) / math.sqrt(n) if n > 1 else np.zeros_like(m)
    return m, h


def learning_curves(curves: dict[str, np.ndarray], block: int, best_obs: float, oracle: float, path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for p in ("qlearn", "sarsa", "bandit", "static"):
        runs = curves[p]
        nb = runs.shape[1] // block
        blocks = runs[:, :nb * block].reshape(runs.shape[0], nb, block).mean(axis=2)
        m, h = _band(blocks)
        x = (np.arange(nb) + 1) * block
        ax.fill_between(x, m - h, m + h, color=SERIES[p], alpha=0.15, linewidth=0)
        ax.plot(x, m, color=SERIES[p], linewidth=1.8, label=LABEL[p])
    for y, name, style in ((oracle, "Oracle (type known)", (0, (1, 2))), (best_obs, "Best observable policy", (0, (5, 3)))):
        ax.axhline(y, color=INK2, linewidth=1.1, linestyle=style)
        ax.annotate(name, xy=(1.0, y), xycoords=("axes fraction", "data"), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK2)
    rnd = float(curves["random"].mean())
    ax.set_ylim(4.4, 6.05)
    ax.text(0.01, 0.02, f"Random ≈ {rnd:.2f} (below axis)", transform=ax.transAxes, fontsize=8.5, color=SERIES["random"])
    ax.set_xlabel("Training episode (attacker sessions)")
    ax.set_ylabel("Discounted return per session")
    ax.set_title(f"Online performance while learning (ε ≥ 0.05 exploration), mean of "
                 f"{next(iter(curves.values())).shape[0]} seeds; bands: 95% CI")
    ax.legend(loc="lower right", ncol=2, fontsize=9)
    _save(fig, path)


def final_performance(summary: dict, bench: dict, path) -> None:
    """Dot plot (no zero baseline needed): the policies differ by a few percent."""
    order = ["qlearn", "sarsa", "bandit", "static"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4), sharey=True)
    for ax, key, title in ((axes[0], "return", "Expected discounted return"),
                           (axes[1], "commands", "Expected commands per session")):
        ys = np.arange(len(order))
        for y, p in zip(ys, order):
            m, h = summary[p][key]
            ax.errorbar(m, y, xerr=h, fmt="o", ms=8, color=SERIES[p], ecolor=SERIES[p], elinewidth=1.4, capsize=3,
                        markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=3)
            ax.annotate(f"{m:.3f}", xy=(m, y), xytext=(0, 9), textcoords="offset points", ha="center",
                        fontsize=8.5, color=INK2)
        refs = [(bench["best_obs"][key], "best observable", (0, (5, 3)))]
        if key == "return":
            refs.append((bench["oracle_return"], "oracle", (0, (1, 2))))
        for x, name, style in refs:
            ax.axvline(x, color=INK2, linestyle=style, linewidth=1.1)
            ax.annotate(name, xy=(x, 1.0), xycoords=("data", "axes fraction"), xytext=(3, 2), textcoords="offset points",
                        fontsize=8, color=INK2, rotation=0, va="bottom")
        ax.set_title(title, pad=16)
        ax.grid(axis="y", visible=False)
        ax.set_ylim(len(order) - 0.4, -0.6)
    axes[0].set_yticks(np.arange(len(order)), [LABEL[p] for p in order])
    rnd = summary["random"]
    fig.text(0.01, -0.03, f"Random policy (off scale): return {rnd['return'][0]:.2f}, {rnd['commands'][0]:.2f} commands. "
             "Error bars: 95% CI over seeds; values are exact expectations of each final greedy policy.",
             fontsize=8.5, color=INK2)
    fig.tight_layout()
    _save(fig, path)


def policy_map(pmap: dict, path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    ax.grid(False)
    for i, c in enumerate(CATEGORIES):
        for j, ph in enumerate(PHASES):
            cell = pmap[f"{c}|{ph}"]
            agr = cell["agreement"]
            color = SEQ[min(len(SEQ) - 1, int(agr * (len(SEQ) - 1) + 1e-9))]
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=color, linewidth=0))
            txt_color = "#ffffff" if agr >= 0.6 else INK
            mark = "" if cell["action"] == cell["best_obs"] else " ≠"
            ax.text(j + 0.48, i + 0.46, f"{cell['action']}{mark}\n{agr:.0%}", ha="center", va="center", fontsize=8.5,
                    color=txt_color, linespacing=1.2)
    ax.set_xlim(0, 3)
    ax.set_ylim(len(CATEGORIES), 0)
    ax.set_xticks(np.arange(3) + 0.48, PHASES)
    ax.set_yticks(np.arange(len(CATEGORIES)) + 0.46, CATEGORIES)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Learned Q-learning policy: modal action across seeds\n"
                 "(shade and % = share of seeds agreeing; ≠ = differs from best observable policy)", fontsize=10)
    _save(fig, path)


def sensitivity(rows: list[dict], path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    mixes = list(dict.fromkeys(r["mix"] for r in rows))
    for ax, obj in zip(axes, ("intel", "attrition")):
        rs = [r for r in rows if r["objective"] == obj]
        ys = np.arange(len(rs))
        pct = lambda v, base: 100 * (v - base) / abs(base)  # noqa: E731
        q = [pct(r["qlearn_return"][0], r["static_return"]) for r in rs]
        qe = [100 * r["qlearn_return"][1] / abs(r["static_return"]) for r in rs]
        bo = [pct(r["best_obs_return"], r["static_return"]) for r in rs]
        orc = [pct(r["oracle_return"], r["static_return"]) for r in rs]
        ax.scatter(orc, ys, marker="|", s=160, color=INK2, linewidths=1.5, label="Oracle (type known)", zorder=3)
        ax.scatter(bo, ys, marker="D", s=36, facecolor=SURFACE, edgecolor=INK2, linewidths=1.2, label="Best observable", zorder=3)
        ax.errorbar(q, ys, xerr=qe, fmt="o", ms=7, color=SERIES["qlearn"], ecolor=SERIES["qlearn"], elinewidth=1.2,
                    capsize=3, label="Q-learning (95% CI)", zorder=4, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.axvline(0, color=AXIS, linewidth=1)
        ax.set_title(f"Objective: {obj}")
        ax.set_xlabel("Improvement over static honeypot (% of return)")
        ax.set_yticks(ys, [r["mix"].replace("_", "-") for r in rs])
        ax.grid(axis="y", visible=False)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    _save(fig, path)


def type_posterior(names: list[str], post: np.ndarray, path) -> None:
    fig, ax = plt.subplots(figsize=(7, 3.8))
    t = np.arange(1, post.shape[0] + 1)
    for k, n in enumerate(names):
        ax.plot(t, post[:, k], color=TYPE_COLORS[k], linewidth=1.8, marker="o", ms=4, label=n.replace("_", " "))
        ax.annotate(n.replace("_", " "), xy=(t[-1], post[-1, k]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK2)
    for x, ph in ((2, "early"), (7, "mid"), (11, "late")):
        ax.text(x, 1.02, ph, ha="center", fontsize=8.5, color=MUTED, transform=ax.get_xaxis_transform())
    for x in (3.5, 10.5):
        ax.axvline(x, color=AXIS, linewidth=0.8, linestyle=(0, (2, 2)))
    ax.set_ylim(0, 1)
    ax.set_xticks(t, [str(i) if i < 11 else "≥11" for i in t])
    ax.set_xlabel("Command index t (session has reached this command)")
    ax.set_ylabel("P(attacker type | reached t)")
    ax.set_title("Who is still there? Posterior over the hidden attacker type (static policy)", pad=18)
    ax.legend(loc="upper right", fontsize=9, ncol=3)
    _save(fig, path)


def ablation(rows: list[dict], static: float, best: float, path) -> None:
    """Final return of Q-learning per step-size schedule, at two training lengths."""
    variants = list(dict.fromkeys(r["variant"] for r in rows))
    lengths = sorted({r["episodes"] for r in rows})
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ys = np.arange(len(variants))
    shades = {lengths[0]: "#86b6ef", lengths[-1]: "#256abf"}  # one hue, light = shorter training
    offs = {lengths[0]: -0.14, lengths[-1]: 0.14}
    for n in lengths:
        rs = [next(r for r in rows if r["variant"] == v and r["episodes"] == n) for v in variants]
        ax.errorbar([r["return"][0] for r in rs], ys + offs[n], xerr=[r["return"][1] for r in rs], fmt="o", ms=7,
                    color=shades[n], ecolor=shades[n], elinewidth=1.2, capsize=3, markeredgecolor=SURFACE,
                    markeredgewidth=1.2, label=f"{n:,} episodes", zorder=3)
    for x, name, style in ((static, "static", "-"), (best, "best observable", (0, (5, 3)))):
        ax.axvline(x, color=INK2, linewidth=1.1, linestyle=style)
        ax.text(x, len(variants) - 0.45, f" {name}", fontsize=8.5, color=INK2, va="bottom")
    ax.set_yticks(ys, variants)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Expected discounted return of final greedy policy (95% CI)")
    ax.set_title("Step-size ablation: constant α never settles; Robbins–Monro schedules converge", pad=16)
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, path)
