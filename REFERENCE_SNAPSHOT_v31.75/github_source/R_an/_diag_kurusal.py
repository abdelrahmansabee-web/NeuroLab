import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\R an")
import pandas as pd
from stroke_kinematic_pipeline import analyze_trial, prepare_trial_timeseries, _coords_for_trial
from motion_invariants import palm_image_speed, outbound_reach_window, _list_segments

trials = [
    ("pre", r"D:\Thesis app\participants\kurusal\pre_20260617_142855_pre.csv", "left", "affected"),
    ("post", r"D:\Thesis app\participants\kurusal\post_20260617_142949_post.csv", "left", "affected"),
    ("healthy", r"D:\Thesis app\participants\kurusal\baseline_20260617_143108_healthy_side.csv", "right", "reference"),
]
for label, path, side, prof in trials:
    r = analyze_trial(path, affected_side=side, trial_role="healthy" if label == "healthy" else label)
    df, nfs, afs, up = prepare_trial_timeseries(pd.read_csv(path))
    c, sw, _ = _coords_for_trial(df, path, side, 1920, 1080)
    spd = palm_image_speed(c["palm_x"], c["palm_y"], afs)
    on, off, pk = outbound_reach_window(c["palm_x"], c["palm_y"], afs, sw, analysis_profile=prof)
    segs = _list_segments(spd, c["palm_x"], c["palm_y"], afs, 3.0, 6, 10)
    print(f"\n{label} side={side} SPARC={r['sparc']:.3f}")
    print(f"  move={r['movement_onset_frame']}-{r['movement_offset_frame']} bell={r['sparc_window_onset_frame']}-{r['sparc_window_offset_frame']}")
    print(f"  amp={r['reach_amplitude_sw']:.3f} trunk={r['trunk_ratio']*100:.1f}% space={r.get('sparc_speed_space')}")
    print(f"  outbound={on}-{off} pk={pk}")
    print(f"  segs={[(int(s['start']), int(s['end']), round(s['disp']/sw, 3)) for s in segs[:6]]}")
