import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\R an")
import pandas as pd
from stroke_kinematic_pipeline import (
    prepare_trial_timeseries, _coords_for_trial, calculate_sparc_from_speed,
    _upsample_coord_dict, ANALYSIS_TARGET_FS,
)
from motion_invariants import body_frame_palm, reach_speed_series, sparc_bell_window, palm_image_speed, primary_reach_window

def sparc_window(path, side, ms, me, fs):
    c, sw, _ = _coords_for_trial(pd.read_csv(path), path, side, 1920, 1080)
    df, nfs, afs, up = prepare_trial_timeseries(pd.read_csv(path))
    if nfs < 55:
        c = _upsample_coord_dict(c, nfs, 60)
        fs = 60
    bx, by, bz, _ = body_frame_palm(c["palm_x"], c["palm_y"], c["shoulder_x"], c["shoulder_y"], sw)
    spd = reach_speed_series(bx, by, bz, fs)
    ws, we = sparc_bell_window(spd, ms, me)
    return calculate_sparc_from_speed(spd[ws:we+1], fs=fs), ws, we

path_h = r"D:\Thesis app\participants\kurusal\baseline_20260617_143108_healthy_side.csv"
path_p = r"D:\Thesis app\participants\kurusal\post_20260617_142949_post.csv"

for label, path, side, windows in [
    ("healthy", path_h, "right", [(20,102), (33,85), (66,170), (40,120)]),
    ("post", path_p, "left", [(189,259), (95,129), (86,180), (110,200)]),
]:
    print(f"\n{label}:")
    for ms, me in windows:
        s, ws, we = sparc_window(path, side, ms, me, 60)
        print(f"  win {ms}-{me} bell {ws}-{we} SPARC={s:.3f}")

# first reach only via primary
df, nfs, afs, _ = prepare_trial_timeseries(pd.read_csv(path_h))
c, sw, _ = _coords_for_trial(df, path_h, "right", 1920, 1080)
if nfs < 55:
    c = _upsample_coord_dict(c, nfs, 60)
    afs = 60
pix = palm_image_speed(c["palm_x"], c["palm_y"], afs)
ps, pe = primary_reach_window(pix, c["palm_x"], c["palm_y"], afs, 3.0, sw, min_amp_sw=0.15)
print(f"\nhealthy primary_reach {ps}-{pe}")
s, ws, we = sparc_window(path_h, "right", ps, pe, afs)
print(f"  SPARC={s:.3f} bell {ws}-{we}")

df2, nfs2, _, _ = prepare_trial_timeseries(pd.read_csv(path_p))
c2, sw2, _ = _coords_for_trial(df2, path_p, "left", 1920, 1080)
if nfs2 < 55:
    c2 = _upsample_coord_dict(c2, nfs2, 60)
    afs2 = 60
else:
    afs2 = nfs2
pix2 = palm_image_speed(c2["palm_x"], c2["palm_y"], afs2)
ps2, pe2 = primary_reach_window(pix2, c2["palm_x"], c2["palm_y"], afs2, 3.0, sw2, min_amp_sw=0.15)
print(f"\npost primary_reach {ps2}-{pe2}")
s2, ws2, we2 = sparc_window(path_p, "left", ps2, pe2, afs2)
print(f"  SPARC={s2:.3f} bell {ws2}-{we2}")
