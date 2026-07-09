import sys
sys.path.insert(0, r'D:\Thesis app\NeuroLab\hf_repo')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stroke_kinematic_pipeline import _coords_for_trial

csv = r'D:/Thesis app/participants/kurusal/pre_20260617_142855_pre.csv'
df = pd.read_csv(csv)
coords, sw, side = _coords_for_trial(df, csv, 'left', 1920, 1080)
px, py = coords['palm_x'], coords['palm_y']
print('side:', side, 'sw:', sw)
print('palm range x:', px.min(), px.max(), 'y:', py.min(), py.max())

from motion_invariants import select_literature_matched_window, body_frame_palm, forward_reach_window
fs = 30
on, off = select_literature_matched_window(px, py, fs, shoulder_width=sw, velocity_threshold_frac=0.05, min_duration_s=0.50, min_amplitude_sw=0.12, amplitude_tolerance=0.20)
print('lit window:', on, off, 'dur:', (off-on+1)/fs)
bx, by, bz, _ = body_frame_palm(px, py, coords.get('shoulder_x', px), coords.get('shoulder_y', py), sw)
amp = np.hypot(bx[off]-bx[on], by[off]-by[on])
print('native amp sw:', amp)

fig, ax = plt.subplots(1,1,figsize=(10,6))
ax.plot(px, py, 'b-', alpha=0.5, label='palm path')
ax.plot(px[on], py[on], 'go', markersize=10, label='lit onset')
ax.plot(px[off], py[off], 'ro', markersize=10, label='lit offset')
ax.invert_yaxis()
ax.set_aspect('equal')
ax.legend()
plt.title('Kurusal Pre palm path')
plt.savefig(r'C:\Users\acer\AppData\Local\Temp\opencode\kurusal_pre_path.png')
print('saved')
