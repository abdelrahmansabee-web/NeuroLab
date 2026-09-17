# -*- coding: utf-8 -*-
"""
Compute shoulder elevation and trunk compensation from MediaPipe Pose.
Rotates video 90 degrees clockwise to correct orientation metadata.
Affected side read from manual metadata JSON.
"""
import cv2
import json
import numpy as np
import pandas as pd
import mediapipe as mp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
input_dir = Path(r"D:\Thesis app\participants\3 مرضى\33\انا ٢")
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
out_dir.mkdir(parents=True, exist_ok=True)

videos = {
    'H': str(input_dir / 'H.MOV'),
    'S': str(input_dir / 'S.MOV'),
}

metadata_path = out_dir / "patient_33_metadata.json"
metadata = {
    "patient_id": "33",
    "affected_side": "RIGHT",
    "shoulder_width_cm": 40.0,
    "camera_side": "RIGHT",
    "video_rotation_degrees": -90,
    "notes": "Video recorded with -90 degree rotation; corrected by rotating 90 degrees clockwise."
}
with open(metadata_path, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

affected_side = metadata['affected_side']
shoulder_width_cm = metadata['shoulder_width_cm']
VISIBILITY_THRESHOLD = 0.5

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils


def rotate_frame_90_clockwise(frame):
    """Rotate frame 90 degrees clockwise to correct orientation metadata."""
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)


def get_landmark_xy(lm, idx, w, h):
    p = lm[idx]
    if p.visibility < VISIBILITY_THRESHOLD:
        return np.array([np.nan, np.nan]), p.visibility
    return np.array([p.x * w, p.y * h]), p.visibility


def lowpass_filter(x, fs, cutoff=6.0, order=4):
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


def compute_metrics_for_video(label, video_path):
    print(f"\n=== Pose analysis: {label} ===")
    print(f"  Affected side: {affected_side}")
    print(f"  Video rotation: 90 deg clockwise")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open video for {label}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # After rotation, width and height swap
    w, h = orig_h, orig_w
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    pose = mp_pose.Pose(static_image_mode=False, model_complexity=2,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = str(out_dir / f"pose_compensation_{label}.mp4")
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    opp = 'RIGHT' if affected_side == 'LEFT' else 'LEFT'
    sh_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_SHOULDER')
    el_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_ELBOW')
    wr_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_WRIST')
    hip_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_HIP')
    opp_sh_idx = getattr(mp_pose.PoseLandmark, f'{opp}_SHOULDER')

    rows = []
    frame_idx = 0
    rejected_frames = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = rotate_frame_90_clockwise(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if results.pose_landmarks:
            lm = results.pose_landmarks.landmark
            sh, vis_sh = get_landmark_xy(lm, sh_idx, w, h)
            el, vis_el = get_landmark_xy(lm, el_idx, w, h)
            wr, vis_wr = get_landmark_xy(lm, wr_idx, w, h)
            hip, vis_hip = get_landmark_xy(lm, hip_idx, w, h)
            opp_sh, _ = get_landmark_xy(lm, opp_sh_idx, w, h)

            if np.isnan(sh[0]) or np.isnan(el[0]) or np.isnan(wr[0]) or np.isnan(hip[0]):
                rejected_frames += 1
                sh = el = wr = hip = opp_sh = np.array([np.nan, np.nan])

            rows.append({
                'frame': frame_idx,
                'time': frame_idx / fps,
                'sh_x': sh[0], 'sh_y': sh[1],
                'el_x': el[0], 'el_y': el[1],
                'wr_x': wr[0], 'wr_y': wr[1],
                'hip_x': hip[0], 'hip_y': hip[1],
                'opp_sh_x': opp_sh[0], 'opp_sh_y': opp_sh[1],
                'vis_sh': vis_sh, 'vis_el': vis_el, 'vis_wr': vis_wr, 'vis_hip': vis_hip,
            })
            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        else:
            rejected_frames += 1
            rows.append({
                'frame': frame_idx,
                'time': frame_idx / fps,
                'sh_x': np.nan, 'sh_y': np.nan,
                'el_x': np.nan, 'el_y': np.nan,
                'wr_x': np.nan, 'wr_y': np.nan,
                'hip_x': np.nan, 'hip_y': np.nan,
                'opp_sh_x': np.nan, 'opp_sh_y': np.nan,
                'vis_sh': np.nan, 'vis_el': np.nan, 'vis_wr': np.nan, 'vis_hip': np.nan,
            })

        writer.write(frame)
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  processed {frame_idx}/{n_frames}")

    cap.release()
    writer.release()
    pose.close()

    df = pd.DataFrame(rows)
    valid_frames = df['sh_x'].notna().sum()
    print(f"  Valid frames: {valid_frames}/{n_frames} ({rejected_frames} rejected)")

    if valid_frames < 10:
        print("  Too few valid frames for analysis.")
        return None

    df = df.interpolate(method='linear', limit_direction='both')

    for col in ['sh_x', 'sh_y', 'hip_x', 'hip_y', 'wr_x', 'wr_y', 'el_x', 'el_y']:
        df[col] = lowpass_filter(df[col].values, fps, cutoff=6.0)

    # Forward direction: in clockwise-rotated video, reach goes rightward (positive x)
    baseline_x_wr = df['wr_x'].iloc[:10].mean()
    df['wrist_forward_px'] = df['wr_x'] - baseline_x_wr

    # Shoulder elevation: upward is negative y movement
    baseline_y_sh = df['sh_y'].iloc[:10].mean()
    df['shoulder_elevation_px'] = baseline_y_sh - df['sh_y']

    # Trunk compensation: horizontal displacement of mid-shoulder (sternum proxy)
    df['mid_shoulder_x'] = (df['sh_x'] + df['opp_sh_x']) / 2
    baseline_x_mid_sh = df['mid_shoulder_x'].iloc[:10].mean()
    df['trunk_x_displacement_px'] = df['mid_shoulder_x'] - baseline_x_mid_sh

    # Shoulder width in rotated video
    shoulder_width_px = abs(df['sh_x'].iloc[:10].mean() - df['opp_sh_x'].iloc[:10].mean())
    if np.isnan(shoulder_width_px) or shoulder_width_px < 1:
        shoulder_width_px = abs(df['sh_x'].iloc[:10].mean() - df['hip_x'].iloc[:10].mean()) * 0.7

    cm_per_px = shoulder_width_cm / shoulder_width_px if shoulder_width_px > 0 else np.nan

    df['shoulder_elevation_cm'] = df['shoulder_elevation_px'] * cm_per_px
    df['trunk_x_displacement_cm'] = df['trunk_x_displacement_px'] * cm_per_px
    df['wrist_forward_cm'] = df['wrist_forward_px'] * cm_per_px

    def angle_3points(a, b, c):
        ba = a - b
        bc = c - b
        cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
        return np.degrees(np.arccos(np.clip(cos, -1, 1)))

    elbow_angles = []
    for i in range(len(df)):
        a = np.array([df['sh_x'].iloc[i], df['sh_y'].iloc[i]])
        b = np.array([df['el_x'].iloc[i], df['el_y'].iloc[i]])
        c = np.array([df['wr_x'].iloc[i], df['wr_y'].iloc[i]])
        elbow_angles.append(angle_3points(a, b, c))
    df['elbow_flexion_angle'] = elbow_angles

    max_shoulder_elev_cm = df['shoulder_elevation_cm'].max()
    max_trunk_disp_cm = df['trunk_x_displacement_cm'].max()
    max_wrist_forward_cm = df['wrist_forward_cm'].max()
    trunk_ratio = abs(max_trunk_disp_cm) / abs(max_wrist_forward_cm) if abs(max_wrist_forward_cm) > 1 else np.nan

    summary = {
        'label': label,
        'affected_side': affected_side,
        'fps': fps,
        'n_frames': n_frames,
        'valid_frames': int(valid_frames),
        'rejected_frames': rejected_frames,
        'shoulder_width_px': shoulder_width_px,
        'cm_per_px': cm_per_px,
        'max_shoulder_elevation_cm': max_shoulder_elev_cm,
        'max_trunk_displacement_cm': max_trunk_disp_cm,
        'max_wrist_forward_cm': max_wrist_forward_cm,
        'trunk_ratio': trunk_ratio,
        'trunk_percent': trunk_ratio * 100 if not np.isnan(trunk_ratio) else np.nan,
        'elbow_flexion_min': df['elbow_flexion_angle'].min(),
        'elbow_flexion_max': df['elbow_flexion_angle'].max(),
        'elbow_flexion_range': df['elbow_flexion_angle'].max() - df['elbow_flexion_angle'].min(),
    }

    print(f"  Shoulder width px: {shoulder_width_px:.1f} px -> cm/px: {cm_per_px:.4f}")
    print(f"  Max shoulder elevation: {max_shoulder_elev_cm:.2f} cm")
    print(f"  Max trunk displacement: {max_trunk_disp_cm:.2f} cm")
    print(f"  Max wrist forward: {max_wrist_forward_cm:.2f} cm")
    print(f"  Trunk ratio: {trunk_ratio:.3f} ({trunk_ratio*100 if not np.isnan(trunk_ratio) else 0:.1f}%)")
    print(f"  Elbow flexion: {summary['elbow_flexion_min']:.1f} - {summary['elbow_flexion_max']:.1f} deg (range {summary['elbow_flexion_range']:.1f})")

    fig, axs = plt.subplots(4, 1, figsize=(12, 14))
    axs[0].plot(df['time'], df['shoulder_elevation_cm'], label='shoulder elevation')
    axs[0].axhline(0, color='gray', linestyle='--')
    axs[0].set_ylabel('Shoulder elevation (cm)')
    axs[0].set_title(f'{label}: shoulder elevation ({affected_side} side)')
    axs[0].legend()

    axs[1].plot(df['time'], df['trunk_x_displacement_cm'], label='trunk displacement', color='orange')
    axs[1].axhline(0, color='gray', linestyle='--')
    axs[1].set_ylabel('Trunk x displacement (cm)')
    axs[1].set_title(f'{label}: trunk compensation')
    axs[1].legend()

    axs[2].plot(df['time'], df['wrist_forward_cm'], label='wrist forward', color='green')
    axs[2].axhline(0, color='gray', linestyle='--')
    axs[2].set_ylabel('Wrist forward (cm)')
    axs[2].set_title(f'{label}: wrist forward reach')
    axs[2].legend()

    axs[3].plot(df['time'], df['elbow_flexion_angle'], label='elbow flexion', color='red')
    axs[3].set_ylabel('Elbow flexion (deg)')
    axs[3].set_xlabel('Time (s)')
    axs[3].set_title(f'{label}: elbow flexion angle')
    axs[3].set_ylim(0, 180)
    axs[3].legend()

    plt.tight_layout()
    plt.savefig(out_dir / f"pose_compensation_{label}.png", dpi=150)
    plt.close()

    df.to_csv(out_dir / f"pose_compensation_{label}.csv", index=False)

    return summary, df, out_video_path


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
all_summaries = []
all_dfs = {}
for label, path in videos.items():
    res = compute_metrics_for_video(label, path)
    if res is not None:
        all_summaries.append(res[0])
        all_dfs[label] = res[1]

if all_summaries:
    df_summary = pd.DataFrame(all_summaries)
    df_summary.to_csv(out_dir / 'pose_compensation_summary.csv', index=False)
    print(f"\nSaved: {out_dir / 'pose_compensation_summary.csv'}")
    print(df_summary.to_string(index=False))
