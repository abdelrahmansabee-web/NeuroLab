import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

from stroke_kinematic_pipeline import analyze_trial

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

print("=== AFFECTED with right side ===")
r = analyze_trial(str(ROOT / "affected.mov"), affected_side="right", trial_role="pre")
print(f"  SPARC: {r['sparc']:.3f}")
print(f"  Reach amp (SW): {r.get('reach_amplitude_sw')}")
print(f"  Native amp (SW): {r.get('native_reach_amplitude_sw')}")
print(f"  Movement time: {r.get('movement_time_sec')} s")
print(f"  Peak velocity: {r.get('peak_velocity_cm_s')} cm/s")
print(f"  Trunk ratio: {r.get('trunk_ratio')}")
print(f"  Window: {r.get('sparc_window_onset_frame')}-{r.get('sparc_window_offset_frame')}")
print(f"  Camera view: {r.get('camera_view')}")

print("\n=== HEALTHY with right side ===")
r = analyze_trial(str(ROOT / "healthy.mov"), affected_side="right", trial_role="healthy")
print(f"  SPARC: {r['sparc']:.3f}")
print(f"  Reach amp (SW): {r.get('reach_amplitude_sw')}")
print(f"  Native amp (SW): {r.get('native_reach_amplitude_sw')}")
print(f"  Movement time: {r.get('movement_time_sec')} s")
print(f"  Peak velocity: {r.get('peak_velocity_cm_s')} cm/s")
print(f"  Trunk ratio: {r.get('trunk_ratio')}")
print(f"  Window: {r.get('sparc_window_onset_frame')}-{r.get('sparc_window_offset_frame')}")
print(f"  Camera view: {r.get('camera_view')}")
