# ================================================================
# kinematics_analyzer_v6.py
# Stroke Rehab Platform — Phase-Based Reach-and-Wipe Analysis
#
# Segments the full movement into 4 phases:
#   forward → wipe_right → wipe_left → return
# Each phase is a single-direction reach/wipe detected by velocity
# peaks separated by velocity troughs.
#
# Spatial metrics normalized by shoulder_width (ref_scale) instead of
# arm length — more robust across recordings with different camera
# distances or patient positioning.
#
# Missing phases report present: false with null metrics.
# Healthy controls and impaired patients use identical pipeline.
# ================================================================

import numpy as np
import pandas as pd
import scipy.signal as signal
import traceback

FILTER_CUTOFF_HZ  = 6.0
FILTER_ORDER      = 4


# ─── Signal utilities ────────────────────────────────────────

def _lp(data, cutoff, fs, order=4):
    b, a = signal.butter(order, min(cutoff/(fs/2), 0.99), btype='low')
    return signal.filtfilt(b, a, data)

def _tang_vel(x, y, fs):
    return np.sqrt((np.gradient(x)*fs)**2 + (np.gradient(y)*fs)**2)

def _arm_len(rs_x, rs_y, re_x, re_y, rw_x, rw_y):
    upper = np.median(np.sqrt((rs_x-re_x)**2 + (rs_y-re_y)**2))
    fore  = np.median(np.sqrt((re_x-rw_x)**2 + (re_y-rw_y)**2))
    return float(upper + fore)

def _elbow_angle(rs_x, rs_y, re_x, re_y, rw_x, rw_y):
    va = np.vstack([rs_x-re_x, rs_y-re_y]).T
    vf = np.vstack([rw_x-re_x, rw_y-re_y]).T
    dot  = np.sum(va*vf, axis=1)
    norm = np.linalg.norm(va, axis=1) * np.linalg.norm(vf, axis=1)
    return np.degrees(np.arccos(np.clip(dot/np.where(norm<1e-9,1e-9,norm), -1, 1)))


# ─── Idle / Pause Ratio (primary smoothness) ─────────────────
# % of movement window where velocity < threshold.
# Higher = more hesitation / stop-and-go = less smooth.
# Robust across durations and severity (no "smoothness paradox").

def _idle_ratio(v, threshold=0.03):
    """
    Pause ratio: % of time where velocity < fixed threshold (0.03).
    Same for all recordings/patients — avoids smoothness paradox.
    """
    if len(v) < 3:
        return 0.0
    return float(np.sum(v < threshold)) / len(v)


# ─── Segmentation ────────────────────────────────────────────

def _find_rest(v_mag, fs, min_rest_s=0.3):
    """Quietest window, tries first 50% then last 50% if noisy."""
    win = max(4, int(min_rest_s*fs))
    for half in [0, 0.5]:
        start = int(len(v_mag) * half)
        end = int(len(v_mag) * (half + 0.5)) - win
        if end <= start:
            continue
        means = [v_mag[i:i+win].mean() for i in range(start, end)]
        best = start + int(np.argmin(means))
        if v_mag[best:best+win].mean() < 0.05:
            return best, best+win
    # Fallback: absolute quietest anywhere
    means = [v_mag[i:i+win].mean() for i in range(len(v_mag)-win)]
    best = int(np.argmin(means))
    return best, best+win


def _onset_offset_hybrid(palm_x, palm_y, v_mag, fs):
    """
    Hybrid onset/offset: peak-based detection extended backward via
    displacement for slow/jittery stroke movements.

    Phase 1: Detect main movement window via peak-relative velocity
             (onset where v >= 5% of peak, offset at trailing gap).
    Phase 2: Extend onset backward to the first sustained displacement
             from rest position (captures slow preparatory movement).
    Phase 3: Also extend offset forward if needed.

    This keeps the peak-focused segmentation (correctly identifying
    the forward/wipe/return structure) while including early slow movement.
    """
    # --- Step 1: Peak-based detection (original approach, lower threshold) ---
    pki = int(np.argmax(v_mag))
    pkv = v_mag[pki]
    thr_peak = max(0.05 * pkv, 0.02)

    # Onset: walk back from peak
    pk_ons = pki
    for i in range(pki - 1, -1, -1):
        if v_mag[i] < thr_peak:
            pk_ons = i + 1
            break
        pk_ons = i
    pk_ons = max(0, pk_ons - 2)

    # Offset: find trailing idle gap
    min_gap_frames = int(1.0 * fs)
    max_gap_frames = int(2.0 * fs)
    min_post_peak_ratio = 0.30

    pk_off = pki
    in_gap = False
    gap_len = 0
    gap_start = 0

    for i in range(pki, len(v_mag)):
        if v_mag[i] < thr_peak:
            if not in_gap:
                in_gap = True
                gap_start = i
                gap_len = 1
            else:
                gap_len += 1
        else:
            if in_gap:
                in_gap = False
                if gap_len >= min_gap_frames:
                    if gap_len >= max_gap_frames:
                        pk_off = gap_start - 1 if gap_start > 0 else 0
                        break
                    lookahead = int(2.0 * fs)
                    post_end = min(i + lookahead, len(v_mag))
                    post_peak = float(v_mag[i:post_end].max()) if i < len(v_mag) else 0.0
                    if post_peak < min_post_peak_ratio * pkv:
                        pk_off = gap_start - 1 if gap_start > 0 else 0
                        break
                else:
                    pk_off = i
            else:
                pk_off = i

    if in_gap:
        pk_off = gap_start - 1 if gap_start > 0 else 0
    if pk_off < pki:
        pk_off = len(v_mag) - 1

    # --- Step 2: Extend onset backward via displacement ---
    # Use first 0.5s as reference
    rest_frames = min(int(0.5 * fs) + 1, max(10, len(palm_x) // 20))
    rest_x = float(np.median(palm_x[:rest_frames]))
    rest_y = float(np.median(palm_y[:rest_frames]))
    disp   = np.sqrt((palm_x - rest_x)**2 + (palm_y - rest_y)**2)

    early_noise = float(disp[:rest_frames].std())
    disp_thr = float(max(early_noise * 5, disp.max() * 0.02, 0.003))
    min_sustain = max(5, int(0.15 * fs))

    # Walk backward from pk_ons, find where displacement drops to noise level
    ext_ons = pk_ons
    for i in range(pk_ons, -1, -1):
        if disp[i] < disp_thr:
            ext_ons = i + 1
            break
        ext_ons = i

    # Ensure minimum distance from pk_ons
    ext_ons = min(ext_ons, max(0, pk_ons - int(0.3 * fs)))

    return ext_ons, pk_off


def _onset_offset_peak(v_mag, fs):
    """
    Peak-based onset/offset detection with gap separation.
    Onset = first frame before peak where v < threshold.
    Offset = last frame before a long gap (>= 0.5s) followed by
             insignificant movement (< 50% of peak).
    """
    pki = int(np.argmax(v_mag))
    pkv = v_mag[pki]
    thr = max(0.20 * pkv, 0.03)

    # Onset: walk back from peak
    ons = pki
    for i in range(pki - 1, -1, -1):
        if v_mag[i] < thr:
            ons = i + 1
            break
        ons = i
    ons = max(0, ons - 2)

    # Offset: find gaps >= 0.33s; skip gaps where post-gap peak >= 50% of main peak
    # If gap >= 1.5s, always cut (new movement attempt regardless of peak)
    min_gap_frames = max(5, int(0.33 * fs))
    max_gap_frames = int(1.5 * fs)
    min_post_peak_ratio = 0.50

    off = pki
    in_gap = False
    gap_len = 0
    gap_start = 0

    for i in range(pki, len(v_mag)):
        if v_mag[i] < thr:
            if not in_gap:
                in_gap = True
                gap_start = i
                gap_len = 1
            else:
                gap_len += 1
        else:
            if in_gap:
                in_gap = False
                if gap_len >= min_gap_frames:
                    if gap_len >= max_gap_frames:
                        off = gap_start - 1 if gap_start > 0 else 0
                        break
                    lookahead = int(2.0 * fs)
                    post_end = min(i + lookahead, len(v_mag))
                    post_peak = float(v_mag[i:post_end].max()) if i < len(v_mag) else 0.0
                    if post_peak >= min_post_peak_ratio * pkv:
                        off = i
                    else:
                        off = gap_start - 1 if gap_start > 0 else 0
                        break
                else:
                    off = i
            else:
                off = i

    if in_gap:
        off = gap_start - 1 if gap_start > 0 else 0

    if off < pki:
        off = len(v_mag) - 1

    return ons, off


# ─── Phase Segmentation ──────────────────────────────────────

def _phase_code(v_peak, n_frames, min_frames=6):
    """Check if phase has enough data for meaningful metrics."""
    return v_peak >= 0.05 and n_frames >= 3


def _segment_phases(v_mag, fs, palm_x=None, palm_y=None):
    """
    Detect velocity peaks within the global movement window and segment into phases.
    Returns (phases_dict, global_onset, global_offset).
    phases_dict: {name: (onset, offset, peak_idx)} — at most 4 phases.

    Uses position-based onset/offset (when palm_x/y provided) for robust
    detection even with slow/jittery stroke patient movement.
    Falls back to peak-based detection if palm data not available.
    """
    if palm_x is not None and palm_y is not None:
        global_onset, global_offset = _onset_offset_hybrid(palm_x, palm_y, v_mag, fs)
    else:
        global_onset, global_offset = _onset_offset_peak(v_mag, fs)
    global_win = np.arange(global_onset, global_offset + 1)

    # Smooth velocity within the window for cleaner peak detection
    v_win = v_mag[global_win].copy()
    v_s = _lp(v_win, 3.0, fs, 2)

    # Find local maxima above 20% of max within window
    win_pk = float(v_win.max())
    min_h = max(0.20 * win_pk, 0.06)
    raw_peaks = []
    for i in range(1, len(v_s) - 1):
        if v_s[i] > v_s[i-1] and v_s[i] > v_s[i+1] and v_s[i] >= min_h:
            raw_peaks.append(global_onset + i)

    # Enforce minimum separation (0.33s — same as gap detection)
    min_sep = max(6, int(0.33 * fs))
    peaks = []
    for p in raw_peaks:
        if not peaks or p - peaks[-1] >= min_sep:
            peaks.append(p)

    # Limit to first 4 phases
    phase_names = ['forward', 'wipe_right', 'wipe_left', 'return']
    peaks = peaks[:4]

    # Build phase boundaries from troughs between consecutive peaks
    phases = {}
    for i, pk in enumerate(peaks):
        name = phase_names[i]
        # Onset: trough before this peak (or global onset for first)
        if i == 0:
            ons = global_onset
        else:
            prev = peaks[i - 1]
            seg = v_mag[prev:pk + 1]
            ons = prev + int(np.argmin(seg))
        offset_candidates = v_mag[pk:global_offset + 1]
        # Offset: trough after this peak (or global offset for last)
        if i == len(peaks) - 1:
            off = global_offset
        else:
            nxt = peaks[i + 1]
            seg = v_mag[pk:nxt + 1]
            off = pk + int(np.argmin(seg))

        # Safety: ensure ons < off
        ons = max(ons, global_onset)
        off = min(off, global_offset)
        if ons >= off:
            off = min(ons + int(0.5 * fs), global_offset)
        if ons >= off:
            off = global_offset

        phases[name] = (int(ons), int(off), int(pk))

    return phases, global_onset, global_offset


# ─── Per-Phase Metrics ──────────────────────────────────────

def _compute_phase_metrics(palm_x, palm_y, trunk_x, trunk_y, rs_x, rs_y, re_x, re_y,
                           rw_x, rw_y, ri_x, ri_y, ls_x, sh_sep, elbow,
                           v_mag, time, onset, offset, ref_scale, fs,
                           idle_threshold=0.03):
    """
    Compute all metrics for a single phase window.
    ref_scale: anatomical reference used for spatial normalization
               (shoulder width, which is more camera-distance-invariant than arm_len).
    """
    win = np.arange(onset, offset + 1)
    pk = float(v_mag[win].max())
    n_frames = len(win)
    valid = pk >= 0.05 and n_frames >= 3

    phase = {"present": valid}

    phase["duration_s"] = round(float(time[offset] - time[onset]), 3)
    phase["peak_velocity"] = round(pk, 4)
    phase["mean_velocity"] = round(float(np.mean(v_mag[win])), 4)
    phase["distance_norm"] = round(np.sqrt((palm_x[offset]-palm_x[onset])**2 +
                                            (palm_y[offset]-palm_y[onset])**2) / ref_scale, 4)
    phase["lateral_range_norm"] = round((palm_x[win].max() - palm_x[win].min()) / ref_scale, 4)
    phase["forward_range_norm"] = round((palm_y[win].max() - palm_y[win].min()) / ref_scale, 4)
    phase["max_elbow_deg"] = round(float(elbow[win].max()), 2)

    if not valid:
        phase["path_ratio"] = None
        phase["pause_pct"] = None
        phase["trunk_palm_ratio"] = None
        phase["net_displacement"] = None
        return phase

    # ── Full metrics ──
    dur = float(time[offset] - time[onset])
    mean_v = float(np.mean(v_mag[win]))

    # Path ratio
    actual = float(np.sum(np.sqrt(np.diff(palm_x[win])**2 + np.diff(palm_y[win])**2)))
    straight = float(np.sqrt((palm_x[offset]-palm_x[onset])**2 +
                             (palm_y[offset]-palm_y[onset])**2))
    min_disp = 0.005
    if straight > min_disp:
        pr = round(actual / straight, 3)
    else:
        pr = None

    # Net distance (body-proportional units via ref_scale)
    dist = round(straight / ref_scale, 4) if straight > min_disp else round(actual / ref_scale, 4)
    lat_r = round((palm_x[win].max() - palm_x[win].min()) / ref_scale, 4)
    fwd_r = round((palm_y[win].max() - palm_y[win].min()) / ref_scale, 4)

    # Trunk/palm ratio: net displacement ratio
    palm_move = np.sqrt((palm_x[offset]-palm_x[onset])**2 + (palm_y[offset]-palm_y[onset])**2)
    trunk_move = np.sqrt((trunk_x[offset]-trunk_x[onset])**2 + (trunk_y[offset]-trunk_y[onset])**2)
    tpr = round(trunk_move / palm_move, 3) if palm_move > min_disp else None

    # Pause
    pause = round(_idle_ratio(v_mag[win], idle_threshold) * 100, 1)

    # Velocity profile for chart (downsampled to max 100 pts)
    v_win = v_mag[win]
    t_win = time[win]
    if len(v_win) > 100:
        idx = np.linspace(0, len(v_win) - 1, 100).astype(int)
        v_win = v_win[idx]
        t_win = t_win[idx]
    phase["velocity_profile"] = {
        "t": [round(float(x), 3) for x in t_win],
        "v": [round(float(x), 4) for x in v_win],
    }

    phase.update({
        "duration_s": round(dur, 3),
        "path_ratio": pr,
        "pause_pct": pause,
        "distance_norm": dist,
        "lateral_range_norm": lat_r,
        "forward_range_norm": fwd_r,
        "trunk_palm_ratio": tpr,
        "net_displacement": {
            "palm_x": round(float(palm_x[offset] - palm_x[onset]), 4),
            "palm_y": round(float(palm_y[offset] - palm_y[onset]), 4),
            "trunk_x": round(float(trunk_x[offset] - trunk_x[onset]), 4),
            "trunk_y": round(float(trunk_y[offset] - trunk_y[onset]), 4),
            "elbow_deg": round(float(elbow[offset] - elbow[onset]), 2),
        },
    })

    return phase


# ─── Main ─────────────────────────────────────────────────────

def _hand_total_path(wrist_x, wrist_y):
    """Total path length traveled by the wrist over the whole recording."""
    return float(np.sum(np.sqrt(np.diff(wrist_x)**2 + np.diff(wrist_y)**2)))


def analyze_reach_and_wipe(
    file_path:        str,
    cutoff_frequency: float = FILTER_CUTOFF_HZ,
    filter_order:     int   = FILTER_ORDER,
    affected_side:    str   = "right",
    metric_scale:     float = 0.0,      # shoulder width in meters (0 = use normalized)
) -> dict:
    """
    Full-recording kinematic analysis for reach-and-wipe task.

    1. Auto-detects which hand (right/left) is more active by comparing
       total path length of each wrist across the entire video.
    2. Analyzes the more active hand — no phase segmentation.
    3. Reports whole-movement metrics: duration, path length, net
       displacement, path ratio, velocity, range, pause, trunk involvement.

    Also computes phase-based segmentation as secondary output.
    """
    try:
        df = pd.read_csv(file_path)
        if 'time' not in df.columns:
            return {"error": "CSV missing 'time' column."}
        time = df['time'].values
        if len(time) < 30:
            return {"error": "Recording too short (< 30 frames)."}

        fs = float(1.0 / np.mean(np.diff(time)))

        # Filter all X/Y columns
        for c in df.columns:
            if c.endswith('_X') or c.endswith('_Y'):
                df[c] = _lp(df[c].values, cutoff_frequency, fs, filter_order)

        def col(lm, ax):
            k = f"{lm}_{ax}"
            if k not in df.columns:
                raise KeyError(k)
            return df[k].values.copy()

        # ── Read BOTH sides ──
        rw_x = col("RIGHT_WRIST", "X"); rw_y = col("RIGHT_WRIST", "Y")
        lw_x = col("LEFT_WRIST",  "X"); lw_y = col("LEFT_WRIST",  "Y")
        rs_x = col("RIGHT_SHOULDER", "X"); rs_y = col("RIGHT_SHOULDER", "Y")
        ls_x = col("LEFT_SHOULDER",  "X"); ls_y = col("LEFT_SHOULDER",  "Y")
        re_x = col("RIGHT_ELBOW", "X"); re_y = col("RIGHT_ELBOW", "Y")
        le_x = col("LEFT_ELBOW",  "X"); le_y = col("LEFT_ELBOW",  "Y")

        # ── Auto-detect the more active hand ──
        right_path = _hand_total_path(rw_x, rw_y)
        left_path  = _hand_total_path(lw_x, lw_y)

        side = affected_side.lower()
        if side == "auto":
            side = "right" if right_path >= left_path else "left"

        if side == "right":
            prefix, opp = "RIGHT", "LEFT"
            palm_x = (rw_x + col("RIGHT_INDEX", "X")) / 2.0
            palm_y = (rw_y + col("RIGHT_INDEX", "Y")) / 2.0
            elbow = _elbow_angle(rs_x, rs_y, re_x, re_y, rw_x, rw_y)
        else:
            prefix, opp = "LEFT", "RIGHT"
            palm_x = (lw_x + col("LEFT_INDEX", "X")) / 2.0
            palm_y = (lw_y + col("LEFT_INDEX", "Y")) / 2.0
            elbow = _elbow_angle(ls_x, ls_y, le_x, le_y, lw_x, lw_y)

        # Trunk centroid
        try:
            lh_x = col("LEFT_HIP",  "X"); lh_y = col("LEFT_HIP",  "Y")
            rh_x = col("RIGHT_HIP", "X"); rh_y = col("RIGHT_HIP", "Y")
            trunk_x = (rs_x + ls_x + lh_x + rh_x) / 4.0
            trunk_y = (rs_y + ls_y + lh_y + rh_y) / 4.0
        except KeyError:
            trunk_x = (rs_x + ls_x) / 2.0
            trunk_y = (rs_y + ls_y) / 2.0

        # Anatomical reference: shoulder width
        arm_len = _arm_len(
            rs_x if side == "right" else ls_x,
            rs_y if side == "right" else ls_y,
            re_x if side == "right" else le_x,
            re_y if side == "right" else le_y,
            rw_x if side == "right" else lw_x,
            rw_y if side == "right" else lw_y,
        )
        shoulder_width = float(np.median(np.sqrt((rs_x - ls_x)**2 + (rs_y - ls_y)**2)))
        ref_scale = max(shoulder_width, 0.05)
        v_mag = _tang_vel(palm_x, palm_y, fs)

        if v_mag.max() < 1e-6:
            return {"error": "No palm movement detected."}

        # Rest period
        rs_i, re_i = _find_rest(v_mag, fs)
        rest_v_arr = v_mag[rs_i:re_i]
        rest_v = float(rest_v_arr.mean())
        # Fixed absolute threshold (0.03) — same for all recordings & patients.
        # Avoids smoothness paradox from peak-relative or noise-adaptive thresholds.
        idle_threshold = 0.03
        baseline_elbow = float(np.median(elbow[rs_i:re_i]))
        sh_sep = np.abs(rs_x - ls_x)

        # ── Active movement window (single, no phase split) ──
        # Use onset/offset detection to trim rest periods at start/end,
        # but DO NOT subdivide into phases.
        g_onset, g_offset = _onset_offset_hybrid(palm_x, palm_y, v_mag, fs)
        win = np.arange(g_onset, g_offset + 1)
        if len(win) < 10:
            win = np.arange(len(time))  # fallback: full recording

        gp_x, gp_y = palm_x[win], palm_y[win]
        gt_x, gt_y = trunk_x[win], trunk_y[win]
        gv         = v_mag[win]
        g_time     = time[win]

        g_peak   = float(gv.max())
        g_mean   = float(np.mean(gv))
        g_pause  = round(_idle_ratio(gv, idle_threshold) * 100, 1)
        g_lat    = round((gp_x.max() - gp_x.min()) / ref_scale, 4)

        # Total path length over active window
        actual_path = float(np.sum(np.sqrt(np.diff(gp_x)**2 + np.diff(gp_y)**2)))
        g_pathlen = round(actual_path / ref_scale, 4)

        # Trunk-to-palm path ratio over active window
        trunk_path = float(np.sum(np.sqrt(np.diff(gt_x)**2 + np.diff(gt_y)**2)))
        g_tpr = round(trunk_path / actual_path, 4) if actual_path > 0.001 else None

        g_elbow = float(elbow[win].max())

        g_trunk_lat  = round((gt_x.max() - gt_x.min()) / ref_scale, 4)
        g_trunk_vert = round((gt_y.max() - gt_y.min()) / ref_scale, 4)
        g_sh_win     = sh_sep[win]
        g_trunk_rot  = round((g_sh_win.max() - g_sh_win.min()) / ref_scale, 4)

        trial_dur = float(g_time[-1] - g_time[0])

        # ── Phase-based metrics (secondary, may be None if unreliable) ──
        try:
            phases, go, goff = _segment_phases(v_mag, fs, palm_x, palm_y)
            all_pn = ['forward', 'wipe_right', 'wipe_left', 'return']
            phase_results = {}
            for name in all_pn:
                if name in phases:
                    ons, off, pki = phases[name]
                    phase_results[name] = _compute_phase_metrics(
                        palm_x, palm_y, trunk_x, trunk_y,
                        rs_x, rs_y, re_x, re_y,
                        rw_x if side == "right" else lw_x,
                        rw_y if side == "right" else lw_y,
                        col(f"{prefix}_INDEX", "X"),
                        col(f"{prefix}_INDEX", "Y"),
                        ls_x, sh_sep, elbow,
                        v_mag, time, ons, off, ref_scale, fs,
                        idle_threshold,
                    )
                    phase_results[name]["onset_time_s"] = round(float(time[ons]), 3)
                    phase_results[name]["offset_time_s"] = round(float(time[off]), 3)
                    phase_results[name]["peak_frame"] = int(pki)
                else:
                    phase_results[name] = {"present": False, "duration_s": None,
                        "peak_velocity": None, "mean_velocity": None, "path_ratio": None,
                        "pause_pct": None, "distance_norm": None, "lateral_range_norm": None,
                        "forward_range_norm": None, "trunk_palm_ratio": None,
                        "max_elbow_deg": None, "net_displacement": None}
            phases_detected = len(phases)
        except Exception:
            phase_results = {}
            phases_detected = 0

        # ── Velocity profile (active window, downsampled) ──
        if len(gv) > 100:
            idx = np.linspace(0, len(gv) - 1, 100).astype(int)
            vp_t = [round(float(g_time[i]), 3) for i in idx]
            vp_v = [round(float(gv[i]), 4) for i in idx]
        else:
            vp_t = [round(float(t), 3) for t in g_time]
            vp_v = [round(float(v), 4) for v in gv]

        result = {
            # QC / metadata
            "side_analyzed":        side,
            "active_hand_path":     round(right_path if side == "right" else left_path, 4),
            "inactive_hand_path":   round(left_path if side == "right" else right_path, 4),
            "arm_length_norm":      round(arm_len, 4),
            "shoulder_width_norm":  round(shoulder_width, 4),
            "ref_scale":            round(ref_scale, 4),
            "fs_hz":                round(fs, 2),
            "rest_velocity":        round(rest_v, 5),
            "idle_threshold":       round(idle_threshold, 5),

            # Active window boundaries
            "active_onset_s":     round(float(time[g_onset]), 3),
            "active_offset_s":    round(float(time[g_offset]), 3),

            # Global metrics (over the active movement window only)
            "total_duration_s":       round(trial_dur, 3),
            "total_peak_velocity":    round(g_peak, 4),
            "total_mean_velocity":    round(g_mean, 4),
            "total_path_length":      g_pathlen,
            "total_lat_range_norm":   g_lat,
            "total_trunk_palm_ratio": g_tpr,
            "total_max_elbow_deg":    round(g_elbow, 2),
            "trunk_lat_norm":         g_trunk_lat,
            "trunk_vert_norm":        g_trunk_vert,
            "trunk_rot_norm":         g_trunk_rot,
            "smoothness_pause_pct":   g_pause,

            # Per-phase data (secondary — may be unreliable for stroke)
            "phases_detected": phases_detected,
            "phases": phase_results,

            # Velocity profile
            "velocity_profile": {"t": vp_t, "v": vp_v},

            # Calibration
            "baseline_elbow_deg": round(baseline_elbow, 2),
        }

        # ── Metric (cm) values when metric_scale is available ──
        if metric_scale > 0:
            m2cm = metric_scale * 100.0  # meters → cm (times shoulder_width factor)
            # ref_scale is in pixels; shoulder_width is also in pixels.
            # normalized value = value_px / shoulder_width_px
            # metric value = value_px * (shoulder_width_m / shoulder_width_px) = norm * shoulder_width_m
            # In cm: metric_cm = norm * shoulder_width_m * 100
            result["shoulder_width_cm"]    = round(metric_scale * 100, 1)
            result["arm_length_cm"]        = round(arm_len * m2cm, 1)
            result["total_path_length_cm"] = round(g_pathlen * m2cm, 1)
            result["total_lat_range_cm"]   = round(g_lat * m2cm, 2)
            result["trunk_lat_cm"]         = round(g_trunk_lat * m2cm, 2)
            result["trunk_vert_cm"]        = round(g_trunk_vert * m2cm, 2)
            result["trunk_rot_cm"]         = round(g_trunk_rot * m2cm, 2)
            result["metric_scale_m"]       = round(metric_scale, 4)

        return result

    except KeyError as ke:
        return {"error": f"Missing CSV column: {ke}"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
