# -*- coding: utf-8 -*-
"""
 compare_trials.py

 Compare affected (pre/post) to healthy reference using:
   - SPARC: absolute + within-patient change (pre vs post)
   - Other kinematics: percentage of healthy reference

 Works with both video files and CSV landmark files.

 Usage:
   python compare_trials.py --healthy path/to/healthy.MOV --affected path/to/affected.mov \
                            --healthy-side left --affected-side right --label affected --out report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
from stroke_kinematic_pipeline import analyze_trial, calculate_sparc
from motion_invariants import body_frame_palm, compute_elbow_reach_metric


def _native_window_from_analyze_trial(metrics: dict, native_fs: float, n_native: int):
    onset_s = metrics.get("reach_window_onset_s")
    offset_s = metrics.get("reach_window_offset_s")
    if onset_s is None or offset_s is None or not native_fs or native_fs <= 0 or n_native <= 0:
        return 0, max(0, n_native - 1)
    on = int(round(float(onset_s) * native_fs))
    off = int(round(float(offset_s) * native_fs))
    on = max(0, min(on, n_native - 1))
    off = max(on, min(off, n_native - 1))
    return on, off


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
    cols = [f"{s}_WRIST_X", f"{s}_WRIST_Y", f"{s}_SHOULDER_X", f"{s}_SHOULDER_Y",
            f"{s}_ELBOW_X", f"{s}_ELBOW_Y"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return None
    return {
        "df": df, "side": s, "fw": fw, "fh": fh,
        "px": df[f"{s}_WRIST_X"].values * fw,
        "py": df[f"{s}_WRIST_Y"].values * fh,
        "sx": df[f"{s}_SHOULDER_X"].values * fw,
        "sy": df[f"{s}_SHOULDER_Y"].values * fh,
        "ex": df[f"{s}_ELBOW_X"].values * fw,
        "ey": df[f"{s}_ELBOW_Y"].values * fh,
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


def _analyze_path(path: str, side: str, view: str = "oblique") -> dict:
    """Analyze one video or CSV using the validated pipeline reach window."""
    from motion_invariants import infer_trial_role
    role = infer_trial_role(path, affected_side=side)
    r = analyze_trial(path, affected_side=side, trial_role=role, camera_view=view)
    lm = _load_landmarks(path, side)
    if lm is None:
        return {
            "sparc": r.get("sparc"),
            "reach_amplitude_sw": r.get("reach_amplitude_sw"),
            "movement_time_sec": r.get("movement_time_sec"),
            "peak_velocity_pct": None,
            "trunk_ratio": r.get("trunk_ratio"),
            "shoulder_elevation_cm": r.get("shoulder_elevation_cm"),
            "elbow_angle_deg": r.get("elbow_angle_deg"),
            "hand_displacement_cm": r.get("hand_displacement_cm"),
            "trunk_cheat_ratio": r.get("trunk_cheat_ratio"),
            "reach_window_onset_s": r.get("reach_window_onset_s"),
            "reach_window_offset_s": r.get("reach_window_offset_s"),
        }

    df, s, fw, fh = lm["df"], lm["side"], lm["fw"], lm["fh"]
    px, py, sx, sy, ex, ey = lm["px"], lm["py"], lm["sx"], lm["sy"], lm["ex"], lm["ey"]
    sw = _shoulder_width(df, fw, fh)
    if not (sw > 0):
        sw = max(np.ptp(px), np.ptp(py), 50.0)
    fs = _fs(df)

    # Use the validated pipeline window mapped to native CSV indices.
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
        return {
            "sparc": r.get("sparc"),
            "reach_amplitude_sw": r.get("reach_amplitude_sw"),
            "movement_time_sec": r.get("movement_time_sec"),
            "peak_velocity_pct": None,
            "trunk_ratio": r.get("trunk_ratio"),
            "shoulder_elevation_cm": r.get("shoulder_elevation_cm"),
            "elbow_angle_deg": r.get("elbow_angle_deg"),
            "hand_displacement_cm": r.get("hand_displacement_cm"),
            "trunk_cheat_ratio": r.get("trunk_cheat_ratio"),
            "reach_window_onset_s": onset_s,
            "reach_window_offset_s": offset_s,
        }

    bx, by, _, _ = body_frame_palm(px, py, sx, sy, sw)

    # Amplitude matching on the validated window keeps the comparison fair.
    amp_total = float(np.hypot(bx[off] - bx[on], by[off] - by[on]))
    target_amp = min(0.9, max(0.15, amp_total))
    cum = np.maximum.accumulate(np.hypot(bx[on:off + 1] - bx[on], by[on:off + 1] - by[on]))
    idx = np.searchsorted(cum, target_amp, side="right")
    if idx == 0:
        idx = len(cum)
    matched_off = on + idx - 1
    if matched_off - on + 1 < 10:
        matched_off = min(off, on + 9)

    sparc = calculate_sparc(bx[on:matched_off + 1], by[on:matched_off + 1], fs=fs)
    amp = float(np.hypot(bx[matched_off] - bx[on], by[matched_off] - by[on]))
    dur = (matched_off - on + 1) / fs

    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    spd = np.sqrt(vx ** 2 + vy ** 2)
    peak_v = float(np.max(spd[on:matched_off + 1]))

    elbow_res = compute_elbow_reach_metric(sx, sy, ex, ey, px, py, on, matched_off, camera_view=view)
    elbow_angle = elbow_res.get("primary") if elbow_res else None

    cm_per_px = 40.0 / sw
    peak_v_cm_s = peak_v * cm_per_px
    shoulder_elev_abs_px = float(np.max(sy[on:matched_off + 1]) - np.min(sy[on:matched_off + 1]))
    shoulder_elev_cm = shoulder_elev_abs_px * cm_per_px

    # Prefer validated pipeline compensation metrics; fall back to raw recompute.
    trunk_ratio = r.get("trunk_ratio")
    if trunk_ratio is None or not np.isfinite(float(trunk_ratio)):
        if "LEFT_HIP_X" in df.columns and "RIGHT_HIP_X" in df.columns:
            hx = (df["LEFT_HIP_X"].values * fw + df["RIGHT_HIP_X"].values * fw) / 2.0
            hy = (df["LEFT_HIP_Y"].values * fh + df["RIGHT_HIP_Y"].values * fh) / 2.0
        elif "LEFT_SHOULDER_X" in df.columns and "RIGHT_SHOULDER_X" in df.columns:
            hx = (df["LEFT_SHOULDER_X"].values * fw + df["RIGHT_SHOULDER_X"].values * fw) / 2.0
            hy = (df["LEFT_SHOULDER_Y"].values * fh + df["RIGHT_SHOULDER_Y"].values * fh) / 2.0
        else:
            hx = hy = None
        if hx is not None:
            trunk_path = float(np.sum(np.hypot(np.diff(hx[on:matched_off + 1]), np.diff(hy[on:matched_off + 1]))))
            palm_path = float(np.sum(np.hypot(np.diff(px[on:matched_off + 1]), np.diff(py[on:matched_off + 1]))))
            if palm_path > 0:
                trunk_ratio = trunk_path / palm_path

    return {
        "sparc": round(sparc, 3),
        "reach_amplitude_sw": round(amp, 3),
        "movement_time_sec": round(dur, 3),
        "peak_velocity_pct": 100.0,
        "trunk_ratio": round(float(trunk_ratio), 4) if trunk_ratio is not None and np.isfinite(float(trunk_ratio)) else None,
        "shoulder_elevation_cm": round(shoulder_elev_cm, 2),
        "elbow_angle_deg": round(float(elbow_angle), 1) if elbow_angle is not None and np.isfinite(float(elbow_angle)) else None,
        "hand_displacement_cm": round(float(r.get("hand_displacement_cm")), 2) if r.get("hand_displacement_cm") is not None and np.isfinite(float(r.get("hand_displacement_cm"))) else None,
        "trunk_cheat_ratio": round(float(r.get("trunk_cheat_ratio")), 3) if r.get("trunk_cheat_ratio") is not None and np.isfinite(float(r.get("trunk_cheat_ratio"))) else None,
        "reach_window_onset_s": onset_s,
        "reach_window_offset_s": offset_s,
    }


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthy", required=True)
    parser.add_argument("--affected", required=True)
    parser.add_argument("--healthy-side", required=True, choices=["left", "right"])
    parser.add_argument("--affected-side", required=True, choices=["left", "right"])
    parser.add_argument("--label", default="affected", help="e.g. pre or post")
    parser.add_argument("--view", default="oblique", choices=["frontal", "oblique", "sagittal"])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    h = _analyze_path(args.healthy, args.healthy_side, args.view)
    a = _analyze_path(args.affected, args.affected_side, args.view)

    # Compute peak velocity relative percentage from raw speeds using the same windows
    h_lm = _load_landmarks(args.healthy, args.healthy_side)
    a_lm = _load_landmarks(args.affected, args.affected_side)
    peak_v_pct = None
    if h_lm is not None and a_lm is not None:
        h_fs = _fs(h_lm["df"])
        a_fs = _fs(a_lm["df"])
        h_v = np.sqrt((np.gradient(h_lm["px"]) * h_fs) ** 2 + (np.gradient(h_lm["py"]) * h_fs) ** 2)
        a_v = np.sqrt((np.gradient(a_lm["px"]) * a_fs) ** 2 + (np.gradient(a_lm["py"]) * a_fs) ** 2)
        h_on, h_off = _native_window_from_analyze_trial(h, h_fs, len(h_lm["px"]))
        a_on, a_off = _native_window_from_analyze_trial(a, a_fs, len(a_lm["px"]))
        if h_off > h_on and a_off > a_on:
            h_pv = np.max(h_v[h_on:h_off + 1])
            a_pv = np.max(a_v[a_on:a_off + 1])
            if h_pv > 0:
                peak_v_pct = round((a_pv / h_pv) * 100, 1)

    report = {
        "healthy": {
            "video": args.healthy,
            "side": args.healthy_side,
            "sparc": h.get("sparc"),
            "reach_amplitude_sw": h.get("reach_amplitude_sw"),
            "movement_time_sec": h.get("movement_time_sec"),
            "peak_velocity_pct": 100.0,
            "trunk_ratio": h.get("trunk_ratio"),
            "shoulder_elevation_cm": h.get("shoulder_elevation_cm"),
            "elbow_angle_deg": h.get("elbow_angle_deg"),
            "hand_displacement_cm": h.get("hand_displacement_cm"),
            "trunk_cheat_ratio": h.get("trunk_cheat_ratio"),
        },
        args.label: {
            "video": args.affected,
            "side": args.affected_side,
            "sparc": a.get("sparc"),
            "reach_amplitude_sw": a.get("reach_amplitude_sw"),
            "movement_time_sec": a.get("movement_time_sec"),
            "peak_velocity_pct": peak_v_pct,
            "trunk_ratio": a.get("trunk_ratio"),
            "shoulder_elevation_cm": a.get("shoulder_elevation_cm"),
            "elbow_angle_deg": a.get("elbow_angle_deg"),
            "hand_displacement_cm": a.get("hand_displacement_cm"),
            "trunk_cheat_ratio": a.get("trunk_cheat_ratio"),
        },
        "relative_to_healthy_percent": {
            "reach_amplitude_sw": relative_pct(a.get("reach_amplitude_sw"), h.get("reach_amplitude_sw")),
            "movement_time_sec": relative_pct(a.get("movement_time_sec"), h.get("movement_time_sec")),
            "peak_velocity_pct": peak_v_pct,
            "trunk_ratio": relative_pct(a.get("trunk_ratio"), h.get("trunk_ratio")),
            "shoulder_elevation_cm": relative_pct(a.get("shoulder_elevation_cm"), h.get("shoulder_elevation_cm")),
            "elbow_angle_deg": relative_pct(a.get("elbow_angle_deg"), h.get("elbow_angle_deg")),
            "hand_displacement_cm": relative_pct(a.get("hand_displacement_cm"), h.get("hand_displacement_cm")),
            "trunk_cheat_ratio": relative_pct(a.get("trunk_cheat_ratio"), h.get("trunk_cheat_ratio")),
        },
    }

    for key in ["healthy", args.label]:
        sparc = report[key]["sparc"]
        if sparc is not None and np.isfinite(float(sparc)):
            if sparc >= -1.5:
                rating = "excellent"
            elif sparc >= -2.5:
                rating = "good"
            elif sparc >= -3.5:
                rating = "moderate"
            elif sparc >= -5.0:
                rating = "poor"
            else:
                rating = "very poor"
            report[key]["sparc_rating"] = rating

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved report to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
