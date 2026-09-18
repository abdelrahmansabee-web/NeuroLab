# -*- coding: utf-8 -*-
"""
Create a comprehensive validation video for H and S showing ALL variables literally:
- Marker tracking with trajectory
- Speed profile with peaks (NVP), pause time threshold
- Straightness / path
- Shoulder elevation, trunk displacement (mid-shoulder), wrist forward
- Elbow angle
- Time and speed metrics
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


def compute_marker_metrics(df_marker):
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
    
    # Straightness: displacement / path length
    path_len = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    disp = np.hypot(x[-1]-x[0], y[-1]-y[0])
    straightness = disp / path_len if path_len > 0 else np.nan
    
    # Pause time: speed < 5% of max for >= 0.1s
    threshold = 0.05 * speed.max()
    paused = speed < threshold
    pause_time = 0.0
    i = 0
    while i < len(paused):
        if paused[i]:
            j = i
            while j < len(paused) and paused[j]:
                j += 1
            dur = t[j-1] - t[i]
            if dur >= 0.1:
                pause_time += dur
            i = j
        else:
            i += 1
    
    # Movement time from speed threshold
    moving = speed > threshold
    move_time = 0.0
    i = 0
    while i < len(moving):
        if moving[i]:
            j = i
            while j < len(moving) and moving[j]:
                j += 1
            move_time += t[j-1] - t[i]
            i = j
        else:
            i += 1
    
    peak_speed = speed.max()
    peak_speed_idx = speed.argmax()
    time_to_peak = t[peak_speed_idx] - t[0]
    
    return {
        't': t, 'x': x, 'y': y, 'speed': speed, 'peaks': peaks,
        'straightness': straightness, 'pause_time': pause_time,
        'move_time': move_time, 'peak_speed': peak_speed,
        'time_to_peak': time_to_peak, 'threshold': threshold,
        'fps': fps, 'dt': dt
    }


def draw_text_panel(frame, lines, x=10, y=10, w=420, line_h=22):
    h = len(lines) * line_h + 15
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 0, 0), -1)
    frame = cv2.addWeighted(frame, 0.8, overlay, 0.2, 0)
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (x+10, y+25+i*line_h), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame


def process_video(label, video_path):
    print(f"\n=== Full variables validation: {label} ===")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rot_w, rot_h = orig_h, orig_w

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    out_path = str(out_dir / f"all_variables_final_validation_{label}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (rot_w, rot_h))

    pose_csv = out_dir / f"pose_compensation_{label}.csv"
    marker_csv = out_dir / f"{label.lower()}_red_marker_tracking.csv"
    df_pose = pd.read_csv(pose_csv) if pose_csv.exists() else None
    df_marker = pd.read_csv(marker_csv) if marker_csv.exists() else None

    mm = compute_marker_metrics(df_marker) if df_marker is not None else None
    if mm:
        print(f"  NVP: {len(mm['peaks'])}, Straightness: {mm['straightness']:.3f}, Pause time: {mm['pause_time']:.2f}s, Peak speed: {mm['peak_speed']:.1f} px/s")

    # Precompute overall summary for video
    if df_pose is not None:
        summary = {
            'shoulder_elev_max_cm': df_pose['shoulder_elevation_cm'].max(),
            'trunk_disp_max_cm': df_pose['trunk_x_displacement_cm'].max(),
            'wrist_forward_max_cm': df_pose['wrist_forward_cm'].max(),
            'elbow_min': df_pose['elbow_flexion_angle'].min(),
            'elbow_max': df_pose['elbow_flexion_angle'].max(),
        }
    else:
        summary = {}

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

        # Marker
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(annotated, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(annotated, (mx, my), 4, (0, 0, 255), -1)
            trajectory.append((mx, my))
        else:
            trajectory.append((np.nan, np.nan))

        valid_traj = [(int(x), int(y)) for x, y in trajectory if not np.isnan(x)]
        for i in range(1, len(valid_traj)):
            cv2.line(annotated, valid_traj[i-1], valid_traj[i], (255, 255, 0), 2)

        # Speed and NVP
        if mm and frame_idx < len(mm['speed']):
            cur_speed = mm['speed'][frame_idx]
            nvp_so_far = np.sum(mm['peaks'] <= frame_idx)
            info.append(f"Speed: {cur_speed:.1f} px/s")
            info.append(f"NVP so far: {nvp_so_far}/{len(mm['peaks'])}")
            # Pause indicator
            if cur_speed < mm['threshold']:
                cv2.putText(annotated, "PAUSE", (rot_w-120, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        # Pose landmarks
        if results.pose_landmarks and df_pose is not None and frame_idx < len(df_pose):
            lm = results.pose_landmarks.landmark
            mp_drawing.draw_landmarks(annotated, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            row = df_pose.iloc[frame_idx]
            sh = np.array([row['sh_x'], row['sh_y']])
            el = np.array([row['el_x'], row['el_y']])
            wr = np.array([row['wr_x'], row['wr_y']])
            hip = np.array([row['hip_x'], row['hip_y']])
            mid_sh = np.array([row['mid_shoulder_x'], (row['sh_y'] + row['opp_sh_y'])/2])

            for pt, name in [(sh, 'SH'), (el, 'EL'), (wr, 'WR'), (hip, 'HIP'), (mid_sh, 'M_SH')]:
                if not np.isnan(pt[0]):
                    cv2.circle(annotated, (int(pt[0]), int(pt[1])), 8, (0, 0, 255), -1)
                    cv2.putText(annotated, name, (int(pt[0])+10, int(pt[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            elbow_angle = angle_3points(sh, el, wr)
            info.append(f"Elbow: {elbow_angle:.1f} deg")
            info.append(f"Shoulder elev: {row['shoulder_elevation_cm']:.2f} / {summary['shoulder_elev_max_cm']:.2f} cm")
            info.append(f"Trunk disp: {row['trunk_x_displacement_cm']:.2f} / {summary['trunk_disp_max_cm']:.2f} cm")
            info.append(f"Wrist forward: {row['wrist_forward_cm']:.2f} / {summary['wrist_forward_max_cm']:.2f} cm")

        # Overall marker summary
        if mm:
            info.append(f"Straightness: {mm['straightness']:.3f}")
            info.append(f"Total pause time: {mm['pause_time']:.2f}s")
            info.append(f"Move time: {mm['move_time']:.2f}s")
            info.append(f"Peak speed: {mm['peak_speed']:.1f} px/s")
            info.append(f"Time to peak: {mm['time_to_peak']:.2f}s")

        annotated = draw_text_panel(annotated, info)
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
