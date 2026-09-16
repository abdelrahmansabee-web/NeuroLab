# -*- coding: utf-8 -*-
"""
Temporal landmark refinement for MediaPipe pose CSV / video extraction.

- One Euro Filter (Casiez et al.) — reduces jitter while preserving fast reaches
- Gap interpolation + Savitzky–Golay polish
- Shoulder-girdle trunk proxy (literature-aligned trunk recruitment)
- Enhanced frame preprocessing for video re-extraction (CLAHE + denoise + upscale)
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

try:
    from extract_pose_csv_robust import LANDMARK_NAMES
except ImportError:
    LANDMARK_NAMES = []


class OneEuroFilter1D:
    """1D One Euro Filter — adaptive low-pass for pose streams."""

    def __init__(
        self,
        t0: float,
        x0: float,
        *,
        min_cutoff: float = 0.7,
        beta: float = 0.05,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev = float(x0)
        self._dx_prev = 0.0
        self._t_prev = float(t0)

    @staticmethod
    def _alpha(cutoff: float, te: float) -> float:
        tau = 1.0 / (2.0 * math.pi * max(cutoff, 1e-6))
        return 1.0 / (1.0 + tau / max(te, 1e-6))

    def __call__(self, t: float, x: float) -> float:
        te = max(float(t) - self._t_prev, 1e-6)
        ad = self._alpha(self.d_cutoff, te)
        dx = (float(x) - self._x_prev) / te
        dx_hat = ad * dx + (1.0 - ad) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, te)
        x_hat = a * float(x) + (1.0 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = float(t)
        return x_hat


def infer_fps_from_df(df: pd.DataFrame, default: float = 30.0) -> float:
    if "fps" in df.columns:
        v = pd.to_numeric(df["fps"], errors="coerce").dropna()
        if len(v) and float(v.iloc[0]) > 0:
            return float(v.iloc[0])
    if "time" in df.columns and len(df) > 2:
        t = pd.to_numeric(df["time"], errors="coerce").values.astype(float)
        dt = np.diff(t[t > 0])
        if len(dt):
            med = float(np.median(dt))
            if med > 1e-6:
                return 1.0 / med
    return float(default)


def _landmark_names_in_df(df: pd.DataFrame) -> List[str]:
    if LANDMARK_NAMES:
        return [n for n in LANDMARK_NAMES if f"{n}_X" in df.columns]
    names = set()
    for c in df.columns:
        if c.endswith("_X"):
            names.add(c[:-2])
    return sorted(names)


def _interpolate_landmark_gaps(
    series: np.ndarray,
    visibility: Optional[np.ndarray],
    max_gap: int = 10,
    vis_threshold: float = 0.22,
) -> np.ndarray:
    arr = np.asarray(series, dtype=float).copy()
    if visibility is not None:
        vis = np.asarray(visibility, dtype=float)
        bad = vis < vis_threshold
        arr[bad] = np.nan
    n = len(arr)
    isnan = ~np.isfinite(arr)
    if not isnan.any():
        return arr
    idx = np.arange(n)
    good = np.isfinite(arr)
    if good.sum() < 2:
        return arr
    arr[isnan] = np.interp(idx[isnan], idx[good], arr[good])
    # Short-gap only: re-mask long gaps then fill again
    i = 0
    while i < n:
        if np.isfinite(arr[i]):
            i += 1
            continue
        g0 = i
        while i < n and not np.isfinite(arr[i]):
            i += 1
        if (i - g0) > max_gap and g0 > 0 and i < n:
            arr[g0:i] = np.nan
    good = np.isfinite(arr)
    if good.sum() >= 2:
        arr[~good] = np.interp(idx[~good], idx[good], arr[good])
    return arr


def apply_one_euro_series(
    values: np.ndarray,
    times: np.ndarray,
    *,
    min_cutoff: float = 0.7,
    beta: float = 0.05,
) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    t = np.asarray(times, dtype=float)
    if len(v) < 2:
        return v.copy()
    out = np.empty_like(v)
    filt = OneEuroFilter1D(t[0], v[0], min_cutoff=min_cutoff, beta=beta)
    out[0] = v[0]
    for i in range(1, len(v)):
        out[i] = filt(t[i], v[i])
    return out


def refine_pose_landmarks_df(
    df: pd.DataFrame,
    fps: Optional[float] = None,
    *,
    min_cutoff: float = 0.65,
    beta: float = 0.06,
    max_gap: int = 10,
    savgol_window_s: float = 0.09,
) -> pd.DataFrame:
    """
    Post-hoc landmark refinement on raw MediaPipe CSV (no video required).
    """
    out = df.copy()
    fs = float(fps or infer_fps_from_df(out))
    names = _landmark_names_in_df(out)
    if not names:
        return out

    if "time" in out.columns:
        times = pd.to_numeric(out["time"], errors="coerce").values.astype(float)
    else:
        times = np.arange(len(out), dtype=float) / fs

    axes = ("X", "Y", "Z")
    for name in names:
        vis = None
        vkey = f"{name}_VISIBILITY"
        if vkey in out.columns:
            vis = pd.to_numeric(out[vkey], errors="coerce").values.astype(float)
        for ax in axes:
            key = f"{name}_{ax}"
            if key not in out.columns:
                continue
            raw = pd.to_numeric(out[key], errors="coerce").values.astype(float)
            filled = _interpolate_landmark_gaps(raw, vis, max_gap=max_gap)
            smoothed = apply_one_euro_series(filled, times, min_cutoff=min_cutoff, beta=beta)
            win = max(5, int(savgol_window_s * fs) | 1)
            if len(smoothed) >= win:
                try:
                    smoothed = savgol_filter(smoothed, window_length=win, polyorder=2, mode="interp")
                except ValueError:
                    pass
            out[key] = smoothed
    return out


def compute_trunk_coords(
    ls_x: np.ndarray,
    ls_y: np.ndarray,
    rs_x: np.ndarray,
    rs_y: np.ndarray,
    lh_x: Optional[np.ndarray] = None,
    lh_y: Optional[np.ndarray] = None,
    rh_x: Optional[np.ndarray] = None,
    rh_y: Optional[np.ndarray] = None,
    mode: str = "shoulder_girdle",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Trunk proxy for recruitment ratio.

    shoulder_girdle: midpoint of bilateral shoulders (sensitive to forward lean).
    blended: 75% shoulder midpoint + 25% hip midpoint.
    """
    ls_x = np.asarray(ls_x, dtype=float)
    ls_y = np.asarray(ls_y, dtype=float)
    rs_x = np.asarray(rs_x, dtype=float)
    rs_y = np.asarray(rs_y, dtype=float)
    sx = (ls_x + rs_x) / 2.0
    sy = (ls_y + rs_y) / 2.0
    if mode == "shoulder_girdle" or lh_x is None or rh_x is None:
        return sx, sy
    hx = (np.asarray(lh_x, dtype=float) + np.asarray(rh_x, dtype=float)) / 2.0
    hy = (np.asarray(lh_y, dtype=float) + np.asarray(rh_y, dtype=float)) / 2.0
    return 0.75 * sx + 0.25 * hx, 0.75 * sy + 0.25 * hy


def enhanced_preprocess_frame(
    frame_bgr: np.ndarray,
    *,
    use_clahe: bool = True,
    denoise: bool = True,
    upscale_min_height: int = 720,
) -> np.ndarray:
    """BGR in → RGB out, tuned for phone stroke videos."""
    import cv2

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    if denoise:
        rgb = cv2.bilateralFilter(rgb, d=5, sigmaColor=55, sigmaSpace=55)
    if use_clahe:
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        rgb = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
    h, w = rgb.shape[:2]
    if upscale_min_height > 0 and h < upscale_min_height:
        scale = upscale_min_height / float(h)
        rgb = cv2.resize(
            rgb,
            (max(1, int(w * scale)), upscale_min_height),
            interpolation=cv2.INTER_LANCZOS4,
        )
    return rgb
