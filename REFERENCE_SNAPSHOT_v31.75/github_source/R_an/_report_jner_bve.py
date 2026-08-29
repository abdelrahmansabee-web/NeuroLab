# -*- coding: utf-8 -*-
"""JNER 2025-style metrics: shoulder BVE, trunk BVE, mean palm speed (block-level)."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stroke_kinematic_pipeline import (
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    _coords_for_trial,
    _infer_fs,
    _normalize_landmark_columns,
    _pose_landmark_df,
    _try_load_raw_pose_csv,
)

PART = Path(r"D:/Thesis app/participants")
OUT = Path(r"D:/Thesis app/NeuroLab/backend/outputs")

PATIENTS = [
    ("Murat", [
        ("pre", OUT / "murat/pre_landmarks.csv", "right"),
        ("post", OUT / "murat/post_landmarks.csv", "right"),
        ("healthy", OUT / "murat/healthy_landmarks.csv", "left"),
    ]),
    ("Kurusal", [
        ("pre", PART / "kurusal/pre_20260617_142855_pre.csv", "left"),
        ("post", PART / "kurusal/post_20260617_142949_post.csv", "left"),
        ("healthy", PART / "kurusal/baseline_20260617_143108_healthy_side.csv", "right"),
    ]),
    ("Zeinab", [
        ("pre", PART / "mediapipe/movs/zeyneb/pre_20260603_165439_pre.csv", "left"),
        ("post", PART / "mediapipe/movs/zeyneb/post_20260603_165651_post.csv", "left"),
        ("healthy", PART / "mediapipe/movs/zeyneb/baseline_20260603_165330_baseline.csv", "right"),
    ]),
]


def bve(x: np.ndarray, y: np.ndarray) -> float:
    """JNER Eq: sqrt( (1/n) * sum((xi-xc)^2 + (yi-yc)^2) ). Lower = more consistent."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 2:
        return float("nan")
    xc = float(np.mean(x))
    yc = float(np.mean(y))
    return float(np.sqrt(np.sum((x - xc) ** 2 + (y - yc) ** 2) / n))


def mean_landmark_speed(x: np.ndarray, y: np.ndarray, fs: float) -> float:
    """JNER: mean framewise Euclidean speed (px/s)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or fs <= 0:
        return float("nan")
    dx = np.diff(x)
    dy = np.diff(y)
    speeds = np.hypot(dx, dy) * fs
    return float(np.mean(speeds))


def _frame_size(df: pd.DataFrame) -> Tuple[int, int]:
    fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else DEFAULT_FRAME_WIDTH
    fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else DEFAULT_FRAME_HEIGHT
    return fw, fh


def _jner_series_from_raw(
    raw: pd.DataFrame,
    side: str,
    fw: int,
    fh: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Strict JNER landmarks: palm=(pinky+index+wrist)/3, trunk=mean(4 landmarks), paretic shoulder."""
    p = side.upper()

    def px(name: str) -> np.ndarray:
        return raw[f"{name}_X"].astype(float).values * fw

    def py(name: str) -> np.ndarray:
        return raw[f"{name}_Y"].astype(float).values * fh

    palm_x = (px(f"{p}_PINKY") + px(f"{p}_INDEX") + px(f"{p}_WRIST")) / 3.0
    palm_y = (py(f"{p}_PINKY") + py(f"{p}_INDEX") + py(f"{p}_WRIST")) / 3.0
    shoulder_x = px(f"{p}_SHOULDER")
    shoulder_y = py(f"{p}_SHOULDER")
    trunk_x = (px("LEFT_SHOULDER") + px("RIGHT_SHOULDER") + px("LEFT_HIP") + px("RIGHT_HIP")) / 4.0
    trunk_y = (py("LEFT_SHOULDER") + py("RIGHT_SHOULDER") + py("LEFT_HIP") + py("RIGHT_HIP")) / 4.0
    return palm_x, palm_y, shoulder_x, shoulder_y, trunk_x, trunk_y


def compute_jner_block_metrics(
    csv_path: str,
    affected_side: str,
) -> Dict[str, Any]:
    """Full-video block metrics (JNER 2025 Methods)."""
    path = str(csv_path)
    df = pd.read_csv(path)
    fw, fh = _frame_size(df)
    fs = float(_infer_fs(df))

    coords, _sw, side_used = _coords_for_trial(df, path, affected_side, fw, fh)

    raw = _pose_landmark_df(df, path)
    if raw is not None and f"{affected_side.upper()}_PINKY_X" in _normalize_landmark_columns(raw).columns:
        raw = _normalize_landmark_columns(raw)
        side = affected_side if affected_side in ("left", "right") else side_used
        palm_x, palm_y, shoulder_x, shoulder_y, trunk_x, trunk_y = _jner_series_from_raw(raw, side, fw, fh)
        palm_source = "pinky+index+wrist/3"
        trunk_source = "mean(LS,RS,LH,RH)"
    else:
        palm_x = coords["palm_x"]
        palm_y = coords["palm_y"]
        shoulder_x = coords["shoulder_x"]
        shoulder_y = coords["shoulder_y"]
        trunk_x = coords["trunk_x"]
        trunk_y = coords["trunk_y"]
        palm_source = "pipeline palm (wrist+index)/2 fallback"
        trunk_source = "pipeline trunk proxy fallback"

    sw = float(coords.get("shoulder_width") or _sw or np.nan)
    n_frames = len(palm_x)

    shoulder_bve = bve(shoulder_x, shoulder_y)
    trunk_bve = bve(trunk_x, trunk_y)
    palm_bve = bve(palm_x, palm_y)
    mean_speed = mean_landmark_speed(palm_x, palm_y, fs)

    return {
        "shoulder_bve_px": shoulder_bve,
        "trunk_bve_px": trunk_bve,
        "palm_bve_px": palm_bve,
        "mean_palm_speed_px_s": mean_speed,
        "shoulder_bve_norm_sw": shoulder_bve / sw if sw > 0 else float("nan"),
        "trunk_bve_norm_sw": trunk_bve / sw if sw > 0 else float("nan"),
        "mean_palm_speed_norm_sw_s": mean_speed / sw if sw > 0 else float("nan"),
        "n_frames": n_frames,
        "duration_s": round(n_frames / fs, 2) if fs > 0 else float("nan"),
        "fps": fs,
        "shoulder_width_px": sw,
        "side": side_used,
        "palm_source": palm_source,
        "trunk_source": trunk_source,
    }


def _fmt(v: Optional[float], fmt: str = "{:.2f}") -> str:
    if v is None or not math.isfinite(float(v)):
        return "—"
    return fmt.format(float(v))


def _pct(pre: float, post: float) -> str:
    if not (math.isfinite(pre) and math.isfinite(post)) or pre == 0:
        return "—"
    return f"{(post - pre) / abs(pre) * 100:+.1f}%"


def _pattern_bve(pre: float, post: float, healthy: float) -> str:
    """Lower BVE = better consistency. Expect impaired pre highest, healthy lowest."""
    if not all(math.isfinite(v) for v in (pre, post, healthy)):
        return "—"
    return "✅" if pre > post > healthy else "❌"


def _pattern_speed(pre: float, post: float, healthy: float) -> str:
    """Higher speed = better. Expect post >= pre and healthy highest."""
    if not all(math.isfinite(v) for v in (pre, post, healthy)):
        return "—"
    ok = post >= pre and healthy >= post
    return "✅" if ok else "❌"


def _rate_bve(value: float, healthy: float) -> str:
    """
    Rating vs healthy reference (JNER: lower BVE = better consistency).
    🟢 near healthy | 🟡 moderate scatter | 🔴 high scatter
    """
    if not (math.isfinite(value) and math.isfinite(healthy)) or healthy <= 0:
        return "—"
    ratio = value / healthy
    if ratio <= 1.25:
        return "🟢 Good"
    if ratio <= 2.0:
        return "🟡 Moderate"
    return "🔴 Poor"


def _rate_speed(value: float, healthy: float) -> str:
    """Higher speed vs healthy. 🟢 ≥80% healthy | 🟡 50–80% | 🔴 <50%"""
    if not (math.isfinite(value) and math.isfinite(healthy)) or healthy <= 0:
        return "—"
    ratio = value / healthy
    if ratio >= 0.80:
        return "🟢 Good"
    if ratio >= 0.50:
        return "🟡 Moderate"
    return "🔴 Poor"


METRICS = [
    (
        "Shoulder BVE ↓",
        "shoulder_bve_px",
        "{:.1f}",
        "Pre > Post > H (lower=better)",
        _pattern_bve,
        _rate_bve,
    ),
    (
        "Trunk BVE ↓",
        "trunk_bve_px",
        "{:.1f}",
        "Pre > Post > H (lower=better)",
        _pattern_bve,
        _rate_bve,
    ),
    (
        "Mean palm speed ↑",
        "mean_palm_speed_px_s",
        "{:.1f}",
        "H ≥ Post ≥ Pre",
        _pattern_speed,
        _rate_speed,
    ),
]


def main() -> None:
    import io

    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    all_rows: Dict[str, Dict[str, Dict[str, Any]]] = {}

    print("\n# JNER 2025-style block metrics (full video, all frames)\n")
    print("Method: BVE = scatter around mean position; mean speed = avg frame displacement x fps")
    print("Lower BVE = more consistent (JNER). Block = entire trial video.\n")

    for name, trials in PATIENTS:
        rows: Dict[str, Dict[str, Any]] = {}
        for label, csv_path, side in trials:
            if not Path(csv_path).exists():
                rows[label] = {"error": f"missing {csv_path}"}
                continue
            rows[label] = compute_jner_block_metrics(str(csv_path), side)
        all_rows[name] = rows

        print(f"## {name}\n")
        print(f"| Meta | Pre | Post | Healthy |")
        print(f"|---|---:|---:|---:|")
        for k in ("n_frames", "duration_s", "fps", "palm_source"):
            print(
                f"| {k} | "
                f"{rows['pre'].get(k, '—')} | "
                f"{rows['post'].get(k, '—')} | "
                f"{rows['healthy'].get(k, '—')} |"
            )
        print()

        print("| Variable | Pre | Post | Healthy | Pre→Post | Expected | Rating Pre | Rating Post |")
        print("|---|---:|---:|---:|---:|---|---:|---:|")
        hel = rows["healthy"]
        for mname, key, fmt, expected, pat_fn, rate_fn in METRICS:
            pre_v = rows["pre"].get(key)
            post_v = rows["post"].get(key)
            hel_v = hel.get(key)
            ok = pat_fn(pre_v, post_v, hel_v) if pre_v is not None else "—"
            print(
                f"| {mname} | {_fmt(pre_v, fmt)} | {_fmt(post_v, fmt)} | {_fmt(hel_v, fmt)} | "
                f"{_pct(pre_v, post_v) if pre_v is not None else '—'} | {expected} {ok} | "
                f"{rate_fn(pre_v, hel_v) if pre_v is not None else '—'} | "
                f"{rate_fn(post_v, hel_v) if post_v is not None else '—'} |"
            )
        print()

    print("## Summary table (px units)\n")
    print("| Patient | Sh BVE Pre/Post/H | Trunk BVE Pre/Post/H | Speed Pre/Post/H | Pattern |")
    print("|---|---|---|---|---|")
    for name, _ in PATIENTS:
        r = all_rows[name]
        pre, post, h = r["pre"], r["post"], r["healthy"]
        sb = f"{_fmt(pre.get('shoulder_bve_px'), '{:.1f}')}/{_fmt(post.get('shoulder_bve_px'), '{:.1f}')}/{_fmt(h.get('shoulder_bve_px'), '{:.1f}')}"
        tb = f"{_fmt(pre.get('trunk_bve_px'), '{:.1f}')}/{_fmt(post.get('trunk_bve_px'), '{:.1f}')}/{_fmt(h.get('trunk_bve_px'), '{:.1f}')}"
        sp = f"{_fmt(pre.get('mean_palm_speed_px_s'), '{:.0f}')}/{_fmt(post.get('mean_palm_speed_px_s'), '{:.0f}')}/{_fmt(h.get('mean_palm_speed_px_s'), '{:.0f}')}"
        pats = []
        for _, key, _, _, pat_fn, _ in METRICS:
            pats.append(pat_fn(pre.get(key), post.get(key), h.get(key)))
        pat = "✅✅✅" if pats == ["✅", "✅", "✅"] else "".join(pats)
        print(f"| {name} | {sb} | {tb} | {sp} | {pat} |")

    print("\n## Rating system (vs healthy reference per patient)\n")
    print("| Metric | 🟢 Good | 🟡 Moderate | 🔴 Poor |")
    print("|---|---|---|---|")
    print("| Shoulder BVE | ≤ 1.25× healthy | 1.25–2.0× | > 2.0× |")
    print("| Trunk BVE | ≤ 1.25× healthy | 1.25–2.0× | > 2.0× |")
    print("| Mean palm speed | ≥ 80% healthy | 50–80% | < 50% |")
    print("\nPattern check (AOMI hypothesis): BVE Pre>Post>H; Speed H≥Post≥Pre\n")


if __name__ == "__main__":
    main()
