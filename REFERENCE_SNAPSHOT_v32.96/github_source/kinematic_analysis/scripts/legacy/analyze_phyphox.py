# -*- coding: utf-8 -*-
"""
Analyze Phyphox accelerometer recordings for reach-to-target tasks.

Primary smoothness metric: Log Dimensionless Jerk (LDJ)
Secondary smoothness metric: SPARC (Spectral Arc Length)

Assumes:
- CSV has columns: Time (s), Acceleration x, y, z (m/s^2), Absolute acceleration (m/s^2)
- Phone is fixed on the dorsal wrist/forearm.
- Movement phases are detected from absolute acceleration peaks.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, find_peaks
from scipy.integrate import cumulative_trapezoid as cumtrapz

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
base_dir = Path(r"D:\Thesis app\phyphox\t")
conditions = ['h', 'a']  # healthy/affected or pre/post - infer from folder names
out_dir = Path(r"C:\Users\acer\AppData\Local\Temp\opencode")
out_dir.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------
FS_TARGET = 100  # resample to 100 Hz
LOWCUT = 0.5     # high-pass for drift removal
HIGHCUT = 10.0   # low-pass smoothness cutoff
ORDER = 4

# Movement detection
PEAK_PROMINENCE_M_S2 = 1.5   # min peak in |acc|
MIN_PEAK_DISTANCE_S = 1.0    # avoid double peaks
MOVEMENT_DURATION_S = 2.5    # window around each peak
PRE_PEAK_S = 0.3
POST_PEAK_S = 1.5


def load_phyphox_csv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().strip('"') for c in df.columns]
    t = df['Time (s)'].values
    ax = df['Acceleration x (m/s^2)'].values
    ay = df['Acceleration y (m/s^2)'].values
    az = df['Acceleration z (m/s^2)'].values
    a_mag = df['Absolute acceleration (m/s^2)'].values
    return t, ax, ay, az, a_mag


def resample(t, *signals, fs=100):
    dt = 1.0 / fs
    t_new = np.arange(t[0], t[-1] + dt/2, dt)
    out = [np.interp(t_new, t, s) for s in signals]
    return t_new, out


def bandpass_filter(x, fs, lowcut, highcut, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, x)


def compute_ldj(t, speed):
    """
    Log Dimensionless Jerk (LDJ) from speed profile.
    Primary smoothness metric. Lower (more negative) = less smooth.
    Reference: Rohrer et al. 2002; Hogan & Sternad 2009.
    """
    dt = np.mean(np.diff(t))
    acc = np.gradient(speed, dt)
    jerk = np.gradient(acc, dt)
    displacement = np.trapz(speed, t)
    if displacement <= 0:
        return np.nan
    jerk_sq = np.trapz(jerk**2, t)
    movement_time = t[-1] - t[0]
    dimensionless_jerk = jerk_sq * (movement_time**5) / (displacement**2)
    ldj = -np.log(dimensionless_jerk)
    return ldj


def compute_sparc(t, speed):
    """
    SPARC (Spectral Arc Length) from speed profile.
    Secondary smoothness metric; reported for comparison with literature.
    Reference: Balasubramanian et al. 2011, 2015.
    """
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
    sparc = -np.sum(arcs)
    return sparc


def analyze_condition(cond_dir):
    csv_path = cond_dir / 'Raw Data.csv'
    time_path = cond_dir / 'meta' / 'time.csv'
    if not csv_path.exists():
        return None

    t_raw, ax, ay, az, a_mag = load_phyphox_csv(csv_path)
    meta = pd.read_csv(time_path) if time_path.exists() else None

    # Resample to uniform 100 Hz
    t, (ax, ay, az, a_mag) = resample(t_raw, ax, ay, az, a_mag, fs=FS_TARGET)
    fs = FS_TARGET

    # Bandpass filter each axis for velocity integration
    ax_f = bandpass_filter(ax, fs, LOWCUT, HIGHCUT)
    ay_f = bandpass_filter(ay, fs, LOWCUT, HIGHCUT)
    az_f = bandpass_filter(az, fs, LOWCUT, HIGHCUT)

    # Integrate to velocity (drift removed by bandpass)
    vx = cumtrapz(ax_f, t, initial=0)
    vy = cumtrapz(ay_f, t, initial=0)
    vz = cumtrapz(az_f, t, initial=0)
    v_mag = np.sqrt(vx**2 + vy**2 + vz**2)

    # Detect movement peaks from absolute acceleration
    peaks, props = find_peaks(a_mag, prominence=PEAK_PROMINENCE_M_S2, distance=int(MIN_PEAK_DISTANCE_S*fs))

    bouts = []
    for pk in peaks:
        i0 = max(0, int(pk - PRE_PEAK_S*fs))
        i1 = min(len(t), int(pk + POST_PEAK_S*fs))
        if i1 - i0 < int(0.3*fs):
            continue
        t_w = t[i0:i1]
        v_w = v_mag[i0:i1]
        a_w = a_mag[i0:i1]

        ldj = compute_ldj(t_w, v_w)
        sparc = compute_sparc(t_w, v_w)
        peak_v = np.max(v_w)
        mean_v = np.mean(v_w)
        movement_time = t_w[-1] - t_w[0]
        displacement = np.trapz(v_w, t_w)

        bouts.append({
            'start_s': t_w[0],
            'end_s': t_w[-1],
            'movement_time_s': movement_time,
            'peak_velocity_m_s': peak_v,
            'mean_velocity_m_s': mean_v,
            'displacement_m': displacement,
            'ldj': ldj,
            'sparc': sparc,
            'peak_acc_m_s2': a_w.max(),
        })

    result = {
        'condition': cond_dir.name,
        'duration_total_s': t[-1] - t[0],
        'fs_hz': fs,
        'n_samples': len(t),
        'n_detected_bouts': len(bouts),
        'bouts': bouts,
    }
    return result, t, a_mag, v_mag, peaks, bouts


# ------------------------------------------------------------------
# Run analysis
# ------------------------------------------------------------------
all_results = {}
for cond in conditions:
    cond_dir = base_dir / cond
    out = analyze_condition(cond_dir)
    if out is None:
        print(f"Skipping {cond}: no Raw Data.csv")
        continue
    result, t, a_mag, v_mag, peaks, bouts = out
    all_results[cond] = result

    print(f"\n=== Condition: {cond} ===")
    print(f"Duration: {result['duration_total_s']:.2f} s")
    print(f"Samples: {result['n_samples']} @ {result['fs_hz']} Hz")
    print(f"Detected bouts: {result['n_detected_bouts']}")
    for i, b in enumerate(bouts):
        print(f"  Bout {i+1}: MT={b['movement_time_s']:.2f}s, peak_v={b['peak_velocity_m_s']:.3f}m/s, disp={b['displacement_m']:.3f}m, LDJ={b['ldj']:.3f}, SPARC={b['sparc']:.3f}")

    # Plot
    fig, axs = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axs[0].plot(t, a_mag, 'k-', lw=0.8)
    axs[0].plot(t[peaks], a_mag[peaks], 'ro', ms=6)
    axs[0].set_ylabel('|Acceleration| (m/s^2)')
    axs[0].set_title(f'Condition {cond}: acceleration peaks')

    axs[1].plot(t, v_mag, 'b-', lw=0.8)
    for b in bouts:
        mask = (t >= b['start_s']) & (t <= b['end_s'])
        axs[1].plot(t[mask], v_mag[mask], 'r-', lw=1.5)
    axs[1].set_ylabel('Velocity magnitude (m/s)')

    axs[2].plot(t, v_mag, 'b-', lw=0.5, alpha=0.5)
    for i, b in enumerate(bouts):
        mask = (t >= b['start_s']) & (t <= b['end_s'])
        axs[2].plot(t[mask], v_mag[mask], label=f"B{i+1} LDJ={b['ldj']:.2f} SPARC={b['sparc']:.2f}")
    axs[2].set_ylabel('Velocity magnitude (m/s)')
    axs[2].set_xlabel('Time (s)')
    axs[2].legend(loc='upper right', fontsize=7)

    plt.tight_layout()
    plt.savefig(out_dir / f"phyphox_analysis_{cond}.png", dpi=150)
    plt.close()

# Summary CSV
rows = []
for cond, res in all_results.items():
    for b in res['bouts']:
        row = {'condition': cond}
        row.update(b)
        rows.append(row)

if rows:
    df_summary = pd.DataFrame(rows)
    summary_path = out_dir / 'phyphox_summary.csv'
    df_summary.to_csv(summary_path, index=False)
    print(f"\nSaved summary: {summary_path}")
    print(df_summary.to_string(index=False))
