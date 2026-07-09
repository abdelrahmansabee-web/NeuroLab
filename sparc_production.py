"""
SPARC Production-Ready — Movement Smoothness Analysis
======================================================

يتجنب كل المشاكل المعروفة:
  • Auto-trimming (يقطع السكون تلقائياً)
  • Noise smoothing (Gaussian filter)
  • Time + Amplitude normalization (يتجنب تأثير السرعة)
  • Validation against # of peaks (يكشف SPARC الكاذب)
  • Fallback metrics (لو SPARC غير موثوق)

Compatible with: MediaPipe Pose, OpenPose, or any (x,y) tracker output.

Usage:
------
    from sparc_production import sparc_production

    # x, y = arrays of wrist coordinates from MediaPipe
    result = sparc_production(x, y, fs=30)

    print(result['verdict'])      # 'smooth' / 'moderate' / 'jerky'
    print(result['sparc'])        # SPARC normalized
    print(result['peaks'])          # number of velocity peaks
    print(result['warning'])        # any warnings

Returns dict with keys:
  sparc, sparc_raw, peaks, straightness, duration, distance,
  max_speed, verdict, confidence, trimmed, used_fallback,
  warning, original_frames, trimmed_frames
"""

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.integrate import simpson
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from itertools import groupby


def _sparc_core(velocity, fs):
    """Internal: SPARC calculation on a velocity array."""
    velocity = np.asarray(velocity, dtype=float)
    N = len(velocity)
    if N < 4:
        return np.nan
    dt = 1.0 / fs
    Vf = fft(velocity)
    freqs = fftfreq(N, d=dt)
    pos_mask = freqs > 0
    freqs_pos = freqs[pos_mask]
    Vf_pos = np.abs(Vf[pos_mask])
    vmax = Vf_pos.max()
    if vmax == 0 or len(freqs_pos) < 2:
        return np.nan
    Vf_norm = Vf_pos / vmax
    dV = np.gradient(Vf_norm, freqs_pos)
    integrand = np.sqrt((1.0 / freqs_pos) ** 2 + dV ** 2)
    arc_length = simpson(integrand, freqs_pos)
    return -float(arc_length)


def _auto_trim(x, y, fs, speed_threshold_ratio=0.12, min_frames=8, margin=3):
    """
    Auto-trim: removes static periods at start/end.
    Uses adaptive threshold based on peak speed.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    dt = 1.0 / fs
    v = np.sqrt(np.gradient(x, dt)**2 + np.gradient(y, dt)**2)
    if v.max() == 0:
        return x, y, False
    threshold = speed_threshold_ratio * v.max()
    moving = v > threshold
    sequences = []
    start = 0
    for k, g in groupby(moving):
        length = sum(1 for _ in g)
        if k and length >= min_frames:
            sequences.append((start, start + length))
        start += length
    if not sequences:
        return x, y, False
    s, e = max(sequences, key=lambda seg: seg[1] - seg[0])
    s = max(0, s - margin)
    e = min(len(x), e + margin)
    return x[s:e], y[s:e], True


def _count_peaks(v, prominence_ratio=0.12):
    """Count velocity peaks on lightly smoothed profile."""
    v = np.asarray(v, dtype=float)
    if len(v) < 5:
        return 0
    v_smooth = gaussian_filter1d(v, sigma=1.0)
    prom = prominence_ratio * v_smooth.max()
    peaks, _ = find_peaks(v_smooth, prominence=prom, distance=3)
    return len(peaks)


def _straightness(x, y):
    """Ratio: direct distance / path length (1.0 = perfectly straight)."""
    x, y = np.asarray(x), np.asarray(y)
    if len(x) < 2:
        return 1.0
    path = np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2))
    direct = np.sqrt((x[-1] - x[0])**2 + (y[-1] - y[0])**2)
    return direct / path if path > 0 else 1.0


def sparc_production(x, y, fs=30, n_points=100,
                     auto_trim=True, smooth_sigma=1.5,
                     speed_threshold_ratio=0.12, validate=True):
    """
    Production-ready SPARC analysis with all safeguards.

    Parameters
    ----------
    x, y : 1D array-like
        Coordinates (e.g., wrist_x, wrist_y from MediaPipe).
    fs : float, default 30
        Sampling frequency (FPS).
    n_points : int, default 100
        Number of points after time-normalization.
    auto_trim : bool, default True
        Automatically remove static start/end periods.
    smooth_sigma : float, default 1.5
        Gaussian smoothing sigma (0 = disabled).
    speed_threshold_ratio : float, default 0.12
        Fraction of peak speed used as movement threshold.
    validate : bool, default True
        Cross-check SPARC against # of peaks and use fallback if unreliable.

    Returns
    -------
    dict
        Full analysis results including SPARC, peaks, verdict, and warnings.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    original_len = len(x)
    warning = None
    used_fallback = False

    # 1. AUTO-TRIM
    if auto_trim:
        x, y, trimmed = _auto_trim(x, y, fs, speed_threshold_ratio)
    else:
        trimmed = False

    if len(x) < 10:
        return {
            'sparc': None, 'sparc_raw': None, 'peaks': 0,
            'straightness': 1.0, 'duration': 0.0, 'distance': 0.0,
            'max_speed': 0.0, 'verdict': 'invalid', 'confidence': 'none',
            'trimmed': trimmed, 'used_fallback': True,
            'warning': 'Movement too short after trimming',
            'original_frames': original_len, 'trimmed_frames': len(x)
        }

    # 2. SMOOTH (for SPARC calculation)
    x_smooth = gaussian_filter1d(x, sigma=smooth_sigma) if smooth_sigma > 0 else x
    y_smooth = gaussian_filter1d(y, sigma=smooth_sigma) if smooth_sigma > 0 else y

    dt = 1.0 / fs
    vx = np.gradient(x_smooth, dt)
    vy = np.gradient(y_smooth, dt)
    v_raw = np.sqrt(vx**2 + vy**2)

    duration = len(x) * dt
    distance = np.sum(v_raw) * dt
    max_speed = v_raw.max()

    # 3. TIME + AMPLITUDE NORMALIZATION
    t_orig = np.linspace(0, 1, len(v_raw))
    t_new = np.linspace(0, 1, n_points)
    v_interp = interp1d(t_orig, v_raw, kind='cubic', fill_value='extrapolate')(t_new)
    v_norm = v_interp / (v_interp.max() + 1e-12)

    # 4. SPARC
    sparc_norm = _sparc_core(v_norm, fs=n_points)
    sparc_raw = _sparc_core(v_raw, fs)

    # 5. PEAKS (on unsmoothed velocity for sensitivity)
    vx_un = np.gradient(x, dt)
    vy_un = np.gradient(y, dt)
    v_un = np.sqrt(vx_un**2 + vy_un**2)
    peaks = _count_peaks(v_un)

    straight = _straightness(x, y)

    # 6. VERDICT & VALIDATION
    verdict = 'moderate'
    confidence = 'medium'

    if validate:
        # SPARC كاذب: "smooth" value but many peaks
        if peaks >= 5 and sparc_norm > -3.5:
            warning = (f"SPARC unreliable ({sparc_norm:.2f}) vs {peaks} peaks. "
                       f"Using fallback metrics.")
            used_fallback = True
            score = peaks * (2 - straight)
            if score < 3:
                verdict = 'smooth'
            elif score < 6:
                verdict = 'moderate'
            else:
                verdict = 'jerky'
            sparc_norm = None
            confidence = 'low'

        elif duration < 0.5:
            warning = "Movement too short for reliable SPARC"
            used_fallback = True
            confidence = 'low'

        else:
            # Normal classification
            if sparc_norm > -2.8 and peaks <= 2:
                verdict = 'smooth'
                confidence = 'high'
            elif sparc_norm > -3.5 and peaks <= 3:
                verdict = 'smooth'
                confidence = 'medium'
            elif sparc_norm < -5.0 or peaks >= 6:
                verdict = 'jerky'
                confidence = 'high'
            elif sparc_norm < -4.0 or peaks >= 4:
                verdict = 'jerky'
                confidence = 'medium'
            else:
                verdict = 'moderate'
                confidence = 'medium'

    return {
        'sparc': float(sparc_norm) if not np.isnan(sparc_norm) else None,
        'sparc_raw': float(sparc_raw),
        'peaks': int(peaks),
        'straightness': float(straight),
        'duration': float(duration),
        'distance': float(distance),
        'max_speed': float(max_speed),
        'verdict': verdict,
        'confidence': confidence,
        'trimmed': trimmed,
        'used_fallback': used_fallback,
        'warning': warning,
        'original_frames': int(original_len),
        'trimmed_frames': int(len(x))
    }


# ═══════════════════════════════════════════════════════════════════
#  HELPER: Read from MediaPipe CSV
# ═══════════════════════════════════════════════════════════════════

def analyze_csv(csv_path, landmark='wrist', side='right', fs=None, **kwargs):
    """
    Analyze smoothness directly from a MediaPipe CSV file.

    Expected columns: {side}_{landmark}_x, {side}_{landmark}_y, frame

    Parameters
    ----------
    csv_path : str
        Path to CSV file.
    landmark : str, default 'wrist'
        Landmark name (e.g., 'wrist', 'elbow', 'shoulder').
    side : str, default 'right'
        'right' or 'left'.
    fs : float, optional
        FPS. If None, auto-detected from 'frame' column.
    **kwargs : passed to sparc_production().

    Returns
    -------
    dict
        Same output as sparc_production().
    """
    import pandas as pd
    df = pd.read_csv(csv_path)
    col_x = f"{side}_{landmark}_x"
    col_y = f"{side}_{landmark}_y"

    if col_x not in df.columns or col_y not in df.columns:
        raise ValueError(f"Columns {col_x} or {col_y} not found. "
                         f"Available: {list(df.columns)}")

    x = df[col_x].values.astype(float)
    y = df[col_y].values.astype(float)

    if fs is None and 'frame' in df.columns:
        frames = df['frame'].values
        if len(frames) > 1:
            fs = int(np.round(1.0 / np.median(np.diff(frames))))
        else:
            fs = 30
    elif fs is None:
        fs = 30

    return sparc_production(x, y, fs=fs, **kwargs)


if __name__ == "__main__":
    print("SPARC Production-Ready Module")
    print("Import and use: sparc_production(x, y, fs=30)")
