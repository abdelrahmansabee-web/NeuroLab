# -*- coding: utf-8 -*-
"""
High-quality wrist tracking using a physical colored marker (blob) on the back of the hand.

Protocol:
- Place a small, round, colored marker (e.g., red/orange sticker) on the dorsal wrist/back of hand.
- Record from the same side as the affected limb (side view).
- This script:
  1. Detects the marker via HSV color thresholding.
  2. Tracks it with a Kalman filter.
  3. Falls back to MediaPipe Pose wrist if marker is lost.
  4. Outputs CSV + overlay video.
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import argparse
import os

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Track a red wrist marker using HSV + Kalman.")
parser.add_argument("--video", required=True, help="Input video path")
parser.add_argument("--output-csv", required=True, help="Output CSV path")
parser.add_argument("--output-video", required=True, help="Output overlay video path")
parser.add_argument("--side", default="LEFT", choices=["LEFT", "RIGHT"], help="Affected side")
parser.add_argument("--min-radius", type=int, default=3, help="Minimum marker radius in px")
parser.add_argument("--max-radius", type=int, default=120, help="Maximum marker radius in px")
args = parser.parse_args()

video_path = args.video
output_csv = args.output_csv
output_video = args.output_video
affected_side = args.side

# Tight HSV range for a pure red marker on the wrist.
# Red appears in two Hue wraps in OpenCV HSV.
hsv_lower1 = np.array([0, 140, 70])
hsv_upper1 = np.array([10, 255, 255])
hsv_lower2 = np.array([170, 140, 70])
hsv_upper2 = np.array([179, 255, 255])

MIN_RADIUS = args.min_radius
MAX_RADIUS = args.max_radius

# Minimum marker radius in pixels (depends on camera distance)
MIN_RADIUS = 3
MAX_RADIUS = 120


# Search / rejection parameters
max_jump_px = 60.0
lost_reset_frames = 10

# ------------------------------------------------------------------
# MediaPipe Pose (fallback only)
# ------------------------------------------------------------------
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils


def get_pose_wrist_xy(pose_results, side, w, h):
    if not pose_results.pose_landmarks:
        return None
    lm = pose_results.pose_landmarks.landmark
    idx = mp_pose.PoseLandmark.LEFT_WRIST if side == "LEFT" else mp_pose.PoseLandmark.RIGHT_WRIST
    p = lm[idx]
    if p.visibility < 0.5:
        return None
    return np.array([p.x * w, p.y * h])


def detect_colored_marker(hsv_frame, lower1, upper1, lower2, upper2, min_r, max_r):
    """
    Returns the (x, y) center of the largest circular contour matching the color range.
    """
    mask1 = cv2.inRange(hsv_frame, lower1, upper1)
    mask2 = cv2.inRange(hsv_frame, lower2, upper2)
    mask = cv2.bitwise_or(mask1, mask2)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_score = -1.0
    for c in contours:
        (x, y), radius = cv2.minEnclosingCircle(c)
        if radius < min_r or radius > max_r:
            continue
        area = cv2.contourArea(c)
        # circularity score
        perimeter = cv2.arcLength(c, True)
        if perimeter <= 0:
            continue
        circularity = 4 * np.pi * area / (perimeter ** 2)
        score = area * circularity
        if score > best_score:
            best_score = score
            best = (np.array([x, y]), radius, circularity)
    return best, mask


# ------------------------------------------------------------------
# Main processing
# ------------------------------------------------------------------
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(output_video, fourcc, fps, (w, h))

kalman = cv2.KalmanFilter(4, 2)
kalman.transitionMatrix = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)
kalman.processNoiseCov = np.array([[5e-3, 0, 0, 0], [0, 5e-3, 0, 0], [0, 0, 5e-2, 0], [0, 0, 0, 5e-2]], dtype=np.float32)
kalman.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
kalman.measurementNoiseCov = np.array([[2e-1, 0], [0, 2e-1]], dtype=np.float32)
kalman.errorCovPost = np.eye(4, dtype=np.float32)

rows = []
tracked_point = None
initialized = False
lost_frames = 0
frame_idx = 0

print(f"Processing {n_frames} frames...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    pose_results = pose.process(rgb)
    pose_wrist = get_pose_wrist_xy(pose_results, affected_side, w, h)

    predicted_pt = None
    predicted_vel = np.array([0.0, 0.0])
    if initialized:
        pred = kalman.predict()
        predicted_pt = np.array([pred[0, 0], pred[1, 0]])
        predicted_vel = np.array([pred[2, 0], pred[3, 0]])

    measurement = None
    marker_radius = np.nan
    marker_score = np.nan

    # 1) Detect colored marker
    det, mask = detect_colored_marker(hsv, hsv_lower1, hsv_upper1, hsv_lower2, hsv_upper2, MIN_RADIUS, MAX_RADIUS)
    if det is not None:
        cand, radius, circularity = det
        marker_radius = radius
        marker_score = circularity
        if not initialized:
            measurement = cand
        elif np.linalg.norm(cand - predicted_pt) <= max_jump_px:
            measurement = cand
        else:
            marker_score = -marker_score  # rejected as jump

    # 2) Fallback to pose wrist if marker lost
    if measurement is None and pose_wrist is not None:
        if not initialized:
            measurement = pose_wrist
        elif np.linalg.norm(pose_wrist - predicted_pt) <= max_jump_px * 1.5:
            measurement = pose_wrist

    # 3) Kalman update
    if initialized and measurement is not None:
        kalman.correct(np.array([[np.float32(measurement[0])], [np.float32(measurement[1])]]))
        tracked_point = np.array([kalman.statePost[0, 0], kalman.statePost[1, 0]])
        lost_frames = 0
    elif initialized:
        tracked_point = predicted_pt
        lost_frames += 1
        if lost_frames >= lost_reset_frames:
            initialized = False
            lost_frames = 0
    elif measurement is not None:
        kalman.statePost = np.array([[measurement[0]], [measurement[1]], [0.0], [0.0]], dtype=np.float32)
        initialized = True
        tracked_point = measurement
    else:
        tracked_point = None

    rows.append({
        "frame": frame_idx,
        "time": frame_idx / fps,
        "fps": fps,
        "frame_width_px": w,
        "frame_height_px": h,
        "tracked_x": tracked_point[0] if tracked_point is not None else np.nan,
        "tracked_y": tracked_point[1] if tracked_point is not None else np.nan,
        "marker_detected": 1.0 if det is not None and marker_score >= 0 else 0.0,
        "marker_radius": marker_radius,
        "marker_score": marker_score,
        "pose_wrist_x": pose_wrist[0] if pose_wrist is not None else np.nan,
        "pose_wrist_y": pose_wrist[1] if pose_wrist is not None else np.nan,
    })

    # Draw
    if tracked_point is not None:
        cx, cy = int(np.clip(tracked_point[0], 0, w)), int(np.clip(tracked_point[1], 0, h))
        cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
        cv2.circle(frame, (cx, cy), 10, (255, 255, 255), 2)
    if det is not None:
        mx, my = int(det[0][0]), int(det[0][1])
        cv2.circle(frame, (mx, my), int(det[1]), (255, 0, 0), 2)
    if pose_wrist is not None:
        wx, wy = int(pose_wrist[0]), int(pose_wrist[1])
        cv2.circle(frame, (wx, wy), 5, (0, 255, 0), -1)
    cv2.putText(frame, f"Frame {frame_idx} | marker={det is not None} | r={marker_radius:.1f}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    if pose_results.pose_landmarks:
        mp_drawing.draw_landmarks(frame, pose_results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

    writer.write(frame)
    frame_idx += 1
    if frame_idx % 100 == 0:
        print(f"Processed {frame_idx}/{n_frames}")

cap.release()
writer.release()
pose.close()

df = pd.DataFrame(rows)
df.to_csv(output_csv, index=False)
print(f"Saved CSV: {output_csv}")
print(f"Saved overlay: {output_video}")
print(f"Frames with marker detection: {df['marker_detected'].sum():.0f}/{len(df)}")
print(f"Frames with tracked point: {df['tracked_x'].notna().sum()}/{len(df)}")
if df['tracked_x'].notna().any():
    print(f"Tracked x range: {df['tracked_x'].min():.1f} - {df['tracked_x'].max():.1f}")
    print(f"Tracked y range: {df['tracked_y'].min():.1f} - {df['tracked_y'].max():.1f}")
