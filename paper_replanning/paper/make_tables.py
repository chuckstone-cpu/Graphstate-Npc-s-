"""Write the paper's LaTeX tables straight from the analysis output (no hand-copied numbers).

    python paper/make_tables.py        (run after analysis/analyze.py)

Reads   results/tables/expansions_summary.csv, paired_tests.csv, time_summary_secondary.csv,
        results/runs.csv
Writes  paper/tables/*.tex
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.analyze import LABEL, PLANNERS, PRANKSTERS, fmt_num, fmt_p, fmt_ratio  # noqa: E402

TABLES = ROOT / "results" / "tables"
OUT = Path(__file__).resolve().parent / "tables"
SCOPE_NAME = {"all": "all maps", "dao": "dao", "street": "street", "room": "room"}
METRIC_NAME = {"total": "Total effort", "replan": "Replanning effort", "hitch": "Worst single replan"}


def tex(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def cell(row):
    return f"{fmt_num(row['mean'])} [{fmt_num(row['ci_lo'])}, {fmt_num(row['ci_hi'])}]"


def means_rows(summary, scope, metric, pranksters):
    s = summary[(summary.scope == scope) & (summary.metric == metric)]
    rows = []
    for p in PLANNERS:
        cells = s[s.planner == p].set_index("prankster")
        rows.append(" & ".join([LABEL[p]] + [cell(cells.loc[k]) for k in pranksters]) + r" \\")
    return rows, int(s.n.max())


def means_table(summary, scope, metric, label, caption, pranksters=PRANKSTERS):
    rows, n = means_rows(summary, scope, metric, pranksters)
    head = " & ".join(["Planner"] + [LABEL[k].capitalize() for k in pranksters]) + r" \\"
    return "\n".join([
        r"\begin{table*}[!t]", r"\centering", r"\footnotesize",
        rf"\caption{{{caption} ({SCOPE_NAME[scope]}, $n={n}$ runs per cell). Mean expansions "
        r"with 95\% bootstrap confidence interval.}", rf"\label{{{label}}}",
        r"\begin{tabular}{l" + "c" * len(pranksters) + "}", r"\toprule", head, r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])


def tests_rows(tests, scope, metric):
    t = tests[(tests.scope == scope) & (tests.metric == metric)]
    out = []
    for r in t.itertuples():
        out.append(" & ".join([
            METRIC_NAME[metric], LABEL[r.prankster].capitalize(), "D* Lite vs " + LABEL[r.baseline],
            f"{r.wins}/{r.ties}/{r.losses}", f"{fmt_ratio(r.median_ratio)} ({r.n_ratio})",
            f"${r.r_rank_biserial:+.2f}$", fmt_p(r.p_holm)]).replace("< ", "$<$ ") + r" \\")
    return out


def tests_table(tests, scope, metrics, label, caption, explain=False):
    """explain=True: the caption defines every column (only for the first such table, tab:tests)."""
    body = []
    for i, m in enumerate(metrics):
        if i:
            body.append(r"\midrule")
        body += tests_rows(tests, scope, m)
    n = int(tests[tests.scope == scope].n_pairs.max())
    if explain:
        legend = (r" W/T/L = problems where D* Lite searched less / the same / more; ratio = median "
                  r"D*/baseline over the $n$ problems where the baseline is $>0$; $r$ = matched-pairs "
                  r"rank-biserial correlation (positive favours D* Lite); $p$ = Wilcoxon signed-rank, "
                  r"Holm-adjusted over all 80 tests.")
    else:
        legend = r" Columns as in Table~\ref{tab:tests}."
    return "\n".join([
        r"\begin{table*}[!t]", r"\centering", r"\footnotesize",
        rf"\caption{{{caption} ({SCOPE_NAME[scope]}, $n={n}$ paired problems).{legend}}}",
        rf"\label{{{label}}}", r"\begin{tabular}{lllcccc}", r"\toprule",
        r"Metric & Prankster & Comparison & W/T/L & Median ratio ($n$) & $r$ & $p$ (Holm) \\",
        r"\midrule", *body, r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])


def sets_table(tests):
    """One compact table: the key D* Lite vs A* lazy comparisons, overall and per map set."""
    def get(scope, metric, prank):
        return tests[(tests.scope == scope) & (tests.metric == metric) & (tests.prankster == prank)
                     & (tests.baseline == "astar_lazy")].iloc[0]

    def ratio_p(t):
        return f"{fmt_ratio(t.median_ratio)} ({fmt_p(t.p_holm)})".replace("< ", "$<$")

    rows = []
    for scope in ["dao", "street", "room", "all"]:
        rg, sab, hitch = get(scope, "total", "random_global"), get(scope, "total", "saboteur"), \
            get(scope, "hitch", "saboteur")
        name = SCOPE_NAME[scope].capitalize() if scope != "all" else "All"
        rows.append(" & ".join([name, str(sab.n_pairs), ratio_p(rg), ratio_p(sab),
                                f"{hitch.wins}/{hitch.ties}/{hitch.losses}",
                                fmt_p(hitch.p_holm).replace("< ", "$<$")]) + r" \\")
        if scope == "room":
            rows.append(r"\midrule")
    return "\n".join([
        r"\begin{table}[!t]", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{3pt}",
        r"\caption{\dstar{} vs.\ A* lazy per map set. Total effort: median \dstar{}/A* lazy ratio "
        r"(Holm $p$); hitch: W/T/L and Holm $p$. Columns as in Table~\ref{tab:tests}.}",
        r"\label{tab:sets}", r"\begin{tabular}{lccccc}", r"\toprule",
        r" & & Total, & Total, & \multicolumn{2}{c}{Hitch, saboteur} \\",
        r"Set & $n$ & random global & saboteur & W/T/L & $p$ \\", r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])


def time_table(time_summary, runs):
    rows, n = means_rows(time_summary, "all", "total_ms", PRANKSTERS)
    runs = runs.assign(exp=runs.initial_expansions + runs.replan_expansions_total,
                       ms=runs.initial_time_ms + runs.replan_time_ms_total)
    g = runs.groupby("planner")
    us = (g.ms.sum() / g.exp.sum() * 1000)
    per = [f"{LABEL[p]}: {us[p]:.1f}" for p in PLANNERS]
    return "\n".join([
        r"\begin{table*}[!t]", r"\centering", r"\footnotesize",
        rf"\caption{{Secondary measure: mean search time per run in ms (first plan + replans), all maps, "
        rf"$n={n}$ runs per cell, 95\% bootstrap CI. Not used in any statistical test. Time per expansion "
        rf"over all runs ($\mu$s): {'; '.join(per)}.}}", r"\label{tab:time}",
        r"\begin{tabular}{l" + "c" * len(PRANKSTERS) + "}", r"\toprule",
        " & ".join(["Planner"] + [LABEL[k].capitalize() for k in PRANKSTERS]) + r" \\", r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])


def main():
    OUT.mkdir(exist_ok=True)
    summary = pd.read_csv(TABLES / "expansions_summary.csv")
    tests = pd.read_csv(TABLES / "paired_tests.csv")
    time_summary = pd.read_csv(TABLES / "time_summary_secondary.csv")
    runs = pd.read_csv(ROOT / "results" / "runs.csv")
    files = {
        "tab_total_all.tex": means_table(summary, "all", "total", "tab:total",
                                         "Total search effort (first plan + all replans)"),
        "tab_tests_main.tex": tests_table(tests, "all", ["total", "hitch"], "tab:tests",
                                          "Paired comparisons of D* Lite with both A* variants for total effort and the hitch",
                                          explain=True),
        "tab_sets.tex": sets_table(tests),
        "tab_time.tex": time_table(time_summary, runs),
    }
    for old in OUT.glob("*.tex"):                    # remove tables the paper no longer uses
        if old.name not in files:
            old.unlink()
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} tables to {OUT}")


if __name__ == "__main__":
    main()
