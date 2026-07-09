"""
Preliminary stats for KT Study (Real-KT vs Sham-KT vs Control).
Usage: python run_preliminary_stats.py
"""

from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "KT_Study_Database.xlsx"
OUT = Path(__file__).resolve().parent / "kt_preliminary_stats.txt"


def main():
    df = pd.read_excel(DATA)
    df["Dominant Hand"] = df["Dominant Hand"].str.strip()
    lines = []

    for g in sorted(df["Group"].unique()):
        sub = df[df["Group"] == g]
        lines.append(f"\n=== {g} (n={len(sub)}) ===")
        lines.append(f"Age: {sub.Age.mean():.1f} +/- {sub.Age.std():.1f}")
        lines.append(f"Sex: {sub.Sex.value_counts().to_dict()}")
        for pre, post, name in [
            ("Grip-Pre", "Grip-Post", "Grip (kg)"),
            ("WPM-Pre", "WPM-Post", "WPM"),
            ("Mean RT-Pre(ms)", "Mean RT-Post(ms)", "RT (ms)"),
            ("NHPT-Pre (sec)", "NHPT-Post (sec)", "NHPT (sec)"),
        ]:
            d = sub[post] - sub[pre]
            t, p = stats.ttest_rel(sub[pre], sub[post])
            lines.append(
                f"{name}: Pre={sub[pre].mean():.2f}, Post={sub[post].mean():.2f}, "
                f"Delta={d.mean():.2f}, paired t p={p:.4f}"
            )
        for col in ["Vas-Performance", "VAS-Ease", "VAS-Comfort", "GRC"]:
            lines.append(f"{col}: mean={sub[col].mean():.1f} +/- {sub[col].std():.1f}")

    lines.append("\n=== Baseline equivalence (Pre scores) ===")
    for col in ["Grip-Pre", "WPM-Pre", "Mean RT-Pre(ms)", "NHPT-Pre (sec)", "Age"]:
        groups = [df[df.Group == g][col].values for g in sorted(df["Group"].unique())]
        f, p = stats.f_oneway(*groups)
        lines.append(f"{col}: F={f:.2f}, p={p:.4f}")

    lines.append("\n=== Normality of change scores (Shapiro) ===")
    for col_pre, col_post, label in [
        ("Grip-Pre", "Grip-Post", "Grip"),
        ("WPM-Pre", "WPM-Post", "WPM"),
    ]:
        for g in sorted(df["Group"].unique()):
            sub = df[df["Group"] == g]
            d = sub[col_post] - sub[col_pre]
            w, p = stats.shapiro(d)
            lines.append(f"{g} delta {label}: W={w:.3f}, p={p:.4f}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
