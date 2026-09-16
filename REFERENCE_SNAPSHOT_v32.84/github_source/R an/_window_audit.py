# -*- coding: utf-8 -*-
"""Window detection audit — when/where does movement start and end?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAN = Path(__file__).resolve().parent
sys.path.insert(0, str(RAN))

from stroke_kinematic_pipeline import analyze_trial, _coords_for_trial, _infer_fs, prepare_trial_timeseries
from motion_invariants import (
    forward_reach_window,
    kinematic_reach_window,
    select_reach_window,
    table_reach_window,
)
from table_calibrator import calibrate_table_scale, px_to_cm

PART = Path(r"D:/Thesis app/participants")
OUT = Path(r"D:/Thesis app/NeuroLab/backend/outputs")

TRIALS = [
    ("Murat", "pre", OUT / "murat/pre_landmarks.csv", PART / "murat/pre.mp4", "right"),
    ("Murat", "post", OUT / "murat/post_landmarks.csv", PART / "murat/post.mp4", "right"),
    ("Murat", "healthy", OUT / "murat/healthy_landmarks.csv", PART / "murat/healthy side.mp4", "left"),
    ("Kurusal", "pre", PART / "kurusal/pre_20260617_142855_pre.csv", None, "left"),
    ("Kurusal", "post", PART / "kurusal/post_20260617_142949_post.csv", None, "left"),
    ("Kurusal", "healthy", PART / "kurusal/baseline_20260617_143108_healthy_side.csv", None, "right"),
    ("Zeinab", "pre", PART / "mediapipe/movs/zeyneb/pre_20260603_165439_pre.csv", None, "left"),
    ("Zeinab", "post", PART / "mediapipe/movs/zeyneb/post_20260603_165651_post.csv", None, "left"),
    ("Zeinab", "healthy", PART / "mediapipe/movs/zeyneb/baseline_20260603_165330_baseline.csv", None, "right"),
]


def trunk_peak_cm(trunk_x, trunk_y, palm_x, palm_y, s, e, cm_per_px):
    rel_x = palm_x - trunk_x
    rel_y = palm_y - trunk_y
    rx0, ry0 = float(rel_x[s]), float(rel_y[s])
    dists = np.hypot(rel_x[s : e + 1] - rx0, rel_y[s : e + 1] - ry0)
    return px_to_cm(float(np.max(dists)), cm_per_px)


def palm_net_cm(palm_x, palm_y, s, e, cm_per_px):
    d = float(np.hypot(palm_x[e] - palm_x[s], palm_y[e] - palm_y[s]))
    return px_to_cm(d, cm_per_px)


def fmt_win(s, e, fs):
    return f"f{s}-f{e} ({(e - s + 1) / fs:.2f}s @ {fs:.0f}Hz)"


print("=" * 90)
print("WINDOW AUDIT: onset/offset detection vs hand reach (cm, table 60cm calib)")
print("=" * 90)

for patient, label, csv_path, video, side in TRIALS:
    df, native_fs, _, _ = prepare_trial_timeseries(__import__("pandas").read_csv(csv_path))
    coords, sw, _ = _coords_for_trial(df, str(csv_path), side, 1920, 1080)
    px, py = coords["palm_x"], coords["palm_y"]
    tx, ty = coords["trunk_x"], coords["trunk_y"]
    n = len(px)
    role = "healthy" if label == "healthy" else label
    profile = "reference" if label == "healthy" else "affected"

    sparc_on, sparc_off = select_reach_window(px, py, native_fs, shoulder_width=sw, analysis_profile=profile)
    kin_on, kin_off = kinematic_reach_window(px, py, native_fs, shoulder_width=sw, analysis_profile=profile)
    fwd_on, fwd_off, disp_peak = forward_reach_window(px, py, native_fs, shoulder_width=sw)
    tbl_on, tbl_off = table_reach_window(px, py, native_fs, shoulder_width=sw)

    scale = calibrate_table_scale(str(csv_path), px, py, shoulder_width_px=sw, video_path=str(video) if video else None)
    cm_per_px = scale["cm_per_px"]

    r = analyze_trial(
        str(csv_path), affected_side=side, trial_role=label,
        video_path=str(video) if video else None,
    )

    full_peak = trunk_peak_cm(tx, ty, px, py, 0, n - 1, cm_per_px)
    rw0 = int(r.get("hand_reach_window_onset_frame", sparc_on))
    rw1 = int(r.get("hand_reach_window_offset_frame", sparc_off))

    print(f"\n{patient} / {label}  |  {n} frames native, fs={native_fs:.1f}Hz, dur={n/native_fs:.2f}s")
    print(f"  scale: {scale['scale_method']}  table_px={scale.get('table_width_px')}  cm/px={cm_per_px:.4f}")
    print(f"  HAND REACH window (forward):     {fmt_win(rw0, rw1, r['analysis_fs_hz'])}  [{r.get('hand_reach_window_onset_s')}–{r.get('hand_reach_window_offset_s')} s]")
    print(f"  SPARC window:                    f{r.get('reach_window_onset_frame')}-f{r.get('reach_window_offset_frame')} ({r.get('reach_window_duration_s')} s)")
    print(f"  Trunk/mtime window (kinematic):  {fmt_win(kin_on, kin_off, native_fs)}")
    print(f"  hand reach cm (pipeline):        {r.get('hand_displacement_norm'):.1f} cm  method={r.get('hand_displacement_method')}")
    print(f"  reach cm [full trial 2D peak]:   {full_peak:.1f}")
