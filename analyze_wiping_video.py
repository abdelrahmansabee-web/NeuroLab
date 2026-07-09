"""
Wiping-task kinematic analysis.
Adapted from the standalone analyze_wiping_video.py script so it can be called
from overlay_data.py using already-extracted landmark CSVs.
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


def _auto_trim_wiping(x, y, fs, speed_threshold_ratio=0.12, margin=5):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    dt = 1.0 / fs
    v = np.sqrt(np.gradient(x, dt) ** 2 + np.gradient(y, dt) ** 2)
    if v.max() == 0:
        return x, y, False
    threshold = speed_threshold_ratio * v.max()
    moving = v > threshold
    if not moving.any():
        return x, y, False
    first = np.where(moving)[0][0]
    last = np.where(moving)[0][-1]
    first = max(0, first - margin)
    last = min(len(x) - 1, last + margin)
    return x[first : last + 1], y[first : last + 1], True


def detect_strokes(x, y, fs=30, min_stroke_frames=5, min_distance=5.0):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    dt = 1.0 / fs
    x_range = x.max() - x.min()
    y_range = y.max() - y.min()
    primary = x.copy() if x_range >= y_range else y.copy()
    primary_axis = "horizontal" if x_range >= y_range else "vertical"

    v_primary = np.gradient(primary, dt)
    v_primary_smooth = gaussian_filter1d(v_primary, sigma=2)
    sign = np.sign(v_primary_smooth)
    sign_clean = np.copy(sign)
    for i in range(1, len(sign_clean)):
        if sign_clean[i] == 0:
            sign_clean[i] = sign_clean[i - 1]
    crossings = np.where(np.diff(sign_clean) != 0)[0] + 1
    boundaries = np.unique(np.concatenate([[0], crossings, [len(primary) - 1]]))

    strokes = []
    for i in range(len(boundaries) - 1):
        s, e = int(boundaries[i]), int(boundaries[i + 1])
        if e - s < min_stroke_frames:
            continue
        sx, sy = x[s:e], y[s:e]
        vx = np.gradient(sx, dt)
        vy = np.gradient(sy, dt)
        v = np.sqrt(vx**2 + vy**2)
        dist = np.sum(v) * dt
        if dist < min_distance:
            continue
        dir_sign = np.sign(v_primary_smooth[s:e].mean())
        direction = "right" if dir_sign > 0 else "left" if dir_sign < 0 else "none"
        strokes.append(
            {
                "start": s,
                "end": e,
                "direction": direction,
                "frames": e - s,
                "duration": (e - s) * dt,
                "distance": float(dist),
                "mean_speed": float(np.mean(v)),
                "max_speed": float(np.max(v)),
                "displacement": float(abs(primary[e] - primary[s])),
            }
        )
    return strokes, primary_axis


def stroke_smoothness(x, y, fs=30, smooth_sigma=1.5):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    dt = 1.0 / fs
    if smooth_sigma > 0:
        x = gaussian_filter1d(x, sigma=smooth_sigma)
        y = gaussian_filter1d(y, sigma=smooth_sigma)
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    v = np.sqrt(vx**2 + vy**2)
    v_mean = v.mean()
    cv_speed = v.std() / (v_mean + 1e-12)
    v_smooth = gaussian_filter1d(v, sigma=1.0)
    prom = 0.1 * v_smooth.max()
    peaks, _ = find_peaks(v_smooth, prominence=prom, distance=3)
    n_speed_peaks = len(peaks)
    ax = np.gradient(vx, dt)
    ay = np.gradient(vy, dt)
    a = np.sqrt(ax**2 + ay**2)
    accel_var = a.std() / (a.mean() + 1e-12) if a.mean() > 0 else 0
    direction = np.arctan2(vy, vx)
    dir_changes = int(np.sum(np.abs(np.diff(direction)) > 0.5))
    path_len = np.sum(np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2))
    direct = np.sqrt((x[-1] - x[0]) ** 2 + (y[-1] - y[0]) ** 2)
    straightness = direct / path_len if path_len > 0 else 1.0
    total_time = len(x) * dt
    efficiency = path_len / total_time if total_time > 0 else 0
    return {
        "cv_speed": float(cv_speed),
        "n_speed_peaks": int(n_speed_peaks),
        "accel_variability": float(accel_var),
        "direction_changes": dir_changes,
        "straightness": float(straightness),
        "efficiency": float(efficiency),
        "mean_speed": float(v_mean),
        "max_speed": float(v.max()),
        "total_distance": float(path_len),
        "duration": float(total_time),
    }


def analyze_wiping(x, y, fs=30, auto_trim=True, smooth_sigma=1.5):
    """
    Analyze a wiping trajectory.

    Parameters
    ----------
    x, y : array-like
        Wrist (or hand) coordinates. Use pixel units so that the default
        min_distance=5.0 corresponds to a few pixels; otherwise the
        stroke-detection threshold will not match the standalone script.
    fs : float
        Sampling frequency in Hz.
    auto_trim : bool
        Whether to trim leading/trailing static frames.
    smooth_sigma : float
        Gaussian smoothing sigma applied before computing derivatives.

    Returns
    -------
    dict
        Full wiping analysis result including verdict, strokes, and overall metrics.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    original_len = len(x)
    if auto_trim:
        x, y, trimmed = _auto_trim_wiping(x, y, fs)
    else:
        trimmed = False
    if len(x) < 10:
        return {
            "valid": False,
            "verdict": "invalid",
            "confidence": "low",
            "warning": "Movement too short",
            "original_frames": int(original_len),
            "trimmed_frames": int(len(x)),
        }

    smooth = stroke_smoothness(x, y, fs, smooth_sigma)
    strokes, primary_axis = detect_strokes(x, y, fs)
    n_strokes = len(strokes)

    stroke_details = []
    for stroke in strokes:
        sx = x[stroke["start"] : stroke["end"]]
        sy = y[stroke["start"] : stroke["end"]]
        s_smooth = stroke_smoothness(sx, sy, fs, smooth_sigma=0.5)
        stroke_details.append(
            {
                **stroke,
                "cv_speed": s_smooth["cv_speed"],
                "straightness": s_smooth["straightness"],
                "n_speed_peaks": s_smooth["n_speed_peaks"],
            }
        )

    x_range = x.max() - x.min()
    y_range = y.max() - y.min()
    coverage = x_range * y_range

    warning = None
    verdict = "moderate"
    confidence = "medium"
    score = 0
    if smooth["cv_speed"] < 0.35:
        score += 2
    elif smooth["cv_speed"] < 0.6:
        score += 1
    else:
        score -= 1
    if 2 <= n_strokes <= 5:
        score += 2
    elif n_strokes == 1:
        score += 1
    elif n_strokes > 8:
        score -= 2
    if smooth["straightness"] > 0.8:
        score += 2
    elif smooth["straightness"] > 0.6:
        score += 1
    else:
        score -= 1
    if smooth["n_speed_peaks"] <= 2:
        score += 1
    elif smooth["n_speed_peaks"] >= 5:
        score -= 1

    if score >= 5:
        verdict = "smooth"
        confidence = "high"
    elif score >= 3:
        verdict = "smooth"
        confidence = "medium"
    elif score >= 1:
        verdict = "moderate"
        confidence = "medium"
    elif score >= -1:
        verdict = "moderate"
        confidence = "low"
    else:
        verdict = "jerky"
        confidence = "high"

    if smooth["duration"] < 1.0:
        warning = "Very short movement"
        confidence = "low"

    return {
        "valid": True,
        "verdict": verdict,
        "confidence": confidence,
        "warning": warning,
        "primary_axis": primary_axis,
        "n_strokes": n_strokes,
        "strokes": stroke_details,
        "overall": smooth,
        "coverage": float(coverage),
        "x_range": float(x_range),
        "y_range": float(y_range),
        "trimmed": trimmed,
        "original_frames": int(original_len),
        "trimmed_frames": int(len(x)),
    }
