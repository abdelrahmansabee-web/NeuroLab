# -*- coding: utf-8 -*-
"""
Premium validation video v2 - clean layout, large fonts, visible metrics.
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
    
    path_len = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    disp = np.hypot(x[-1]-x[0], y[-1]-y[0])
    straightness = disp / path_len if path_len > 0 else np.nan
    
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


def draw_panel_bg(canvas, x, y, w, h):
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (35, 38, 45), -1)
    canvas = cv2.addWeighted(canvas, 1.0, overlay, 0.95, 0)
    return canvas


def draw_text(img, text, x, y, size=0.7, color=(255,255,255), thickness=2):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, thickness, cv2.LINE_AA)


def draw_value_box(img, x, y, w, h, label, value, unit, color, font_scale=0.75):
    # Background box
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (45, 48, 55), -1)
    cv2.rectangle(overlay, (x, y), (x+w, y+h), color, 2)
    img = cv2.addWeighted(img, 0.3, overlay, 0.7, 0)
    # Label
    draw_text(img, label, x+8, y+18, size=0.5, color=(180,180,180), thickness=1)
    # Value
    value_text = f"{value:.1f}" if isinstance(value, float) else str(value)
    draw_text(img, value_text, x+8, y+44, size=font_scale, color=(255,255,255), thickness=2)
    # Unit
    draw_text(img, unit, x+w-50, y+44, size=0.5, color=color, thickness=1)
    return img


def draw_mini_graph(img, values, x, y, w, h, color, max_val=None, current_idx=0, label=""):
    if len(values) < 2:
        return img
    valid = np.array(values, dtype=float)
    max_val = max_val if max_val else np.nanmax(valid) if np.nanmax(valid) > 0 else 1
    min_val = np.nanmin(valid)
    rng = max_val - min_val if max_val != min_val else 1
    pts = []
    for i, v in enumerate(valid):
        px = x + int(i * w / len(valid))
        py = y + h - int((v - min_val) / rng * h)
        pts.append((px, py))
    # Graph background
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (30, 32, 38), -1)
    img = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)
    # Grid lines
    for gy in [y+h//4, y+h//2, y+3*h//4]:
        cv2.line(img, (x, gy), (x+w, gy), (60, 60, 65), 1)
    # Line
    for i in range(1, len(pts)):
        cv2.line(img, pts[i-1], pts[i], color, 2)
    if 0 <= current_idx < len(pts):
        cv2.circle(img, pts[current_idx], 5, (255,255,255), -1)
        cv2.circle(img, pts[current_idx], 3, color, -1)
    if label:
        draw_text(img, label, x, y-8, size=0.55, color=(200,200,200), thickness=1)
    return img


def process_video(label, video_path):
    print(f"\n=== Premium validation v2: {label} ===")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rot_w, rot_h = orig_h, orig_w
    
    # Panel on the right, keep video visible
    panel_w = 360
    out_w = rot_w + panel_w
    out_h = rot_h
    
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    
    out_path = str(out_dir / f"premium_validation_v2_{label}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (out_w, out_h))
    
    pose_csv = out_dir / f"pose_compensation_{label}.csv"
    marker_csv = out_dir / f"{label.lower()}_red_marker_tracking.csv"
    df_pose = pd.read_csv(pose_csv) if pose_csv.exists() else None
    df_marker = pd.read_csv(marker_csv) if marker_csv.exists() else None
    
    mm = compute_marker_metrics(df_marker) if df_marker is not None else None
    if mm:
        print(f"  NVP: {len(mm['peaks'])}, Straightness: {mm['straightness']:.3f}, "
              f"Pause: {mm['pause_time']:.2f}s, Peak speed: {mm['peak_speed']:.1f} px/s")
    
    if df_pose is not None:
        summary = {
            'shoulder_elev_max': df_pose['shoulder_elevation_cm'].max(),
            'trunk_disp_max': df_pose['trunk_x_displacement_cm'].max(),
            'wrist_forward_max': df_pose['wrist_forward_cm'].max(),
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
        
        # Canvas
        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[:, :rot_w] = rotated
        
        # Panel background
        canvas = draw_panel_bg(canvas, rot_w, 0, panel_w, out_h)
        
        px, py = rot_w + 15, 15
        
        # Title
        draw_text(canvas, "Kinematic Variables", px, py+25, size=0.85, color=(255,255,255), thickness=2)
        draw_text(canvas, f"{label}  |  Frame {frame_idx}/{n_frames}", px, py+48, size=0.55, color=(180,180,180), thickness=1)
        py += 70
        
        # HAND MOVEMENT
        draw_text(canvas, "HAND MOVEMENT", px, py, size=0.7, color=(100, 200, 255), thickness=2)
        cv2.line(canvas, (px, py+8), (px+330, py+8), (100,200,255), 2)
        py += 25
        
        if mm:
            nvp_so_far = int(np.sum(mm['peaks'] <= frame_idx))
            cur_speed = mm['speed'][frame_idx] if frame_idx < len(mm['speed']) else 0
            is_pause = cur_speed < mm['threshold']
            
            row_h = 48
            col_w = 160
            # Row 1: NVP, Speed
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "NVP", nvp_so_far, f"/{len(mm['peaks'])}", (100,200,255))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Speed", cur_speed, "px/s", (100,200,255))
            py += row_h + 8
            # Row 2: Straightness, Pause Time
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Straightness", mm['straightness'], "", (100,200,255))
            pause_color = (255,100,100) if is_pause else (100,200,255)
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Pause Time", mm['pause_time'], "s", pause_color)
            py += row_h + 8
            # Row 3: Move Time, Peak Speed
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Move Time", mm['move_time'], "s", (100,200,255))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Peak Speed", mm['peak_speed'], "px/s", (100,200,255))
            py += row_h + 12
            # Speed graph
            canvas = draw_mini_graph(canvas, mm['speed'], px, py, 330, 50, (100,200,255), current_idx=frame_idx, label="Speed Profile")
            py += 70
        
        # BODY COMPENSATION
        draw_text(canvas, "BODY COMPENSATION", px, py, size=0.7, color=(255, 180, 100), thickness=2)
        cv2.line(canvas, (px, py+8), (px+330, py+8), (255,180,100), 2)
        py += 25
        
        if df_pose is not None and frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            row_h = 48
            col_w = 160
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Shoulder Elev", row['shoulder_elevation_cm'], "cm", (255,180,100))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Trunk Disp", row['trunk_x_displacement_cm'], "cm", (255,180,100))
            py += row_h + 8
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Wrist Forward", row['wrist_forward_cm'], "cm", (255,180,100))
            trunk_ratio = row['trunk_x_displacement_cm'] / summary['wrist_forward_max'] * 100 if summary['wrist_forward_max'] > 0 else 0
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Trunk Ratio", trunk_ratio, "%", (255,180,100))
            py += row_h + 12
            canvas = draw_mini_graph(canvas, df_pose['trunk_x_displacement_cm'].values, px, py, 330, 45, (255,180,100), current_idx=frame_idx, label="Trunk Displacement")
            py += 65
        
        # JOINT ANGLE
        draw_text(canvas, "JOINT ANGLE", px, py, size=0.7, color=(150, 255, 150), thickness=2)
        cv2.line(canvas, (px, py+8), (px+330, py+8), (150,255,150), 2)
        py += 25
        
        if df_pose is not None and frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            elbow_angle = angle_3points(
                np.array([row['sh_x'], row['sh_y']]),
                np.array([row['el_x'], row['el_y']]),
                np.array([row['wr_x'], row['wr_y']])
            )
            row_h = 48
            col_w = 160
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Elbow Angle", elbow_angle, "deg", (150,255,150))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Elbow Range", summary['elbow_max']-summary['elbow_min'], "deg", (150,255,150))
            py += row_h + 12
            canvas = draw_mini_graph(canvas, df_pose['elbow_flexion_angle'].values, px, py, 330, 45, (150,255,150), max_val=180, current_idx=frame_idx, label="Elbow Angle")
            py += 65
        
        # Progress bar
        pb_y = out_h - 35
        progress = frame_idx / n_frames
        cv2.rectangle(canvas, (px, pb_y), (px+330, pb_y+12), (60,60,65), -1)
        cv2.rectangle(canvas, (px, pb_y), (px+int(330*progress), pb_y+12), (100,200,255), -1)
        draw_text(canvas, f"Progress: {progress*100:.1f}%", px, pb_y-8, size=0.55, color=(180,180,180), thickness=1)
        
        # Marker
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(canvas, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(canvas, (mx, my), 6, (0, 0, 255), -1)
            trajectory.append((mx, my))
        else:
            trajectory.append((np.nan, np.nan))
        
        # Trajectory
        valid_traj = [(int(x), int(y)) for x, y in trajectory if not np.isnan(x)]
        for i in range(1, len(valid_traj)):
            cv2.line(canvas, valid_traj[i-1], valid_traj[i], (255, 255, 0), 3)
        
        # Pose landmarks
        if results.pose_landmarks and df_pose is not None and frame_idx < len(df_pose):
            lm = results.pose_landmarks.landmark
            mp_drawing.draw_landmarks(canvas, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            row = df_pose.iloc[frame_idx]
            points = {
                'SH': np.array([row['sh_x'], row['sh_y']]),
                'EL': np.array([row['el_x'], row['el_y']]),
                'WR': np.array([row['wr_x'], row['wr_y']]),
                'HIP': np.array([row['hip_x'], row['hip_y']]),
                'M_SH': np.array([row['mid_shoulder_x'], (row['sh_y']+row['opp_sh_y'])/2])
            }
            colors = {'SH': (255,80,80), 'EL': (80,255,80), 'WR': (80,80,255),
                      'HIP': (255,255,80), 'M_SH': (255,120,255)}
            for name, pt in points.items():
                if not np.isnan(pt[0]):
                    cx, cy = int(pt[0]), int(pt[1])
                    cv2.circle(canvas, (cx, cy), 9, colors[name], -1)
                    cv2.circle(canvas, (cx, cy), 11, (255,255,255), 2)
                    lx, ly = cx + 25, cy - 25
                    cv2.line(canvas, (cx, cy), (lx, ly), colors[name], 2)
                    draw_text(canvas, name, lx+5, ly+8, size=0.65, color=colors[name], thickness=2)
        
        # Pause overlay
        if mm and frame_idx < len(mm['speed']) and mm['speed'][frame_idx] < mm['threshold']:
            overlay = canvas[:, :rot_w].copy()
            overlay[:] = (0, 0, 60)
            canvas[:, :rot_w] = cv2.addWeighted(canvas[:, :rot_w], 0.85, overlay, 0.15, 0)
            draw_text(canvas, "PAUSE", 20, 50, size=1.2, color=(255,100,100), thickness=3)
        
        writer.write(canvas)
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
