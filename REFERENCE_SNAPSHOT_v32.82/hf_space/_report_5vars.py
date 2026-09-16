# -*- coding: utf-8 -*-
"""Report SPARC + 4 secondary kinematics for Murat, Kurusal, Zeinab."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stroke_kinematic_pipeline import analyze_patient_kinematic_triad

PART = Path(r"D:/Thesis app/participants")
OUT = Path(r"D:/Thesis app/NeuroLab/backend/outputs")

PATIENTS = [
    ("Murat", [
        ("pre", OUT / "murat/pre_landmarks.csv", PART / "murat/pre.mp4", "right"),
        ("post", OUT / "murat/post_landmarks.csv", PART / "murat/post.mp4", "right"),
        ("healthy", OUT / "murat/healthy_landmarks.csv", PART / "murat/healthy side.mp4", "left"),
    ]),
    ("Kurusal", [
        ("pre", PART / "kurusal/pre_20260617_142855_pre.csv", None, "left"),
        ("post", PART / "kurusal/post_20260617_142949_post.csv", None, "left"),
        ("healthy", PART / "kurusal/baseline_20260617_143108_healthy_side.csv", None, "right"),
    ]),
    ("Zeinab", [
        ("pre", PART / "mediapipe/movs/zeyneb/pre_20260603_165439_pre.csv", None, "left"),
        ("post", PART / "mediapipe/movs/zeyneb/post_20260603_165651_post.csv", None, "left"),
        ("healthy", PART / "mediapipe/movs/zeyneb/baseline_20260603_165330_baseline.csv", None, "right"),
    ]),
]

METRICS = [
    ("SPARC ↑", "sparc", False, "{:.3f}", "H > Post > Pre"),
    ("Trunk ratio ↓", "trunk_ratio", True, "{:.1f}%", "Pre > Post > H"),
    ("Shoulder elev ↓", "shoulder_elevation_norm", True, "{:.1f}%", "Pre > Post > H"),
    ("Movement time ↓", "movement_time_sec", False, "{:.2f} s", "Post ≤ Pre"),
    ("Peak velocity ↑", "peak_velocity_cm_s", False, "{:.1f} cm/s", "Post ≥ Pre"),
]


def _fmt(val, scale_pct, fmt):
    if val is None or not math.isfinite(float(val)):
        return "—"
    v = float(val) * 100 if scale_pct else float(val)
    return fmt.format(v)


def _pct(pre, post):
    if pre is None or post is None:
        return "—"
    pre, post = float(pre), float(post)
    if not (math.isfinite(pre) and math.isfinite(post)) or pre == 0:
        return "—"
    return f"{(post - pre) / abs(pre) * 100:+.1f}%"


def _check(key, pre, post, healthy):
    if not all(v is not None and math.isfinite(float(v)) for v in (pre, post, healthy)):
        return "—"
    pre, post, healthy = float(pre), float(post), float(healthy)
    if key == "sparc":
        return "✅" if healthy > post > pre else "❌"
    if key == "trunk_ratio":
        return "✅" if pre > post > healthy else "❌"
    if key == "shoulder_elevation_norm":
        return "✅" if pre >= post else "❌"
    if key == "movement_time_sec":
        return "✅" if post <= pre else "❌"
    if key == "peak_velocity_cm_s":
        return "✅" if post >= pre else "❌"
    return "—"


all_rows = {}
for name, trials in PATIENTS:
    paths = {label: (str(p), side, str(v) if v else None) for label, p, v, side in trials}
    bundle = analyze_patient_kinematic_triad(
        paths["pre"][0],
        paths["post"][0],
        paths["healthy"][0],
        pre_side=paths["pre"][1],
        post_side=paths["post"][1],
        healthy_side=paths["healthy"][1],
        pre_video=paths["pre"][2],
        post_video=paths["post"][2],
        healthy_video=paths["healthy"][2],
    )
    all_rows[name] = {k: bundle[k] for k in ("pre", "post", "healthy")}

print("\n# Kinematic report — SPARC (primary) + 4 secondary\n")
for name, trials in PATIENTS:
    rows = all_rows[name]
    print(f"## {name}\n")
    print("| Variable | Pre | Post | Healthy | Pre→Post | Expected |")
    print("|---|---:|---:|---:|---:|---|")
    for mname, key, scale, fmt, expected in METRICS:
        pre_v = rows["pre"].get(key)
        post_v = rows["post"].get(key)
        hel_v = rows["healthy"].get(key)
        ok = _check(key, pre_v, post_v, hel_v)
        print(
            f"| {mname} | {_fmt(pre_v, scale, fmt)} | {_fmt(post_v, scale, fmt)} | "
            f"{_fmt(hel_v, scale, fmt)} | {_pct(pre_v, post_v)} | {expected} {ok} |"
        )
    print()

# Summary table all patients SPARC + trunk
print("## Summary — Primary + Trunk (locked pattern)\n")
print("| Patient | SPARC Pre | Post | Healthy | Trunk Pre | Post | Healthy |")
print("|---|---:|---:|---:|---:|---:|---:|")
for name, _ in PATIENTS:
    r = all_rows[name]
    print(
        f"| {name} | {r['pre']['sparc']:.3f} | {r['post']['sparc']:.3f} | {r['healthy']['sparc']:.3f} | "
        f"{r['pre']['trunk_ratio']*100:.1f}% | {r['post']['trunk_ratio']*100:.1f}% | {r['healthy']['trunk_ratio']*100:.1f}% |"
    )
