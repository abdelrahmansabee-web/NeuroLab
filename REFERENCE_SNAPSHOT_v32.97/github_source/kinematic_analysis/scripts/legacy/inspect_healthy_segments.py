import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
import pandas as pd
import numpy as np

csv = r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv"
df = pd.read_csv(csv)
fw = 1920; fh = 1080
s = "RIGHT"
px = df[f"{s}_WRIST_X"].values * fw
py = df[f"{s}_WRIST_Y"].values * fh
print(f"Total wrist range: x={np.min(px):.0f}-{np.max(px):.0f}, y={np.min(py):.0f}-{np.max(py):.0f}")
print(f"Raw net displacement: {np.hypot(px[-1]-px[0], py[-1]-py[0]):.1f} px")

# Longest x-span between consecutive low-speed frames
fs = 1.0 / np.median(np.diff(df["time"].values))
vx = np.gradient(px) * fs
vy = np.gradient(py) * fs
spd = np.hypot(vx, vy)
mask = spd > 20
starts = []
ends = []
in_seg = False
for i, m in enumerate(mask):
    if m and not in_seg:
        starts.append(i)
        in_seg = True
    elif not m and in_seg:
        ends.append(i-1)
        in_seg = False
if in_seg: ends.append(len(mask)-1)

segs = []
for a, b in zip(starts, ends):
    if b - a + 1 >= 10:
        dx = np.max(px[a:b+1]) - np.min(px[a:b+1])
        dy = np.max(py[a:b+1]) - np.min(py[a:b+1])
        segs.append((a, b, dx, dy, np.hypot(dx, dy)))

for a, b, dx, dy, d in sorted(segs, key=lambda x: -x[4])[:5]:
    print(f"segment {a}-{b}: dx={dx:.0f}px, dy={dy:.0f}px, net={d:.0f}px")
