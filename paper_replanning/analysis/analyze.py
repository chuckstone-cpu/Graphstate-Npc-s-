"""Analyse the experiment logs: tables, paired tests, figures and SUMMARY.md.

    python analysis/analyze.py                         # full results in results/
    python analysis/analyze.py --results-dir results/smoke

Reads   <results>/runs.csv, <results>/events.csv
Writes  <results>/tables/*.csv and *.tex, <results>/figures/*.png and *.pdf,
        <results>/SUMMARY.md

What is measured (all in EXPANSIONS = cells taken off a search's open list;
machine-independent, so every statistical test uses them):
    replan  replan_expansions_total        search work caused by change events
    total   initial + replan (+ move)      everything the NPC searched in the trip
    hitch   max_single_replan_expansions   the worst single replan (a frame "hitch")
Time in ms is reported in a secondary table only (Python timing is noisy).

Statistics:
    - mean with a 95% bootstrap CI (percentile method, 2000 resamples, seeded per cell)
    - paired by problem (same map, start, goal, prankster seed): D* Lite vs astar_lazy and
      D* Lite vs astar_restart, per prankster, overall and per map set:
        Wilcoxon signed-rank test (zero differences dropped; their number is reported),
        win/tie/loss counts (win = D* Lite searched LESS), median D*/baseline ratio,
        matched-pairs rank-biserial correlation r (POSITIVE = favours D* Lite, range -1..1),
        Holm-adjusted p over all tests in the table (we run many tests).
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                         # draw to files, no window
import matplotlib.pyplot as plt               # noqa: E402
import numpy as np                            # noqa: E402
import pandas as pd                           # noqa: E402
from scipy import stats                       # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.seeding import derive_seed           # noqa: E402

PLANNERS = ["bfs_restart", "astar_restart", "astar_lazy", "dstar_lite"]
PRANKSTERS = ["none", "random_global", "random_local", "saboteur"]
SCOPES = ["all", "dao", "street", "room"]
LABEL = {"bfs_restart": "BFS restart", "astar_restart": "A* restart", "astar_lazy": "A* lazy",
         "dstar_lite": "D* Lite", "none": "none", "random_global": "random global",
         "random_local": "random local", "saboteur": "saboteur", "all": "All maps",
         "dao": "dao", "street": "street", "room": "room"}
METRICS = {"total": "total_expansions", "replan": "replan_expansions_total",
           "hitch": "max_single_replan_expansions"}
METRIC_TEXT = {"total": "total search work (first plan + replanning)",
               "replan": "replanning work", "hitch": "worst single replan (hitch)"}
TIME_METRICS = {"replan_ms": "replan_time_ms_total", "hitch_ms": "max_single_replan_ms",
                "initial_ms": "initial_time_ms", "total_ms": "total_time_ms"}
COMPARISONS = [("dstar_lite", "astar_lazy"), ("dstar_lite", "astar_restart")]

# Colours: the first four slots of the validated categorical palette (dataviz skill),
# in a fixed order, plus a marker shape per planner so print/greyscale still works.
COLOR = {"bfs_restart": "#2a78d6", "astar_restart": "#eb6834", "astar_lazy": "#1baf7a",
         "dstar_lite": "#eda100"}
MARKER = {"bfs_restart": "o", "astar_restart": "s", "astar_lazy": "^", "dstar_lite": "D"}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


# ---------------------------------------------------------------- loading
def load(results_dir):
    runs = pd.read_csv(results_dir / "runs.csv")
    events = pd.read_csv(results_dir / "events.csv")
    runs["total_expansions"] = (runs.initial_expansions + runs.replan_expansions_total
                                + runs.move_expansions_total)
    runs["total_time_ms"] = runs.initial_time_ms + runs.replan_time_ms_total
    runs["path_overhead"] = runs.steps / runs.opt_len_initial
    return runs, events


def in_scope(df, scope):
    return df if scope == "all" else df[df.map_set == scope]


# ---------------------------------------------------------------- statistics
def bootstrap_ci(values, seed, resamples):
    """Mean and 95% percentile bootstrap CI of the mean."""
    x = np.asarray(values, dtype=float)
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(resamples, len(x)))].mean(axis=1)
    return x.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def summary_table(runs, metrics, master_seed, resamples):
    """One row per (scope, metric, planner, prankster): n, mean, CI, median.

    All planners in a (scope, metric, prankster) cell use the SAME seed and their runs are
    sorted by problem_id, so they resample the same problems (common random numbers, as
    in the paired design). Identical data therefore gets identical CIs.
    """
    rows = []
    for scope in SCOPES:
        part = in_scope(runs, scope).sort_values("problem_id")
        for mname, col in metrics.items():
            for planner in PLANNERS:
                for prank in PRANKSTERS:
                    x = part[(part.planner == planner) & (part.prankster == prank)][col]
                    seed = derive_seed(master_seed, "bootstrap", scope, mname, prank)
                    mean, lo, hi = bootstrap_ci(x, seed, resamples)
                    rows.append({"scope": scope, "metric": mname, "planner": planner,
                                 "prankster": prank, "n": len(x), "mean": mean,
                                 "ci_lo": lo, "ci_hi": hi, "median": x.median()})
    return pd.DataFrame(rows)


def holm(pvalues):
    """Holm step-down adjustment; NaN p-values are left as NaN."""
    p = np.asarray(pvalues, dtype=float)
    ok = ~np.isnan(p)
    order = np.argsort(p[ok])
    m = ok.sum()
    adj_ok = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[ok][idx])
        adj_ok[idx] = min(1.0, running)
    out = np.full_like(p, np.nan)
    out[ok] = adj_ok
    return out


def paired_test(dstar, base):
    """Paired comparison of two arrays (same problems, same order)."""
    d = np.asarray(dstar, float) - np.asarray(base, float)     # < 0 means D* Lite searched less
    wins, ties, losses = int((d < 0).sum()), int((d == 0).sum()), int((d > 0).sum())
    nz = d[d != 0]
    if len(nz) == 0:
        w = p = r = np.nan
    else:
        w, p = stats.wilcoxon(nz, zero_method="wilcox", alternative="two-sided")
        ranks = stats.rankdata(np.abs(nz))
        r = (ranks[nz < 0].sum() - ranks[nz > 0].sum()) / ranks.sum()   # + favours D* Lite
    base = np.asarray(base, float)
    keep = base > 0
    ratios = np.asarray(dstar, float)[keep] / base[keep]
    return {"n_pairs": len(d), "wins": wins, "ties": ties, "losses": losses,
            "n_nonzero": len(nz), "W": w, "p": p, "r_rank_biserial": r,
            "median_ratio": float(np.median(ratios)) if len(ratios) else np.nan,
            "n_ratio": int(keep.sum())}


def paired_tests(runs):
    rows = []
    for scope in SCOPES:
        part = in_scope(runs, scope)
        for mname, col in METRICS.items():
            wide = part.pivot_table(index=["problem_id", "prankster"], columns="planner",
                                    values=col, aggfunc="first")
            for prank in PRANKSTERS:
                if prank == "none" and mname != "total":
                    continue            # no changes -> no replans: nothing to compare
                w = wide.xs(prank, level="prankster")
                for dstar, base in COMPARISONS:
                    pair = w[[dstar, base]].dropna()
                    res = paired_test(pair[dstar], pair[base])
                    rows.append({"scope": scope, "metric": mname, "prankster": prank,
                                 "comparison": f"{dstar} vs {base}", "baseline": base, **res})
    df = pd.DataFrame(rows)
    df["p_holm"] = holm(df.p)
    return df


# ---------------------------------------------------------------- tables
def fmt_num(x):
    if pd.isna(x):
        return "-"
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.1f}" if abs(x) >= 1 else f"{x:.2f}"


def fmt_ci(row):
    return f"{fmt_num(row['mean'])} [{fmt_num(row['ci_lo'])}, {fmt_num(row['ci_hi'])}]"


def fmt_ratio(x):
    """Two significant digits, so small ratios such as 0.004 do not print as 0.00."""
    return "-" if pd.isna(x) else f"{x:.2g}"


def fmt_p(p):
    if pd.isna(p):
        return "-"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def latex_escape(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")


def write_latex(df, path, caption, label):
    """A plain booktabs table (pandas' to_latex needs jinja2, which we don't install)."""
    cols = list(df.columns)
    lines = [r"\begin{table}[t]", r"\centering", r"\small",
             rf"\caption{{{latex_escape(caption)}}}", rf"\label{{{label}}}",
             r"\begin{tabular}{" + "l" * len(cols) + "}", r"\toprule",
             " & ".join(latex_escape(c) for c in cols) + r" \\", r"\midrule"]
    for _, row in df.iterrows():
        lines.append(" & ".join(latex_escape(v) for v in row.values) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def grid_view(summary, scope, metric, pranksters=PRANKSTERS):
    """planner rows x prankster columns, cells 'mean [lo, hi]'."""
    s = summary[(summary.scope == scope) & (summary.metric == metric)]
    out = pd.DataFrame(index=[LABEL[p] for p in PLANNERS])
    for prank in pranksters:
        cells = s[s.prankster == prank].set_index("planner")
        out[LABEL[prank]] = [fmt_ci(cells.loc[p]) for p in PLANNERS]
    out.index.name = "planner"
    n = int(s.n.max()) if len(s) else 0
    return out.reset_index(), n


def tests_view(tests, scope, metric):
    t = tests[(tests.scope == scope) & (tests.metric == metric)]
    return pd.DataFrame({
        "prankster": [LABEL[p] for p in t.prankster],
        "comparison": ["D* Lite vs " + LABEL[b] for b in t.baseline],
        "pairs": t.n_pairs, "win/tie/loss": [f"{a}/{b}/{c}" for a, b, c in zip(t.wins, t.ties, t.losses)],
        "median ratio (n)": [f"{fmt_ratio(x)} ({n})" for x, n in zip(t.median_ratio, t.n_ratio)],
        "r": [fmt_num(x) for x in t.r_rank_biserial],
        "p": [fmt_p(x) for x in t.p], "p (Holm)": [fmt_p(x) for x in t.p_holm]})


def write_tables(summary, time_summary, tests, overhead, fig1, tables_dir):
    tables_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(tables_dir / "expansions_summary.csv", index=False)
    time_summary.to_csv(tables_dir / "time_summary_secondary.csv", index=False)
    tests.to_csv(tables_dir / "paired_tests.csv", index=False)
    overhead.to_csv(tables_dir / "path_overhead_summary.csv", index=False)
    fig1.to_csv(tables_dir / "fig1_expansions_by_distance.csv", index=False)
    for scope in SCOPES:
        for metric in METRICS:
            view, n = grid_view(summary, scope, metric)
            write_latex(view, tables_dir / f"table_{metric}_{scope}.tex",
                        f"Mean {METRIC_TEXT[metric]} in expansions, with 95% bootstrap CI "
                        f"({LABEL[scope]}, n = {n} runs per cell).", f"tab:{metric}-{scope}")
            write_latex(tests_view(tests, scope, metric), tables_dir / f"table_tests_{metric}_{scope}.tex",
                        f"Paired comparison of {METRIC_TEXT[metric]} ({LABEL[scope]}). Win = D* Lite "
                        "searched less; ratio = median D*/baseline over the n problems where the "
                        "baseline is > 0; r = rank-biserial, positive "
                        "favours D* Lite; p from the Wilcoxon signed-rank test.",
                        f"tab:tests-{metric}-{scope}")
    view, n = grid_view(time_summary, "all", "total_ms")
    write_latex(view, tables_dir / "table_time_total_all.tex",
                f"SECONDARY: mean total search time in ms (first plan + replans), 95% bootstrap CI "
                f"(n = {n} runs per cell). Python timing is noisy; use expansions for conclusions.",
                "tab:time-total")


# ---------------------------------------------------------------- figures
def style():
    plt.rcParams.update({
        "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 8,
        "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "lines.linewidth": 2, "savefig.dpi": 200, "figure.facecolor": "white"})


def legend_handles():
    return [plt.Line2D([], [], color=COLOR[p], marker=MARKER[p], markersize=6, linewidth=2,
                       label=LABEL[p]) for p in PLANNERS]


def save(fig, figures_dir, name):
    figures_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(figures_dir / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)


DIST_BINS = [0, 25, 50, 100, 150, 200, 300, np.inf]
DIST_LABELS = ["0-24", "25-49", "50-99", "100-149", "150-199", "200-299", "300+"]


def fig1_data(events):
    ev = events.copy()
    ev["dist_bin"] = pd.cut(ev.dist_block_goal, DIST_BINS, right=False, labels=DIST_LABELS)
    g = ev.groupby(["prankster", "planner", "dist_bin"], observed=True).expansions
    return g.agg(["mean", "count"]).reset_index().rename(columns={"count": "n_events"})


def figure1(data, figures_dir):
    pr = [p for p in PRANKSTERS if p in set(data.prankster)]
    fig, axes = plt.subplots(1, len(pr), figsize=(7.2, 2.6), sharey=True, squeeze=False)
    for ax, prank in zip(axes[0], pr):
        for planner in PLANNERS:
            d = data[(data.prankster == prank) & (data.planner == planner)]
            x = [DIST_LABELS.index(b) for b in d.dist_bin]
            ax.plot(x, d["mean"], color=COLOR[planner], marker=MARKER[planner], markersize=5)
        ax.set_title(LABEL[prank], color=INK)
        ax.set_xticks(range(len(DIST_LABELS)))
        ax.set_xticklabels(DIST_LABELS, rotation=45, ha="right")
        ax.set_xlabel("distance from block to goal (cells)")
        ax.set_yscale("symlog", linthresh=1)
    axes[0][0].set_ylabel("mean expansions per change event")
    fig.legend(handles=legend_handles(), loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.08))
    save(fig, figures_dir, "fig1_expansions_vs_distance")


def box_grid(runs, column, pranksters, ylabel, name, figures_dir, plus_one=False, note=""):
    """Small multiples: rows = prankster, columns = scope, one box per planner (log y)."""
    fig, axes = plt.subplots(len(pranksters), len(SCOPES), figsize=(7.2, 1.9 * len(pranksters)),
                             sharey=True, squeeze=False)
    for i, prank in enumerate(pranksters):
        for j, scope in enumerate(SCOPES):
            ax = axes[i][j]
            part = in_scope(runs, scope)
            data = [part[(part.planner == p) & (part.prankster == prank)][column] + (1 if plus_one else 0)
                    for p in PLANNERS]
            bp = ax.boxplot(data, widths=0.6, patch_artist=True, showfliers=True,
                            medianprops={"color": INK, "linewidth": 1.2},
                            whiskerprops={"color": INK_2, "linewidth": 0.8},
                            capprops={"color": INK_2, "linewidth": 0.8},
                            flierprops={"marker": ".", "markersize": 2, "markeredgecolor": INK_2})
            for patch, p in zip(bp["boxes"], PLANNERS):
                patch.set_facecolor(COLOR[p])
                patch.set_edgecolor("white")
                patch.set_linewidth(1)
            ax.set_yscale("log")
            ax.set_xticks(range(1, len(PLANNERS) + 1))
            ax.set_xticklabels([LABEL[p] for p in PLANNERS], rotation=45, ha="right")
            ax.tick_params(axis="x", labelbottom=(i == len(pranksters) - 1))   # names on bottom row only
            if i == 0:
                ax.set_title(LABEL[scope], color=INK)
            if j == 0:
                ax.set_ylabel(f"{LABEL[prank]}\n{ylabel}")
    if note:
        fig.text(0.5, -0.02, note, ha="center", va="top", color=INK_2, fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.legend(handles=legend_handles(), loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    save(fig, figures_dir, name)


def ci_points(summary, metric, pranksters, ylabel, name, figures_dir):
    """Panels = scope; x = prankster; one point + 95% CI per planner (log y)."""
    fig, axes = plt.subplots(1, len(SCOPES), figsize=(7.2, 2.6), sharey=True, squeeze=False)
    offsets = np.linspace(-0.27, 0.27, len(PLANNERS))
    for ax, scope in zip(axes[0], SCOPES):
        s = summary[(summary.scope == scope) & (summary.metric == metric)]
        for off, planner in zip(offsets, PLANNERS):
            d = s[s.planner == planner].set_index("prankster").loc[pranksters]
            x = np.arange(len(pranksters)) + off
            ax.errorbar(x, d["mean"], yerr=[d["mean"] - d.ci_lo, d.ci_hi - d["mean"]],
                        fmt=MARKER[planner], color=COLOR[planner], markersize=5,
                        elinewidth=2, capsize=0, markeredgecolor="white", markeredgewidth=0.8)
        # symlog = log above 1, linear near 0, so a mean of exactly 0 (e.g. a planner that
        # never had to replan) is still drawn instead of vanishing off a log axis.
        ax.set_yscale("symlog", linthresh=1)
        ax.set_xticks(range(len(pranksters)))
        ax.set_xticklabels([LABEL[p] for p in pranksters], rotation=45, ha="right")
        ax.set_title(LABEL[scope], color=INK)
    axes[0][0].set_ylabel(ylabel)
    fig.legend(handles=legend_handles(), loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.08))
    save(fig, figures_dir, name)


def make_figures(runs, summary, fig1, figures_dir):
    style()
    figure1(fig1, figures_dir)
    changing = ["random_global", "random_local", "saboteur"]
    box_grid(runs, "replan_expansions_total", changing, "replan exp. + 1", "fig2_replan_boxplot",
             figures_dir, plus_one=True,
             note="Log scale, so 1 is added to every value (a run with no replans shows as 1). "
                  "The 'none' prankster is omitted: every planner has 0 replans there.")
    ci_points(summary, "hitch", changing, "worst single replan\n(expansions, mean, 95% CI)",
              "fig3_hitch", figures_dir)
    box_grid(runs, "path_overhead", changing, "steps / optimal", "fig4_path_overhead", figures_dir,
             note="Steps walked divided by the initial optimal path length (1 = no detour). "
                  "With 'none' every planner walks exactly the optimal length.")
    ci_points(summary, "total", PRANKSTERS, "total expansions\n(first plan + replans, mean, 95% CI)",
              "fig5_total_effort", figures_dir)


# ---------------------------------------------------------------- SUMMARY.md
def md_table(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.values]
    return "\n".join(out)


def finding_line(t):
    """One plain-English sentence for one paired test (wording follows the Holm p-value)."""
    base = LABEL[t.baseline]
    who = f"against the {LABEL[t.prankster]} prankster" if t.prankster != "none" else "with no changes"
    stats_txt = (f"D* Lite searched less in {t.wins}, tied in {t.ties} and searched more in "
                 f"{t.losses} of {t.n_pairs} problems; median D*/{base} ratio {fmt_ratio(t.median_ratio)} "
                 f"over the {t.n_ratio} problems where {base} > 0; "
                 f"r = {fmt_num(t.r_rank_biserial)}; Holm p {fmt_p(t.p_holm)}")
    if pd.isna(t.p_holm):
        verdict = f"D* Lite and {base} were identical on every problem"
    elif t.p_holm < 0.05:
        verdict = (f"D* Lite's {METRIC_TEXT[t.metric]} was {'LOWER' if t.r_rank_biserial > 0 else 'HIGHER'} "
                   f"than {base}'s")
    else:
        verdict = f"no significant difference in {METRIC_TEXT[t.metric]} between D* Lite and {base}"
    return f"- **{METRIC_TEXT[t.metric].capitalize()}, {who}:** {verdict} ({stats_txt})."


def direction(t):
    if pd.isna(t.p_holm) or t.p_holm >= 0.05:
        return "n.s."
    return "D* lower" if t.r_rank_biserial > 0 else "D* higher"


def heterogeneity_lines(tests):
    """Per-set results whose direction differs from the overall result."""
    lines = []
    overall = tests[tests.scope == "all"].set_index(["metric", "prankster", "baseline"])
    for t in tests[tests.scope != "all"].itertuples():
        o = overall.loc[(t.metric, t.prankster, t.baseline)]
        if direction(t) != direction(o):
            lines.append(f"- {METRIC_TEXT[t.metric].capitalize()}, {LABEL[t.prankster]}, D* Lite vs "
                         f"{LABEL[t.baseline]}: overall **{direction(o)}**, but on **{t.scope}** "
                         f"**{direction(t)}** (wins/ties/losses {t.wins}/{t.ties}/{t.losses}, "
                         f"Holm p {fmt_p(t.p_holm)}).")
    return lines or ["- None: every per-set result has the same direction as the overall result."]


DATA_HANDLING = """\
- **Step cap.** Main run: `max_steps = 10 x opt + 100`. 52 runs (all saboteur, all on room maps)
  still hit it. They were re-run with `30 x opt + 100` (`scripts/rerun_capped.py`) and matched the
  originals **exactly** in every count column and every event; only `steps`, `success` and the
  re-measured timings differed. They were merged into `runs.csv`/`events.csv` with backups
  (`scripts/merge_capped_reruns.py`, `results/backup/`). All change events happen by step 150, so
  the cap could never affect blocks, replans or expansions.
- **Path length limit.** D* Lite's `current_path()` stops at `max_len` cells (2000 in the game).
  The simulator now asks for 10000; the port keeps 2000. The longest planned path measured was
  **1999 cells** (room/64room_009, saboteur). Re-running the 67 runs with the longest paths
  reproduced every count column and every event exactly (`scripts/verify_long_paths.py`).
- **Timing noise.** Identical re-runs differed by a median of 6-14% (full run) and 12-38% (smoke
  run) in their timing columns, so expansions are the primary metric and time is secondary only."""

THREATS = """\
- **Python timing noise:** times depend on load, power state and the interpreter; we draw no
  conclusion from them. Expansions do not measure the cost per expansion, which differs between
  algorithms (a D* Lite expansion updates neighbours' rhs values, so it costs more than an A* one).
- **Block-only changes:** cells are only ever blocked, never freed. This is exactly the case where
  lazy A* is safe (an untouched path stays optimal); with unblocking, results may differ.
- **Full-knowledge NPC:** every change is announced instantly; no sensing or fog of war.
- **4-connected grids, unit costs, Manhattan heuristic;** results may not carry over to octile
  movement or weighted terrain. Water was treated as blocked.
- **Map selection:** maps up to 256x256, except room (all 512x512, allowed up to 512); 8 maps x
  15 problems per set, BFS length 60-250. Room maps are bigger, so set and size are confounded.
- **The saboteur reacts to each planner's own path,** so planners do not face identical block
  sequences and trajectories (and path lengths) differ between planners on the same problem.
- **Tie order:** the port reproduces the game's numbers on level1, but level1 cannot distinguish
  different tie-breaking orders between equal-key cells (tested by deliberate mutation), so exact
  equality with the game's tie order is untested beyond what level1 shows."""


def write_summary(runs, events, summary, time_summary, tests, overhead, results_dir, notes_path):
    n_runs, n_prob = len(runs), runs.problem_id.nunique()
    per_set = runs.groupby("map_set").problem_id.nunique().to_dict()
    n_maps = runs.groupby("map_set").map_name.nunique().to_dict()
    ev_n = events.groupby("prankster").size().to_dict()
    cell_n = int(runs.groupby(["planner", "prankster"]).size().min())
    lines = ["# Results summary", "",
             "_Generated by `analysis/analyze.py` from `results/runs.csv` and `results/events.csv`. "
             "Do not edit by hand: re-run the script._", "",
             "## Data", "",
             f"- **{n_runs} runs** = {n_prob} problems x {len(PLANNERS)} planners x {len(PRANKSTERS)} pranksters "
             f"(at least {cell_n} runs per planner x prankster cell).",
             "- Problems per map set: " + ", ".join(f"{s} {per_set[s]} ({n_maps[s]} maps)" for s in sorted(per_set)) + ".",
             f"- Success (agent reached the goal): {runs.success.mean() * 100:.1f}% of runs.",
             "- Change events (blocks): " + ", ".join(f"{LABEL[k]} {v}" for k, v in ev_n.items()) + ".",
             "- Unit: **expansions** (cells taken off a search's open list). Means with 95% bootstrap CIs "
             "(2000 resamples, seeded). Paired tests: Wilcoxon signed-rank on the same problems; "
             "r = matched-pairs rank-biserial (positive favours D* Lite); Holm-adjusted over all "
             f"{int(tests.p.notna().sum())} tests.", ""]

    lines += ["## Findings (all maps; one line per paired test)", ""]
    order = {"total": 0, "replan": 1, "hitch": 2}
    t_all = tests[tests.scope == "all"].sort_values(["metric", "prankster", "baseline"],
                                                    key=lambda c: c.map(order) if c.name == "metric" else c)
    lines += [finding_line(t) for t in t_all.itertuples()]
    lines += ["", "### Where a map set differs from the overall result", ""] + heterogeneity_lines(tests)
    ov = overhead[(overhead.scope == "all")]
    lines += ["", "### Path length", "",
              "Mean steps / initial optimal length (95% CI), all maps:", "",
              md_table(grid_view(ov, "all", "overhead")[0]), ""]

    for metric in ["total", "replan", "hitch"]:
        view, n = grid_view(summary, "all", metric)
        lines += [f"## Key numbers: {METRIC_TEXT[metric]} (all maps, n = {n} runs per cell)", "",
                  "Mean expansions [95% CI].", "", md_table(view), "",
                  "Paired tests:", "", md_table(tests_view(tests, "all", metric)), ""]

    lines += ["## Per map set", ""]
    for scope in ["dao", "street", "room"]:
        lines += [f"### {scope}", ""]
        for metric in ["total", "replan", "hitch"]:
            view, n = grid_view(summary, scope, metric)
            lines += [f"**{METRIC_TEXT[metric].capitalize()}** (n = {n} per cell), mean [95% CI]:", "",
                      md_table(view), "", md_table(tests_view(tests, scope, metric)), ""]

    view, n = grid_view(time_summary, "all", "total_ms")
    lines += ["## Secondary: time (ms)", "",
              f"Mean total search time per run (first plan + replans), all maps, n = {n} per cell. "
              "**Not used for any test** (timing is noisy; see Data handling).", "", md_table(view), ""]
    lines += ["## Data handling", "", DATA_HANDLING, "", "## Threats to validity", "", THREATS, ""]
    if notes_path.exists():
        lines += ["## Notes (written by hand after reading the numbers above)", "",
                  notes_path.read_text(encoding="utf-8").strip(), ""]
    (results_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "mvp.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    seed, resamples = config["master_seed"], config["analysis"]["bootstrap_resamples"]
    out = args.results_dir

    runs, events = load(out)
    print(f"{len(runs)} runs, {len(events)} events from {out}")
    if not runs.success.all():
        print(f"WARNING: {(~runs.success).sum()} runs did not reach the goal")
    summary = summary_table(runs, METRICS, seed, resamples)
    time_summary = summary_table(runs, TIME_METRICS, seed, resamples)
    overhead = summary_table(runs, {"overhead": "path_overhead"}, seed, resamples)
    tests = paired_tests(runs)
    fig1 = fig1_data(events)
    write_tables(summary, time_summary, tests, overhead, fig1, out / "tables")
    make_figures(runs, summary, fig1, out / "figures")
    # Hand-written notes describe the FULL results, so only add them to that summary.
    is_main = out.resolve() == (ROOT / "results").resolve()
    notes = ROOT / "analysis" / "notes.md" if is_main else out / "_no_notes"
    write_summary(runs, events, summary, time_summary, tests, overhead, out, notes)
    print(f"wrote tables to {out / 'tables'}, figures to {out / 'figures'}, {out / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
