# -*- coding: utf-8 -*-
"""
Kinematic QC plots for reach-wipe trials.

Visual check (extraction + windows) is separate from SPARC numbers.
Plots show the same outbound / bell windows used by stroke_kinematic_pipeline v12.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from motion_invariants import (
    body_frame_palm,
    infer_trial_role,
    outbound_reach_window,
    reach_speed_series,
    sparc_bell_window,
)
from stroke_kinematic_pipeline import (
    ANALYSIS_TARGET_FS,
    NATIVE_FS_UPSAMPLE_BELOW,
    _coords_for_trial,
    _upsample_coord_dict,
    prepare_trial_timeseries,
)


def _analysis_profile(role: str) -> str:
    return "reference" if (role or "").lower() == "healthy" else "affected"


def trial_kinematic_series(
    csv_path: str,
    affected_side: str = "auto",
    trial_role: Optional[str] = None,
    frame_width: int = 1920,
    frame_height: int = 1080,
) -> Dict[str, Any]:
    """Load trial and compute displacement/speed series + analysis windows."""
    df = pd.read_csv(csv_path)
    df, native_fs, analysis_fs, upsampled = prepare_trial_timeseries(df)
    fs = float(analysis_fs)

    if "frame_width_px" in df.columns:
        frame_width = int(df["frame_width_px"].iloc[0])
    if "frame_height_px" in df.columns:
        frame_height = int(df["frame_height_px"].iloc[0])

    coords, shoulder_width, side = _coords_for_trial(
        df, csv_path, affected_side, frame_width, frame_height
    )
    role = (trial_role or infer_trial_role(csv_path, affected_side=side)).lower()
    profile = _analysis_profile(role)

    move_start_native, move_end_native, _ = outbound_reach_window(
        coords["palm_x"],
        coords["palm_y"],
        native_fs,
        shoulder_width=shoulder_width,
        analysis_profile=profile,
    )

    if not upsampled and native_fs < NATIVE_FS_UPSAMPLE_BELOW:
        coords = _upsample_coord_dict(coords, native_fs, ANALYSIS_TARGET_FS)
        fs = ANALYSIS_TARGET_FS
        n = len(coords["palm_x"])
        move_start = int(round(move_start_native / native_fs * fs))
        move_end = int(round(move_end_native / native_fs * fs))
        move_start = max(0, min(move_start, n - 1))
        move_end = max(move_start, min(move_end, n - 1))
    else:
        move_start, move_end = int(move_start_native), int(move_end_native)

    px, py = coords["palm_x"], coords["palm_y"]
    sx, sy = coords["shoulder_x"], coords["shoulder_y"]
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else 50.0

    bx, by, bz, _ = body_frame_palm(px, py, sx, sy, shoulder_width)
    speed = reach_speed_series(bx, by, bz, fs)

    n_prefix = max(5, int(0.12 * len(px)))
    x0, y0 = float(np.median(px[:n_prefix])), float(np.median(py[:n_prefix]))
    disp_sw = np.hypot(px - x0, py - y0) / sw
    t = np.arange(len(px)) / fs

    sparc_start, sparc_end = sparc_bell_window(speed, move_start, move_end)

    return {
        "csv_path": str(csv_path),
        "side": side,
        "role": role,
        "analysis_profile": profile,
        "fs_hz": fs,
        "native_fs_hz": native_fs,
        "time_s": t,
        "disp_sw": disp_sw,
        "speed_bf": speed,
        "move_start": move_start,
        "move_end": move_end,
        "sparc_start": sparc_start,
        "sparc_end": sparc_end,
        "shoulder_width_px": sw,
    }


def plot_trial_kinematics(
    csv_path: str,
    output_png: str,
    affected_side: str = "auto",
    trial_role: Optional[str] = None,
    analysis_result: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
) -> str:
    """
    Save 2-panel QC figure: displacement + body-frame speed with windows.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = trial_kinematic_series(csv_path, affected_side, trial_role)
    t = data["time_s"]
    ms, me = data["move_start"], data["move_end"]
    ws, we = data["sparc_start"], data["sparc_end"]

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax0, ax1 = axes

    ax0.plot(t, data["disp_sw"], color="#2563eb", lw=1.6, label="Palm displacement (SW)")
    ax0.axvspan(t[ms], t[me], alpha=0.15, color="#16a34a", label="Outbound window")
    ax0.set_ylabel("Displacement (SW)")
    ax0.grid(True, alpha=0.3)
    ax0.legend(loc="upper right", fontsize=8)

    ax1.plot(t, data["speed_bf"], color="#7c3aed", lw=1.6, label="Body-frame speed")
    ax1.axvspan(t[ms], t[me], alpha=0.12, color="#16a34a", label="Outbound")
    ax1.axvspan(t[ws], t[we], alpha=0.25, color="#f59e0b", label="SPARC bell")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Speed (px/s)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right", fontsize=8)

    sparc_txt = ""
    if analysis_result and analysis_result.get("sparc") is not None:
        sp = analysis_result.get("sparc")
        if np.isfinite(sp):
            sparc_txt = f"  SPARC={sp:.3f}"
    hdr = title or Path(csv_path).stem
    fig.suptitle(
        f"{hdr}  |  {data['role'].upper()}  |  {data['analysis_profile']}  |  "
        f"{data['side']} arm{sparc_txt}",
        fontsize=11,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    out = Path(output_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return str(out)


def plot_patient_triad_overlay(
    trials: Dict[str, Dict[str, Any]],
    output_png: str,
    metric: str = "speed_bf",
) -> str:
    """Overlay pre/post/healthy speed or displacement on one chart for visual compare."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"pre": "#dc2626", "post": "#2563eb", "healthy": "#16a34a"}
    fig, ax = plt.subplots(figsize=(11, 5))

    for label, spec in trials.items():
        data = trial_kinematic_series(
            spec["csv"],
            spec.get("side", "auto"),
            label,
        )
        y = data["disp_sw"] if metric == "disp_sw" else data["speed_bf"]
        t = data["time_s"] - data["time_s"][data["move_start"]]
        ax.plot(t, y, color=colors.get(label, "#666"), lw=1.5, label=label.upper(), alpha=0.9)

    ylab = "Displacement (SW)" if metric == "disp_sw" else "Body-frame speed (px/s)"
    ax.set_xlabel("Time from outbound onset (s)")
    ax.set_ylabel(ylab)
    ax.set_title("Triad overlay (aligned at outbound onset)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out = Path(output_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return str(out)
