"""Full depth + analysis test on one existing video-csv pair."""
from depth_estimator import estimate_shoulder_width_m
from kinematics_analyzer import analyze_reach_and_wipe

base = "pre_20260604_162908_pre"
vid = f"uploads/{base}.MOV"
csv = f"outputs/{base}.csv"

import os; assert os.path.exists(vid), f"not found: {vid}"
assert os.path.exists(csv), f"not found: {csv}"

sw = estimate_shoulder_width_m(vid)
print(f"shoulder_width = {sw:.4f}m = {sw*100:.1f}cm")

ana = analyze_reach_and_wipe(csv, affected_side="auto", metric_scale=sw)
for k in sorted(ana.keys()):
    v = ana[k]
    if k in ("velocity_profile","phases"):
        continue
    print(f"  {k}: {v}")
