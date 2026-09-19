# -*- coding: utf-8 -*-
"""
Compare reach kinematics from three wrist sources:
- Red marker tracking
- MediaPipe Pose wrist
- MediaPipe Hands wrist (fusion)
"""
import pandas as pd
import numpy as np
from pathlib import Path

base = Path(r"D:\Thesis app\kinematic_analysis\data")

red = pd.read_csv(base / "wrist_marker_summary.csv")
red['source'] = 'red_marker'

pose_h = pd.read_csv(base / "pose_compensation_H.csv")
pose_s = pd.read_csv(base / "pose_compensation_S.csv")

# Compute pose wrist metrics
for label, df_pose in [('H', pose_h), ('S', pose_s)]:
    t = df_pose['time'].values
    x = df_pose['wr_x'].values
    y = df_pose['wr_y'].values
    dt = np.mean(np.diff(t))
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed = np.sqrt(vx**2 + vy**2)
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(speed, prominence=np.nanstd(speed)*0.5, distance=int(1/dt*0.15))
    nvp = len(peaks)
    disp = np.hypot(x[-1]-x[0], y[-1]-y[0])
    path = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    straight = disp/path if path>0 else np.nan
    print(f"Pose wrist {label}: NVP={nvp}, straightness={straight:.3f}, peak_speed={np.max(speed):.1f}")

# Load hands fusion summary
hands = pd.read_csv(Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / "hands_wrist_kinematics_summary.csv")
hands['source'] = 'hands_wrist'

print("\n=== Summary comparison ===")
print(red.to_string(index=False))
print("\n=== Hands wrist ===")
print(hands[['label','overall_straightness','nvp','n_stops','total_pause_time_s','peak_speed_px_s','time_to_peak_speed_s','n_submovements']].to_string(index=False))

# Side-by-side
compare = pd.merge(
    red[['label','overall_straightness','nvp','n_stops','total_pause_time_s','peak_speed_px_s','time_to_peak_speed_s']].rename(columns=lambda c: f"red_{c}" if c!='label' else c),
    hands[['label','overall_straightness','nvp','n_stops','total_pause_time_s','peak_speed_px_s','time_to_peak_speed_s']].rename(columns=lambda c: f"hands_{c}" if c!='label' else c),
    on='label'
)
print("\n=== Side-by-side (red vs hands) ===")
print(compare.to_string(index=False))
compare.to_csv(base / "../figures/hands_vs_red_marker_comparison.csv", index=False)
print("Saved comparison to: figures/hands_vs_red_marker_comparison.csv")
