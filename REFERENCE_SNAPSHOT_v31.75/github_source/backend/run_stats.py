"""
run_stats.py — Kinematic analysis: Mixed ANOVA + post-hoc tests

Usage:
  .\venv\Scripts\python.exe run_stats.py spss_kinematics.csv --out stats_results.txt

Requires: statsmodels, pandas, scipy
"""

import sys, os
import pandas as pd
import numpy as np
from scipy import stats

PRIMARY_VARS = [
    ("sparc", "SPARC (smoothness)"),
    ("trunk_ratio", "Trunk ratio"),
    ("shoulder_vert_norm", "Shoulder elevation (norm)"),
    ("elbow_angle_mean", "Elbow angle mean (deg)"),
    ("movement_time_sec", "Movement time (s)"),
    ("peak_velocity_px_s", "Peak velocity (px/s)"),
]

TIMEPOINTS = ["pre", "post", "baseline"]


def welch_ttest(a, b, label_a, label_b):
    """Welch's t-test with Cohen's d."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    t, p = stats.ttest_ind(a, b, equal_var=False)
    n1, n2 = len(a), len(b)
    s1, s2 = np.var(a, ddof=1), np.var(b, ddof=1)
    cohens_d = (np.mean(a) - np.mean(b)) / np.sqrt(((n1-1)*s1 + (n2-1)*s2) / (n1+n2-2))
    return {"t": t, "df": n1 + n2 - 2, "p": p, "d": cohens_d,
            "mean_a": np.mean(a), "mean_b": np.mean(b),
            "sd_a": np.std(a, ddof=1), "sd_b": np.std(b, ddof=1),
            "n_a": n1, "n_b": n2}


def paired_ttest(a, b, label_a, label_b):
    """Paired t-test with Cohen's dz."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    valid = ~(np.isnan(a) | np.isnan(b))
    a, b = a[valid], b[valid]
    if len(a) < 2:
        return None
    t, p = stats.ttest_rel(a, b)
    d = np.mean(a - b) / np.std(a - b, ddof=1)
    return {"t": t, "df": len(a) - 1, "p": p, "dz": d,
            "mean_a": np.mean(a), "mean_b": np.mean(b),
            "sd_a": np.std(a, ddof=1), "sd_b": np.std(b, ddof=1),
            "n": len(a)}


def mixed_anova(df_wide, var, time_cols, group_col="group"):
    """Perform 2×2 Mixed ANOVA (Group × Time) using OLS."""
    from statsmodels.formula.api import ols
    from statsmodels.stats.anova import anova_lm

    # Reshape to long format
    id_vars = ["patient_id", group_col]
    df_long = df_wide.melt(id_vars=id_vars, value_vars=time_cols,
                           var_name="time", value_name="value")
    df_long = df_long.dropna(subset=["value"]).copy()
    df_long["time"] = df_long["time"].astype(str)
    df_long[group_col] = df_long[group_col].astype(str)

    if len(df_long) < 10:
        return None

    formula = f"value ~ C({group_col}) * C(time)"
    model = ols(formula, data=df_long).fit()
    table = anova_lm(model, typ=2)
    eta_sq = table["sum_sq"] / table["sum_sq"].sum()
    return {
        "group_F": table.loc[f"C({group_col})", "F"],
        "group_p": table.loc[f"C({group_col})", "PR(>F)"],
        "time_F": table.loc[f"C(time)", "F"],
        "time_p": table.loc[f"C(time)", "PR(>F)"],
        "interaction_F": table.loc[f"C({group_col}):C(time)", "F"],
        "interaction_p": table.loc[f"C({group_col}):C(time)", "PR(>F)"],
        "eta_sq": eta_sq.to_dict(),
    }


def run_analysis(csv_path, out_path):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    groups = sorted(df["group"].dropna().unique())
    print(f"Groups: {groups}")
    print(f"N: {len(df)}")
    print()

    lines = []
    l = lambda s="": lines.append(s)

    l("=" * 72)
    l("KINEMATIC ANALYSIS RESULTS")
    l(f"File: {os.path.basename(csv_path)}")
    l(f"N = {len(df)} participants ({', '.join(groups)})")
    l("=" * 72)
    l()

    for var, label in PRIMARY_VARS:
        l(f"{'─' * 72}")
        l(f"  {label} ({var})")
        l(f"{'─' * 72}")
        l()

        # Descriptive per timepoint
        for tp in TIMEPOINTS:
            col = f"{tp}_{var}"
            if col in df.columns:
                vals = df[col].dropna()
                if len(vals):
                    l(f"  {tp.capitalize():>10}: M={vals.mean():.3f}, SD={vals.std():.3f}, n={len(vals)}")
        l()

        # Paired: Pre vs Post
        if f"pre_{var}" in df.columns and f"post_{var}" in df.columns:
            res = paired_ttest(df[f"pre_{var}"], df[f"post_{var}"], "Pre", "Post")
            if res:
                l(f"  Pre vs Post (paired t): t({res['df']}) = {res['t']:.3f}, "
                  f"p = {res['p']:.4f}, dz = {res['dz']:.3f}")

        # Paired: Baseline vs Pre, Post vs Baseline
        if "baseline" in TIMEPOINTS:
            if f"baseline_{var}" in df.columns and f"pre_{var}" in df.columns:
                res = paired_ttest(df[f"baseline_{var}"], df[f"pre_{var}"], "Healthy", "Pre")
                if res:
                    l(f"  Healthy vs Pre (paired t): t({res['df']}) = {res['t']:.3f}, "
                      f"p = {res['p']:.4f}, dz = {res['dz']:.3f}")
            if f"post_{var}" in df.columns and f"baseline_{var}" in df.columns:
                res = paired_ttest(df[f"post_{var}"], df[f"baseline_{var}"], "Post", "Healthy")
                if res:
                    l(f"  Post vs Healthy (paired t): t({res['df']}) = {res['t']:.3f}, "
                      f"p = {res['p']:.4f}, dz = {res['dz']:.3f}")

        l()

        # Mixed ANOVA if 2+ groups
        if len(groups) >= 2 and f"pre_{var}" in df.columns and f"post_{var}" in df.columns:
            try:
                anova = mixed_anova(df, var, [f"pre_{var}", f"post_{var}"])
                if anova:
                    l(f"  2×2 Mixed ANOVA (Group × Time):")
                    l(f"    Group:       F = {anova['group_F']:.3f}, p = {anova['group_p']:.4f}")
                    l(f"    Time:        F = {anova['time_F']:.3f}, p = {anova['time_p']:.4f}")
                    l(f"    Interaction: F = {anova['interaction_F']:.3f}, p = {anova['interaction_p']:.4f}")
            except Exception as e:
                l(f"    Mixed ANOVA error: {e}")

        # Between-group on delta
        if len(groups) >= 2 and f"pre_{var}" in df.columns and f"post_{var}" in df.columns:
            delta_col = f"delta_{var}_post_pre"
            if delta_col not in df.columns:
                df[delta_col] = df[f"post_{var}"] - df[f"pre_{var}"]
            for g in groups:
                vals = df.loc[df["group"] == g, delta_col].dropna()
                if len(vals):
                    l(f"    {g} Δ Post-Pre: M={vals.mean():.3f}, SD={vals.std():.3f}, n={len(vals)}")
            g1 = df.loc[df["group"] == groups[0], delta_col].dropna()
            g2 = df.loc[df["group"] == groups[1], delta_col].dropna()
            if len(g1) >= 2 and len(g2) >= 2:
                res = welch_ttest(g1, g2, groups[0], groups[1])
                if res:
                    l(f"    Δ Post-Pre {groups[0]} vs {groups[1]}: "
                      f"t({res['df']}) = {res['t']:.3f}, p = {res['p']:.4f}, d = {res['d']:.3f}")
        l()

    # Summary
    l(f"{'=' * 72}")
    l("INTERPRETATION GUIDE")
    l(f"{'=' * 72}")
    l("  Cohen's d: small=0.2, medium=0.5, large=0.8")
    l("  Cohen's dz (paired): small=0.2, medium=0.5, large=0.8")
    l("  Partial eta-squared: small=.01, medium=.06, large=.14")
    l("  Significance: * p<.05, ** p<.01, *** p<.001")
    l()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✓ Results written to: {out_path}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} spss_kinematics.csv --out stats_results.txt")
        return
    csv_path = sys.argv[1]
    out_path = "stats_results.txt"
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return
    run_analysis(csv_path, out_path)


if __name__ == "__main__":
    main()
