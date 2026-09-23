# -*- coding: utf-8 -*-
"""
Hands-wrist kinematic analysis for reach task.
Uses MediaPipe Pose for shoulder/elbow/hip landmarks.
Uses MediaPipe Hands wrist as primary wrist source.
Falls back to Pose wrist when Hands is not detected.
When two hands detected, selects the hand whose wrist is closest to Pose wrist.
Computes movement-control metrics: NVP, straightness, pause time, peak speed,
time to peak speed, movement time, path length, SPARC, LDJ, submovements.
"""
import cv2
import numpy as np
import pandas as pd
import mediapipe as mp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import butter, filtfilt, find_peaks
import json

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

metadata_path = Path(r"D:\Thesis app\kinematic_analysis\data\patient_33_metadata.json")
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

affected_side = metadata.get("affected_side", "RIGHT")
shoulder_width_cm = metadata.get("shoulder_width_cm", 40.0)
rotation_deg = metadata.get("video_rotation_degrees", -90)
VISIBILITY_THRESHOLD = 0.5

mp_pose = mp.solutions.pose
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# ------------------------------------------------------------------
# Parameters for movement metrics
# ------------------------------------------------------------------
LOWCUT = 0.5
HIGHCUT = 10.0
ORDER = 4
NVP_PROMINENCE_STD = 0.5
NVP_MIN_DISTANCE_S = 0.15
STOP_SPEED_FRACTION = 0.05
STOP_MIN_DURATION_S = 0.1


def rotate_frame_90_clockwise(frame):
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)


def get_pose_landmark_xy(lm, idx, w, h):
    p = lm[idx]
    if p.visibility < VISIBILITY_THRESHOLD:
        return np.array([np.nan, np.nan])
    return np.array([p.x * w, p.y * h])


def get_hands_wrist(results_hands, pose_wrist, w, h):
    """Choose hand whose wrist is closest to pose wrist; fallback if no pose."""
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


def bandpass_filter(x, fs, lowcut=0.5, highcut=10.0, order=4):
    if np.all(np.isnan(x)) or len(x) < 10:
        return x
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low <= 0 or high >= 1:
        return x
    b, a = butter(order, [low, high], btype='band')
    mask = ~np.isnan(x)
    if mask.sum() < 10:
        return x
    xi = np.arange(len(x))
    x_filled = np.interp(xi, xi[mask], x[mask])
    return filtfilt(b, a, x_filled)


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


def segment_submovements(t, speed, fps):
    t = np.asarray(t)
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


def compute_wrist_kinematics(t, x, y, fps):
    dt = 1.0 / fps
    t = np.asarray(t)
    x = np.asarray(x)
    y = np.asarray(y)

    # Filter position lightly to reduce noise
    x_filt = lowpass_filter(x, fps, cutoff=10.0)
    y_filt = lowpass_filter(y, fps, cutoff=10.0)

    vx = np.gradient(x_filt, dt)
    vy = np.gradient(y_filt, dt)
    speed_raw = np.sqrt(vx**2 + vy**2)
    speed_low = lowpass_filter(speed_raw, fps, cutoff=10.0)
    speed_low = np.clip(speed_low, 0, None)
    speed_bp = bandpass_filter(speed_raw, fps, LOWCUT, HIGHCUT)

    peaks, props = find_peaks(speed_low, prominence=np.nanstd(speed_low)*NVP_PROMINENCE_STD,
                              distance=int(fps*NVP_MIN_DISTANCE_S))
    nvp = len(peaks)

    stops = detect_stops(t, speed_low)
    n_stops = len(stops)
    total_pause_time = sum(s[2] for s in stops)

    peak_v_idx = np.argmax(speed_low)
    peak_v = speed_low[peak_v_idx]
    time_to_peak_v = t[peak_v_idx] - t[0]

    total_time = t[-1] - t[0]
    total_displacement = np.hypot(x_filt[-1]-x_filt[0], y_filt[-1]-y_filt[0])
    path_length = np.sum([np.hypot(x_filt[i]-x_filt[i-1], y_filt[i]-y_filt[i-1]) for i in range(1, len(x_filt))])
    straightness = total_displacement / path_length if path_length > 0 else np.nan

    windows = segment_submovements(t, speed_low, fps)
    if not windows:
        windows = [(0, len(t))]

    return {
        't': t, 'x': x_filt, 'y': y_filt,
        'speed_low': speed_low, 'speed_bp': speed_bp,
        'nvp': nvp, 'stops': stops, 'n_stops': n_stops,
        'total_pause_time': total_pause_time,
        'peak_v': peak_v, 'time_to_peak_v': time_to_peak_v,
        'total_time': total_time,
        'total_displacement': total_displacement,
        'path_length': path_length,
        'straightness': straightness,
        'windows': windows,
    }


def analyze_video(label, video_path):
    print(f"\n=== Hands-wrist kinematic analysis: {label} ===")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open video for {label}")
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

    opp = 'RIGHT' if affected_side == 'LEFT' else 'LEFT'
    sh_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_SHOULDER')
    el_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_ELBOW')
    wr_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_WRIST')
    hip_idx = getattr(mp_pose.PoseLandmark, f'{affected_side}_HIP')
    opp_sh_idx = getattr(mp_pose.PoseLandmark, f'{opp}_SHOULDER')
    opp_hip_idx = getattr(mp_pose.PoseLandmark, f'{opp}_HIP')

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
            opp_hip = get_pose_landmark_xy(lm, opp_hip_idx, w, h)

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
                'opp_hip_x': opp_hip[0], 'opp_hip_y': opp_hip[1],
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
                'opp_hip_x': np.nan, 'opp_hip_y': np.nan,
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

    # Filter positions
    for col in ['sh_x', 'sh_y', 'el_x', 'el_y', 'wr_x', 'wr_y', 'hip_x', 'hip_y', 'opp_sh_x', 'opp_sh_y', 'opp_hip_x', 'opp_hip_y']:
        df[col] = lowpass_filter(df[col].values, fps, cutoff=10.0)

    # Compute scale from shoulder width
    shoulder_width_px = abs(df['sh_x'].iloc[:10].mean() - df['opp_sh_x'].iloc[:10].mean())
    if np.isnan(shoulder_width_px) or shoulder_width_px < 1:
        shoulder_width_px = abs(df['hip_x'].iloc[:10].mean() - df['opp_hip_x'].iloc[:10].mean()) * 0.7
    cm_per_px = shoulder_width_cm / shoulder_width_px if shoulder_width_px and shoulder_width_px > 0 else np.nan

    # Compute wrist kinematics
    kin = compute_wrist_kinematics(df['time'].values, df['wr_x'].values, df['wr_y'].values, fps)

    # Add kinematic columns to df
    df['speed_px_s'] = kin['speed_low']
    df['nvp_marker'] = 0

    # Submovement metrics
    submovement_results = []
    for idx, (i0, i1) in enumerate(kin['windows']):
        t_w = kin['t'][i0:i1]
        x_w = kin['x'][i0:i1]
        y_w = kin['y'][i0:i1]
        s_low_w = kin['speed_low'][i0:i1]
        s_bp_w = kin['speed_bp'][i0:i1]

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
        'affected_side': affected_side,
        'fps': fps,
        'n_frames': n_frames,
        'hands_frames': hands_detected,
        'hands_percent': 100*hands_detected/n_frames,
        'shoulder_width_px': shoulder_width_px,
        'cm_per_px': cm_per_px,
        'total_time_s': kin['total_time'],
        'total_displacement_px': kin['total_displacement'],
        'total_path_length_px': kin['path_length'],
        'overall_straightness': kin['straightness'],
        'nvp': kin['nvp'],
        'n_stops': kin['n_stops'],
        'total_pause_time_s': kin['total_pause_time'],
        'peak_speed_px_s': kin['peak_v'],
        'time_to_peak_speed_s': kin['time_to_peak_v'],
        'n_submovements': len(kin['windows']),
        'mean_sparc': np.nanmean([r['sparc'] for r in submovement_results]),
        'mean_ldj': np.nanmean([r['ldj'] for r in submovement_results]),
    }

    print(f"  NVP={kin['nvp']}, stops={kin['n_stops']}, pause={kin['total_pause_time']:.2f}s")
    print(f"  Straightness={kin['straightness']:.3f}, peak_speed={kin['peak_v']:.1f}px/s, ttp={kin['time_to_peak_v']:.2f}s")

    # Plots
    fig, axs = plt.subplots(3, 2, figsize=(14, 12))
    axs[0,0].plot(kin['t'], kin['x'], label='x')
    axs[0,0].plot(kin['t'], kin['y'], label='y')
    for idx, (i0, i1) in enumerate(kin['windows']):
        axs[0,0].axvspan(kin['t'][i0], kin['t'][i1-1], color='red', alpha=0.15)
    axs[0,0].set_ylabel('Position (px)')
    axs[0,0].set_title(f'{label}: Hands wrist position')
    axs[0,0].legend()

    axs[0,1].plot(kin['t'], kin['speed_low'], 'b-', lw=1)
    peaks_arr = np.array([], dtype=int)
    if kin['nvp'] > 0:
        # Recompute peak indices for plotting
        peaks_arr, _ = find_peaks(kin['speed_low'], prominence=np.nanstd(kin['speed_low'])*NVP_PROMINENCE_STD,
                                  distance=int(fps*NVP_MIN_DISTANCE_S))
        axs[0,1].plot(kin['t'][peaks_arr], kin['speed_low'][peaks_arr], 'ro', label=f'NVP={kin["nvp"]}')
    for s in kin['stops']:
        axs[0,1].axvspan(s[0], s[1], color='gray', alpha=0.3)
    axs[0,1].set_ylabel('Speed (px/s)')
    axs[0,1].set_title(f'{label}: speed | stops={kin["n_stops"]}, pause={kin["total_pause_time"]:.2f}s')
    axs[0,1].legend()

    axs[1,0].plot(kin['x'], kin['y'], 'b-', alpha=0.4, label='full path')
    for idx, (i0, i1) in enumerate(kin['windows']):
        axs[1,0].plot(kin['x'][i0:i1], kin['y'][i0:i1], lw=2, label=f'bout {idx+1}')
    axs[1,0].scatter(kin['x'][0], kin['y'][0], c='green', s=50, label='start')
    axs[1,0].scatter(kin['x'][-1], kin['y'][-1], c='red', s=50, label='end')
    axs[1,0].set_xlabel('x (px)')
    axs[1,0].set_ylabel('y (px)')
    axs[1,0].set_title(f'{label}: Hands wrist trajectory')
    axs[1,0].invert_yaxis()
    axs[1,0].legend()

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
        f"Total time: {kin['total_time']:.2f}s\n"
        f"Displacement: {kin['total_displacement']:.1f}px\n"
        f"Path length: {kin['path_length']:.1f}px\n"
        f"Straightness: {kin['straightness']:.3f}\n"
        f"NVP: {kin['nvp']}\n"
        f"Stops: {kin['n_stops']}\n"
        f"Pause time: {kin['total_pause_time']:.2f}s\n"
        f"Peak speed: {kin['peak_v']:.1f}px/s\n"
        f"Time to peak: {kin['time_to_peak_v']:.2f}s\n"
        f"Submovements: {len(kin['windows'])}\n"
        f"Mean SPARC: {summary['mean_sparc']:.2f}\n"
        f"Mean LDJ: {summary['mean_ldj']:.2f}\n"
        f"Hands used: {hands_detected}/{n_frames} ({100*hands_detected/n_frames:.1f}%)"
    )
    axs[2,1].text(0.1, 0.5, text, fontsize=12, verticalalignment='center',
                  fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(out_dir / f"hands_wrist_kinematics_{label}.png", dpi=150)
    plt.close()

    # Save data
    df.to_csv(out_dir / f"hands_wrist_fusion_{label}.csv", index=False)
    pd.DataFrame(submovement_results).to_csv(out_dir / f"hands_wrist_submovements_{label}.csv", index=False)

    return summary, submovement_results, df, kin


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
    df_summary.to_csv(out_dir / 'hands_wrist_kinematics_summary.csv', index=False)
    df_sub.to_csv(out_dir / 'hands_wrist_submovements_all.csv', index=False)
    print(f"\nSaved summary: {out_dir / 'hands_wrist_kinematics_summary.csv'}")
    print(df_summary.to_string(index=False))
    print(f"\nSaved submovements: {out_dir / 'hands_wrist_submovements_all.csv'}")
    print(df_sub.to_string(index=False))
