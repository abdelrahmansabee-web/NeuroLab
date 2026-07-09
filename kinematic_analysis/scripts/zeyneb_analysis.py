# -*- coding: utf-8 -*-
"""
Zeyneb unified analysis: Pose + Hands wrist fusion.
Computes hand movement metrics (NVP, straightness, pause, peak speed, etc.)
and body compensation metrics (shoulder elevation, trunk displacement, elbow angle).
Videos are rotated 90 degrees clockwise before processing.
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks

# ------------------------------------------------------------------
# Paths and metadata
# ------------------------------------------------------------------
input_dir = Path(r"D:\Thesis app\participants\3 مرضى\33\زينب")
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
out_dir.mkdir(parents=True, exist_ok=True)
project_dir = Path(r"D:\Thesis app\kinematic_analysis")

with open(project_dir / "data" / "zeyneb" / "zeyneb_metadata.json", 'r', encoding='utf-8') as f:
    metadata = json.load(f)

affected_side = metadata.get("affected_side", "LEFT")
shoulder_width_cm = metadata.get("shoulder_width_cm", 36.0)
rotation_deg = metadata.get("video_rotation_degrees", -90)
VISIBILITY_THRESHOLD = 0.5

videos = {
    'pre': (str(input_dir / 'Pre.mov'), 'LEFT'),
    'post': (str(input_dir / 'Post.mov'), 'LEFT'),
    'healthyside': (str(input_dir / 'Healthy side.mov'), 'RIGHT'),
}

mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands

# Movement metric parameters
NVP_PROMINENCE_STD = 0.5
NVP_MIN_DISTANCE_S = 0.15


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


def lowpass_filter(x, fs, cutoff=10.0, order=4):
    if np.all(np.isnan(x)) or len(x) < 10:
        return x
    nyq = 0.5 * fs
    if cutoff / nyq >= 1:
        return x
    b, a = butter(order, cutoff / nyq, btype='low')
    mask = ~np.isnan(x)
    if mask.sum() < 10:
        return x
    xi = np.arange(len(x))
    x_filled = np.interp(xi, xi[mask], x[mask])
    return filtfilt(b, a, x_filled)


def angle_3points(a, b, c):
    ba = a - b
    bc = c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def compute_hand_metrics(t, x, y, fps):
    dt = 1.0 / fps
    t = np.asarray(t)
    x = lowpass_filter(np.asarray(x), fps, cutoff=10.0)
    y = lowpass_filter(np.asarray(y), fps, cutoff=10.0)
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed = np.sqrt(vx**2 + vy**2)
    speed = lowpass_filter(speed, fps, cutoff=10.0)
    speed = np.clip(speed, 0, None)

    peaks, _ = find_peaks(speed, prominence=np.nanstd(speed)*NVP_PROMINENCE_STD,
                          distance=int(fps*NVP_MIN_DISTANCE_S))
    nvp = len(peaks)

    threshold = 0.05 * np.max(speed)
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

    peak_v = speed.max()
    peak_idx = speed.argmax()
    time_to_peak = t[peak_idx] - t[0]
    disp = np.hypot(x[-1]-x[0], y[-1]-y[0])
    path = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    straightness = disp / path if path > 0 else np.nan

    return {
        't': t, 'x': x, 'y': y, 'speed': speed, 'nvp': nvp,
        'pause_time': pause_time, 'peak_speed': peak_v,
        'time_to_peak': time_to_peak, 'straightness': straightness,
        'total_displacement': disp, 'path_length': path,
    }


def analyze_video(label, video_path, side_for_video):
    print(f"\n=== Zeyneb analysis: {label} (side: {side_for_video}) ===")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open {video_path}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w, h = orig_h, orig_w
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                           min_detection_confidence=0.3, min_tracking_confidence=0.3)

    opp = 'RIGHT' if side_for_video == 'LEFT' else 'LEFT'
    sh_idx = getattr(mp_pose.PoseLandmark, f'{side_for_video}_SHOULDER')
    el_idx = getattr(mp_pose.PoseLandmark, f'{side_for_video}_ELBOW')
    wr_idx = getattr(mp_pose.PoseLandmark, f'{side_for_video}_WRIST')
    hip_idx = getattr(mp_pose.PoseLandmark, f'{side_for_video}_HIP')
    opp_sh_idx = getattr(mp_pose.PoseLandmark, f'{opp}_SHOULDER')

    rows = []
    frame_idx = 0
    hands_detected = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rotated = rotate_frame_90_clockwise(frame)
        rgb = cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB)

        results_pose = pose.process(rgb)
        results_hands = hands.process(rgb)

        if results_pose.pose_landmarks:
            lm = results_pose.pose_landmarks.landmark
            sh = get_pose_landmark_xy(lm, sh_idx, w, h)
            el = get_pose_landmark_xy(lm, el_idx, w, h)
            pose_wr = get_pose_landmark_xy(lm, wr_idx, w, h)
            hip = get_pose_landmark_xy(lm, hip_idx, w, h)
            opp_sh = get_pose_landmark_xy(lm, opp_sh_idx, w, h)

            hands_wr = get_hands_wrist(results_hands, pose_wr, w, h)
            wr = hands_wr if hands_wr is not None else pose_wr
            if hands_wr is not None:
                hands_detected += 1

            rows.append({
                'frame': frame_idx,
                'time': frame_idx / fps,
                'sh_x': sh[0], 'sh_y': sh[1],
                'el_x': el[0], 'el_y': el[1],
                'wr_x': wr[0], 'wr_y': wr[1],
                'hip_x': hip[0], 'hip_y': hip[1],
                'opp_sh_x': opp_sh[0], 'opp_sh_y': opp_sh[1],
                'hands_used': 1.0 if hands_wr is not None else 0.0,
            })
        else:
            rows.append({
                'frame': frame_idx,
                'time': frame_idx / fps,
                'sh_x': np.nan, 'sh_y': np.nan,
                'el_x': np.nan, 'el_y': np.nan,
                'wr_x': np.nan, 'wr_y': np.nan,
                'hip_x': np.nan, 'hip_y': np.nan,
                'opp_sh_x': np.nan, 'opp_sh_y': np.nan,
                'hands_used': 0.0,
            })

        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  processed {frame_idx}/{n_frames}")

    cap.release()
    pose.close()
    hands.close()

    print(f"  Hands detected in {hands_detected}/{n_frames} frames ({100*hands_detected/n_frames:.1f}%)")

    df = pd.DataFrame(rows)
    df = df.interpolate(method='linear', limit_direction='both')

    for col in ['sh_x', 'sh_y', 'el_x', 'el_y', 'wr_x', 'wr_y', 'hip_x', 'hip_y', 'opp_sh_x', 'opp_sh_y']:
        df[col] = lowpass_filter(df[col].values, fps, cutoff=10.0)

    # Scale
    shoulder_width_px = abs(df['sh_x'].iloc[:10].mean() - df['opp_sh_x'].iloc[:10].mean())
    if np.isnan(shoulder_width_px) or shoulder_width_px < 1:
        shoulder_width_px = abs(df['hip_x'].iloc[:10].mean() - df['opp_hip_x'].iloc[:10].mean()) * 0.7 if 'opp_hip_x' in df.columns else np.nan
    cm_per_px = shoulder_width_cm / shoulder_width_px if shoulder_width_px and shoulder_width_px > 0 else np.nan

    # Compensation metrics
    baseline_x_wr = df['wr_x'].iloc[:10].mean()
    df['wrist_forward_px'] = df['wr_x'] - baseline_x_wr
    df['wrist_forward_cm'] = df['wrist_forward_px'] * cm_per_px

    baseline_y_sh = df['sh_y'].iloc[:10].mean()
    df['shoulder_elevation_px'] = baseline_y_sh - df['sh_y']
    df['shoulder_elevation_cm'] = df['shoulder_elevation_px'] * cm_per_px

    df['mid_shoulder_x'] = (df['sh_x'] + df['opp_sh_x']) / 2
    baseline_x_mid_sh = df['mid_shoulder_x'].iloc[:10].mean()
    df['trunk_x_displacement_px'] = df['mid_shoulder_x'] - baseline_x_mid_sh
    df['trunk_x_displacement_cm'] = df['trunk_x_displacement_px'] * cm_per_px

    elbow_angles = []
    for i in range(len(df)):
        a = np.array([df['sh_x'].iloc[i], df['sh_y'].iloc[i]])
        b = np.array([df['el_x'].iloc[i], df['el_y'].iloc[i]])
        c = np.array([df['wr_x'].iloc[i], df['wr_y'].iloc[i]])
        elbow_angles.append(angle_3points(a, b, c))
    df['elbow_flexion_angle'] = elbow_angles

    # Hand metrics
    hand = compute_hand_metrics(df['time'].values, df['wr_x'].values, df['wr_y'].values, fps)
    df['speed_px_s'] = hand['speed']

    summary = {
        'label': label,
        'affected_side': affected_side,
        'fps': fps,
        'n_frames': n_frames,
        'hands_frames': hands_detected,
        'hands_percent': 100*hands_detected/n_frames,
        'shoulder_width_px': shoulder_width_px,
        'cm_per_px': cm_per_px,
        'max_shoulder_elevation_cm': df['shoulder_elevation_cm'].max(),
        'max_trunk_displacement_cm': df['trunk_x_displacement_cm'].max(),
        'max_wrist_forward_cm': df['wrist_forward_cm'].max(),
        'trunk_ratio': abs(df['trunk_x_displacement_cm'].max()) / abs(df['wrist_forward_cm'].max()) if abs(df['wrist_forward_cm'].max()) > 1 else np.nan,
        'elbow_flexion_min': df['elbow_flexion_angle'].min(),
        'elbow_flexion_max': df['elbow_flexion_angle'].max(),
        'elbow_flexion_range': df['elbow_flexion_angle'].max() - df['elbow_flexion_angle'].min(),
        'total_time_s': hand['t'][-1] - hand['t'][0],
        'total_displacement_px': hand['total_displacement'],
        'path_length_px': hand['path_length'],
        'overall_straightness': hand['straightness'],
        'nvp': hand['nvp'],
        'total_pause_time_s': hand['pause_time'],
        'peak_speed_px_s': hand['peak_speed'],
        'time_to_peak_speed_s': hand['time_to_peak'],
    }

    print(f"  Shoulder width px: {shoulder_width_px:.1f} -> cm/px: {cm_per_px:.4f}")
    print(f"  Max shoulder elevation: {summary['max_shoulder_elevation_cm']:.2f} cm")
    print(f"  Max trunk displacement: {summary['max_trunk_displacement_cm']:.2f} cm")
    print(f"  Max wrist forward: {summary['max_wrist_forward_cm']:.2f} cm")
    print(f"  Trunk ratio: {summary['trunk_ratio']:.3f}")
    print(f"  Elbow range: {summary['elbow_flexion_range']:.1f} deg")
    print(f"  NVP: {summary['nvp']}, Pause: {summary['total_pause_time_s']:.2f}s, Peak speed: {summary['peak_speed_px_s']:.1f} px/s")
    print(f"  Straightness: {summary['overall_straightness']:.3f}")

    # Plots
    fig, axs = plt.subplots(4, 1, figsize=(12, 14))
    axs[0].plot(df['time'], df['shoulder_elevation_cm'], label='shoulder elevation')
    axs[0].axhline(0, color='gray', linestyle='--')
    axs[0].set_ylabel('cm')
    axs[0].set_title(f'{label}: shoulder elevation')
    axs[0].legend()

    axs[1].plot(df['time'], df['trunk_x_displacement_cm'], label='trunk displacement', color='orange')
    axs[1].axhline(0, color='gray', linestyle='--')
    axs[1].set_ylabel('cm')
    axs[1].set_title(f'{label}: trunk compensation')
    axs[1].legend()

    axs[2].plot(df['time'], df['wrist_forward_cm'], label='wrist forward', color='green')
    axs[2].axhline(0, color='gray', linestyle='--')
    axs[2].set_ylabel('cm')
    axs[2].set_title(f'{label}: wrist forward reach')
    axs[2].legend()

    axs[3].plot(df['time'], df['elbow_flexion_angle'], label='elbow flexion', color='red')
    axs[3].set_ylabel('deg')
    axs[3].set_xlabel('Time (s)')
    axs[3].set_title(f'{label}: elbow flexion angle')
    axs[3].set_ylim(0, 180)
    axs[3].legend()

    plt.tight_layout()
    plt.savefig(out_dir / f"zeyneb_pose_{label}.png", dpi=150)
    plt.close()

    # Hand plots
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    axs[0,0].plot(hand['t'], hand['x'], label='x')
    axs[0,0].plot(hand['t'], hand['y'], label='y')
    axs[0,0].set_ylabel('px')
    axs[0,0].set_title(f'{label}: wrist position')
    axs[0,0].legend()

    axs[0,1].plot(hand['t'], hand['speed'], 'b-', lw=1)
    peaks, _ = find_peaks(hand['speed'], prominence=np.nanstd(hand['speed'])*0.5, distance=int(fps*0.15))
    axs[0,1].plot(hand['t'][peaks], hand['speed'][peaks], 'ro', label=f'NVP={hand["nvp"]}')
    axs[0,1].set_ylabel('px/s')
    axs[0,1].set_title(f'{label}: speed')
    axs[0,1].legend()

    axs[1,0].plot(hand['x'], hand['y'], 'b-', alpha=0.4)
    axs[1,0].scatter(hand['x'][0], hand['y'][0], c='green', s=50, label='start')
    axs[1,0].scatter(hand['x'][-1], hand['y'][-1], c='red', s=50, label='end')
    axs[1,0].set_xlabel('x (px)')
    axs[1,0].set_ylabel('y (px)')
    axs[1,0].set_title(f'{label}: trajectory | straightness={hand["straightness"]:.3f}')
    axs[1,0].invert_yaxis()
    axs[1,0].legend()

    axs[1,1].axis('off')
    text = (
        f"NVP: {hand['nvp']}\n"
        f"Pause time: {hand['pause_time']:.2f}s\n"
        f"Peak speed: {hand['peak_speed']:.1f} px/s\n"
        f"Time to peak: {hand['time_to_peak']:.2f}s\n"
        f"Straightness: {hand['straightness']:.3f}\n"
        f"Displacement: {hand['total_displacement']:.1f} px\n"
        f"Path length: {hand['path_length']:.1f} px"
    )
    axs[1,1].text(0.1, 0.5, text, fontsize=12, verticalalignment='center',
                  fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(out_dir / f"zeyneb_hand_{label}.png", dpi=150)
    plt.close()

    df.to_csv(out_dir / f"zeyneb_fusion_{label}.csv", index=False)
    return summary, df


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
all_summaries = []
for label, (path, side) in videos.items():
    res = analyze_video(label, path, side)
    if res is not None:
        all_summaries.append(res[0])

if all_summaries:
    df_summary = pd.DataFrame(all_summaries)
    df_summary.to_csv(out_dir / 'zeyneb_summary.csv', index=False)
    print(f"\nSaved: {out_dir / 'zeyneb_summary.csv'}")
    print(df_summary.to_string(index=False))
