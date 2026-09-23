import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
import pandas as pd
import numpy as np
from motion_invariants import forward_reach_window
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

csvs = [
    ("pre", r"D:\Thesis app\participants\mediapipe\movs\zeyneb\pre_20260603_165439_pre.csv", "left"),
    ("post", r"D:\Thesis app\participants\mediapipe\movs\zeyneb\post_20260603_165651_post.csv", "left"),
]

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for ax, (label, csv, side) in zip(axes, csvs):
    df = pd.read_csv(csv)
    s = side.upper()
    fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else 1920
    fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else 1080
    px = df[f"{s}_WRIST_X"].values * fw
    py = df[f"{s}_WRIST_Y"].values * fh
    sw = np.median(np.hypot(df["LEFT_SHOULDER_X"].values*fw - df["RIGHT_SHOULDER_X"].values*fw,
                            df["LEFT_SHOULDER_Y"].values*fh - df["RIGHT_SHOULDER_Y"].values*fh))
    fs = 1.0 / np.median(np.diff(df["time"].values)) if "time" in df.columns else 30.0
    
    ax.plot(px, py, 'b-', alpha=0.5, label='full path')
    on, off, _ = forward_reach_window(px, py, fs, shoulder_width=sw)
    ax.plot(px[on:off+1], py[on:off+1], 'r-', linewidth=2, label=f'window {on}-{off}')
    ax.scatter(px[on], py[on], c='g', s=50, zorder=5)
    ax.scatter(px[off], py[off], c='r', s=50, zorder=5)
    ax.invert_yaxis()
    ax.set_aspect('equal')
    ax.set_title(f'{label}: forward window {on}-{off}')
    ax.legend()

plt.tight_layout()
out = r"C:\Users\acer\AppData\Local\Temp\opencode\zeinab_paths.png"
plt.savefig(out, dpi=150)
print(f"saved {out}")
