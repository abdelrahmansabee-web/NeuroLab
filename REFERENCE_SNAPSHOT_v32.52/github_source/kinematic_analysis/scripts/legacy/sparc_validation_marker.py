# -*- coding: utf-8 -*-
"""
SPARC validation for wrist-marker videos.
Detects a colored marker on the wrist, tracks it, computes SPARC,
and generates an overlay video + plots.
"""
import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks
from scipy.integrate import cumulative_trapezoid as cumtrapz

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

# ------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------
FS_VIDEO = 30.0  # will be read from video
LOWCUT = 0.5
HIGHCUT = 10.0
ORDER = 4

# Marker detection: try a broad HSV range that catches common marker colors
# (red/orange/yellow/green/blue)
HSV_RANGES = [
    (np.array([0, 80, 80]), np.array([10, 255, 255])),    # red1
    (np.array([160, 80, 80]), np.array([179, 255, 255])), # red2
    (np.array([15, 80, 80]), np.array([35, 255, 255])),   # yellow/orange
    (np.array([35, 80, 80]), np.array([85, 255, 255])),   # green
    (np.array([85, 80, 80]), np.array([130, 255, 255])),  # blue
]

MIN_RADIUS = 3
MAX_RADIUS = 120


def bandpass_filter(x, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, x)


def detect_marker(hsv):
    mask = None
    for lo, hi in HSV_RANGES:
        m = cv2.inRange(hsv, lo, hi)
        mask = m if mask is None else cv2.bitwise_or(mask, m)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_score = -1.0
    for c in contours:
        (x, y), radius = cv2.minEnclosingCircle(c)
        if radius < MIN_RADIUS or radius > MAX_RADIUS:
            continue
        area = cv2.contourArea(c)
        perimeter = cv2.arcLength(c, True)
        if perimeter <= 0:
            continue
        circularity = 4 * np.pi * area / (perimeter ** 2)
        score = area * circularity
        if score > best_score:
            best_score = score
            best = (np.array([x, y]), radius, circularity)
    return best, mask


def compute_sparc(t, speed):
    dt = np.mean(np.diff(t))
    n = len(speed)
    sp = np.fft.rfft(speed - np.mean(speed))
    freqs = np.fft.rfftfreq(n, dt)
    psd = np.abs(sp) ** 2
    if psd.sum() == 0:
        return np.nan
    cum = np.cumsum(psd)
    cum = cum / cum[-1]
    idx = np.where((cum >= 0.99) | (freqs >= 10.0))[0]
    f_max_idx = idx[0] if len(idx) else len(freqs) - 1
    f = freqs[:f_max_idx+1]
    ps = psd[:f_max_idx+1] / psd[:f_max_idx+1].sum()
    df = f[1] - f[0]
    arcs = np.sqrt((df)**2 + (np.diff(ps))**2)
    return -np.sum(arcs)


def compute_ldj(t, speed):
    dt = np.mean(np.diff(t))
    acc = np.gradient(speed, dt)
    jerk = np.gradient(acc, dt)
    displacement = np.trapz(speed, t)
    if displacement <= 0:
        return np.nan
    jerk_sq = np.trapz(jerk**2, t)
    movement_time = t[-1] - t[0]
    dj = jerk_sq * (movement_time**5) / (displacement**2)
    return -np.log(dj)


def analyze_video(label, video_path):
    print(f"\n=== Analyzing {label} ===")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open video for {label}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or FS_VIDEO
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = str(out_dir / f"sparc_validation_{label}.mp4")
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    points = []
    frames_with_marker = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        det, mask = detect_marker(hsv)
        if det is not None:
            cx, cy = int(det[0][0]), int(det[0][1])
            r = int(det[1])
            cv2.circle(frame, (cx, cy), r, (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
            points.append((frame_idx / fps, det[0][0], det[0][1], det[2]))
            frames_with_marker += 1
        else:
            points.append((frame_idx / fps, np.nan, np.nan, np.nan))
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  processed {frame_idx}/{n_frames}")

    cap.release()
    writer.release()

    print(f"  marker detected in {frames_with_marker}/{n_frames} frames")

    df = pd.DataFrame(points, columns=['time', 'x', 'y', 'radius'])
    df = df.interpolate(method='linear', limit_direction='both')

    # Compute pixel speed
    dt = 1.0 / fps
    vx = np.gradient(df['x'].values, dt)
    vy = np.gradient(df['y'].values, dt)
    speed_raw = np.sqrt(vx**2 + vy**2)

    # Filter speed
    speed_filt = bandpass_filter(speed_raw, fps, LOWCUT, HIGHCUT)
    df['speed_px_s'] = speed_filt

    # Detect reach window from speed peaks
    peaks, props = find_peaks(speed_filt, prominence=np.nanstd(speed_filt), distance=int(fps))
    if len(peaks) == 0:
        print("  no speed peaks found")
        return df, None, out_video_path

    # Use the largest peak
    main_peak = peaks[np.argmax(speed_filt[peaks])]
    pre = int(0.3 * fps)
    post = int(1.5 * fps)
    i0 = max(0, main_peak - pre)
    i1 = min(len(df), main_peak + post)

    t_w = df['time'].values[i0:i1]
    s_w = speed_filt[i0:i1]
    x_w = df['x'].values[i0:i1]
    y_w = df['y'].values[i0:i1]

    sparc = compute_sparc(t_w, s_w)
    ldj = compute_ldj(t_w, s_w)
    peak_v = np.max(s_w)
    mean_v = np.mean(s_w)
    movement_time = t_w[-1] - t_w[0]

    # Spectrum for plots
    dt2 = np.mean(np.diff(t_w))
    n = len(s_w)
    sp = np.fft.rfft(s_w - np.mean(s_w))
    freqs = np.fft.rfftfreq(n, dt2)
    psd = np.abs(sp)**2
    psd = psd / psd.sum() if psd.sum() > 0 else psd

    result = {
        'label': label,
        'n_frames': n_frames,
        'fps': fps,
        'frames_with_marker': frames_with_marker,
        'sparc': sparc,
        'ldj': ldj,
        'peak_speed_px_s': peak_v,
        'mean_speed_px_s': mean_v,
        'movement_time_s': movement_time,
        'window_start_s': t_w[0],
        'window_end_s': t_w[-1],
    }
    print(f"  SPARC={sparc:.3f}, LDJ={ldj:.3f}, peak_speed={peak_v:.1f} px/s, MT={movement_time:.2f}s")

    # Generate overlay video with trajectory
    cap = cv2.VideoCapture(video_path)
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    # Trajectory overlay image
    traj_canvas = np.zeros((h, w, 3), dtype=np.uint8)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if not np.isnan(df['x'].iloc[frame_idx]):
            cx, cy = int(df['x'].iloc[frame_idx]), int(df['y'].iloc[frame_idx])
            cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
            cv2.circle(frame, (cx, cy), 8, (255, 255, 255), 2)
            cv2.circle(traj_canvas, (cx, cy), 2, (0, 255, 255), -1)

        # Blend trajectory
        overlay = cv2.addWeighted(frame, 1.0, traj_canvas, 0.6, 0)

        # Add text
        cv2.putText(overlay, f"{label} | Frame {frame_idx} | SPARC={sparc:.3f}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        writer.write(overlay)
        frame_idx += 1

    cap.release()
    writer.release()

    # Save plots separately
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    axs[0,0].plot(df['time'], df['x'], label='x')
    axs[0,0].plot(df['time'], df['y'], label='y')
    axs[0,0].axvspan(t_w[0], t_w[-1], color='red', alpha=0.2)
    axs[0,0].set_xlabel('Time (s)')
    axs[0,0].set_ylabel('Position (px)')
    axs[0,0].legend()
    axs[0,0].set_title(f'{label}: marker position')

    axs[0,1].plot(df['time'], speed_filt, 'b-', lw=1)
    axs[0,1].axvspan(t_w[0], t_w[-1], color='red', alpha=0.2)
    axs[0,1].set_xlabel('Time (s)')
    axs[0,1].set_ylabel('Speed (px/s)')
    axs[0,1].set_title(f'{label}: hand speed | SPARC={sparc:.3f}')

    axs[1,0].plot(x_w, y_w, 'g-', lw=2)
    axs[1,0].scatter(x_w[0], y_w[0], c='blue', s=50, label='start')
    axs[1,0].scatter(x_w[-1], y_w[-1], c='red', s=50, label='end')
    axs[1,0].set_xlabel('x (px)')
    axs[1,0].set_ylabel('y (px)')
    axs[1,0].set_title('Reach path')
    axs[1,0].invert_yaxis()
    axs[1,0].legend()

    axs[1,1].plot(freqs, psd, 'r-', lw=1)
    axs[1,1].set_xlabel('Frequency (Hz)')
    axs[1,1].set_ylabel('Normalized PSD')
    axs[1,1].set_title('Speed spectrum')
    axs[1,1].set_xlim(0, 10)

    plt.tight_layout()
    plt.savefig(out_dir / f"sparc_validation_{label}_plots.png", dpi=150)
    plt.close()

    return df, result, out_video_path


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
all_results = []
for label, path in videos.items():
    res = analyze_video(label, path)
    if res is not None and res[1] is not None:
        all_results.append(res[1])

if all_results:
    df_res = pd.DataFrame(all_results)
    df_res.to_csv(out_dir / 'sparc_validation_summary.csv', index=False)
    print(f"\nSaved summary: {out_dir / 'sparc_validation_summary.csv'}")
    print(df_res.to_string(index=False))
