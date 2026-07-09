# -*- coding: utf-8 -*-
"""
Comprehensive kinematic analysis for wrist-marker videos.
Computes: SPARC, LDJ, NVP, stops, pause time, peak velocity, time to peak velocity,
movement time, path length, straightness, and submovements.
"""
import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks

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
LOWCUT = 0.5
HIGHCUT = 10.0
ORDER = 4

# Tight red HSV
HSV_LOWER1 = np.array([0, 140, 70])
HSV_UPPER1 = np.array([10, 255, 255])
HSV_LOWER2 = np.array([170, 140, 70])
HSV_UPPER2 = np.array([179, 255, 255])

MIN_RADIUS = 3
MAX_RADIUS = 120

# Velocity peak detection
NVP_PROMINENCE_STD = 0.5
NVP_MIN_DISTANCE_S = 0.15

# Stop detection: speed below this fraction of mean is considered a stop
STOP_SPEED_FRACTION = 0.05
STOP_MIN_DURATION_S = 0.1


def bandpass_filter(x, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low <= 0 or high >= 1:
        return x
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, x)


def lowpass_filter(x, fs, cutoff=10.0, order=4):
    nyq = 0.5 * fs
    if cutoff / nyq >= 1:
        return x
    b, a = butter(order, cutoff / nyq, btype='low')
    return filtfilt(b, a, x)


def detect_marker(hsv):
    mask1 = cv2.inRange(hsv, HSV_LOWER1, HSV_UPPER1)
    mask2 = cv2.inRange(hsv, HSV_LOWER2, HSV_UPPER2)
    mask = cv2.bitwise_or(mask1, mask2)
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
    t = np.asarray(t)
    speed = np.asarray(speed)
    if len(speed) < 3:
        return np.nan
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
    arcs = np.sqrt(df**2 + np.diff(ps)**2)
    return -np.sum(arcs)


def compute_ldj(t, speed):
    t = np.asarray(t)
    speed = np.asarray(speed)
    if len(speed) < 3:
        return np.nan
    dt = np.mean(np.diff(t))
    acc = np.gradient(speed, dt)
    jerk = np.gradient(acc, dt)
    displacement = np.trapz(speed, t)
    if displacement <= 0:
        return np.nan
    jerk_sq = np.trapz(jerk**2, t)
    movement_time = t[-1] - t[0]
    if movement_time <= 0:
        return np.nan
    dj = jerk_sq * (movement_time**5) / (displacement**2)
    return -np.log(dj)


def detect_stops(t, speed, stop_fraction=STOP_SPEED_FRACTION, min_duration_s=STOP_MIN_DURATION_S):
    """Detect periods where speed is near zero."""
    threshold = stop_fraction * np.max(speed)
    stopped = speed < threshold
    stops = []
    i = 0
    while i < len(stopped):
        if stopped[i]:
            j = i
            while j < len(stopped) and stopped[j]:
                j += 1
            duration = t[j-1] - t[i]
            if duration >= min_duration_s:
                stops.append((t[i], t[j-1], duration))
            i = j
        else:
            i += 1
    return stops


def segment_submovements(t, x, y, speed, fps):
    """Segment into submovements based on velocity valleys between peaks."""
    t = np.asarray(t)
    x = np.asarray(x)
    y = np.asarray(y)
    speed = np.asarray(speed)

    peaks, props = find_peaks(speed, prominence=np.nanstd(speed)*0.3, distance=int(fps*NVP_MIN_DISTANCE_S))
    if len(peaks) == 0:
        return []

    valleys, _ = find_peaks(-speed, distance=int(fps*0.15))

    windows = []
    for peak in peaks:
        before = valleys[valleys < peak]
        after = valleys[valleys > peak]
        i0 = before[-1] if len(before) > 0 else max(0, peak - int(0.3 * fps))
        i1 = after[0] if len(after) > 0 else min(len(t), peak + int(0.8 * fps))
        if i1 - i0 < int(0.3 * fps):
            continue
        windows.append((int(i0), int(i1)))

    # merge overlaps
    if not windows:
        return []
    windows = sorted(windows)
    merged = [windows[0]]
    for w in windows[1:]:
        last = merged[-1]
        if w[0] < last[1]:
            merged[-1] = (last[0], max(last[1], w[1]))
        else:
            merged.append(w)
    return merged


def analyze_video(label, video_path):
    print(f"\n=== Analyzing {label}: {video_path} ===")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open video for {label}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = str(out_dir / f"wrist_marker_analysis_{label}.mp4")
    writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    points = []
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
        else:
            points.append((frame_idx / fps, np.nan, np.nan, np.nan))

        # Draw existing trajectory
        if len(points) > 1:
            xs = [p[1] for p in points if not np.isnan(p[1])]
            ys = [p[2] for p in points if not np.isnan(p[2])]
            if len(xs) > 1:
                for i in range(1, len(xs)):
                    cv2.line(frame, (int(xs[i-1]), int(ys[i-1])), (int(xs[i]), int(ys[i])), (255, 255, 0), 2)

        writer.write(frame)
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"  processed {frame_idx}/{n_frames}")

    cap.release()
    writer.release()

    df = pd.DataFrame(points, columns=['time', 'x', 'y', 'radius'])
    df = df.interpolate(method='linear', limit_direction='both')

    t = df['time'].values
    x = df['x'].values
    y = df['y'].values
    dt = 1.0 / fps

    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed_raw = np.sqrt(vx**2 + vy**2)
    speed_low = lowpass_filter(speed_raw, fps, cutoff=10.0)
    speed_low = np.clip(speed_low, 0, None)
    speed_bp = bandpass_filter(speed_raw, fps, LOWCUT, HIGHCUT)

    # NVP from lowpass speed
    peaks, props = find_peaks(speed_low, prominence=np.nanstd(speed_low)*NVP_PROMINENCE_STD,
                              distance=int(fps*NVP_MIN_DISTANCE_S))
    nvp = len(peaks)

    # Stops
    stops = detect_stops(t, speed_low)
    n_stops = len(stops)
    total_pause_time = sum(s[2] for s in stops)

    # Peak velocity
    peak_v_idx = np.argmax(speed_low)
    peak_v = speed_low[peak_v_idx]
    time_to_peak_v = t[peak_v_idx] - t[0]

    # Total movement stats
    total_time = t[-1] - t[0]
    total_displacement = np.hypot(x[-1]-x[0], y[-1]-y[0])
    path_length = np.sum([np.hypot(x[i]-x[i-1], y[i]-y[i-1]) for i in range(1, len(x))])
    straightness = total_displacement / path_length if path_length > 0 else np.nan

    # Segment submovements
    windows = segment_submovements(t, x, y, speed_low, fps)
    if not windows:
        # fallback: whole video as one movement
        windows = [(0, len(t))]

    print(f"  Detected {len(windows)} submovement(s), NVP={nvp}, stops={n_stops}, pause_time={total_pause_time:.2f}s")

    # Per-submovement metrics
    submovement_results = []
    for idx, (i0, i1) in enumerate(windows):
        t_w = t[i0:i1]
        x_w = x[i0:i1]
        y_w = y[i0:i1]
        s_low_w = speed_low[i0:i1]
        s_bp_w = speed_bp[i0:i1]

        sparc = compute_sparc(t_w, s_bp_w)
        ldj = compute_ldj(t_w, s_low_w)
        sub_peak_v = np.max(s_low_w)
        sub_mean_v = np.mean(s_low_w)
        sub_mt = t_w[-1] - t_w[0]
        sub_disp = np.hypot(x_w[-1]-x_w[0], y_w[-1]-y_w[0])
        sub_path = np.sum([np.hypot(x_w[j]-x_w[j-1], y_w[j]-y_w[j-1]) for j in range(1, len(x_w))])
        sub_straightness = sub_disp / sub_path if sub_path > 0 else np.nan

        submovement_results.append({
            'label': label,
            'bout': idx + 1,
            'start_s': t_w[0],
            'end_s': t_w[-1],
            'movement_time_s': sub_mt,
            'displacement_px': sub_disp,
            'path_length_px': sub_path,
            'straightness': sub_straightness,
            'peak_speed_px_s': sub_peak_v,
            'mean_speed_px_s': sub_mean_v,
            'sparc': sparc,
            'ldj': ldj,
        })
        print(f"    bout {idx+1}: MT={sub_mt:.2f}s, disp={sub_disp:.1f}px, SPARC={sparc:.2f}, LDJ={ldj:.2f}")

    summary = {
        'label': label,
        'fps': fps,
        'n_frames': n_frames,
        'frames_with_marker': df['x'].notna().sum(),
        'total_time_s': total_time,
        'total_displacement_px': total_displacement,
        'total_path_length_px': path_length,
        'overall_straightness': straightness,
        'nvp': nvp,
        'n_stops': n_stops,
        'total_pause_time_s': total_pause_time,
        'peak_speed_px_s': peak_v,
        'time_to_peak_speed_s': time_to_peak_v,
        'n_submovements': len(windows),
        'mean_sparc': np.nanmean([r['sparc'] for r in submovement_results]),
        'mean_ldj': np.nanmean([r['ldj'] for r in submovement_results]),
    }

    # Plots
    fig, axs = plt.subplots(3, 2, figsize=(14, 12))
    axs[0,0].plot(t, x, label='x')
    axs[0,0].plot(t, y, label='y')
    for idx, (i0, i1) in enumerate(windows):
        axs[0,0].axvspan(t[i0], t[i1-1], color='red', alpha=0.15)
    axs[0,0].set_ylabel('Position (px)')
    axs[0,0].set_title(f'{label}: position vs time')
    axs[0,0].legend()

    axs[0,1].plot(t, speed_low, 'b-', lw=1)
    axs[0,1].plot(t[peaks], speed_low[peaks], 'ro', label=f'NVP={nvp}')
    for s in stops:
        axs[0,1].axvspan(s[0], s[1], color='gray', alpha=0.3)
    axs[0,1].set_ylabel('Speed (px/s)')
    axs[0,1].set_title(f'{label}: speed | stops={n_stops}, pause={total_pause_time:.2f}s')
    axs[0,1].legend()

    axs[1,0].plot(x, y, 'b-', alpha=0.4, label='full path')
    for idx, (i0, i1) in enumerate(windows):
        axs[1,0].plot(x[i0:i1], y[i0:i1], lw=2, label=f'bout {idx+1}')
    axs[1,0].scatter(x[0], y[0], c='green', s=50, label='start')
    axs[1,0].scatter(x[-1], y[-1], c='red', s=50, label='end')
    axs[1,0].set_xlabel('x (px)')
    axs[1,0].set_ylabel('y (px)')
    axs[1,0].set_title(f'{label}: trajectory')
    axs[1,0].invert_yaxis()
    axs[1,0].legend()

    # SPARC and LDJ per bout
    bouts = [r['bout'] for r in submovement_results]
    sparcs = [r['sparc'] for r in submovement_results]
    ldjs = [r['ldj'] for r in submovement_results]
    axs[1,1].bar(bouts, sparcs, color='steelblue')
    axs[1,1].set_xlabel('Bout')
    axs[1,1].set_ylabel('SPARC')
    axs[1,1].set_title('SPARC per submovement')

    axs[2,0].bar(bouts, ldjs, color='coral')
    axs[2,0].set_xlabel('Bout')
    axs[2,0].set_ylabel('LDJ')
    axs[2,0].set_title('LDJ per submovement')

    axs[2,1].axis('off')
    text = (
        f"Total time: {total_time:.2f}s\n"
        f"Total displacement: {total_displacement:.1f}px\n"
        f"Path length: {path_length:.1f}px\n"
        f"Straightness: {straightness:.3f}\n"
        f"NVP: {nvp}\n"
        f"Stops: {n_stops}\n"
        f"Pause time: {total_pause_time:.2f}s\n"
        f"Peak speed: {peak_v:.1f}px/s\n"
        f"Time to peak speed: {time_to_peak_v:.2f}s\n"
        f"Submovements: {len(windows)}\n"
        f"Mean SPARC: {summary['mean_sparc']:.2f}\n"
        f"Mean LDJ: {summary['mean_ldj']:.2f}"
    )
    axs[2,1].text(0.1, 0.5, text, fontsize=12, verticalalignment='center',
                  fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(out_dir / f"wrist_marker_analysis_{label}.png", dpi=150)
    plt.close()

    return summary, submovement_results, out_video_path


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
all_summaries = []
all_submovements = []
for label, path in videos.items():
    res = analyze_video(label, path)
    if res is not None:
        all_summaries.append(res[0])
        all_submovements.extend(res[1])

if all_summaries:
    df_summary = pd.DataFrame(all_summaries)
    df_sub = pd.DataFrame(all_submovements)
    df_summary.to_csv(out_dir / 'wrist_marker_summary.csv', index=False)
    df_sub.to_csv(out_dir / 'wrist_marker_submovements.csv', index=False)
    print(f"\nSaved summary: {out_dir / 'wrist_marker_summary.csv'}")
    print(df_summary.to_string(index=False))
    print(f"\nSaved submovements: {out_dir / 'wrist_marker_submovements.csv'}")
    print(df_sub.to_string(index=False))
