import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import cv2
import pandas as pd

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

for vid in ["healthy.mov", "affected.mov"]:
    p = ROOT / vid
    cap = cv2.VideoCapture(str(p))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = n / fps if fps > 0 else 0
    cap.release()
    print(f"{vid}: {w}x{h}, {fps:.2f} fps, {n} frames, {dur:.1f}s")

# Check extracted CSVs
for label in ["healthy", "affected"]:
    csv = ROOT / "extracted" / f"{label}_landmarks.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        print(f"\n{label}_landmarks.csv: {len(df)} rows")
        print("  columns:", df.columns[:5].tolist(), "...", df.columns[-5:].tolist())
        if "camera_view" in df.columns:
            print("  camera_view:", df["camera_view"].iloc[0])
        if "affected_side" in df.columns:
            print("  affected_side:", df["affected_side"].iloc[0])
        if "frame_width_px" in df.columns:
            print("  frame_width_px:", df["frame_width_px"].iloc[0])
        if "fps" in df.columns:
            print("  fps:", df["fps"].iloc[0])
