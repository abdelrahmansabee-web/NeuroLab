# -*- coding: utf-8 -*-
"""
Create a validation video for the Hands-wrist reach kinematics.
Overlays the fused wrist trajectory, current position, speed trace,
and movement-control metrics on the rotated video.
"""
import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
input_dir = Path(r"D:\Thesis app\participants\3 مرضى\33\انا ٢")
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
data_dir = Path(r"D:\Thesis app\kinematic_analysis\data")

videos = {
    'H': str(input_dir / 'H.MOV'),
    'S': str(input_dir / 'S.MOV'),
}

summary = pd.read_csv(out_dir / "hands_wrist_kinematics_summary.csv")
summary = summary.set_index('label')

def draw_text(frame, text, pos, color=(0, 255, 0), scale=0.5, thickness=1):
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def make_speed_plot(df, peaks, stops, label, out_path):
    fig, ax = plt.subplots(figsize=(4, 1.2), dpi=80)
    ax.plot(df['time'], df['speed_px_s'], 'b-', lw=1)
    if len(peaks) > 0:
        ax.plot(df['time'].iloc[peaks], df['speed_px_s'].iloc[peaks], 'ro', markersize=3)
    for s in stops:
        ax.axvspan(s[0], s[1], color='gray', alpha=0.3)
    ax.set_xlim(df['time'].iloc[0], df['time'].iloc[-1])
    ax.set_ylim(0, df['speed_px_s'].max()*1.1)
    ax.set_ylabel('Speed')
    ax.set_title(f'{label}: speed | NVP={len(peaks)}')
    ax.set_xticks([])
    ax.set_yticks([])
    plt.tight_layout(pad=0.1)
    plt.savefig(out_path, dpi=80)
    plt.close()


def create_validation_video(label, video_path):
    print(f"\n=== Validation video: {label} ===")
    df = pd.read_csv(out_dir / f"hands_wrist_fusion_{label}.csv")
    summ = summary.loc[label]

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w, h = orig_h, orig_w
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    panel_h = 220

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = str(out_dir / f"hands_wrist_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h + panel_h))

    # Precompute peaks and stops
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(df['speed_px_s'].values,
                          prominence=np.nanstd(df['speed_px_s'].values)*0.5,
                          distance=int(fps*0.15))

    threshold = STOP_SPEED_FRACTION = 0.05
    stopped = df['speed_px_s'].values < threshold * np.max(df['speed_px_s'].values)
    stops = []
    i = 0
    while i < len(stopped):
        if stopped[i]:
            j = i
            while j < len(stopped) and stopped[j]:
                j += 1
            duration = df['time'].iloc[j-1] - df['time'].iloc[i]
            if duration >= 0.1:
                stops.append((df['time'].iloc[i], df['time'].iloc[j-1]))
            i = j
        else:
            i += 1

    # Precompute full trajectory image
    traj_path = out_dir / f"hands_wrist_validation_traj_{label}.png"
    fig, ax = plt.subplots(figsize=(w/80, h/80), dpi=80)
    ax.plot(df['wr_x'], df['wr_y'], 'c-', lw=2, alpha=0.6)
    ax.scatter(df['wr_x'].iloc[0], df['wr_y'].iloc[0], c='green', s=80, zorder=5)
    ax.scatter(df['wr_x'].iloc[-1], df['wr_y'].iloc[-1], c='red', s=80, zorder=5)
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis('off')
    plt.tight_layout(pad=0)
    plt.savefig(traj_path, dpi=80)
    plt.close()
    traj_img = cv2.imread(str(traj_path))
    traj_img = cv2.resize(traj_img, (w, h))

    # Speed plot as image strip
    speed_path = out_dir / f"hands_wrist_validation_speed_{label}.png"
    make_speed_plot(df, peaks, stops, label, speed_path)
    speed_img = cv2.imread(str(speed_path))
    speed_h, speed_w = speed_img.shape[:2]

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        # Blend trajectory overlay
        overlay = cv2.addWeighted(rotated, 0.7, traj_img, 0.3, 0)

        # Draw current and past wrist positions
        row = df.iloc[frame_idx]
        wr_x, wr_y = int(row['wr_x']), int(row['wr_y'])
        for j in range(1, min(frame_idx+1, 30)):
            r0 = df.iloc[frame_idx-j]
            r1 = df.iloc[frame_idx-j+1]
            if not np.isnan(r0['wr_x']) and not np.isnan(r1['wr_x']):
                cv2.line(overlay, (int(r0['wr_x']), int(r0['wr_y'])),
                         (int(r1['wr_x']), int(r1['wr_y'])), (0, 0, 255), 2)
        cv2.circle(overlay, (wr_x, wr_y), 6, (0, 0, 255), -1)

        # Metrics panel
        panel_h = 220
        panel = np.zeros((panel_h, w, 3), dtype=np.uint8)
        panel[:] = (40, 40, 40)

        y0 = 30
        line_h = 25
        metrics = [
            f"Hands Wrist Fusion | {label}",
            f"NVP={int(summ['nvp'])}  Stops={int(summ['n_stops'])}  Pause={summ['total_pause_time_s']:.2f}s",
            f"Straightness={summ['overall_straightness']:.3f}  Submovements={int(summ['n_submovements'])}",
            f"Peak speed={summ['peak_speed_px_s']:.1f} px/s  Time to peak={summ['time_to_peak_speed_s']:.2f}s",
            f"Hands detected: {summ['hands_percent']:.1f}%",
            f"Frame {frame_idx+1}/{n_frames}  Time {row['time']:.2f}s",
        ]
        for k, m in enumerate(metrics):
            color = (0, 255, 255) if k == 0 else (255, 255, 255)
            draw_text(panel, m, (20, y0 + k*line_h), color=color, scale=0.6, thickness=1)

        # Add speed plot strip to panel
        sw = min(w-40, speed_w)
        sh = int(sw * speed_h / speed_w)
        speed_resized = cv2.resize(speed_img, (sw, sh))
        y_speed = panel_h - sh - 10
        panel[y_speed:y_speed+sh, 20:20+sw] = speed_resized

        # Add panel on top
        final = np.vstack([panel, overlay])
        writer.write(final)

        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  written {frame_idx}/{n_frames}")

    cap.release()
    writer.release()
    print(f"  Saved: {out_video_path}")
    return out_video_path


for label, path in videos.items():
    create_validation_video(label, path)

print("\nDone.")
