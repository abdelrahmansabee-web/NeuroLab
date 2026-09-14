import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import cv2
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/33/انا")

# Metadata
for vid in ["Affected .mov", "Healthy.MOV"]:
    p = ROOT / vid
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = n / fps if fps > 0 else 0
    cap.release()
    print(f"{vid}: {w}x{h}, {fps:.2f} fps, {n} frames, {dur:.1f}s")

# Extract frames and save sample frames for visual inspection
for vid in ["Affected .mov", "Healthy.MOV"]:
    p = ROOT / vid
    cap = cv2.VideoCapture(str(p))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_to_save = [int(n * f) for f in [0.1, 0.3, 0.5, 0.7, 0.9]]
    for i, fnum in enumerate(frames_to_save):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fnum)
        ret, frame = cap.read()
        if ret:
            out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / f"{Path(vid).stem}_frame_{i}.jpg"
            cv2.imwrite(str(out), frame)
            print(f"saved {out}")
    cap.release()

# Quick path plot from extracted landmarks if exist
for label in ["Affected", "Healthy"]:
    csv = ROOT / "extracted" / f"{label}_landmarks.csv"
    if not csv.exists():
        continue
    df = pd.read_csv(csv)
    time = df["time"].values if "time" in df.columns else np.arange(len(df))
    fs = 1.0 / np.median(np.diff(time)) if len(time) > 1 else 60
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    for s in ["LEFT", "RIGHT"]:
        px = df[f"{s}_WRIST_X"].values * (df["frame_width_px"].iloc[0] if "frame_width_px" in df.columns else 1920)
        py = df[f"{s}_WRIST_Y"].values * (df["frame_height_px"].iloc[0] if "frame_height_px" in df.columns else 1080)
        ax[0].plot(px, py, label=s, alpha=0.7)
        vx = np.gradient(px) * fs
        vy = np.gradient(py) * fs
        spd = np.sqrt(vx**2 + vy**2)
        ax[1].plot(time, spd, label=s, alpha=0.7)
    ax[0].invert_yaxis()
    ax[0].set_aspect('equal')
    ax[0].set_title(f"{label}: wrist paths")
    ax[0].legend()
    ax[1].set_title(f"{label}: wrist speeds")
    ax[1].legend()
    out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / f"{label}_paths.png"
    plt.savefig(out)
    print(f"saved plot {out}")
    plt.close()
