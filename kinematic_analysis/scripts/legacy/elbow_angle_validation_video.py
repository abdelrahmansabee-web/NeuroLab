# -*- coding: utf-8 -*-
"""
Create validation video showing elbow angle overlay on H.MOV and S.MOV.
Displays the elbow flexion angle in degrees on each frame.
"""
import cv2
import numpy as np
import pandas as pd
from pathlib import Path

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
input_dir = Path(r"D:\Thesis app\participants\3 مرضى\33\انا ٢")
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")

videos = {
    'H': str(input_dir / 'H.MOV'),
    'S': str(input_dir / 'S.MOV'),
}

for label, video_path in videos.items():
    csv_path = out_dir / f"pose_compensation_{label}.csv"
    df = pd.read_csv(csv_path)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = str(out_dir / f"elbow_angle_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx < len(df):
            row = df.iloc[frame_idx]
            sh = (int(row['sh_x']), int(row['sh_y']))
            el = (int(row['el_x']), int(row['el_y']))
            wr = (int(row['wr_x']), int(row['wr_y']))
            angle = row['elbow_flexion_angle']

            # Draw skeleton
            if not np.isnan(angle):
                cv2.line(frame, sh, el, (0, 255, 255), 3)
                cv2.line(frame, el, wr, (0, 255, 255), 3)
                cv2.circle(frame, sh, 6, (0, 0, 255), -1)
                cv2.circle(frame, el, 8, (0, 255, 0), -1)
                cv2.circle(frame, wr, 6, (255, 0, 0), -1)

                # Draw angle arc at elbow
                dx1 = sh[0] - el[0]
                dy1 = sh[1] - el[1]
                dx2 = wr[0] - el[0]
                dy2 = wr[1] - el[1]
                a1 = np.degrees(np.arctan2(dy1, dx1))
                a2 = np.degrees(np.arctan2(dy2, dx2))
                start_angle = min(a1, a2)
                end_angle = max(a1, a2)
                cv2.ellipse(frame, el, (30, 30), 0, start_angle, end_angle, (255, 255, 255), 2)

                # Text
                text = f"Elbow: {angle:.1f} deg"
                cv2.putText(frame, text, (el[0] + 20, el[1] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Frame {frame_idx}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        writer.write(frame)
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"{label}: processed {frame_idx}/{n_frames}")

    cap.release()
    writer.release()
    print(f"Saved: {out_video_path}")
