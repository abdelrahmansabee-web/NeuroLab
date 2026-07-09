# -*- coding: utf-8 -*-
"""
Create validation video showing ALL computed variables per frame for H and S.
Top panel: rotated video with pose + marker + trajectory + reach window + elbow angle
Bottom panel: live plots of all metrics
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from io import BytesIO
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
HSV_LOWER1 = np.array([0, 140, 70])
HSV_UPPER1 = np.array([10, 255, 255])
HSV_LOWER2 = np.array([170, 140, 70])
HSV_UPPER2 = np.array([179, 255, 255])

mp_pose = mp.solutions.pose


def lowpass_filter(x, fs, cutoff=10.0, order=4):
    nyq = 0.5 * fs
    if cutoff / nyq >= 1:
        return x
    b, a = butter(order, cutoff / nyq, btype='low')
    return filtfilt(b, a, x)


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


def fig_to_array(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img = cv2.imdecode(np.frombuffer(buf.read(), np.uint8), cv2.IMREAD_COLOR)
    buf.close()
    plt.close(fig)
    return img


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

    out_w = rot_w
    out_h = rot_h + 360  # extra space for plots
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = str(out_dir / f"full_metrics_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (out_w, out_h))

    # Load data
    pose_csv = out_dir / f"pose_compensation_{label}.csv"
    marker_csv = out_dir / f"{label.lower()}_red_marker_tracking.csv"
    df_pose = pd.read_csv(pose_csv)
    df_marker = pd.read_csv(marker_csv)

    # Compute marker metrics
    dt = 1.0 / fps
    x = df_marker['tracked_x'].values
    y = df_marker['tracked_y'].values
    t = df_marker['time'].values
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed_raw = np.sqrt(vx**2 + vy**2)
    speed = lowpass_filter(speed_raw, fps, cutoff=10.0)
    speed = np.clip(speed, 0, None)

    peaks, _ = find_peaks(speed, prominence=np.nanstd(speed)*0.3, distance=int(fps*0.15))
    nvp_total = len(peaks)

    # Straightness
    path_len = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    disp = np.hypot(x[-1]-x[0], y[-1]-y[0])
    straightness = disp / path_len if path_len > 0 else np.nan

    # Pause time
    threshold = 0.05 * np.max(speed)
    paused = speed < threshold
    pause_time = 0
    i = 0
    while i < len(paused):
        if paused[i]:
            j = i
            while j < len(paused) and paused[j]:
                j += 1
            pause_time += t[j-1] - t[i]
            i = j
        else:
            i += 1

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

        # Marker
        marker = detect_marker(rotated)
        if marker:
            mx, my, mr = marker
            cv2.circle(annotated, (mx, my), mr, (0, 255, 0), 2)
            cv2.circle(annotated, (mx, my), 4, (0, 0, 255), -1)
            trajectory.append((mx, my))
        else:
            trajectory.append((np.nan, np.nan))

        for i in range(1, len(trajectory)):
            if not np.isnan(trajectory[i][0]) and not np.isnan(trajectory[i-1][0]):
                cv2.line(annotated, trajectory[i-1], trajectory[i], (255, 255, 0), 2)

        # Pose
        angle = np.nan
        if results.pose_landmarks:
            lm = results.pose_landmarks.landmark
            mp.solutions.drawing_utils.draw_landmarks(annotated, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            sh = np.array([lm[mp_pose.PoseLandmark.RIGHT_SHOULDER].x * rot_w, lm[mp_pose.PoseLandmark.RIGHT_SHOULDER].y * rot_h])
            el = np.array([lm[mp_pose.PoseLandmark.RIGHT_ELBOW].x * rot_w, lm[mp_pose.PoseLandmark.RIGHT_ELBOW].y * rot_h])
            wr = np.array([lm[mp_pose.PoseLandmark.RIGHT_WRIST].x * rot_w, lm[mp_pose.PoseLandmark.RIGHT_WRIST].y * rot_h])
            angle = angle_3points(sh, el, wr)
            for pt, name in [(sh, 'SH'), (el, 'EL'), (wr, 'WR')]:
                cv2.circle(annotated, (int(pt[0]), int(pt[1])), 8, (0, 0, 255), -1)
                cv2.putText(annotated, name, (int(pt[0])+10, int(pt[1])-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Metric plots
        fig, axs = plt.subplots(3, 2, figsize=(10, 5))

        # Speed + peaks + current frame
        axs[0, 0].plot(t, speed, 'b-', lw=1)
        axs[0, 0].plot(t[peaks], speed[peaks], 'ro', markersize=4)
        if frame_idx < len(t):
            axs[0, 0].axvline(t[frame_idx], color='green', linestyle='--')
        axs[0, 0].set_ylabel('Speed (px/s)')
        axs[0, 0].set_title(f'Speed | NVP={nvp_total}')
        axs[0, 0].set_xlim(0, t[-1])

        # Trajectory x vs y
        valid = [(tx, ty) for tx, ty in zip(x, y) if not np.isnan(tx)]
        if valid:
            xs, ys = zip(*valid)
            axs[0, 1].plot(xs, ys, 'b-', lw=1)
            if frame_idx < len(x) and not np.isnan(x[frame_idx]):
                axs[0, 1].scatter(x[frame_idx], y[frame_idx], c='red', s=50)
            axs[0, 1].set_xlabel('x (px)')
            axs[0, 1].set_ylabel('y (px)')
            axs[0, 1].set_title(f'Path | Straightness={straightness:.2f}')
            axs[0, 1].invert_yaxis()

        # Shoulder elevation
        if 'shoulder_elevation_cm' in df_pose.columns and frame_idx < len(df_pose):
            axs[1, 0].plot(df_pose['time'], df_pose['shoulder_elevation_cm'], 'r-', lw=1)
            axs[1, 0].axvline(df_pose['time'].iloc[frame_idx], color='green', linestyle='--')
            axs[1, 0].set_ylabel('Shoulder elev (cm)')
            axs[1, 0].set_title(f'Shoulder Elev | Max={df_pose["shoulder_elevation_cm"].max():.1f} cm')
            axs[1, 0].set_xlim(0, df_pose['time'].max())

        # Trunk displacement
        if 'trunk_x_displacement_cm' in df_pose.columns and frame_idx < len(df_pose):
            axs[1, 1].plot(df_pose['time'], df_pose['trunk_x_displacement_cm'], 'orange', lw=1)
            axs[1, 1].axvline(df_pose['time'].iloc[frame_idx], color='green', linestyle='--')
            axs[1, 1].set_ylabel('Trunk disp (cm)')
            axs[1, 1].set_title(f'Trunk Disp | Max={df_pose["trunk_x_displacement_cm"].max():.1f} cm')
            axs[1, 1].set_xlim(0, df_pose['time'].max())

        # Wrist forward
        if 'wrist_forward_cm' in df_pose.columns and frame_idx < len(df_pose):
            axs[2, 0].plot(df_pose['time'], df_pose['wrist_forward_cm'], 'g-', lw=1)
            axs[2, 0].axvline(df_pose['time'].iloc[frame_idx], color='green', linestyle='--')
            axs[2, 0].set_ylabel('Wrist forward (cm)')
            axs[2, 0].set_xlabel('Time (s)')
            axs[2, 0].set_title(f'Wrist Forward | Max={df_pose["wrist_forward_cm"].max():.1f} cm')
            axs[2, 0].set_xlim(0, df_pose['time'].max())

        # Elbow angle
        if 'elbow_flexion_angle' in df_pose.columns and frame_idx < len(df_pose):
            axs[2, 1].plot(df_pose['time'], df_pose['elbow_flexion_angle'], 'purple', lw=1)
            axs[2, 1].axvline(df_pose['time'].iloc[frame_idx], color='green', linestyle='--')
            axs[2, 1].set_ylabel('Elbow angle (deg)')
            axs[2, 1].set_xlabel('Time (s)')
            axs[2, 1].set_title(f'Elbow | Current={angle:.1f} deg')
            axs[2, 1].set_xlim(0, df_pose['time'].max())
            axs[2, 1].set_ylim(0, 180)

        plt.tight_layout()
        plot_img = fig_to_array(fig)
        plot_img = cv2.resize(plot_img, (out_w, 360))

        # Combine video + plots
        combined = np.vstack([annotated, plot_img])

        # Text overlay
        cv2.putText(combined, f"Frame: {frame_idx}/{n_frames}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(combined, f"NVP: {nvp_total}  Straightness: {straightness:.2f}  Pause: {pause_time:.2f}s",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if not np.isnan(angle):
            cv2.putText(combined, f"Elbow: {angle:.1f} deg", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        writer.write(combined)
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
