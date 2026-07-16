# -*- coding: utf-8 -*-
"""
 compare_trials_graph.py

 Compare affected (pre/post) to healthy reference using graph-based kinematics:
   - Path straightness index (PSI): straight-line displacement / actual path length
   - Normalized jerk cost (NJC)
   - Coefficient of variation of speed (CV_speed)
   - SPARC for reference (forward-peak window)
   - All other variables as % of healthy reference

 Works with video files and CSV landmark files.
"""
from __future__ import annotations

from typing import Tuple

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
from stroke_kinematic_pipeline import analyze_trial, calculate_sparc
from motion_invariants import body_frame_palm


def _load_landmarks(path: str, side: str):
    p = Path(path)
    if p.suffix.lower() in (".mp4", ".mov", ".avi"):
        csv_path = p.parent / "extracted" / (p.stem + "_landmarks.csv")
    else:
        csv_path = p
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path)
    s = side.upper()
    fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else 1920
    fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else 1080
    cols = [f"{s}_WRIST_X", f"{s}_WRIST_Y"]
    if any(c not in df.columns for c in cols):
        return None
    return {
        "df": df, "side": s, "fw": fw, "fh": fh,
        "px": df[f"{s}_WRIST_X"].values * fw,
        "py": df[f"{s}_WRIST_Y"].values * fh,
    }


def _shoulder_width(df: pd.DataFrame, fw: int, fh: int) -> float:
    if "LEFT_SHOULDER_X" not in df.columns or "RIGHT_SHOULDER_X" not in df.columns:
        return float("nan")
    return float(np.median(np.hypot(
        df["LEFT_SHOULDER_X"].values * fw - df["RIGHT_SHOULDER_X"].values * fw,
        df["LEFT_SHOULDER_Y"].values * fh - df["RIGHT_SHOULDER_Y"].values * fh,
    )))


def _fs(df: pd.DataFrame) -> float:
    if "time" in df.columns and len(df) > 1:
        return float(1.0 / np.median(np.diff(df["time"].values)))
    return 30.0


def _native_window_from_analyze_trial(metrics: dict, native_fs: float, n_native: int) -> Tuple[int, int]:
    """Map analyze_trial reach-window seconds back to native CSV frame indices."""
    onset_s = metrics.get("reach_window_onset_s")
    offset_s = metrics.get("reach_window_offset_s")
    if onset_s is None or offset_s is None or not native_fs or native_fs <= 0 or n_native <= 0:
        return 0, max(0, n_native - 1)
    on = int(round(float(onset_s) * native_fs))
    off = int(round(float(offset_s) * native_fs))
    on = max(0, min(on, n_native - 1))
    off = max(on, min(off, n_native - 1))
    return on, off


def _graph_metrics(px: np.ndarray, py: np.ndarray, fs: float, on: int, off: int, sw: float):
    seg_px = px[on:off + 1]
    seg_py = py[on:off + 1]
    n = len(seg_px)
    if n < 10:
        return None

    # Path straightness: straight-line displacement / total path length
    straight = np.hypot(seg_px[-1] - seg_px[0], seg_py[-1] - seg_py[0])
    path_len = float(np.sum(np.hypot(np.diff(seg_px), np.diff(seg_py))))
    psi = straight / path_len if path_len > 0 else float("nan")

    # Speed and acceleration
    vx = np.gradient(seg_px) * fs
    vy = np.gradient(seg_py) * fs
    speed = np.hypot(vx, vy)
    ax = np.gradient(vx) * fs
    ay = np.gradient(vy) * fs

    # Coefficient of variation of speed
    cv_speed = float(np.std(speed) / np.mean(speed)) if np.mean(speed) > 0 else float("nan")

    # Normalized jerk cost (Rohrer & Hogan style)
    jerk = np.hypot(np.gradient(ax) * fs, np.gradient(ay) * fs)
    movement_time = n / fs
    if movement_time > 0 and path_len > 0:
        njc = float(np.sum(jerk ** 2) * (movement_time ** 5) / (path_len ** 2))
    else:
        njc = float("nan")

    # SPARC forward-peak (body-frame)
    x0, y0 = float(np.median(seg_px[:max(3, n // 10)])), float(np.median(seg_py[:max(3, n // 10)]))
    bx = (seg_px - x0) / sw
    by = (seg_py - y0) / sw
    sparc = calculate_sparc(bx, by, fs=fs)

    return {
        "sparc": round(sparc, 3),
        "path_straightness_index": round(psi, 4),
        "normalized_jerk_cost": round(njc, 2),
        "cv_speed": round(cv_speed, 4),
        "reach_amplitude_sw": round(straight / sw, 3),
        "movement_time_sec": round(movement_time, 3),
        "peak_velocity_px_s": round(float(np.max(speed)), 2),
    }


def _analyze_path(path: str, side: str, view: str = "oblique") -> dict:
    from motion_invariants import infer_trial_role
    role = infer_trial_role(path, affected_side=side)
    r = analyze_trial(path, affected_side=side, trial_role=role, camera_view=view)
    lm = _load_landmarks(path, side)
    if lm is None:
        return {
            "sparc": r.get("sparc"),
            "trunk_ratio": r.get("trunk_ratio"),
            "shoulder_elevation_cm": r.get("shoulder_elevation_cm") or (
                round(r.get("shoulder_elevation_abs_px") * (40.0 / r.get("shoulder_width_px")), 2)
                if r.get("shoulder_elevation_abs_px") and r.get("shoulder_width_px") else None
            ),
            "hand_displacement_cm": r.get("hand_displacement_cm"),
            "trunk_cheat_ratio": r.get("trunk_cheat_ratio"),
            "error": "landmarks not available",
        }

    df, fw, fh = lm["df"], lm["fw"], lm["fh"]
    px, py = lm["px"], lm["py"]
    sw = _shoulder_width(df, fw, fh)
    if not (sw > 0):
        sw = max(np.ptp(px), np.ptp(py), 50.0)
    fs = _fs(df)

    # Use the literature-matched reach window from analyze_trial (mapped back to native CSV indices).
    # This captures the same main reach as the validated pipeline, avoiding the first-speed-segment
    # bias of forward_reach_window that can compare non-comparable movement phases.
    onset_s = r.get("reach_window_onset_s")
    offset_s = r.get("reach_window_offset_s")
    native_fs = r.get("native_fs_hz", fs)
    if onset_s is not None and offset_s is not None and native_fs and native_fs > 0:
        on = int(round(float(onset_s) * native_fs))
        off = int(round(float(offset_s) * native_fs))
    else:
        from motion_invariants import forward_reach_window
        on, off, _ = forward_reach_window(px, py, fs, shoulder_width=sw)
    on = max(0, min(on, len(px) - 1))
    off = max(on, min(off, len(px) - 1))

    if off - on + 1 < 10:
        return {"sparc": r.get("sparc"), "error": "reach window too short"}

    metrics = _graph_metrics(px, py, fs, on, off, sw)
    if metrics is None:
        return {"sparc": r.get("sparc"), "error": "metrics computation failed"}

    # Preserve window timing so downstream peak-velocity calculation uses the same window.
    metrics["reach_window_onset_s"] = r.get("reach_window_onset_s")
    metrics["reach_window_offset_s"] = r.get("reach_window_offset_s")

    # Prefer validated compensation metrics from analyze_trial when available.
    metrics["trunk_ratio"] = round(float(r.get("trunk_ratio")), 4) if r.get("trunk_ratio") is not None and np.isfinite(float(r.get("trunk_ratio"))) else None
    metrics["trunk_cheat_ratio"] = round(float(r.get("trunk_cheat_ratio")), 3) if r.get("trunk_cheat_ratio") is not None and np.isfinite(float(r.get("trunk_cheat_ratio"))) else None
    metrics["hand_displacement_cm"] = round(float(r.get("hand_displacement_cm")), 2) if r.get("hand_displacement_cm") is not None and np.isfinite(float(r.get("hand_displacement_cm"))) else None

    # Shoulder elevation: prefer pipeline value, fallback to window-based estimate
    shoulder_elev_cm = None
    if r.get("shoulder_elevation_abs_px") is not None and r.get("shoulder_width_px"):
        shoulder_elev_cm = float(r["shoulder_elevation_abs_px"]) * (40.0 / float(r["shoulder_width_px"]))
    elif r.get("shoulder_elevation_cm") is not None:
        shoulder_elev_cm = float(r["shoulder_elevation_cm"])
    if shoulder_elev_cm is None:
        s = side.upper()
        if f"{s}_SHOULDER_Y" in df.columns:
            sy = df[f"{s}_SHOULDER_Y"].values * fh
            shoulder_elev_px = float(np.max(sy[on:off + 1]) - np.min(sy[on:off + 1]))
            shoulder_elev_cm = shoulder_elev_px * (40.0 / sw)
    metrics["shoulder_elevation_cm"] = round(shoulder_elev_cm, 2) if shoulder_elev_cm is not None else None

    # Elbow angle if available
    s = side.upper()
    if f"{s}_ELBOW_X" in df.columns and f"{s}_SHOULDER_X" in df.columns and f"{s}_WRIST_X" in df.columns:
        ex = df[f"{s}_ELBOW_X"].values * fw
        ey = df[f"{s}_ELBOW_Y"].values * fh
        sx = df[f"{s}_SHOULDER_X"].values * fw
        sy_elb = df[f"{s}_SHOULDER_Y"].values * fh
        peak_frame = on + int(np.argmax(np.hypot(px[on:off + 1] - px[on], py[on:off + 1] - py[on])))
        v1 = np.array([sx[peak_frame] - ex[peak_frame], sy_elb[peak_frame] - ey[peak_frame]])
        v2 = np.array([px[peak_frame] - ex[peak_frame], py[peak_frame] - ey[peak_frame]])
        m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if m1 > 1e-6 and m2 > 1e-6:
            cos_a = np.clip(float(np.dot(v1, v2) / (m1 * m2)), -1.0, 1.0)
            metrics["elbow_angle_deg"] = round(float(np.arccos(cos_a) * 180.0 / np.pi), 1)
        else:
            metrics["elbow_angle_deg"] = None
    else:
        metrics["elbow_angle_deg"] = None

    return metrics


def relative_pct(affected_val, healthy_val):
    if affected_val is None or healthy_val is None:
        return None
    try:
        a, h = float(affected_val), float(healthy_val)
        if not (np.isfinite(a) and np.isfinite(h)) or h == 0:
            return None
        return round((a / h) * 100, 1)
    except Exception:
        return None


def clinical_summary(healthy: dict, affected: dict) -> dict:
    """Interpret compensation vs smoothness trade-off for stroke reach-to-target."""
    notes = []
    lower_better = {
        "trunk_ratio": "trunk compensation",
        "shoulder_elevation_cm": "shoulder hiking",
        "trunk_cheat_ratio": "trunk cheat",
    }
    higher_better = {
        "hand_displacement_cm": "independent reach distance",
        "peak_velocity_pct": "peak velocity",
    }
    for key, label in lower_better.items():
        h, a = healthy.get(key), affected.get(key)
        if h is not None and a is not None and np.isfinite(float(h)) and np.isfinite(float(a)):
            if float(a) < float(h) * 0.9:
                notes.append(f"{label} is lower than healthy reference ({relative_pct(a, h)}%).")
            elif float(a) > float(h) * 1.1:
                notes.append(f"{label} is higher than healthy reference ({relative_pct(a, h)}%), indicating compensation.")
    for key, label in higher_better.items():
        h, a = healthy.get(key), affected.get(key)
        if h is not None and a is not None and np.isfinite(float(h)) and np.isfinite(float(a)):
            if float(a) > float(h) * 1.1:
                notes.append(f"{label} exceeds healthy reference ({relative_pct(a, h)}%).")
            elif float(a) < float(h) * 0.9:
                notes.append(f"{label} is below healthy reference ({relative_pct(a, h)}%).")

    sparc_h = healthy.get("sparc")
    sparc_a = affected.get("sparc")
    if sparc_h is not None and sparc_a is not None and np.isfinite(float(sparc_h)) and np.isfinite(float(sparc_a)):
        if float(sparc_a) < float(sparc_h):
            notes.append(
                "SPARC is more negative than healthy reference: the selected reach window contains more speed-segmentation / deceleration corrections. "
                "When compensation metrics improved simultaneously, this often reflects more independent arm control rather than worse recovery."
            )
        else:
            notes.append("SPARC is close to or better than healthy reference.")

    return {"notes": notes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthy", required=True)
    parser.add_argument("--affected", required=True)
    parser.add_argument("--healthy-side", required=True, choices=["left", "right"])
    parser.add_argument("--affected-side", required=True, choices=["left", "right"])
    parser.add_argument("--label", default="affected")
    parser.add_argument("--view", default="oblique", choices=["frontal", "oblique", "sagittal"])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    h = _analyze_path(args.healthy, args.healthy_side, args.view)
    a = _analyze_path(args.affected, args.affected_side, args.view)

    # For peak velocity, use relative px/s from the validated reach windows
    h_lm = _load_landmarks(args.healthy, args.healthy_side)
    a_lm = _load_landmarks(args.affected, args.affected_side)
    peak_v_pct = None
    if h_lm is not None and a_lm is not None:
        h_fs = _fs(h_lm["df"])
        a_fs = _fs(a_lm["df"])
        h_sw = _shoulder_width(h_lm["df"], h_lm["fw"], h_lm["fh"])
        a_sw = _shoulder_width(a_lm["df"], a_lm["fw"], a_lm["fh"])
        h_sw = h_sw if h_sw > 0 else max(np.ptp(h_lm["px"]), np.ptp(h_lm["py"]), 50.0)
        a_sw = a_sw if a_sw > 0 else max(np.ptp(a_lm["px"]), np.ptp(a_lm["py"]), 50.0)
        h_on, h_off = _native_window_from_analyze_trial(h, h_fs, len(h_lm["px"]))
        a_on, a_off = _native_window_from_analyze_trial(a, a_fs, len(a_lm["px"]))
        if h_off > h_on and a_off > a_on:
            h_v = np.hypot(np.gradient(h_lm["px"]) * h_fs, np.gradient(h_lm["py"]) * h_fs)
            a_v = np.hypot(np.gradient(a_lm["px"]) * a_fs, np.gradient(a_lm["py"]) * a_fs)
            h_pv = np.max(h_v[h_on:h_off + 1])
            a_pv = np.max(a_v[a_on:a_off + 1])
            if h_pv > 0:
                peak_v_pct = round((a_pv / h_pv) * 100, 1)

    relative = {
        "sparc": relative_pct(a.get("sparc"), h.get("sparc")),
        "path_straightness_index": relative_pct(a.get("path_straightness_index"), h.get("path_straightness_index")),
        "normalized_jerk_cost": relative_pct(a.get("normalized_jerk_cost"), h.get("normalized_jerk_cost")),
        "cv_speed": relative_pct(a.get("cv_speed"), h.get("cv_speed")),
        "reach_amplitude_sw": relative_pct(a.get("reach_amplitude_sw"), h.get("reach_amplitude_sw")),
        "movement_time_sec": relative_pct(a.get("movement_time_sec"), h.get("movement_time_sec")),
        "peak_velocity_pct": peak_v_pct,
        "trunk_ratio": relative_pct(a.get("trunk_ratio"), h.get("trunk_ratio")),
        "trunk_cheat_ratio": relative_pct(a.get("trunk_cheat_ratio"), h.get("trunk_cheat_ratio")),
        "shoulder_elevation_cm": relative_pct(a.get("shoulder_elevation_cm"), h.get("shoulder_elevation_cm")),
        "hand_displacement_cm": relative_pct(a.get("hand_displacement_cm"), h.get("hand_displacement_cm")),
        "elbow_angle_deg": relative_pct(a.get("elbow_angle_deg"), h.get("elbow_angle_deg")),
    }

    report = {
        "healthy": {"video": args.healthy, "side": args.healthy_side, **h, "peak_velocity_pct": 100.0},
        args.label: {"video": args.affected, "side": args.affected_side, **a, "peak_velocity_pct": peak_v_pct},
        "relative_to_healthy_percent": relative,
        "clinical_notes": {
            "trunk_ratio_lower_is_better": True,
            "shoulder_elevation_lower_is_better": True,
            "trunk_cheat_ratio_lower_is_better": True,
            "hand_displacement_higher_is_better": True,
        },
        "clinical_summary": clinical_summary(h, a),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved report to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
