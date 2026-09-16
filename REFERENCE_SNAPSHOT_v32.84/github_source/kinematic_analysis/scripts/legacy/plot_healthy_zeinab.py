import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
import pandas as pd
import numpy as np
from stroke_kinematic_pipeline import analyze_trial
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

csv = r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv"
r = analyze_trial(csv, affected_side="right", trial_role="healthy", camera_view="oblique")
df = pd.read_csv(csv)
fw = 1920; fh = 1080
s = "RIGHT"
px = df[f"{s}_WRIST_X"].values * fw
py = df[f"{s}_WRIST_Y"].values * fh
fs = 1.0 / np.median(np.diff(df["time"].values))
on = int(r["reach_window_onset_frame"])
off = int(r["reach_window_offset_frame"])

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Path
axes[0].plot(px, py, 'b-', alpha=0.4, label='full')
axes[0].plot(px[on:off+1], py[on:off+1], 'r-', linewidth=2, label=f'reach window {on}-{off}')
axes[0].scatter(px[on], py[on], c='g', s=60, zorder=5)
axes[0].scatter(px[off], py[off], c='r', s=60, zorder=5)
axes[0].invert_yaxis()
axes[0].set_aspect('equal')
axes[0].set_title('Zeinab healthy: wrist path')
axes[0].legend()

# Speed
spd = np.hypot(np.gradient(px)*fs, np.gradient(py)*fs)
t = np.arange(len(spd)) / fs
axes[1].plot(t, spd, 'b-', alpha=0.4)
axes[1].plot(t[on:off+1], spd[on:off+1], 'r-', linewidth=2)
axes[1].axvline(t[on], color='g', linestyle='--')
axes[1].axvline(t[off], color='r', linestyle='--')
axes[1].set_xlabel('time (s)')
axes[1].set_ylabel('speed (px/s)')
axes[1].set_title('Speed profile')
axes[1].legend(['full', 'reach window'])

plt.tight_layout()
out = r"C:\Users\acer\AppData\Local\Temp\opencode\zeinab_healthy_path_speed.png"
plt.savefig(out, dpi=150)
print(f"saved {out}")
print(f"window: {on}-{off} ({(off-on+1)/fs:.2f}s), peak speed = {np.max(spd[on:off+1]):.1f} px/s")
