# -*- coding: utf-8 -*-
"""
Create a validation video showing ALL computed variables frame-by-frame for H and S.
Displays: frame number, time, marker position, NVP count so far, current speed,
elbow angle, shoulder elevation, trunk displacement, wrist forward, pause time.
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks

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
shoulder_width_cm = 40.0
VISIBILITY_THRESHOLD = 0.5

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


def lowpass_filter(x, fs, cutoff=10.0, order=4):
    if np.all(np.isnan(x)) or len(x) < 10:
        return x
    nyq = 0.5 * fs
    if cutoff / nyq >= 1:
        return x
    b, a = butter(order, cutoff / nyq, btype='low')
    mask = ~np.isnan(x)
    xi = np.arange(len(x))
    x_filled = np.interp(xi, xi[mask], x[mask])
    return filtfilt(b, a, x_filled)


def angle_3points(a, b, c):
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def compute_speed_and_nvp(df_marker):
    fps = df_marker['fps'].iloc[0]
    dt = 1.0 / fps
    x = df_marker['tracked_x'].values
    y = df_marker['tracked_y'].values
    t = df_marker['time'].values
    x = lowpass_filter(x, fps, cutoff=10.0)
    y = lowpass_filter(y, fps, cutoff=10.0)
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed = np.sqrt(vx**2 + vy**2)
    speed = lowpass_filter(speed, fps, cutoff=10.0)
    speed = np.clip(speed, 0, None)
    peaks, _ = find_peaks(speed, prominence=np.nanstd(speed)*0.5, distance=int(fps*0.15))
    return speed, peaks


def process_video(label, video_path):
    print(f"\n=== Full validation video: {label} ===")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rot_w, rot_h = orig_h, orig_w

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = str(out_dir / f"all_variables_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (rot_w, rot_h))

    # Load CSVs
    pose_csv = out_dir / f"pose_compensation_{label}.csv"
    marker_csv = out_dir / f"{label.lower()}_red_marker_tracking.csv"
    df_pose = pd.read_csv(pose_csv) if pose_csv.exists() else None
    df_marker = pd.read_csv(marker_csv) if marker_csv.exists() else None

    speed = None
    peaks = None
    if df_marker is not None:
        speed, peaks = compute_speed_and_nvp(df_marker)
        print(f"  Total NVP: {len(peaks)}")

    # Compute shoulder width in px and cm/px
    if df_pose is not None:
        shoulder_width_px = abs(df_pose['sh_x'].iloc[:10].mean() - df_pose['opp_sh_x'].iloc[:10].mean())
        cm_per_px = shoulder_width_cm / shoulder_width_px
        print(f"  Shoulder width px: {shoulder_width_px:.1f}, cm/px: {cm_per_px:.4f}")

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

        info = [f"Frame: {frame_idx}/{n_frames}"]

        # Marker tracking
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(annotated, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(annotated, (mx, my), 4, (0, 0, 255), -1)
            trajectory.append((mx, my))
            info.append(f"Marker: ({mx}, {my})")
        else:
            trajectory.append((np.nan, np.nan))

        # Trajectory
        valid_traj = [(int(x), int(y)) for x, y in trajectory if not np.isnan(x)]
        for i in range(1, len(valid_traj)):
            cv2.line(annotated, valid_traj[i-1], valid_traj[i], (255, 255, 0), 2)

        # Pose and variables
        if df_pose is not None and frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            sh = np.array([row['sh_x'], row['sh_y']])
            el = np.array([row['el_x'], row['el_y']])
            wr = np.array([row['wr_x'], row['wr_y']])
            hip = np.array([row['hip_x'], row['hip_y']])

            # Draw pose
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(annotated, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # Highlight affected side
            for pt, name in [(sh, 'SH'), (el, 'EL'), (wr, 'WR'), (hip, 'HIP')]:
                if not np.isnan(pt[0]):
                    cv2.circle(annotated, (int(pt[0]), int(pt[1])), 8, (0, 0, 255), -1)
                    cv2.putText(annotated, name, (int(pt[0])+10, int(pt[1])-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Elbow angle
            angle = angle_3points(sh, el, wr)
            info.append(f"Elbow: {angle:.1f} deg")

            # Metrics from pose
            shoulder_elev_cm = row['shoulder_elevation_cm']
            trunk_disp_cm = row['trunk_x_displacement_cm']
            wrist_forward_cm = row['wrist_forward_cm']
            info.append(f"Shoulder elev: {shoulder_elev_cm:.1f} cm")
            info.append(f"Trunk disp: {trunk_disp_cm:.1f} cm")
            info.append(f"Wrist forward: {wrist_forward_cm:.1f} cm")

        # Marker-derived variables
        if df_marker is not None and frame_idx < len(df_marker) and speed is not None:
            info.append(f"Speed: {speed[frame_idx]:.1f} px/s")
            # NVP count so far
            nvp_so_far = np.sum(peaks <= frame_idx)
            info.append(f"NVP so far: {nvp_so_far}")

        # Draw info panel
        panel_h = 25 * len(info) + 15
        overlay = annotated.copy()
        cv2.rectangle(overlay, (5, 5), (450, panel_h), (0, 0, 0), -1)
        annotated = cv2.addWeighted(annotated, 0.7, overlay, 0.3, 0)
        for i, line in enumerate(info):
            cv2.putText(annotated, line, (15, 30 + i*25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

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
