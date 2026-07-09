import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mediapipe_csv_extractor import detect_affected_side, detect_camera_view

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

for idx, label in enumerate(["healthy", "affected"]):
    csv = ROOT / "extracted" / f"{label}_landmarks.csv"
    df = pd.read_csv(csv)
    fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else 1920
    fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else 1080
    
    side_auto = detect_affected_side(df, fw, fh)
    view_auto = detect_camera_view(df, fw, fh)
    print(f"\n{label}: auto side={side_auto}, auto view={view_auto}")
    
    # Plot both wrists and palms
    for s in ["LEFT", "RIGHT"]:
        px = df[f"{s}_WRIST_X"].values
        py = df[f"{s}_WRIST_Y"].values
        axes[idx, 0].plot(px, py, label=f"{s} wrist", alpha=0.7)
    axes[idx, 0].invert_yaxis()
    axes[idx, 0].set_aspect('equal')
    axes[idx, 0].set_title(f"{label}: wrist paths")
    axes[idx, 0].legend()
    
    # Plot speed of both wrists
    time = df["time"].values if "time" in df.columns else np.arange(len(df))
    for s in ["LEFT", "RIGHT"]:
        px = df[f"{s}_WRIST_X"].values
        py = df[f"{s}_WRIST_Y"].values
        fs = 1.0 / np.median(np.diff(time)) if len(time) > 1 else 60
        vx = np.gradient(px) * fs
        vy = np.gradient(py) * fs
        spd = np.sqrt(vx**2 + vy**2)
        axes[idx, 1].plot(time, spd, label=f"{s} wrist speed", alpha=0.7)
    axes[idx, 1].set_title(f"{label}: wrist speeds")
    axes[idx, 1].set_xlabel("time (s)")
    axes[idx, 1].set_ylabel("px/s")
    axes[idx, 1].legend()

plt.tight_layout()
plt.savefig(r"C:\Users\acer\AppData\Local\Temp\opencode\ana_paths.png")
print("\nsaved plot")
