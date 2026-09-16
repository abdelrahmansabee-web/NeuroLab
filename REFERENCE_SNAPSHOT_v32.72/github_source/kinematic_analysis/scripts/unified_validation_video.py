# -*- coding: utf-8 -*-
"""
Unified validation video for all kinematic variables.
Uses:
- MediaPipe Hands wrist as primary wrist source (fallback to Pose wrist)
- MediaPipe Pose for shoulder, elbow, hip, mid-shoulder
- Pre-computed CSVs for smoothness metrics (NVP, straightness, pause, peak speed, etc.)
- Pre-computed pose compensation CSVs for body compensation metrics
Layout: video on left, metrics panel on right.
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import json
from pathlib import Path
from scipy.signal import find_peaks

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
input_dir = Path(r"D:\Thesis app\participants\3 مرضى\33\انا ٢")
project_dir = Path(r"D:\Thesis app\kinematic_analysis")
data_dir = project_dir / "data"
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
out_dir.mkdir(parents=True, exist_ok=True)

videos = {
    'H': str(input_dir / 'H.MOV'),
    'S': str(input_dir / 'S.MOV'),
}

# Load metadata
with open(data_dir / "patient_33_metadata.json", 'r', encoding='utf-8') as f:
    metadata = json.load(f)
affected_side = metadata.get("affected_side", "RIGHT")
VISIBILITY_THRESHOLD = 0.5

mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def rotate_frame_90_clockwise(frame):
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)


def get_pose_landmark_xy(lm, idx, w, h):
    p = lm[idx]
    if p.visibility < VISIBILITY_THRESHOLD:
        return np.array([np.nan, np.nan])
    return np.array([p.x * w, p.y * h])


def get_hands_wrist(results_hands, pose_wrist, w, h):
    if not results_hands or not results_hands.multi_hand_landmarks:
        return None
    best = None
    best_dist = float('inf')
    for hand in results_hands.multi_hand_landmarks:
        wr = hand.landmark[mp_hands.HandLandmark.WRIST]
        wrist_xy = np.array([wr.x * w, wr.y * h])
        if pose_wrist is None or np.isnan(pose_wrist[0]):
            return wrist_xy
        d = np.linalg.norm(wrist_xy - pose_wrist)
        if d < best_dist:
            best_dist = d
            best = wrist_xy
    return best


def angle_3points(a, b, c):
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def draw_text(img, text, x, y, size=0.7, color=(255,255,255), thickness=2):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, thickness, cv2.LINE_AA)


def draw_value_box(img, x, y, w, h, label, value, unit, color, font_scale=0.75):
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (45, 48, 55), -1)
    cv2.rectangle(overlay, (x, y), (x+w, y+h), color, 2)
    img = cv2.addWeighted(img, 0.3, overlay, 0.7, 0)
    draw_text(img, label, x+8, y+18, size=0.5, color=(180,180,180), thickness=1)
    if isinstance(value, float):
        value_text = f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"
    else:
        value_text = str(value)
    draw_text(img, value_text, x+8, y+44, size=font_scale, color=(255,255,255), thickness=2)
    draw_text(img, unit, x+w-50, y+44, size=0.5, color=color, thickness=1)
    return img


def draw_mini_graph(img, values, x, y, w, h, color, max_val=None, current_idx=0, label=""):
    if len(values) < 2:
        return img
    valid = np.array(values, dtype=float)
    max_val = max_val if max_val is not None else (np.nanmax(valid) if np.nanmax(valid) > 0 else 1)
    min_val = np.nanmin(valid)
    rng = max_val - min_val if max_val != min_val else 1
    pts = []
    for i, v in enumerate(valid):
        px = x + int(i * w / len(valid))
        py = y + h - int((v - min_val) / rng * h)
        pts.append((px, py))
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (30, 32, 38), -1)
    img = cv2.addWeighted(img, 0.5, overlay, 0.5, 0)
    for gy in [y+h//4, y+h//2, y+3*h//4]:
        cv2.line(img, (x, gy), (x+w, gy), (60, 60, 65), 1)
    for i in range(1, len(pts)):
        cv2.line(img, pts[i-1], pts[i], color, 2)
    if 0 <= current_idx < len(pts):
        cv2.circle(img, pts[current_idx], 5, (255,255,255), -1)
        cv2.circle(img, pts[current_idx], 3, color, -1)
    if label:
        draw_text(img, label, x, y-8, size=0.55, color=(200,200,200), thickness=1)
    return img


def process_video(label, video_path):
    print(f"\n=== Unified validation video: {label} ===")

    # Load data
    df_hands = pd.read_csv(data_dir / f"hands_wrist_fusion_{label}.csv")
    df_pose = pd.read_csv(data_dir / f"pose_compensation_{label}.csv")
    summ_hands = pd.read_csv(data_dir / "hands_wrist_kinematics_summary.csv")
    summ_hands = summ_hands.set_index('label').loc[label]
    summ_pose = pd.read_csv(data_dir / "pose_compensation_summary.csv")
    summ_pose = summ_pose[summ_pose['label'] == label].iloc[0]

    # Precompute peaks/stops for hands speed
    fps = df_hands['fps'].iloc[0] if 'fps' in df_hands.columns else (df_pose['fps'].iloc[0] if 'fps' in df_pose.columns else 60.0)
    speed = df_hands['speed_px_s'].values
    peaks, _ = find_peaks(speed, prominence=np.nanstd(speed)*0.5, distance=int(fps*0.15))
    threshold = 0.05 * np.max(speed)
    paused = speed < threshold
    pause_time = 0.0
    i = 0
    while i < len(paused):
        if paused[i]:
            j = i
            while j < len(paused) and paused[j]:
                j += 1
            dur = df_hands['time'].iloc[j-1] - df_hands['time'].iloc[i]
            if dur >= 0.1:
                pause_time += dur
            i = j
        else:
            i += 1

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    rot_w, rot_h = orig_h, orig_w
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    panel_w = 400
    out_w = rot_w + panel_w
    out_h = rot_h

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                           min_detection_confidence=0.3, min_tracking_confidence=0.3)

    out_path = str(out_dir / f"unified_validation_{label}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (out_w, out_h))

    opp = 'RIGHT' if affected_side == 'LEFT' else 'LEFT'
    sh_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_SHOULDER')
    el_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_ELBOW')
    wr_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_WRIST')
    hip_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_HIP')

    trajectory = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rotated = rotate_frame_90_clockwise(frame)
        rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)
        results_pose = pose.process(rgb)
        results_hands = hands.process(rgb)

        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[:, :rot_w] = rotated

        # Panel background
        overlay = canvas.copy()
        cv2.rectangle(overlay, (rot_w, 0), (out_w, out_h), (35, 38, 45), -1)
        canvas = cv2.addWeighted(canvas, 1.0, overlay, 0.95, 0)

        px, py = rot_w + 15, 15

        # Title
        draw_text(canvas, "All Kinematic Variables", px, py+25, size=0.85, color=(255,255,255), thickness=2)
        draw_text(canvas, f"{label}  |  Frame {frame_idx+1}/{n_frames}  |  Hands Wrist", px, py+48, size=0.55, color=(180,180,180), thickness=1)
        py += 70

        # HAND MOVEMENT
        draw_text(canvas, "HAND MOVEMENT", px, py, size=0.7, color=(100, 200, 255), thickness=2)
        cv2.line(canvas, (px, py+8), (px+370, py+8), (100,200,255), 2)
        py += 25

        if frame_idx < len(df_hands):
            row_h = 48
            col_w = 180
            cur_speed = df_hands['speed_px_s'].iloc[frame_idx]
            nvp_so_far = int(np.sum(peaks <= frame_idx))
            is_pause = cur_speed < threshold

            canvas = draw_value_box(canvas, px, py, col_w, row_h, "NVP", nvp_so_far, f"/{len(peaks)}", (100,200,255))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Speed", cur_speed, "px/s", (100,200,255))
            py += row_h + 8
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Straightness", summ_hands['overall_straightness'], "", (100,200,255))
            pause_color = (255,100,100) if is_pause else (100,200,255)
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Pause Time", pause_time, "s", pause_color)
            py += row_h + 8
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Peak Speed", summ_hands['peak_speed_px_s'], "px/s", (100,200,255))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Time to Peak", summ_hands['time_to_peak_speed_s'], "s", (100,200,255))
            py += row_h + 12
            canvas = draw_mini_graph(canvas, df_hands['speed_px_s'].values, px, py, 370, 55, (100,200,255), current_idx=frame_idx, label="Speed Profile")
            py += 75

        # BODY COMPENSATION
        draw_text(canvas, "BODY COMPENSATION", px, py, size=0.7, color=(255, 180, 100), thickness=2)
        cv2.line(canvas, (px, py+8), (px+370, py+8), (255,180,100), 2)
        py += 25

        if frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            row_h = 48
            col_w = 180
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Shoulder Elev", row['shoulder_elevation_cm'], "cm", (255,180,100))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Trunk Disp", row['trunk_x_displacement_cm'], "cm", (255,180,100))
            py += row_h + 8
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Wrist Forward", row['wrist_forward_cm'], "cm", (255,180,100))
            wf_max = summ_pose['max_wrist_forward_cm']
            trunk_ratio = row['trunk_x_displacement_cm'] / wf_max * 100 if wf_max > 0 else 0
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Trunk Ratio", trunk_ratio, "%", (255,180,100))
            py += row_h + 12
            canvas = draw_mini_graph(canvas, df_pose['trunk_x_displacement_cm'].values, px, py, 370, 50, (255,180,100), current_idx=frame_idx, label="Trunk Displacement")
            py += 70

        # JOINT ANGLE
        draw_text(canvas, "JOINT ANGLE", px, py, size=0.7, color=(150, 255, 150), thickness=2)
        cv2.line(canvas, (px, py+8), (px+370, py+8), (150,255,150), 2)
        py += 25

        if frame_idx < len(df_pose):
            row = df_pose.iloc[frame_idx]
            row_h = 48
            col_w = 180
            canvas = draw_value_box(canvas, px, py, col_w, row_h, "Elbow Angle", row['elbow_flexion_angle'], "deg", (150,255,150))
            canvas = draw_value_box(canvas, px+col_w+8, py, col_w, row_h, "Elbow Range", summ_pose['elbow_flexion_range'], "deg", (150,255,150))
            py += row_h + 12
            canvas = draw_mini_graph(canvas, df_pose['elbow_flexion_angle'].values, px, py, 370, 50, (150,255,150), max_val=180, current_idx=frame_idx, label="Elbow Angle")
            py += 70

        # Progress bar
        pb_y = out_h - 35
        progress = (frame_idx + 1) / n_frames
        cv2.rectangle(canvas, (px, pb_y), (px+370, pb_y+12), (60,60,65), -1)
        cv2.rectangle(canvas, (px, pb_y), (px+int(370*progress), pb_y+12), (100,200,255), -1)
        draw_text(canvas, f"Progress: {progress*100:.1f}%", px, pb_y-8, size=0.55, color=(180,180,180), thickness=1)

        # Draw fused wrist trajectory and current point
        if frame_idx < len(df_hands):
            row = df_hands.iloc[frame_idx]
            wr_x, wr_y = int(row['wr_x']), int(row['wr_y'])
            trajectory.append((wr_x, wr_y))
            for j in range(1, len(trajectory)):
                x0, y0 = trajectory[j-1]
                x1, y1 = trajectory[j]
                if not (np.isnan(x0) or np.isnan(x1)):
                    cv2.line(canvas, (int(x0), int(y0)), (int(x1), int(y1)), (255, 255, 0), 3)
            cv2.circle(canvas, (wr_x, wr_y), 7, (0, 0, 255), -1)
            cv2.circle(canvas, (wr_x, wr_y), 9, (255, 255, 255), 2)

        # Pose skeleton: draw only selected landmarks and connections
        if results_pose.pose_landmarks and frame_idx < len(df_pose):
            lm = results_pose.pose_landmarks.landmark
            row = df_pose.iloc[frame_idx]
            sh = np.array([row['sh_x'], row['sh_y']])
            el = np.array([row['el_x'], row['el_y']])
            wr = np.array([row['wr_x'], row['wr_y']])
            hip = np.array([row['hip_x'], row['hip_y']])
            opp_sh = np.array([row['opp_sh_x'], row['opp_sh_y']])
            m_sh = np.array([row['mid_shoulder_x'], (row['sh_y'] + row['opp_sh_y']) / 2])
            pts = {'SH': sh, 'EL': el, 'WR': wr, 'HIP': hip, 'M_SH': m_sh}
            colors = {'SH': (255,80,80), 'EL': (80,255,80), 'WR': (80,80,255), 'HIP': (255,255,80), 'M_SH': (255,120,255)}

            # Draw selected connections
            connections = [
                (sh, el, (80,255,80)),
                (el, wr, (80,80,255)),
                (sh, hip, (255,255,80)),
                (opp_sh, sh, (200,120,200)),
                (m_sh, hip, (255,120,255)),
            ]
            for a, b, c in connections:
                if not (np.isnan(a[0]) or np.isnan(b[0])):
                    cv2.line(canvas, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), c, 2)

            # Draw selected points and labels
            for name, pt in pts.items():
                if not np.isnan(pt[0]):
                    cx, cy = int(pt[0]), int(pt[1])
                    cv2.circle(canvas, (cx, cy), 9, colors[name], -1)
                    cv2.circle(canvas, (cx, cy), 11, (255,255,255), 2)
                    lx, ly = cx + 30, cy - 30
                    cv2.line(canvas, (cx, cy), (lx, ly), colors[name], 2)
                    draw_text(canvas, name, lx+5, ly+8, size=0.65, color=colors[name], thickness=2)

        # Pause overlay
        if frame_idx < len(df_hands) and df_hands['speed_px_s'].iloc[frame_idx] < threshold:
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
    hands.close()
    print(f"Saved: {out_path}")
    return out_path


for label, path in videos.items():
    process_video(label, path)

print("\nDone.")
