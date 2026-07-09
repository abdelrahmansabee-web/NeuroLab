import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

from stroke_kinematic_pipeline import analyze_trial

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

def analyze_one(path, side, role):
    print(f"\n=== {path.name} ({role}, {side}) ===")
    r = analyze_trial(str(path), affected_side=side, trial_role=role)
    print(f"  SPARC: {r['sparc']:.3f}")
    print(f"  Rating: {r.get('sparc_interpretation', {}).get('rating')}")
    print(f"  Reach amp (SW): {r.get('reach_amplitude_sw')}")
    print(f"  Native amp (SW): {r.get('native_reach_amplitude_sw')}")
    print(f"  Movement time: {r.get('movement_time_sec')} s")
    print(f"  Peak velocity: {r.get('peak_velocity_cm_s')} cm/s")
    print(f"  Trunk ratio: {r.get('trunk_ratio')}")
    print(f"  Window: {r.get('sparc_window_onset_frame')}-{r.get('sparc_window_offset_frame')}")
    print(f"  Camera view: {r.get('camera_view')}")
    return r

healthy_r = analyze_one(ROOT / "healthy.mov", "right", "healthy")
affected_r = analyze_one(ROOT / "affected.mov", "left", "pre")

# Cross-condition check (affected vs healthy)
sp_h = float(healthy_r.get("sparc"))
sp_a = float(affected_r.get("sparc"))
print(f"\n--- Comparison ---")
print(f"Healthy SPARC: {sp_h:.3f}")
print(f"Affected SPARC: {sp_a:.3f}")
if sp_h >= sp_a:
    print("Healthy side is smoother than affected side (expected).")
else:
    print("WARNING: Affected side appears smoother than healthy side; check camera view / side / movement quality.")
