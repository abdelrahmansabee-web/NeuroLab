import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\R an")
import pandas as pd
from stroke_kinematic_pipeline import _coords_for_trial, _infer_fs, analyze_trial
from motion_invariants import select_reach_window, outbound_reach_window, _list_segments, palm_image_speed

for label, path, side, role in [
    ("pre", r"D:\Thesis app\participants\kurusal\pre_20260617_142855_pre.csv", "left", "affected"),
    ("post", r"D:\Thesis app\participants\kurusal\post_20260617_142949_post.csv", "left", "affected"),
    ("healthy", r"D:\Thesis app\participants\kurusal\baseline_20260617_143108_healthy_side.csv", "right", "reference"),
]:
    df = pd.read_csv(path)
    nfs = _infer_fs(df)
    c, sw, _ = _coords_for_trial(df, path, side, 1920, 1080)
    ms, me = select_reach_window(c["palm_x"], c["palm_y"], nfs, shoulder_width=sw, analysis_profile=role if role != "affected" else "affected")
    on, off, pk = outbound_reach_window(c["palm_x"], c["palm_y"], nfs, sw, analysis_profile="reference" if role == "reference" else "affected")
    spd = palm_image_speed(c["palm_x"], c["palm_y"], nfs)
    segs = _list_segments(spd, c["palm_x"], c["palm_y"], nfs, 3.0, 6, 10)
    r = analyze_trial(path, affected_side=side, trial_role="healthy" if label == "healthy" else label)
    print(f"\n{label} native_fs={nfs:.1f} n={len(df)}")
    print(f"  native select {ms}-{me} outbound {on}-{off}")
    print(f"  analyze move {r['movement_onset_frame']}-{r['movement_offset_frame']} SPARC={r['sparc']:.3f}")
    print(f"  segs={[(int(s['start']), int(s['end']), round(s['disp']/sw,3)) for s in segs]}")
