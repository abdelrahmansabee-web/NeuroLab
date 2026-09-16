# -*- coding: utf-8 -*-
"""
Lower-extremity + core kinematics for NeuroLab LE.

Tasks: sts_stand, bodyweight_squat, overground_gait, quiet_stance_balance.
Normative bands from Perry/Burnfield gait literature (clinic-facing constants).
Muscle roles are kinematic proxies only (no EMG).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

LE_CLINICAL_TASKS: Dict[str, Dict[str, Any]] = {
    "sts_stand": {
        "label_en": "Sit-to-Stand",
        "label_tr": "Oturmadan ayağa kalkma",
        "phase_ids": ["sts"],
    },
    "bodyweight_squat": {
        "label_en": "Bodyweight squat",
        "label_tr": "Vücut ağırlığı squat",
        "phase_ids": ["squat"],
    },
    "overground_gait": {
        "label_en": "Overground gait",
        "label_tr": "Yürüme analizi",
        "phase_ids": ["gait"],
    },
    "quiet_stance_balance": {
        "label_en": "Quiet stance balance",
        "label_tr": "Dengede duruş",
        "phase_ids": ["balance"],
    },
}

# Clinic-facing healthy adult level-walking norms (approx. peaks / ROM).
GAIT_NORMS = {
    "ankle_df_peak_deg": 8.0,
    "ankle_pf_peak_deg": 20.0,
    "ankle_sagittal_rom_deg": 32.0,
    "knee_flex_peak_swing_deg": 60.0,
    "knee_ext_min_stance_deg": 0.0,
    "hip_flex_peak_deg": 20.0,
    "hip_ext_peak_deg": 20.0,
    "hip_rotation_rom_deg": 22.0,
    "foot_progression_angle_deg": 6.0,  # external
    "pelvis_rotation_rom_deg": 15.0,
    "gait_speed_m_s": 1.3,
    "cadence_spm": 115.0,
    "stance_pct": 60.0,
    "swing_pct": 40.0,
}


def is_le_clinical_task(task: Optional[str]) -> bool:
    t = (task or "").strip().lower()
    return t in LE_CLINICAL_TASKS


def _col(df: pd.DataFrame, name: str, axis: str) -> np.ndarray:
    key = f"{name}_{axis}"
    if key not in df.columns:
        return np.full(len(df), np.nan)
    return pd.to_numeric(df[key], errors="coerce").to_numpy(dtype=float)


def _angle_deg(ax, ay, bx, by, cx, cy) -> np.ndarray:
    """Interior angle ABC in degrees (2D)."""
    bax, bay = ax - bx, ay - by
    bcx, bcy = cx - bx, cy - by
    na = np.hypot(bax, bay)
    nc = np.hypot(bcx, bcy)
    denom = np.maximum(na * nc, 1e-9)
    cos = np.clip((bax * bcx + bay * bcy) / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def _nanmean(a: np.ndarray) -> float:
    v = a[np.isfinite(a)]
    return float(np.mean(v)) if v.size else float("nan")


def _nanstd(a: np.ndarray) -> float:
    v = a[np.isfinite(a)]
    return float(np.std(v)) if v.size > 1 else float("nan")


def _rom(a: np.ndarray) -> float:
    v = a[np.isfinite(a)]
    if v.size < 2:
        return float("nan")
    return float(np.nanmax(v) - np.nanmin(v))


def _peak(a: np.ndarray, mode: str = "max") -> float:
    v = a[np.isfinite(a)]
    if not v.size:
        return float("nan")
    return float(np.nanmax(v) if mode == "max" else np.nanmin(v))


def _pct_of_norm(val: float, norm: float) -> Optional[float]:
    if not np.isfinite(val) or not np.isfinite(norm) or abs(norm) < 1e-9:
        return None
    return round(100.0 * float(val) / float(norm), 1)


def _symmetry_index(a: float, b: float) -> float:
    """1 = perfect symmetry, 0 = large asymmetry (0–1)."""
    if not np.isfinite(a) or not np.isfinite(b):
        return float("nan")
    denom = abs(a) + abs(b)
    if denom < 1e-9:
        return 1.0
    return float(max(0.0, 1.0 - abs(a - b) / denom))


def _smooth(y: np.ndarray, win: int = 5) -> np.ndarray:
    if y.size < 3:
        return y.copy()
    w = max(3, int(win) | 1)
    k = np.ones(w) / w
    out = np.convolve(np.nan_to_num(y, nan=0.0), k, mode="same")
    mask = np.isfinite(y)
    out[~mask] = np.nan
    return out


def _sparc_from_speed(speed: np.ndarray, fs: float) -> float:
    """Lightweight SPARC-like smoothness on a speed series (higher = smoother)."""
    try:
        from sparc_production import sparc
        v = speed[np.isfinite(speed)]
        if v.size < 8 or fs <= 0:
            return float("nan")
        return float(sparc(v, fs))
    except Exception:
        v = speed[np.isfinite(speed)]
        if v.size < 8:
            return float("nan")
        # Fallback: negative CV of acceleration as smoothness proxy
        dv = np.diff(v) * fs
        cv = float(np.std(dv) / (np.mean(np.abs(v)) + 1e-6))
        return float(-cv)


def load_pose_arrays(df: pd.DataFrame, frame_w: float = 1920.0, frame_h: float = 1080.0) -> Dict[str, np.ndarray]:
    """Extract bilateral LE + trunk landmarks in pixel space."""
    # MediaPipe normalized 0–1; scale if values look normalized
    sample = _col(df, "LEFT_HIP", "X")
    scale_x = frame_w if np.nanmedian(np.abs(sample)) <= 1.5 else 1.0
    scale_y = frame_h if scale_x == frame_w else 1.0

    def px(name: str, axis: str) -> np.ndarray:
        a = _col(df, name, axis)
        return a * (scale_x if axis == "X" else scale_y)

    out = {}
    for side, pref in (("L", "LEFT"), ("R", "RIGHT")):
        for joint in ("HIP", "KNEE", "ANKLE", "HEEL", "FOOT_INDEX", "SHOULDER"):
            out[f"{side}_{joint}_x"] = px(f"{pref}_{joint}", "X")
            out[f"{side}_{joint}_y"] = px(f"{pref}_{joint}", "Y")
    out["NOSE_x"] = px("NOSE", "X")
    out["NOSE_y"] = px("NOSE", "Y")
    return out


def compute_joint_series(P: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Sagittal-ish 2D angles + COM proxies."""
    series: Dict[str, np.ndarray] = {}
    for side in ("L", "R"):
        hx, hy = P[f"{side}_HIP_x"], P[f"{side}_HIP_y"]
        kx, ky = P[f"{side}_KNEE_x"], P[f"{side}_KNEE_y"]
        ax, ay = P[f"{side}_ANKLE_x"], P[f"{side}_ANKLE_y"]
        fx, fy = P[f"{side}_FOOT_INDEX_x"], P[f"{side}_FOOT_INDEX_y"]
        sx, sy = P[f"{side}_SHOULDER_x"], P[f"{side}_SHOULDER_y"]
        # Knee flexion: 180 - interior hip-knee-ankle (larger = more flexed in image coords)
        knee_int = _angle_deg(hx, hy, kx, ky, ax, ay)
        series[f"knee_flex_{side}"] = 180.0 - knee_int
        # Hip: shoulder-hip-knee
        hip_int = _angle_deg(sx, sy, hx, hy, kx, ky)
        series[f"hip_flex_{side}"] = 180.0 - hip_int
        # Ankle: knee-ankle-foot; DF positive when shin–foot opens forward (approx)
        ankle_int = _angle_deg(kx, ky, ax, ay, fx, fy)
        # Map: ~90° neutral; >90 ≈ PF, <90 ≈ DF in many side views — store signed DF
        series[f"ankle_df_{side}"] = 90.0 - ankle_int  # +DF, -PF
        # Foot progression proxy: foot vector vs vertical (deg from down)
        fdx, fdy = fx - ax, fy - ay
        series[f"fpa_{side}"] = np.degrees(np.arctan2(fdx, np.maximum(fdy, 1e-6)))
    # COM ≈ mid-hips
    series["com_x"] = 0.5 * (P["L_HIP_x"] + P["R_HIP_x"])
    series["com_y"] = 0.5 * (P["L_HIP_y"] + P["R_HIP_y"])
    # Trunk lean: shoulder mid vs hip mid (lateral)
    sh_x = 0.5 * (P["L_SHOULDER_x"] + P["R_SHOULDER_x"])
    sh_y = 0.5 * (P["L_SHOULDER_y"] + P["R_SHOULDER_y"])
    series["trunk_lean"] = np.degrees(
        np.arctan2(sh_x - series["com_x"], np.maximum(series["com_y"] - sh_y, 1e-6))
    )
    series["trunk_flex"] = np.degrees(
        np.arctan2(series["com_y"] - sh_y, np.maximum(np.abs(sh_x - series["com_x"]), 1e-6))
    )
    # Pelvis rotation proxy: hip line angle
    series["pelvis_yaw"] = np.degrees(
        np.arctan2(P["R_HIP_y"] - P["L_HIP_y"], P["R_HIP_x"] - P["L_HIP_x"])
    )
    return series


def _hip_width(P: Dict[str, np.ndarray]) -> float:
    w = np.hypot(P["R_HIP_x"] - P["L_HIP_x"], P["R_HIP_y"] - P["L_HIP_y"])
    m = float(np.nanmedian(w[np.isfinite(w)])) if np.any(np.isfinite(w)) else float("nan")
    return m if m > 1 else float("nan")


def _movement_window_from_signal(sig: np.ndarray, fs: float, frac: float = 0.15) -> Tuple[int, int]:
    s = _smooth(sig, max(3, int(0.1 * fs)))
    v = np.isfinite(s)
    if not np.any(v):
        return 0, max(0, len(sig) - 1)
    s2 = s.copy()
    s2[~v] = np.nanmedian(s[v])
    amp = np.nanmax(s2) - np.nanmin(s2)
    thr = np.nanmin(s2) + frac * max(amp, 1e-6)
    # Rising activity
    active = s2 > thr if amp > 0 else np.ones_like(s2, dtype=bool)
    idx = np.where(active)[0]
    if idx.size < 3:
        return 0, max(0, len(sig) - 1)
    return int(idx[0]), int(idx[-1])


def _shared_metrics(series: Dict[str, np.ndarray], P: Dict[str, np.ndarray], fs: float, start: int, end: int) -> Dict[str, Any]:
    sl = slice(start, end + 1)
    hw = _hip_width(P)
    com_x, com_y = series["com_x"][sl], series["com_y"][sl]
    com_spd = np.hypot(np.gradient(com_x, 1.0 / fs), np.gradient(com_y, 1.0 / fs))
    m: Dict[str, Any] = {
        "movement_time_sec": round((end - start) / fs, 3) if fs > 0 else None,
        "sparc_com": _round(_sparc_from_speed(com_spd, fs)),
        "hip_width_px": _round(hw),
        "trunk_lean_max_deg": _round(_peak(np.abs(series["trunk_lean"][sl]), "max")),
        "trunk_flexion_rom_deg": _round(_rom(series["trunk_flex"][sl])),
        "trunk_sway_rom_deg": _round(_rom(series["trunk_lean"][sl])),
        "pelvis_rotation_rom_deg": _round(_rom(series["pelvis_yaw"][sl])),
    }
    for side, tag in (("L", "L"), ("R", "R")):
        kf = series[f"knee_flex_{side}"][sl]
        hf = series[f"hip_flex_{side}"][sl]
        ad = series[f"ankle_df_{side}"][sl]
        m[f"knee_rom_{tag}_deg"] = _round(_rom(kf))
        m[f"hip_rom_{tag}_deg"] = _round(_rom(hf))
        m[f"peak_knee_vel_{tag}_deg_s"] = _round(_peak(np.abs(np.gradient(kf, 1.0 / fs)), "max")) if fs > 0 else None
        m[f"ankle_df_peak_{tag}_deg"] = _round(_peak(ad, "max"))
        m[f"ankle_pf_peak_{tag}_deg"] = _round(abs(min(0.0, _peak(ad, "min"))))
        m[f"ankle_sagittal_rom_{tag}_deg"] = _round(_rom(ad))
        m[f"hip_flex_peak_{tag}_deg"] = _round(_peak(hf, "max"))
        m[f"hip_ext_peak_{tag}_deg"] = _round(max(0.0, -_peak(hf, "min"))) if np.isfinite(_peak(hf, "min")) else None
        m[f"knee_flex_peak_swing_{tag}_deg"] = _round(_peak(kf, "max"))
        m[f"knee_ext_min_stance_{tag}_deg"] = _round(_peak(kf, "min"))
        m[f"foot_progression_angle_{tag}_deg"] = _round(_nanmean(series[f"fpa_{side}"][sl]))
        m[f"hip_rotation_rom_{tag}_deg"] = _round(_rom(series[f"fpa_{side}"][sl]))  # proxy
    m["lr_symmetry_index"] = _round(
        _symmetry_index(m.get("knee_rom_L_deg") or float("nan"), m.get("knee_rom_R_deg") or float("nan"))
    )
    # Quality composite
    sym = m["lr_symmetry_index"] if np.isfinite(m.get("lr_symmetry_index") or float("nan")) else 0.5
    lean = m.get("trunk_lean_max_deg") or 0.0
    lean_pen = min(1.0, float(lean) / 25.0)
    m["movement_quality_index"] = _round(100.0 * (0.55 * (sym if np.isfinite(sym) else 0.5) + 0.45 * (1.0 - lean_pen)))
    m["trunk_compensation_index"] = _round(min(1.0, float(lean) / 20.0)) if np.isfinite(lean) else None
    return m


def _attach_norms(m: Dict[str, Any]) -> None:
    pairs = [
        ("ankle_df_peak_L_deg", "ankle_df_peak_deg"),
        ("ankle_df_peak_R_deg", "ankle_df_peak_deg"),
        ("ankle_pf_peak_L_deg", "ankle_pf_peak_deg"),
        ("ankle_pf_peak_R_deg", "ankle_pf_peak_deg"),
        ("ankle_sagittal_rom_L_deg", "ankle_sagittal_rom_deg"),
        ("ankle_sagittal_rom_R_deg", "ankle_sagittal_rom_deg"),
        ("knee_flex_peak_swing_L_deg", "knee_flex_peak_swing_deg"),
        ("knee_flex_peak_swing_R_deg", "knee_flex_peak_swing_deg"),
        ("gait_speed_m_s", "gait_speed_m_s"),
        ("cadence_spm", "cadence_spm"),
        ("pelvis_rotation_rom_deg", "pelvis_rotation_rom_deg"),
    ]
    for key, nkey in pairs:
        if key in m and m[key] is not None:
            m[f"norm_{nkey}"] = GAIT_NORMS[nkey]
            m[f"pct_of_norm_{key}"] = _pct_of_norm(float(m[key]), GAIT_NORMS[nkey])


def _gait_compensation(series: Dict[str, np.ndarray], P: Dict[str, np.ndarray], start: int, end: int, fs: float) -> Dict[str, Any]:
    sl = slice(start, end + 1)
    out: Dict[str, Any] = {}
    # Hip hike: vertical hip difference during high knee of one side
    hip_dy = P["L_HIP_y"][sl] - P["R_HIP_y"][sl]
    out["hip_hike_deg"] = _round(_peak(np.abs(hip_dy), "max") * 0.15)  # px→soft deg proxy
    out["hip_hike_index"] = _round(min(1.0, abs(out["hip_hike_deg"] or 0) / 12.0))
    # Circumduction: lateral ankle path vs straight
    for side, tag in (("L", "L"), ("R", "R")):
        ax = P[f"{side}_ANKLE_x"][sl]
        path = np.nansum(np.abs(np.diff(ax)))
        net = abs(float(ax[-1] - ax[0])) if ax.size > 1 else 0.0
        circ = (path / (net + 1e-6)) - 1.0
        out[f"circumduction_raw_{tag}"] = _round(max(0.0, circ))
    out["circumduction_index"] = _round(
        min(1.0, 0.5 * ((out.get("circumduction_raw_L") or 0) + (out.get("circumduction_raw_R") or 0)))
    )
    # Foot drop: low DF during presumed swing (high knee flex)
    for side, tag in (("L", "L"), ("R", "R")):
        kf = series[f"knee_flex_{side}"][sl]
        ad = series[f"ankle_df_{side}"][sl]
        swing_mask = kf > (np.nanmedian(kf) + 0.2 * _rom(kf) if np.isfinite(_rom(kf)) else np.nanmedian(kf))
        swing_df = ad[swing_mask] if np.any(swing_mask) else ad
        peak_swing_df = _peak(swing_df, "max")
        out[f"swing_df_{tag}"] = _round(peak_swing_df)
        out[f"foot_drop_{tag}"] = 1.0 if (np.isfinite(peak_swing_df) and peak_swing_df < 0) else 0.0
    out["foot_drop_index"] = _round(max(out.get("foot_drop_L", 0), out.get("foot_drop_R", 0)))
    # Foot slap: rapid PF after DF peak early in cycle — use DF derivative
    for side, tag in (("L", "L"), ("R", "R")):
        ad = series[f"ankle_df_{side}"][sl]
        d = np.gradient(ad, 1.0 / fs) if fs > 0 else np.zeros_like(ad)
        slap = _peak(-d, "max")  # rapid loss of DF
        out[f"foot_slap_{tag}"] = _round(min(1.0, (slap or 0) / 200.0))
    out["foot_slap_index"] = _round(max(out.get("foot_slap_L") or 0, out.get("foot_slap_R") or 0))
    # Stiff knee
    for side, tag in (("L", "L"), ("R", "R")):
        peak_k = _peak(series[f"knee_flex_{side}"][sl], "max")
        out[f"stiff_knee_{tag}"] = _round(min(1.0, max(0.0, (60.0 - (peak_k or 0)) / 60.0)))
    out["stiff_knee_index"] = _round(max(out.get("stiff_knee_L") or 0, out.get("stiff_knee_R") or 0))
    # Hyperextension
    for side, tag in (("L", "L"), ("R", "R")):
        mn = _peak(series[f"knee_flex_{side}"][sl], "min")
        out[f"knee_hyperextension_{tag}_deg"] = _round(abs(min(0.0, mn or 0)))
    # Push-off deficit: low PF peak
    for side, tag in (("L", "L"), ("R", "R")):
        pf = abs(min(0.0, _peak(series[f"ankle_df_{side}"][sl], "min")))
        out[f"push_off_deficit_{tag}"] = _round(min(1.0, max(0.0, (20.0 - pf) / 20.0)))
    out["push_off_deficit_index"] = _round(
        0.5 * ((out.get("push_off_deficit_L") or 0) + (out.get("push_off_deficit_R") or 0))
    )
    # Vaulting proxy: excess stance PF on one side while other swings
    out["vaulting_index"] = _round(min(1.0, (out.get("push_off_deficit_index") or 0) * 0.3 + (out.get("hip_hike_index") or 0) * 0.4))
    return out


def analyze_overground_gait(series, P, fs, start, end, walkway_m: Optional[float] = None) -> Dict[str, Any]:
    m = _shared_metrics(series, P, fs, start, end)
    sl = slice(start, end + 1)
    # Cadence from ankle vertical peaks
    ay = 0.5 * (P["L_ANKLE_y"][sl] + P["R_ANKLE_y"][sl])
    # Step detection via left ankle y peaks (side view) or speed of ankles
    la = _smooth(P["L_ANKLE_y"][sl], max(3, int(0.08 * fs)))
    ra = _smooth(P["R_ANKLE_y"][sl], max(3, int(0.08 * fs)))
    def _peaks(y):
        if y.size < 5:
            return []
        thr = np.nanmedian(y) - 0.15 * (np.nanmax(y) - np.nanmin(y) + 1e-6)
        idx = []
        for i in range(2, len(y) - 2):
            if not np.isfinite(y[i]):
                continue
            if y[i] <= y[i - 1] and y[i] <= y[i + 1] and y[i] < thr:
                if not idx or i - idx[-1] > int(0.25 * fs):
                    idx.append(i)
        return idx
    lp, rp = _peaks(la), _peaks(ra)
    steps = len(lp) + len(rp)
    dur = (end - start) / fs if fs > 0 else float("nan")
    m["step_count"] = int(steps)
    m["cadence_spm"] = _round((steps / dur) * 60.0) if dur and dur > 0 else None
    # Step times
    def _step_times(peaks):
        if len(peaks) < 2 or fs <= 0:
            return float("nan")
        return float(np.mean(np.diff(peaks)) / fs)
    m["step_time_L_sec"] = _round(_step_times(lp))
    m["step_time_R_sec"] = _round(_step_times(rp))
    m["step_length_symmetry"] = _round(_symmetry_index(m.get("step_time_L_sec") or float("nan"), m.get("step_time_R_sec") or float("nan")))
    # Speed: COM horizontal path / time, convert via hip-width heuristic if no walkway
    com_x = series["com_x"][sl]
    path_px = float(np.nansum(np.abs(np.diff(com_x))))
    hw = _hip_width(P)
    # Assume hip width ~ 0.30 m adult
    m_per_px = (0.30 / hw) if (np.isfinite(hw) and hw > 1) else float("nan")
    if walkway_m and walkway_m > 0 and dur > 0:
        m["gait_speed_m_s"] = _round(walkway_m / dur)
    elif np.isfinite(m_per_px) and dur > 0:
        m["gait_speed_m_s"] = _round((path_px * m_per_px) / dur)
    else:
        m["gait_speed_m_s"] = None
    m["gait_speed_norm"] = _round(path_px / hw) if (np.isfinite(hw) and hw > 1) else None
    # Stance/swing crude split 60/40 scaled by asymmetry of step times
    m["stance_pct_L"] = 60.0
    m["stance_pct_R"] = 60.0
    m["swing_pct_L"] = 40.0
    m["swing_pct_R"] = 40.0
    m["double_support_pct"] = 20.0
    if np.isfinite(m.get("step_time_L_sec") or float("nan")) and np.isfinite(m.get("step_time_R_sec") or float("nan")):
        # Longer step time side → more swing on that side (paretic often)
        tl, tr = m["step_time_L_sec"], m["step_time_R_sec"]
        if tl > tr:
            m["swing_pct_L"], m["stance_pct_L"] = 45.0, 55.0
            m["swing_pct_R"], m["stance_pct_R"] = 35.0, 65.0
        elif tr > tl:
            m["swing_pct_R"], m["stance_pct_R"] = 45.0, 55.0
            m["swing_pct_L"], m["stance_pct_L"] = 35.0, 65.0
    m["stance_time_symmetry"] = m["step_length_symmetry"]
    m.update(_gait_compensation(series, P, start, end, fs))
    _attach_norms(m)
    norm_map = {
        "ankle_df_peak": "ankle_df_peak_deg",
        "ankle_pf_peak": "ankle_pf_peak_deg",
        "ankle_sagittal_rom": "ankle_sagittal_rom_deg",
        "knee_flex_peak_swing": "knee_flex_peak_swing_deg",
        "foot_progression_angle": "foot_progression_angle_deg",
    }
    for base, nkey in norm_map.items():
        lv, rv = m.get(f"{base}_L_deg"), m.get(f"{base}_R_deg")
        vals = [v for v in (lv, rv) if v is not None and np.isfinite(v)]
        if vals:
            m[f"{base}_deg"] = _round(float(np.mean(vals)))
            m[f"pct_of_norm_{base}_deg"] = _pct_of_norm(m[f"{base}_deg"], GAIT_NORMS[nkey])
    return m


def analyze_sts(series, P, fs, start, end) -> Dict[str, Any]:
    # Window from COM rise (y decreases in image coords)
    com_y = series["com_y"]
    if start == 0 and end >= len(com_y) - 1:
        start, end = _movement_window_from_signal(-com_y, fs, 0.2)
    m = _shared_metrics(series, P, fs, start, end)
    sl = slice(start, end + 1)
    hw = _hip_width(P)
    rise_px = float(np.nanmax(series["com_y"][sl]) - np.nanmin(series["com_y"][sl])) if end > start else float("nan")
    m["sts_time_sec"] = m["movement_time_sec"]
    m["com_rise_norm"] = _round(rise_px / hw) if (np.isfinite(hw) and hw > 1) else None
    m["seat_off_time_sec"] = _round(0.35 * (m["sts_time_sec"] or 0))
    m["sparc_knee_extension"] = m.get("sparc_com")
    m["weight_shift_asymmetry"] = _round(1.0 - (m.get("lr_symmetry_index") or 0.5))
    m["knee_extension_rom_deg"] = _round(0.5 * ((m.get("knee_rom_L_deg") or 0) + (m.get("knee_rom_R_deg") or 0)))
    return m


def analyze_squat(series, P, fs, start, end) -> Dict[str, Any]:
    kf = 0.5 * (series["knee_flex_L"] + series["knee_flex_R"])
    if start == 0 and end >= len(kf) - 1:
        start, end = _movement_window_from_signal(kf, fs, 0.2)
    m = _shared_metrics(series, P, fs, start, end)
    sl = slice(start, end + 1)
    mid = start + (end - start) // 2
    m["min_knee_angle_deg"] = _round(min(_peak(series["knee_flex_L"][sl], "max"), _peak(series["knee_flex_R"][sl], "max")))
    # depth: COM drop
    hw = _hip_width(P)
    drop = float(np.nanmax(series["com_y"][sl]) - np.nanmin(series["com_y"][sl]))
    m["squat_depth_norm"] = _round(drop / hw) if (np.isfinite(hw) and hw > 1) else None
    half = (end - start) / 2.0 / fs if fs > 0 else float("nan")
    m["eccentric_time_sec"] = _round(half)
    m["concentric_time_sec"] = _round(half)
    m["trunk_forward_lean_max_deg"] = m.get("trunk_lean_max_deg")
    m["lr_knee_depth_symmetry"] = m.get("lr_symmetry_index")
    m["sparc_knee"] = m.get("sparc_com")
    return m


def analyze_balance(series, P, fs, start, end) -> Dict[str, Any]:
    m = _shared_metrics(series, P, fs, start, end)
    sl = slice(start, end + 1)
    hw = _hip_width(P)
    cx, cy = series["com_x"][sl], series["com_y"][sl]
    path = float(np.nansum(np.hypot(np.diff(cx), np.diff(cy))))
    m["com_sway_path_norm"] = _round(path / hw) if (np.isfinite(hw) and hw > 1) else None
    m["com_sway_area_norm"] = _round((_rom(cx) * _rom(cy)) / (hw * hw)) if (np.isfinite(hw) and hw > 1) else None
    spd = np.hypot(np.gradient(cx, 1.0 / fs), np.gradient(cy, 1.0 / fs)) if fs > 0 else np.array([])
    m["sway_velocity_mean"] = _round(_nanmean(spd))
    m["time_in_balance_sec"] = m["movement_time_sec"]
    m["lr_loading_symmetry"] = m.get("lr_symmetry_index")
    return m


def _round(v: Any, nd: int = 3):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, nd)


def analyze_le_task(
    df: pd.DataFrame,
    clinical_task: str,
    *,
    fs: float = 30.0,
    frame_width: float = 1920.0,
    frame_height: float = 1080.0,
    walkway_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Main entry: returns analysis dict compatible with overlay + results UI.
    """
    task = (clinical_task or "").strip().lower()
    if task not in LE_CLINICAL_TASKS:
        task = "overground_gait"
    spec = LE_CLINICAL_TASKS[task]
    if "time" in df.columns:
        t = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=float)
        dt = np.diff(t)
        dt = dt[np.isfinite(dt) & (dt > 0)]
        if dt.size:
            fs = float(1.0 / np.median(dt))
    P = load_pose_arrays(df, frame_width, frame_height)
    series = compute_joint_series(P)
    n = len(df)
    start, end = 0, max(0, n - 1)

    if task == "sts_stand":
        metrics = analyze_sts(series, P, fs, start, end)
        start, end = _movement_window_from_signal(-series["com_y"], fs, 0.2)
        metrics = analyze_sts(series, P, fs, start, end)
        phase_id = "sts"
    elif task == "bodyweight_squat":
        start, end = _movement_window_from_signal(0.5 * (series["knee_flex_L"] + series["knee_flex_R"]), fs, 0.2)
        metrics = analyze_squat(series, P, fs, start, end)
        phase_id = "squat"
    elif task == "quiet_stance_balance":
        metrics = analyze_balance(series, P, fs, start, end)
        phase_id = "balance"
    else:
        start, end = _movement_window_from_signal(
            np.hypot(np.gradient(series["com_x"]), np.gradient(series["com_y"])), fs, 0.12
        )
        metrics = analyze_overground_gait(series, P, fs, start, end, walkway_m=walkway_m)
        phase_id = "gait"

    metrics["clinical_task"] = task
    metrics["clinical_task_label"] = spec["label_en"]
    metrics["analysis_fs_hz"] = round(fs, 2)
    metrics["movement_window_start"] = int(start)
    metrics["movement_window_end"] = int(end)
    # Norm constants always present for UI
    for k, v in GAIT_NORMS.items():
        metrics[f"norm_{k}"] = v

    phase = {
        "id": phase_id,
        "label": spec["label_en"],
        "start_idx": int(start),
        "end_idx": int(end),
        "metrics": {k: v for k, v in metrics.items() if not str(k).startswith("clinical_")},
    }

    return {
        "clinical_task": task,
        "clinical_task_label": spec["label_en"],
        "task_phases": [phase],
        "task_complete": 1,
        "task_completion_ratio": 1.0,
        "expected_phase_ids": spec["phase_ids"],
        "completed_phase_ids": [phase_id],
        "movement_bouts_detected": 1,
        "analysis_fs_hz": round(fs, 2),
        "fs_hz": round(fs, 2),
        "movement_window_start": int(start),
        "movement_window_end": int(end),
        "side_analyzed": "bilateral",
        "side": "bilateral",
        "le_analysis": True,
        "gait_norms": dict(GAIT_NORMS),
        **metrics,
    }
