import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from stroke_kinematic_pipeline import _landmarks_from_mediapipe_csv, calculate_sparc_from_speed
from motion_invariants import body_frame_palm, smooth_series, select_literature_matched_window, forward_reach_window, literature_reach_window, sparc_speed_profile

BASE = Path(r"D:/Thesis app/participants/3 مرضى/33")
PATIENTS = ["مراد", "كوروسال", "زينب"]
SIDES = {"مراد": "left", "كوروسال": "right", "زينب": "right"}

for patient in PATIENTS:
    csv_path = BASE / patient / "extracted" / "Healthy side_landmarks.csv"
    df = pd.read_csv(csv_path)
    frame_width = int(df.get("frame_width_px", 1920).iloc[0]) if "frame_width_px" in df.columns else 1920
    frame_height = int(df.get("frame_height_px", 1080).iloc[0]) if "frame_height_px" in df.columns else 1080
    coords, side, sw = _landmarks_from_mediapipe_csv(df, affected_side=SIDES[patient], frame_width=frame_width, frame_height=frame_height)
    
    px, py, sx, sy = coords["palm_x"], coords["palm_y"], coords["shoulder_x"], coords["shoulder_y"]
    fs = 60.0
    
    # Current method
    on1, off1 = select_literature_matched_window(px, py, fs, shoulder_width=sw)
    speed, _ = sparc_speed_profile(px, py, sx, sy, sw, fs, on1, off1)
    on_s1, off_s1 = literature_reach_window(speed, fs, v_frac=0.05, search_start=on1, search_end=off1)
    sparc1 = calculate_sparc_from_speed(speed[on_s1:off_s1+1], fs=fs, fc=10.0, amp_th=0.05)
    
    # Forward-reach capped
    on2, off2, _ = forward_reach_window(px, py, fs, shoulder_width=sw)
    speed2, _ = sparc_speed_profile(px, py, sx, sy, sw, fs, on2, off2)
    on_s2, off_s2 = literature_reach_window(speed2, fs, v_frac=0.05, search_start=on2, search_end=off2)
    sparc2 = calculate_sparc_from_speed(speed2[on_s2:off_s2+1], fs=fs, fc=10.0, amp_th=0.05)
    
    # Forward-reach with higher threshold
    on_s3, off_s3 = literature_reach_window(speed2, fs, v_frac=0.10, search_start=on2, search_end=off2)
    sparc3 = calculate_sparc_from_speed(speed2[on_s3:off_s3+1], fs=fs, fc=10.0, amp_th=0.05)
    
    print(f"\n{patient} HEALTHY:")
    print(f"  Current: window={on1}-{off1}, sparc={sparc1:.4f}")
    print(f"  Forward cap: window={on2}-{off2}, sparc={sparc2:.4f}")
    print(f"  Forward cap + 10% thr: window={on_s3}-{off_s3}, sparc={sparc3:.4f}")
