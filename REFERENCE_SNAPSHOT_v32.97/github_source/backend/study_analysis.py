"""
study_analysis.py — Full RCT analysis for PETTLEP AOMI trial (Group × Time).

Usage:
  python study_analysis.py master_study_data.csv --out study_results.txt
  python study_analysis.py master_study_data.csv --json results.json
"""

import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

# Manuscript-aligned — SPARC primary + 5 secondary kinematics
PRIMARY_KIN_KEYS = {"sparc"}
KINEMATIC_PRIMARY = [
    ("sparc", "SPARC (PRIMARY)"),
]
KINEMATIC_SECONDARY = [
    ("trunk_ratio", "Trunk ratio"),
    ("shoulder_vert_norm", "Shoulder elevation norm"),
    ("hand_displacement_norm", "Hand reach trunk-relative (SW)"),
    ("movement_time_sec", "Movement time (s)"),
    ("peak_velocity_px_s", "Peak velocity (px/s)"),
]
KINEMATIC_EXPLORATORY = []
KINEMATIC_OUTCOMES = KINEMATIC_PRIMARY + KINEMATIC_SECONDARY + KINEMATIC_EXPLORATORY
SECONDARY_KIN_KEYS = {b for b, _ in KINEMATIC_SECONDARY}

SECONDARY_CLIN = [
    ("WMFT_Rating", "WMFT-4 rating sum"),
    ("WMFT_Time", "WMFT-4 time sum (s)"),
    ("VAMS_Happy", "VAMS Happy"),
    ("VAMS_Calm", "VAMS Calm"),
    ("VAMS_Sad", "VAMS Sad"),
    ("VAMS_Tense", "VAMS Tense"),
    ("KVIQ_Vis", "KVIQ-10 visual total"),
    ("KVIQ_Kin", "KVIQ-10 kinesthetic total"),
    ("VAS", "VAS pain (mean)"),
]

ALL_OUTCOMES = KINEMATIC_OUTCOMES + SECONDARY_CLIN


def _paired(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = ~(np.isnan(a) | np.isnan(b))
    a, b = a[m], b[m]
    if len(a) < 2:
        return None
    t, p = stats.ttest_rel(a, b)
    d = np.mean(b - a) / np.std(b - a, ddof=1) if np.std(b - a, ddof=1) > 0 else 0
    return {"n": len(a), "t": float(t), "p": float(p), "dz": float(d),
            "mean_pre": float(np.mean(a)), "mean_post": float(np.mean(b))}


def _welch(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    t, p = stats.ttest_ind(a, b, equal_var=False)
    s1, s2 = np.var(a, ddof=1), np.var(b, ddof=1)
    n1, n2 = len(a), len(b)
    pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    d = (np.mean(a) - np.mean(b)) / pooled if pooled > 0 else 0
    return {"n1": n1, "n2": n2, "t": float(t), "p": float(p), "d": float(d),
            "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b))}


def mixed_anova_2x2(df, pre_col, post_col, group_col="Group"):
    """2×2 mixed ANOVA via OLS (Group × Time). Returns F and p for interaction."""
    from statsmodels.formula.api import ols
    from statsmodels.stats.anova import anova_lm

    sub = df[[group_col, pre_col, post_col]].dropna()
    if len(sub) < 8:
        return None

    long = sub.melt(id_vars=[group_col], value_vars=[pre_col, post_col],
                    var_name="time", value_name="value")
    long["time"] = long["time"].map({pre_col: "pre", post_col: "post"})
    long[group_col] = long[group_col].astype(str)

    model = ols(f"value ~ C({group_col}) * C(time)", data=long).fit()
    table = anova_lm(model, typ=2)
    ss_total = table["sum_sq"].sum()

    def row(name):
        if name not in table.index:
            return None
        eta = float(table.loc[name, "sum_sq"] / ss_total) if ss_total > 0 else 0
        return {
            "F": float(table.loc[name, "F"]),
            "p": float(table.loc[name, "PR(>F)"]),
            "eta_p2": round(eta, 4),
        }

    return {
        "group": row(f"C({group_col})"),
        "time": row("C(time)"),
        "interaction": row(f"C({group_col}):C(time)"),
        "n": len(sub),
    }


def holm_bonferroni(p_values):
    """Return Holm-adjusted significance flags for a list of (name, p)."""
    items = sorted([(n, p) for n, p in p_values if p is not None], key=lambda x: x[1])
    m = len(items)
    results = []
    for i, (name, p) in enumerate(items):
        adj_alpha = 0.05 / (m - i)
        results.append({
            "name": name,
            "p": p,
            "holm_alpha": round(adj_alpha, 5),
            "significant": p <= adj_alpha,
        })
    return results


def analyze_outcome(df, base, label):
    pre, post = f"{base}_Pre", f"{base}_Post"
    if pre not in df.columns or post not in df.columns:
        return {"label": label, "base": base, "error": "columns missing"}

    df = df.copy()
    df["delta"] = df[post] - df[pre]
    aomi = df[df["Group"].astype(str) == "1"]
    ctrl = df[df["Group"].astype(str) == "2"]

    out = {
        "label": label,
        "base": base,
        "is_primary": base in PRIMARY_KIN_KEYS,
        "descriptives": {
            "aomi_pre": _desc(aomi[pre]),
            "aomi_post": _desc(aomi[post]),
            "ctrl_pre": _desc(ctrl[pre]),
            "ctrl_post": _desc(ctrl[post]),
        },
        "within_aomi": _paired(aomi[pre], aomi[post]),
        "within_ctrl": _paired(ctrl[pre], ctrl[post]),
        "between_delta": _welch(aomi["delta"], ctrl["delta"]),
        "baseline_equiv": _welch(aomi[pre], ctrl[pre]),
        "mixed_anova": mixed_anova_2x2(df, pre, post),
    }
    return out


def _desc(series):
    v = series.dropna()
    if len(v) == 0:
        return None
    return {"n": int(len(v)), "mean": round(float(v.mean()), 4), "sd": round(float(v.std(ddof=1)), 4)}


def run_study_analysis(csv_path):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if "Group" not in df.columns:
        raise ValueError("CSV must contain Group column (1=AOMI, 2=Control)")

    results = {
        "n_total": len(df),
        "n_aomi": int((df["Group"].astype(str) == "1").sum()),
        "n_control": int((df["Group"].astype(str) == "2").sum()),
        "outcomes": [],
    }

    for base, label in ALL_OUTCOMES:
        results["outcomes"].append(analyze_outcome(df, base, label))

    # Holm–Bonferroni on RQI kinematic family (k=6)
    primary_p = []
    for o in results["outcomes"]:
        if o.get("base") in PRIMARY_KIN_KEYS and not o.get("error"):
            ix = o.get("mixed_anova", {}) or {}
            p = ix.get("interaction", {}) or {}
            primary_p.append((o["base"], p.get("p")))
    results["holm_primary_kinematic"] = holm_bonferroni(primary_p)

    # Holm–Bonferroni on secondary kinematic family
    secondary_p = []
    for o in results["outcomes"]:
        if o.get("base") in PRIMARY_KIN_KEYS or o.get("error"):
            continue
        if o["base"] in SECONDARY_KIN_KEYS:
            ix = o.get("mixed_anova", {}) or {}
            p = ix.get("interaction", {}) or {}
            secondary_p.append((o["base"], p.get("p")))
    results["holm_secondary_kinematic"] = holm_bonferroni(secondary_p)

    return results


def format_report(results):
    lines = []
    l = lines.append
    l("=" * 72)
    l("PETTLEP AOMI RCT — STATISTICAL ANALYSIS REPORT")
    l(f"N = {results['n_total']} (AOMI n={results['n_aomi']}, Control n={results['n_control']})")
    l("=" * 72)
    l("")

    for o in results["outcomes"]:
        if o.get("error"):
            l(f"── {o['label']}: SKIPPED ({o['error']})")
            l("")
            continue
        tag = " [PRIMARY]" if o.get("is_primary") else ""
        l(f"── {o['label']} ({o['base']}){tag}")
        l("-" * 60)
        for k, title in [("aomi_pre", "AOMI Pre"), ("aomi_post", "AOMI Post"),
                         ("ctrl_pre", "Ctrl Pre"), ("ctrl_post", "Ctrl Post")]:
            d = o["descriptives"].get(k)
            if d:
                l(f"  {title:12} M={d['mean']:.3f}, SD={d['sd']:.3f}, n={d['n']}")
        if o.get("mixed_anova") and o["mixed_anova"].get("interaction"):
            ix = o["mixed_anova"]["interaction"]
            l(f"  Group×Time:  F={ix['F']:.3f}, p={ix['p']:.4f}, ηp²={ix['eta_p2']:.3f}")
        if o.get("between_delta"):
            b = o["between_delta"]
            l(f"  Δ AOMI vs Ctrl: t={b['t']:.3f}, p={b['p']:.4f}, d={b['d']:.3f}")
        l("")

    if results.get("holm_primary_kinematic"):
        l("HOLM–BONFERRONI (Reach Quality Index, k=6)")
        l("-" * 60)
        for h in results["holm_primary_kinematic"]:
            sig = " *" if h["significant"] else ""
            l(f"  {h['name']:16} p={h['p']:.4f}  Holm α={h['holm_alpha']:.4f}{sig}")
        l("")

    if results.get("holm_secondary_kinematic"):
        l(f"HOLM–BONFERRONI (secondary kinematic, k={len(SECONDARY_KIN_KEYS)})")
        l("-" * 60)
        for h in results["holm_secondary_kinematic"]:
            sig = " *" if h["significant"] else ""
            l(f"  {h['name']:16} p={h['p']:.4f}  Holm α={h['holm_alpha']:.4f}{sig}")
        l("")

    l("INTERPRETATION: Primary = Group×Time on RQI + 5 components (Holm k=6).")
    l("Partial η²: small=.01, medium=.06, large=.14 (Cohen, 1988).")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} master_study_data.csv [--out file.txt] [--json file.json]")
        return
    csv_path = sys.argv[1]
    out_txt = "study_results.txt"
    out_json = None
    if "--out" in sys.argv:
        out_txt = sys.argv[sys.argv.index("--out") + 1]
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]

    results = run_study_analysis(csv_path)
    report = format_report(results)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✓ Report: {out_txt}")
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"✓ JSON: {out_json}")


if __name__ == "__main__":
    main()
