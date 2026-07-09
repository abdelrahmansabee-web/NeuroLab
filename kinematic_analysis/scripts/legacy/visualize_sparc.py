# -*- coding: utf-8 -*-
"""
Create an MP4 that visualizes how SPARC is computed from a reach-to-target video.

Side-by-side layout:
  - Left: original video frame with hand trajectory overlay and current hand position.
  - Right: speed profile + SPARC spectrum panel.

The speed curve shows:
  - image-plane hand speed (px/s)
  - body-frame hand speed (shoulder-width normalized) used for SPARC
  - the selected SPARC window (green shaded region)
  - the current frame marker

The spectrum panel shows the normalized amplitude spectrum of the SPARC window
with the amplitude-threshold cutoff.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from numpy.fft import fft

REPO = Path(r"D:\Thesis app\NeuroLab\hf_repo")
sys.path.insert(0, str(REPO))

from stroke_kinematic_pipeline import analyze_trial
from motion_invariants import body_frame_palm, sparc_speed_profile


def load_video_frame_size(video_path: str):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return w, h, fps, n_frames


def load_landmarks(csv_path: str, side: str, fw: int, fh: int):
    df = pd.read_csv(csv_path)
    s = side.upper()
    px = df[f"{s}_WRIST_X"].values * fw
    py = df[f"{s}_WRIST_Y"].values * fh
    sx = df[f"{s}_SHOULDER_X"].values * fw
    sy = df[f"{s}_SHOULDER_Y"].values * fh
    time = df["time"].values if "time" in df.columns else np.arange(len(df)) / 30.0
    fs = 1.0 / np.median(np.diff(time)) if len(time) > 1 else 30.0
    sw = float(
        np.nanmedian(
            np.hypot(
                df["LEFT_SHOULDER_X"].values * fw - df["RIGHT_SHOULDER_X"].values * fw,
                df["LEFT_SHOULDER_Y"].values * fh - df["RIGHT_SHOULDER_Y"].values * fh,
            )
        )
    )
    return {
        "px": px,
        "py": py,
        "sx": sx,
        "sy": sy,
        "time": time,
        "fs": fs,
        "sw": sw,
    }


def image_plane_speed(px: np.ndarray, py: np.ndarray, fs: float) -> np.ndarray:
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    return np.sqrt(vx ** 2 + vy ** 2)


def lowpass_speed(v: np.ndarray, fs: float, cutoff: float = 10.0) -> np.ndarray:
    try:
        from scipy.signal import butter, filtfilt

        nyq = fs / 2.0
        b, a = butter(N=2, Wn=cutoff / nyq, btype="low")
        return filtfilt(b, a, v)
    except Exception:
        return v


def spectrum_figure(
    v_window: np.ndarray,
    fs: float,
    sparc_value: float,
    fc: float = 10.0,
    amp_th: float = 0.05,
    padlevel: int = 4,
    width: int = 640,
    height: int = 360,
) -> np.ndarray:
    """Render normalized speed spectrum for the SPARC window."""
    v = np.asarray(v_window, dtype=float)
    t_span = len(v) / fs
    path_len = float(np.sum(v)) / fs
    v_norm = v * t_span / path_len if path_len > 0 else v

    nfft = int(pow(2, np.ceil(np.log2(len(v_norm))) + padlevel))
    f = np.arange(0, fs, fs / nfft)
    mf = np.abs(fft(v_norm, nfft))
    peak = np.max(mf) if len(mf) else 1.0
    mf = mf / peak if peak > 0 else mf

    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    ax = fig.add_axes([0.12, 0.15, 0.86, 0.75])
    ax.plot(f, mf, color="#2c3e50", lw=1.5)
    ax.axhline(amp_th, color="red", ls="--", lw=1, label=f"amp threshold = {amp_th}")
    ax.axvline(fc, color="green", ls="--", lw=1, label=f"fc = {fc} Hz")

    # highlight the SPARC integration band
    sel = (f <= fc) & (mf >= amp_th)
    if np.any(sel):
        idx = np.where(sel)[0]
        ax.fill_between(f[idx[0] : idx[-1] + 1], 0, mf[idx[0] : idx[-1] + 1], color="green", alpha=0.15)

    ax.set_xlim(0, min(fs / 2, fc + 2))
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Normalized amplitude")
    ax.set_title(f"SPARC window spectrum  |  SPARC = {sparc_value:.3f}")
    ax.legend(loc="upper right", fontsize=7)
    ax.grid(True, alpha=0.3)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    img = np.frombuffer(canvas.tostring_argb(), dtype=np.uint8).reshape(canvas.get_width_height()[::-1] + (4,))
    plt.close(fig)
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    return img


def speed_figure(
    time: np.ndarray,
    image_speed: np.ndarray,
    body_speed: np.ndarray,
    sparc_speed: np.ndarray,
    sparc_start: int,
    sparc_end: int,
    current_frame: int,
    fs: float,
    sw: float,
    width: int = 640,
    height: int = 360,
) -> np.ndarray:
    """Render speed profile with current frame marker and SPARC window."""
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    ax = fig.add_axes([0.10, 0.15, 0.88, 0.75])

    ax.plot(time, image_speed, color="gray", lw=1, alpha=0.7, label="image-plane speed (px/s)")
    ax.plot(time, body_speed * sw, color="#2980b9", lw=1.5, label="body-frame speed (px/s)")

    # SPARC window speed
    sparc_t = time[sparc_start : sparc_end + 1]
    sparc_v = body_speed[sparc_start : sparc_end + 1] * sw
    ax.plot(sparc_t, sparc_v, color="#27ae60", lw=2.5, label="SPARC window speed")
    ax.axvspan(time[sparc_start], time[sparc_end], color="green", alpha=0.08)

    # current frame marker
    if 0 <= current_frame < len(time):
        ax.axvline(time[current_frame], color="red", ls="-", lw=1.5, alpha=0.8)

    ax.set_xlim(time[0], time[-1])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (px/s)")
    ax.set_title("Hand speed profile")
    ax.legend(loc="upper right", fontsize=7)
    ax.grid(True, alpha=0.3)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    img = np.frombuffer(canvas.tostring_argb(), dtype=np.uint8).reshape(canvas.get_width_height()[::-1] + (4,))
    plt.close(fig)
    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    return img


def make_visualization(
    video_path: str,
    csv_path: str,
    side: str,
    output_mp4: str,
    trial_role: str = "pre",
    camera_view: str = "oblique",
):
    video_path = str(video_path)
    csv_path = str(csv_path)
    vw, vh, vfps, vn = load_video_frame_size(video_path)
    lm = load_landmarks(csv_path, side, vw, vh)
    px, py, time, fs, sw = lm["px"], lm["py"], lm["time"], lm["fs"], lm["sw"]

    # Run validated pipeline to get SPARC window
    r = analyze_trial(csv_path, affected_side=side, trial_role=trial_role, camera_view=camera_view)
    sparc = float(r["sparc"])
    sparc_start = int(r["sparc_window_onset_frame"])
    sparc_end = int(r["sparc_window_offset_frame"])
    move_start = int(r["reach_window_onset_frame"])
    move_end = int(r["reach_window_offset_frame"])

    # Body-frame coordinates for SPARC
    bx, by, bz, _ = body_frame_palm(px, py, lm["sx"], lm["sy"], sw)
    body_speed = np.sqrt(np.gradient(bx) ** 2 + np.gradient(by) ** 2) * fs
    body_speed = lowpass_speed(body_speed, fs, cutoff=10.0)
    image_speed = image_plane_speed(px, py, fs)

    # Speed used inside the SPARC window (with outlier clip)
    sparc_speed = body_speed[sparc_start : sparc_end + 1].copy()
    if len(sparc_speed) > 10:
        med = float(np.median(sparc_speed))
        mad = float(np.median(np.abs(sparc_speed - med)))
        if mad > 1e-9:
            sparc_speed = np.clip(sparc_speed, 0.0, med + 3.0 * 1.4826 * mad)

    # Video output
    cap = cv2.VideoCapture(video_path)
    output_w = vw if vw % 2 == 0 else vw - 1  # keep even width for split panels
    output_h = vh + 360  # video on top, plots stacked below
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_mp4), fourcc, vfps, (output_w, output_h))

    # Pre-compute trajectory mask (bright trail)
    trail = np.zeros((vh, vw, 3), dtype=np.uint8)
    valid = np.isfinite(px) & np.isfinite(py)
    pts = np.column_stack((px[valid], py[valid])).astype(np.int32)
    if len(pts) > 1:
        for i in range(1, len(pts)):
            alpha = int(255 * i / len(pts))
            cv2.line(trail, tuple(pts[i - 1]), tuple(pts[i]), (0, 255 - alpha, alpha), 2)

    # Pre-render static spectrum figure
    spec_img = spectrum_figure(sparc_speed, fs, sparc, fc=10.0, amp_th=0.05, width=output_w // 2, height=360)
    spec_img = cv2.resize(spec_img, (output_w // 2, 360))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Blend trajectory trail
        display = cv2.addWeighted(frame, 1.0, trail, 0.6, 0)

        # Current hand position
        if 0 <= frame_idx < len(px) and np.isfinite(px[frame_idx]) and np.isfinite(py[frame_idx]):
            cx, cy = int(px[frame_idx]), int(py[frame_idx])
            cv2.circle(display, (cx, cy), 8, (0, 0, 255), -1)
            cv2.circle(display, (cx, cy), 10, (255, 255, 255), 2)

        # Text overlay
        txt_y = 30
        cv2.putText(display, f"Frame {frame_idx}  |  SPARC = {sparc:.3f}", (15, txt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(display, f"Frame {frame_idx}  |  SPARC = {sparc:.3f}", (15, txt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        in_window = "INSIDE SPARC WINDOW" if sparc_start <= frame_idx <= sparc_end else ""
        if in_window:
            txt_y += 28
            cv2.putText(display, in_window, (15, txt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(display, in_window, (15, txt_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Render dynamic speed figure
        speed_img = speed_figure(
            time, image_speed, body_speed, sparc_speed,
            sparc_start, sparc_end, frame_idx, fs, sw,
            width=output_w // 2, height=360,
        )
        speed_img = cv2.resize(speed_img, (output_w // 2, 360))

        # Compose bottom panel
        bottom = np.zeros((360, output_w, 3), dtype=np.uint8)
        bottom[:, : output_w // 2] = speed_img
        bottom[:, output_w // 2 :] = spec_img

        # Add legend labels on bottom panel
        cv2.putText(bottom, "SPEED PROFILE", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(bottom, "SPARC SPECTRUM", (output_w // 2 + 15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        full = np.vstack([display, bottom])
        out.write(full)
        frame_idx += 1

    cap.release()
    out.release()
    print(f"Saved SPARC visualization to: {output_mp4}")
    print(f"  SPARC = {sparc:.3f}  |  window frames = {sparc_start}-{sparc_end}  |  fs = {fs:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--side", required=True)
    parser.add_argument("--role", default="pre")
    parser.add_argument("--view", default="oblique")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    make_visualization(args.video, args.csv, args.side, args.output, args.role, args.view)
