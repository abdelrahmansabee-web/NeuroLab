# -*- coding: utf-8 -*-
"""
High-quality validation video with glassmorphism UI panel.
Shows all kinematic variables organized by sections with mini graphs.
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


def draw_rounded_rect(img, x1, y1, x2, y2, color, radius=15, alpha=0.7):
    """Draw a rounded rectangle with alpha blending (glassmorphism effect)."""
    overlay = img.copy()
    # Draw rounded rectangle
    cv2.rectangle(overlay, (x1+radius, y1), (x2-radius, y2), color, -1)
    cv2.rectangle(overlay, (x1, y1+radius), (x2, y2-radius), color, -1)
    cv2.circle(overlay, (x1+radius, y1+radius), radius, color, -1)
    cv2.circle(overlay, (x2-radius, y1+radius), radius, color, -1)
    cv2.circle(overlay, (x1+radius, y2-radius), radius, color, -1)
    cv2.circle(overlay, (x2-radius, y2-radius), radius, color, -1)
    return cv2.addWeighted(img, 1-alpha, overlay, alpha, 0)


def draw_text(img, text, x, y, size=0.7, color=(255,255,255), thickness=2):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, thickness, cv2.LINE_AA)


def draw_mini_graph(img, values, x, y, w, h, color, max_val=None, current_idx=0):
    """Draw a small sparkline graph."""
    if len(values) < 2:
        return
    max_val = max_val or np.nanmax(values) if np.nanmax(values) > 0 else 1
    min_val = np.nanmin(values)
    rng = max_val - min_val if max_val != min_val else 1
    pts = []
    for i, v in enumerate(values):
        px = x + int(i * w / len(values))
        py = y + h - int((v - min_val) / rng * h)
        pts.append((px, py))
    for i in range(1, len(pts)):
        cv2.line(img, pts[i-1], pts[i], color, 2)
    # Current position indicator
    if 0 <= current_idx < len(pts):
        cv2.circle(img, pts[current_idx], 4, (255, 255, 255), -1)


def draw_metric_card(img, title, value, unit, max_val, x, y, w, h, accent_color):
    """Draw a single metric card."""
    img = draw_rounded_rect(img, x, y, x+w, y+h, (40, 40, 50), radius=10, alpha=0.75)
    draw_text(img, title, x+12, y+22, size=0.55, color=(180, 180, 180), thickness=1)
    draw_text(img, f"{value:.1f}", x+12, y+52, size=0.85, color=(255,255,255), thickness=2)
    draw_text(img, unit, x+12, y+72, size=0.5, color=(180,180,180), thickness=1)
    if max_val is not None:
        draw_text(img, f"max: {max_val:.1f}", x+w-80, y+52, size=0.5, color=accent_color, thickness=1)


def draw_section_header(img, title, x, y, color):
    draw_text(img, title, x, y, size=0.75, color=color, thickness=2)
    cv2.line(img, (x, y+8), (x+280, y+8), color, 2)


def process_video(label, video_path):
    print(f"\n=== Premium validation video: {label} ===")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rot_w, rot_h = orig_h, orig_w
    
    # Output: add 360px panel on the right
    panel_w = 380
    out_w = rot_w + panel_w
    out_h = rot_h
    
    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    
    out_path = str(out_dir / f"premium_validation_{label}.mp4")
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
        
        # Create canvas with panel on the right
        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[:, :rot_w] = rotated
        
        # Dark gradient panel background
        panel = np.zeros((out_h, panel_w, 3), dtype=np.uint8)
        panel[:, :] = (25, 28, 35)
        canvas[:, rot_w:] = panel
        
        # Glassmorphism main panel
        px, py = rot_w + 15, 15
        pw, ph = panel_w - 30, out_h - 110
        canvas = draw_rounded_rect(canvas, px, py, px+pw, py+ph, (60, 65, 75), radius=20, alpha=0.4)
        
        # Title
        draw_text(canvas, "Kinematic Variables", px+20, py+35, size=0.9, color=(255,255,255), thickness=2)
        draw_text(canvas, f"Video: {label}  |  Frame: {frame_idx}/{n_frames}", px+20, py+60, size=0.5, color=(180,180,180), thickness=1)
        
        y_offset = py + 95
        
        # Section: Hand Movement
        draw_section_header(canvas, "HAND MOVEMENT", px+20, y_offset, (100, 200, 255))
        y_offset += 35
        
        if mm:
            nvp_so_far = int(np.sum(mm['peaks'] <= frame_idx))
            cur_speed = mm['speed'][frame_idx] if frame_idx < len(mm['speed']) else 0
            is_pause = cur_speed < mm['threshold']
            
            draw_metric_card(canvas, "NVP", nvp_so_far, f"/ {len(mm['peaks'])}", None,
                           px+20, y_offset, 150, 60, (100,200,255))
            draw_metric_card(canvas, "Speed", cur_speed, "px/s", mm['peak_speed'],
                           px+180, y_offset, 150, 60, (100,200,255))
            y_offset += 75
            draw_metric_card(canvas, "Straightness", mm['straightness'], "", 1.0,
                           px+20, y_offset, 150, 60, (100,200,255))
            draw_metric_card(canvas, "Pause Time", mm['pause_time'], "s", None,
                           px+180, y_offset, 150, 60, (255,100,100) if is_pause else (100,200,255))
            y_offset += 75
            draw_metric_card(canvas, "Move Time", mm['move_time'], "s", None,
                           px+20, y_offset, 150, 60, (100,200,255))
            draw_metric_card(canvas, "Peak Speed", mm['peak_speed'], "px/s", None,
                           px+180, y_offset, 150, 60, (100,200,255))
            y_offset += 75
            draw_metric_card(canvas, "Time to Peak", mm['time_to_peak'], "s", None,
                           px+20, y_offset, 150, 60, (100,200,255))
            y_offset += 85
            
            # Mini speed graph
            graph_w, graph_h = 310, 50
            draw_text(canvas, "Speed Profile", px+20, y_offset, size=0.6, color=(180,180,180), thickness=1)
            y_offset += 20
            canvas = draw_rounded_rect(canvas, px+20, y_offset, px+20+graph_w, y_offset+graph_h, (30,30,35), radius=8, alpha=0.6)
            draw_mini_graph(canvas, mm['speed'], px+25, y_offset+5, graph_w-10, graph_h-10,
                          (100, 200, 255), current_idx=frame_idx)
            y_offset += 65
        
        # Section: Body Compensation
        draw_section_header(canvas, "BODY COMPENSATION", px+20, y_offset, (255, 180, 100))
        y_offset += 35
        
        if df_pose is not None and frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            draw_metric_card(canvas, "Shoulder Elev", row['shoulder_elevation_cm'], "cm",
                           summary['shoulder_elev_max'], px+20, y_offset, 150, 60, (255,180,100))
            draw_metric_card(canvas, "Trunk Disp", row['trunk_x_displacement_cm'], "cm",
                           summary['trunk_disp_max'], px+180, y_offset, 150, 60, (255,180,100))
            y_offset += 75
            draw_metric_card(canvas, "Wrist Forward", row['wrist_forward_cm'], "cm",
                           summary['wrist_forward_max'], px+20, y_offset, 150, 60, (255,180,100))
            draw_metric_card(canvas, "Trunk Ratio", row['trunk_x_displacement_cm']/summary['wrist_forward_max']*100,
                           "%", None, px+180, y_offset, 150, 60, (255,180,100))
            y_offset += 85
            
            # Mini trunk displacement graph
            graph_w, graph_h = 310, 40
            draw_text(canvas, "Trunk Displacement", px+20, y_offset, size=0.6, color=(180,180,180), thickness=1)
            y_offset += 18
            canvas = draw_rounded_rect(canvas, px+20, y_offset, px+20+graph_w, y_offset+graph_h, (30,30,35), radius=8, alpha=0.6)
            draw_mini_graph(canvas, df_pose['trunk_x_displacement_cm'].values, px+25, y_offset+5,
                          graph_w-10, graph_h-10, (255, 180, 100), current_idx=frame_idx)
            y_offset += 55
        
        # Section: Joint Angle
        draw_section_header(canvas, "JOINT ANGLE", px+20, y_offset, (150, 255, 150))
        y_offset += 35
        
        if df_pose is not None and frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            elbow_angle = angle_3points(
                np.array([row['sh_x'], row['sh_y']]),
                np.array([row['el_x'], row['el_y']]),
                np.array([row['wr_x'], row['wr_y']])
            )
            draw_metric_card(canvas, "Elbow Angle", elbow_angle, "deg",
                           summary['elbow_max'], px+20, y_offset, 150, 60, (150,255,150))
            draw_metric_card(canvas, "Elbow Range", summary['elbow_max']-summary['elbow_min'], "deg", None,
                           px+180, y_offset, 150, 60, (150,255,150))
            y_offset += 70
            
            # Mini elbow angle graph
            graph_w, graph_h = 310, 40
            draw_text(canvas, "Elbow Angle", px+20, y_offset, size=0.6, color=(180,180,180), thickness=1)
            y_offset += 18
            canvas = draw_rounded_rect(canvas, px+20, y_offset, px+20+graph_w, y_offset+graph_h, (30,30,35), radius=8, alpha=0.6)
            draw_mini_graph(canvas, df_pose['elbow_flexion_angle'].values, px+25, y_offset+5,
                          graph_w-10, graph_h-10, (150, 255, 150), max_val=180, current_idx=frame_idx)
        
        # Progress bar at bottom
        pb_y = out_h - 80
        progress = frame_idx / n_frames
        canvas = draw_rounded_rect(canvas, px, pb_y, px+pw, pb_y+12, (50,50,55), radius=6, alpha=0.7)
        filled_w = int((pw-4) * progress)
        cv2.rectangle(canvas, (px+2, pb_y+2), (px+2+filled_w, pb_y+10), (100, 200, 255), -1, cv2.LINE_AA)
        draw_text(canvas, f"Progress: {progress*100:.1f}%", px, pb_y+30, size=0.6, color=(180,180,180), thickness=1)
        
        # Draw marker and trajectory on video area
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(canvas, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(canvas, (mx, my), 5, (0, 0, 255), -1)
            trajectory.append((mx, my))
        else:
            trajectory.append((np.nan, np.nan))
        
        # Speed-colored trajectory
        valid_traj = [(int(x), int(y)) for x, y in trajectory if not np.isnan(x)]
        if mm:
            max_spd = mm['peak_speed'] if mm['peak_speed'] > 0 else 1
            for i in range(1, len(valid_traj)):
                if i < len(mm['speed']):
                    ratio = min(mm['speed'][i] / max_spd, 1.0)
                    color = (int(255*ratio), int(255*(1-ratio)), 0)
                else:
                    color = (255, 255, 0)
                cv2.line(canvas, valid_traj[i-1], valid_traj[i], color, 2)
        
        # Draw pose landmarks with labels
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
            colors = {'SH': (255,100,100), 'EL': (100,255,100), 'WR': (100,100,255),
                      'HIP': (255,255,100), 'M_SH': (255,150,255)}
            for name, pt in points.items():
                if not np.isnan(pt[0]):
                    cx, cy = int(pt[0]), int(pt[1])
                    cv2.circle(canvas, (cx, cy), 8, colors[name], -1)
                    cv2.circle(canvas, (cx, cy), 10, (255,255,255), 2)
                    # Label with line
                    lx, ly = cx + 25, cy - 25
                    cv2.line(canvas, (cx, cy), (lx, ly), colors[name], 1)
                    draw_text(canvas, name, lx+5, ly+5, size=0.55, color=colors[name], thickness=2)
        
        # Pause overlay
        if mm and frame_idx < len(mm['speed']) and mm['speed'][frame_idx] < mm['threshold']:
            overlay = canvas.copy()
            overlay[:, :rot_w] = (0, 0, 80)
            canvas = cv2.addWeighted(canvas, 0.85, overlay, 0.15, 0)
        
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
