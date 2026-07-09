import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
from stroke_kinematic_pipeline import analyze_trial
r = analyze_trial(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv", affected_side="right", trial_role="healthy", camera_view="oblique")
for k in sorted(r.keys()):
    if any(x in k for x in ["frame", "window", "onset", "offset"]): continue
    v = r.get(k)
    if not isinstance(v, (dict, list)):
        print(f"{k}: {v}")
