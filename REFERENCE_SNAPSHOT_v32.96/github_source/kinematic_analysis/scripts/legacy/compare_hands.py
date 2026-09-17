import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import numpy as np
import pandas as pd

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

for label in ["healthy", "affected"]:
    csv = ROOT / "extracted" / f"{label}_landmarks.csv"
    df = pd.read_csv(csv)
    time = df["time"].values if "time" in df.columns else np.arange(len(df))
    fs = 1.0 / np.median(np.diff(time)) if len(time) > 1 else 60
    print(f"\n=== {label} ===")
    print(f"duration: {time[-1]:.1f}s, fs: {fs:.1f}")
    for s in ["LEFT", "RIGHT"]:
        px = df[f"{s}_WRIST_X"].values
        py = df[f"{s}_WRIST_Y"].values
        disp = np.hypot(px[-1] - px[0], py[-1] - py[0])
        path = np.sum(np.hypot(np.diff(px), np.diff(py)))
        vx = np.gradient(px) * fs
        vy = np.gradient(py) * fs
        spd = np.sqrt(vx**2 + vy**2)
        maxspd = np.max(spd)
        meanspd = np.mean(spd)
        amp_x = np.ptp(px)
        amp_y = np.ptp(py)
        print(f"  {s}: displacement={disp:.1f}px, path={path:.1f}px, max_speed={maxspd:.1f}, mean_speed={meanspd:.1f}, range_x={amp_x:.1f}, range_y={amp_y:.1f}")
