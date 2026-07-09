import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
import pandas as pd
import numpy as np
from motion_invariants import forward_reach_window, reach_only_window
from stroke_kinematic_pipeline import calculate_sparc

csvs = [
    ("healthy", r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv", "right"),
    ("pre", r"D:\Thesis app\participants\mediapipe\movs\zeyneb\pre_20260603_165439_pre.csv", "left"),
    ("post", r"D:\Thesis app\participants\mediapipe\movs\zeyneb\post_20260603_165651_post.csv", "left"),
]

for label, csv, side in csvs:
    df = pd.read_csv(csv)
    s = side.upper()
    fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else 1920
    fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else 1080
    px = df[f"{s}_WRIST_X"].values * fw
    py = df[f"{s}_WRIST_Y"].values * fh
    sw = np.median(np.hypot(df["LEFT_SHOULDER_X"].values*fw - df["RIGHT_SHOULDER_X"].values*fw,
                            df["LEFT_SHOULDER_Y"].values*fh - df["RIGHT_SHOULDER_Y"].values*fh))
    fs = 1.0 / np.median(np.diff(df["time"].values)) if "time" in df.columns else 30.0
    
    print(f"\n{label}: n={len(px)}, fs={fs:.1f}, sw={sw:.1f}px")
    
    for win_name, (on, off, peak) in [
        ("forward", forward_reach_window(px, py, fs, shoulder_width=sw)),
        ("reach_only", reach_only_window(px, py, fs, shoulder_width=sw)),
    ]:
        seg_px, seg_py = px[on:off+1], py[on:off+1]
        straight = np.hypot(seg_px[-1]-seg_px[0], seg_py[-1]-seg_py[0])
        path_len = np.sum(np.hypot(np.diff(seg_px), np.diff(seg_py)))
        psi = straight/path_len if path_len>0 else np.nan
        bx = (seg_px - np.median(seg_px[:max(3,len(seg_px)//10)]))/sw
        by = (seg_py - np.median(seg_py[:max(3,len(seg_px)//10)]))/sw
        sparc = calculate_sparc(bx, by, fs=fs)
        print(f"  {win_name}: {on}-{off} ({(off-on+1)/fs:.2f}s), psi={psi:.3f}, sparc={sparc:.3f}, disp={straight/sw:.2f}SW")
