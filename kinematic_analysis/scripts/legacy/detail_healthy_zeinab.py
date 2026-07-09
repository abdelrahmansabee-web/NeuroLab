import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
import pandas as pd
import numpy as np
from stroke_kinematic_pipeline import calculate_sparc
from motion_invariants import forward_reach_window, body_frame_palm, sparc_motion_window

csv = r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv"
df = pd.read_csv(csv)
fw = 1920; fh = 1080
s = "RIGHT"
px = df[f"{s}_WRIST_X"].values * fw
py = df[f"{s}_WRIST_Y"].values * fh
sx = df[f"{s}_SHOULDER_X"].values * fw
sy = df[f"{s}_SHOULDER_Y"].values * fh
sw = np.median(np.hypot(df["LEFT_SHOULDER_X"].values*fw - df["RIGHT_SHOULDER_X"].values*fw,
                        df["LEFT_SHOULDER_Y"].values*fh - df["RIGHT_SHOULDER_Y"].values*fh))
fs = 1.0 / np.median(np.diff(df["time"].values))
on, off, peak = forward_reach_window(px, py, fs, shoulder_width=sw)
print(f"forward window: {on}-{off} ({(off-on+1)/fs:.2f}s), peak frame {peak}")

seg_px, seg_py = px[on:off+1], py[on:off+1]
straight = np.hypot(seg_px[-1]-seg_px[0], seg_py[-1]-seg_py[0])
path_len = np.sum(np.hypot(np.diff(seg_px), np.diff(seg_py)))
print(f"PSI (image) = {straight/path_len:.3f}, displacement = {straight/sw:.2f}SW")

bx, by, _, _ = body_frame_palm(px, py, sx, sy, sw)
seg_bx, seg_by = bx[on:off+1], by[on:off+1]
straight_bf = np.hypot(seg_bx[-1]-seg_bx[0], seg_by[-1]-seg_by[0])
path_len_bf = np.sum(np.hypot(np.diff(seg_bx), np.diff(seg_by)))
print(f"PSI (body-frame) = {straight_bf/path_len_bf:.3f}, displacement = {straight_bf:.2f}SW")

spd = np.hypot(np.gradient(bx)*fs, np.gradient(by)*fs)
a_on, a_off = sparc_motion_window(spd, on, off, speed_frac=0.30)
print(f"accel window: {a_on}-{a_off} ({(a_off-a_on+1)/fs:.2f}s)")
print(f"SPARC full window = {calculate_sparc(seg_bx, seg_by, fs=fs):.3f}")
print(f"SPARC accel = {calculate_sparc(bx[a_on:a_off+1], by[a_on:a_off+1], fs=fs):.3f}")

# Speed profile stats
speed = np.hypot(np.gradient(seg_px)*fs, np.gradient(seg_py)*fs)
print(f"peak speed = {np.max(speed):.1f} px/s, time-to-peak = {(np.argmax(speed)/fs):.2f}s")
print(f"CV speed = {np.std(speed)/np.mean(speed):.3f}")
