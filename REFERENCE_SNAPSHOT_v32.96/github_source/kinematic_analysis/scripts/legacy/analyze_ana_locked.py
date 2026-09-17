import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

from stroke_kinematic_pipeline import analyze_trial

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/انا")

print("=== FORCING same camera view = oblique for both, right side ===")

print("\n--- affected.mov ---")
a = analyze_trial(str(ROOT / "affected.mov"), affected_side="right", trial_role="pre", camera_view="oblique")
print(f"  SPARC: {a['sparc']:.3f}")
print(f"  Reach amp (SW): {a.get('reach_amplitude_sw'):.3f}")
print(f"  Native amp (SW): {a.get('native_reach_amplitude_sw')}")
print(f"  Movement time: {a.get('movement_time_sec')} s")
print(f"  Peak velocity: {a.get('peak_velocity_cm_s')} cm/s")
print(f"  Trunk ratio: {a.get('trunk_ratio')}")
print(f"  Window: {a.get('sparc_window_onset_frame')}-{a.get('sparc_window_offset_frame')}")

print("\n--- healthy.mov ---")
h = analyze_trial(str(ROOT / "healthy.mov"), affected_side="right", trial_role="healthy", camera_view="oblique")
print(f"  SPARC: {h['sparc']:.3f}")
print(f"  Reach amp (SW): {h.get('reach_amplitude_sw'):.3f}")
print(f"  Native amp (SW): {h.get('native_reach_amplitude_sw')}")
print(f"  Movement time: {h.get('movement_time_sec')} s")
print(f"  Peak velocity: {h.get('peak_velocity_cm_s')} cm/s")
print(f"  Trunk ratio: {h.get('trunk_ratio')}")
print(f"  Window: {h.get('sparc_window_onset_frame')}-{h.get('sparc_window_offset_frame')}")

print(f"\nComparison: healthy={h['sparc']:.3f} vs affected={a['sparc']:.3f}")
print("Expected: healthy smoother (less negative) than affected")
