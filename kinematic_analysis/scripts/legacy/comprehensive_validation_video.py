# -*- coding: utf-8 -*-
"""
Create comprehensive validation video for H and S showing:
- Original frame
- Rotated frame
- MediaPipe Pose landmarks on affected side (RIGHT)
- Marker tracking (red wrist marker)
- Start and end of reach window
- Elbow angle overlay
- Trajectory overlay
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
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

affected_side = "RIGHT"

# Red marker HSV
HSV_LOWER1 = np.array([0, 140, 70])
HSV_UPPER1 = np.array([10, 255, 255])
HSV_LOWER2 = np.array([170, 140, 70])
HSV_UPPER2 = np.array([179, 255, 255])

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


def detect_marker(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, HSV_LOWER1, HSV_UPPER1)
    mask2 = cv2.inRange(hsv, HSV_LOWER2, HSV_UPPER2)
    mask = cv2.bitwise_or(mask1, mask2)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    (x, y), r = cv2.minEnclosingCircle(c)
    if r < 3:
        return None
    return (int(x), int(y), int(r))


def angle_3points(a, b, c):
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def process_video(label, video_path):
    print(f"\n=== Validation video: {label} ===")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rot_w, rot_h = orig_h, orig_w

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    out_w, out_h = rot_w, rot_h
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = str(out_dir / f"comprehensive_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (out_w, out_h))

    # Load pose CSV for angle and window data
    pose_csv = out_dir / f"pose_compensation_{label}.csv"
    marker_csv = out_dir / f"{label.lower()}_red_marker_tracking.csv"
    df_pose = pd.read_csv(pose_csv) if pose_csv.exists() else None
    df_marker = pd.read_csv(marker_csv) if marker_csv.exists() else None

    # Find reach window from marker CSV
    reach_start = 0
    reach_end = n_frames - 1
    if df_marker is not None:
        t = df_marker['time'].values
        x = df_marker['tracked_x'].values
        y = df_marker['tracked_y'].values
        # displacement from start
        dx = x - x[0]
        dy = y - y[0]
        disp = np.sqrt(dx**2 + dy**2)
        # find first frame where displacement > 10% of max
        max_disp = disp.max()
        above = np.where(disp > 0.1 * max_disp)[0]
        if len(above) > 0:
            reach_start = above[0]
            reach_end = above[-1]
        print(f"  Reach window (marker): frame {reach_start} to {reach_end}")

    trajectory = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        annotated = rotated.copy()
        info_lines = [f"Frame: {frame_idx}/{n_frames}"]

        # Draw marker
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(annotated, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(annotated, (mx, my), 4, (0, 0, 255), -1)
            info_lines.append(f"Marker: ({mx},{my})")
            trajectory.append((mx, my))
        else:
            trajectory.append((np.nan, np.nan))

        # Draw trajectory
        for i in range(1, len(trajectory)):
            if not np.isnan(trajectory[i][0]) and not np.isnan(trajectory[i-1][0]):
                cv2.line(annotated, trajectory[i-1], trajectory[i], (255, 255, 0), 2)

        # Draw pose landmarks and elbow angle
        if results.pose_landmarks and df_pose is not None:
            lm = results.pose_landmarks.landmark
            mp_drawing.draw_landmarks(annotated, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            sh_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_SHOULDER')
            el_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_ELBOW')
            wr_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_WRIST')

            sh = np.array([lm[sh_idx].x * rot_w, lm[sh_idx].y * rot_h])
            el = np.array([lm[el_idx].x * rot_w, lm[el_idx].y * rot_h])
            wr = np.array([lm[wr_idx].x * rot_w, lm[wr_idx].y * rot_h])

            angle = angle_3points(sh, el, wr)
            info_lines.append(f"Elbow: {angle:.1f} deg")

            # Highlight affected side joints
            for pt, name in [(sh, 'SH'), (el, 'EL'), (wr, 'WR')]:
                cv2.circle(annotated, (int(pt[0]), int(pt[1])), 8, (0, 0, 255), -1)
                cv2.putText(annotated, name, (int(pt[0])+10, int(pt[1])-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Reach window shading
            if reach_start <= frame_idx <= reach_end:
                overlay = annotated.copy()
                cv2.rectangle(overlay, (0, 0), (out_w, out_h), (0, 255, 0), 15)
                annotated = cv2.addWeighted(annotated, 0.9, overlay, 0.1, 0)
                info_lines.append("IN REACH WINDOW")

        # Draw info panel
        y0 = 30
        for i, line in enumerate(info_lines):
            cv2.putText(annotated, line, (10, y0 + i*25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        writer.write(annotated)
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  processed {frame_idx}/{n_frames}")

    cap.release()
    writer.release()
    pose.close()
    print(f"Saved: {out_path}")


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
for label, path in videos.items():
    process_video(label, path)
