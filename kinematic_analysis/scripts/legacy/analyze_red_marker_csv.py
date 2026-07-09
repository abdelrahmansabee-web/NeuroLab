# -*- coding: utf-8 -*-
"""
Analyze the Kalman-filtered red-marker CSVs from colored_marker_tracking.py.
Computes SPARC, LDJ, movement time, and peak speed using a validated reach window.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks
from scipy.integrate import cumulative_trapezoid

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
csvs = {
    'H': out_dir / 'h_red_marker_tracking.csv',
    'S': out_dir / 's_red_marker_tracking.csv',
}

# ------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------
LOWCUT = 0.5
HIGHCUT = 10.0
ORDER = 4
MIN_REACH_DURATION_S = 0.35
MIN_DISPLACEMENT_PX = 10.0


def bandpass_filter(x, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, x)


def compute_sparc(t, speed):
    speed = np.asarray(speed)
    t = np.asarray(t)
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
    if movement_time <= 0 or displacement <= 0:
        return np.nan
    dj = jerk_sq * (movement_time**5) / (displacement**2)
    return -np.log(dj)


def find_reach_window(t, x, y, speed, fps, around_peak=None):
    """
    Find a forward reach window around a speed peak.
    If around_peak is None, pick the peak with largest forward displacement.
    Returns (i0, i1, t_w, s_w, x_w, y_w).
    """
    t = np.asarray(t)
    x = np.asarray(x)
    y = np.asarray(y)
    speed = np.asarray(speed)

    if around_peak is None:
        peaks, props = find_peaks(speed, prominence=np.nanstd(speed)*0.3, distance=int(fps*0.25))
        if len(peaks) == 0:
            return None
        best = None
        best_score = -np.inf
        for peak in peaks:
            i0 = max(0, peak - int(0.2 * fps))
            i1 = min(len(t), peak + int(0.8 * fps))
            if i1 - i0 < int(MIN_REACH_DURATION_S * fps):
                continue
            dx = x[i1-1] - x[i0]
            dy = y[i1-1] - y[i0]
            displacement = np.sqrt(dx**2 + dy**2)
            if displacement < MIN_DISPLACEMENT_PX:
                continue
            score = displacement
            if score > best_score:
                best_score = score
                best = (i0, i1)
        if best is None:
            peak = peaks[np.argmax(speed[peaks])]
            i0 = max(0, peak - int(0.2 * fps))
            i1 = min(len(t), peak + int(0.8 * fps))
            best = (i0, i1)
        i0, i1 = best
    else:
        peak = int(around_peak)
        i0 = max(0, peak - int(0.2 * fps))
        i1 = min(len(t), peak + int(0.8 * fps))

    return i0, i1, t[i0:i1], speed[i0:i1], x[i0:i1], y[i0:i1]


def find_submovements(t, x, y, speed, fps):
    """Segment continuous movement into submovements using speed peaks and valleys."""
    t = np.asarray(t)
    x = np.asarray(x)
    y = np.asarray(y)
    speed = np.asarray(speed)

    # Find peaks
    peaks, props = find_peaks(speed, prominence=np.nanstd(speed)*0.3, distance=int(fps*0.15))
    if len(peaks) == 0:
        return []

    # Find valleys (local minima) between peaks
    valleys, vprops = find_peaks(-speed, distance=int(fps*0.15))

    windows = []
    for pidx, peak in enumerate(peaks):
        # Find valley before and after
        before = valleys[valleys < peak]
        after = valleys[valleys > peak]
        i0 = before[-1] if len(before) > 0 else max(0, peak - int(0.3 * fps))
        i1 = after[0] if len(after) > 0 else min(len(t), peak + int(0.8 * fps))

        if i1 - i0 < int(MIN_REACH_DURATION_S * fps):
            continue
        dx = x[i1-1] - x[i0]
        dy = y[i1-1] - y[i0]
        displacement = np.sqrt(dx**2 + dy**2)
        if displacement < MIN_DISPLACEMENT_PX:
            continue
        windows.append((int(i0), int(i1)))

    return windows


def analyze_csv(label, csv_path, segment_mode='auto'):
    print(f"\n=== Analyzing {label}: {csv_path} ===")
    df = pd.read_csv(csv_path)
    fps = df['fps'].iloc[0]
    dt = 1.0 / fps

    df = df.interpolate(method='linear', limit_direction='both')
    x = df['tracked_x'].values
    y = df['tracked_y'].values
    t = df['time'].values

    # Compute speed from x,y
    vx = np.gradient(x, dt)
    vy = np.gradient(y, dt)
    speed_raw = np.sqrt(vx**2 + vy**2)

    # Low-pass filtered speed for peak detection and LDJ (keeps positive)
    b_low, a_low = butter(ORDER, HIGHCUT / (0.5 * fps), btype='low')
    speed_low = filtfilt(b_low, a_low, speed_raw)
    speed_low = np.clip(speed_low, 0, None)  # speed must be non-negative

    # Bandpass filtered speed for SPARC spectral analysis
    speed_bp = bandpass_filter(speed_raw, fps, LOWCUT, HIGHCUT)

    # Decide segmentation
    windows = []
    if segment_mode == 'single':
        res = find_reach_window(t, x, y, speed_low, fps)
        if res is not None:
            windows = [res[:2]]
    elif segment_mode == 'multi':
        windows = find_all_reach_windows(t, x, y, speed_low, fps)
    else:  # auto: multi if video > 5 s and > 2 peaks, else single
        n_peaks = len(find_peaks(speed_low, prominence=np.nanstd(speed_low)*0.3, distance=int(fps*0.15))[0])
        if (t[-1] - t[0]) > 5.0 and n_peaks > 2:
            windows = find_submovements(t, x, y, speed_low, fps)
            segment_mode = 'multi'
        else:
            res = find_reach_window(t, x, y, speed_low, fps)
            if res is not None:
                windows = [res[:2]]
            segment_mode = 'single'

    print(f"  segment_mode={segment_mode}, windows={len(windows)}")
    if not windows:
        print("  No reach window found.")
        return None

    results = []
    for widx, (i0, i1) in enumerate(windows):
        t_w = t[i0:i1]
        s_bp_w = speed_bp[i0:i1]
        s_low_w = speed_low[i0:i1]
        x_w = x[i0:i1]
        y_w = y[i0:i1]

        sparc = compute_sparc(t_w, s_bp_w)
        ldj = compute_ldj(t_w, s_low_w)
        peak_v = np.max(s_low_w)
        mean_v = np.mean(s_low_w)
        movement_time = t_w[-1] - t_w[0]
        displacement_px = np.sqrt((x_w[-1]-x_w[0])**2 + (y_w[-1]-y_w[0])**2)

        res = {
            'label': label,
            'bout': widx + 1,
            'fps': fps,
            'n_frames': len(df),
            'frames_tracked': df['tracked_x'].notna().sum(),
            'sparc': sparc,
            'ldj': ldj,
            'peak_speed_px_s': peak_v,
            'mean_speed_px_s': mean_v,
            'movement_time_s': movement_time,
            'displacement_px': displacement_px,
            'window_start_s': t_w[0],
            'window_end_s': t_w[-1],
        }
        print(f"  bout {widx+1}: SPARC={sparc:.3f}, LDJ={ldj:.3f}, MT={movement_time:.2f}s, disp={displacement_px:.1f}px")
        results.append(res)

    # Summary plot for first window and full trajectory
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    axs[0,0].plot(t, x, label='x')
    axs[0,0].plot(t, y, label='y')
    for i0, i1 in windows:
        axs[0,0].axvspan(t[i0], t[i1-1], color='red', alpha=0.15)
    axs[0,0].set_xlabel('Time (s)')
    axs[0,0].set_ylabel('Position (px)')
    axs[0,0].legend()
    axs[0,0].set_title(f'{label}: marker position')

    axs[0,1].plot(t, speed_low, 'b-', lw=1)
    for i0, i1 in windows:
        axs[0,1].axvspan(t[i0], t[i1-1], color='red', alpha=0.15)
    axs[0,1].set_xlabel('Time (s)')
    axs[0,1].set_ylabel('Speed (px/s)')
    axs[0,1].set_title(f'{label}: hand speed')

    # Plot first window path
    i0, i1 = windows[0]
    x_w = x[i0:i1]
    y_w = y[i0:i1]
    axs[1,0].plot(x_w, y_w, 'g-', lw=2)
    axs[1,0].scatter(x_w[0], y_w[0], c='blue', s=50, label='start')
    axs[1,0].scatter(x_w[-1], y_w[-1], c='red', s=50, label='end')
    axs[1,0].set_xlabel('x (px)')
    axs[1,0].set_ylabel('y (px)')
    axs[1,0].set_title('First reach path')
    axs[1,0].invert_yaxis()
    axs[1,0].legend()

    # Spectrum of first window
    t_w = t[i0:i1]
    s_w = speed_bp[i0:i1]
    if len(s_w) >= 3:
        dt2 = np.mean(np.diff(t_w))
        n = len(s_w)
        sp = np.fft.rfft(s_w - np.mean(s_w))
        freqs = np.fft.rfftfreq(n, dt2)
        psd = np.abs(sp)**2
        psd = psd / psd.sum() if psd.sum() > 0 else psd
        axs[1,1].plot(freqs, psd, 'r-', lw=1)
    axs[1,1].set_xlabel('Frequency (Hz)')
    axs[1,1].set_ylabel('Normalized PSD')
    axs[1,1].set_title('First reach speed spectrum')
    axs[1,1].set_xlim(0, 10)

    plt.tight_layout()
    plt.savefig(out_dir / f"red_marker_analysis_{label}.png", dpi=150)
    plt.close()

    return results


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
all_results = []
for label, csv_path in csvs.items():
    res_list = analyze_csv(label, csv_path, segment_mode='auto')
    if res_list is not None:
        all_results.extend(res_list)

if all_results:
    df_res = pd.DataFrame(all_results)
    df_res.to_csv(out_dir / 'red_marker_analysis_summary.csv', index=False)
    print(f"\nSaved summary: {out_dir / 'red_marker_analysis_summary.csv'}")
    print(df_res.to_string(index=False))

    # Per-label summary statistics
    print("\n=== Per-label means ===")
    for label in df_res['label'].unique():
        sub = df_res[df_res['label'] == label]
        print(f"{label}: n_bouts={len(sub)}, SPARC={sub['sparc'].mean():.2f}±{sub['sparc'].std():.2f}, "
              f"LDJ={sub['ldj'].mean():.2f}±{sub['ldj'].std():.2f}, "
              f"MT={sub['movement_time_s'].mean():.2f}±{sub['movement_time_s'].std():.2f}s, "
              f"disp={sub['displacement_px'].mean():.1f}±{sub['displacement_px'].std():.1f}px")
