import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import json
from stroke_kinematic_pipeline import analyze_trial

PART = Path(r"D:/Thesis app/participants")

patients = {
    "murat": {
        "pre": (PART / "murat" / "pre.mp4", "right"),
        "post": (PART / "murat" / "post.mp4", "right"),
        "healthy": (PART / "murat" / "healthy side.mp4", "left"),
    },
    "kurusal": {
        "pre": (PART / "kurusal" / "pre_20260617_142855_pre.csv", "left"),
        "post": (PART / "kurusal" / "post_20260617_142949_post.csv", "left"),
        "healthy": (PART / "kurusal" / "baseline_20260617_143108_healthy_side.csv", "right"),
    },
    "zeinab": {
        "pre": (PART / "mediapipe" / "movs" / "zeyneb" / "pre_20260603_165439_pre.csv", "left"),
        "post": (PART / "mediapipe" / "movs" / "zeyneb" / "post_20260603_165651_post.csv", "left"),
        "healthy": (PART / "mediapipe" / "movs" / "zeyneb" / "baseline_20260603_165330_baseline.csv", "right"),
    },
}

scores = {}
for pid, trials in patients.items():
    print(f"\n=== {pid} ===")
    patient_ok = True
    durations = []
    amps = []
    for label, (path, side) in trials.items():
        if not path.exists():
            print(f"  {label}: missing")
            patient_ok = False
            continue
        r = analyze_trial(str(path), affected_side=side, trial_role=label)
        dur = r.get("movement_time_sec")
        amp = r.get("reach_amplitude_sw")
        pv = r.get("peak_velocity_cm_s")
        print(f"  {label}: dur={dur:.2f}s, amp={amp:.3f}SW, pv={pv:.1f}cm/s, sparc={r['sparc']:.3f}, view={r.get('camera_view')}")
        if dur is not None:
            durations.append(dur)
        if amp is not None:
            amps.append(amp)
        # Per-trial criteria
        if dur is None or not (0.5 <= dur <= 5.0) or amp is None or amp < 0.12:
            patient_ok = False
    # Score: prefer patient whose pre/healthy have similar amplitude and short-ish duration
    if patient_ok and amps and durations:
        amp_spread = max(amps) / min(amps)
        mean_dur = sum(durations) / len(durations)
        score = amp_spread * mean_dur
        scores[pid] = (score, amp_spread, mean_dur)
        print(f"  -> amp_spread={amp_spread:.2f}, mean_dur={mean_dur:.2f}, score={score:.2f}")
    else:
        print(f"  -> FAILS protocol criteria")

print("\n=== RANKING (lower score = closer to protocol) ===")
for pid, (score, amp_spread, mean_dur) in sorted(scores.items(), key=lambda x: x[1][0]):
    print(f"{pid}: score={score:.2f} (amp_spread={amp_spread:.2f}, mean_dur={mean_dur:.2f})")
