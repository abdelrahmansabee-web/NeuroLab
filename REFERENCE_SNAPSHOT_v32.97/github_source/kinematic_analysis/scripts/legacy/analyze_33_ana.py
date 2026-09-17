import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

from stroke_kinematic_pipeline import analyze_trial

ROOT = Path(r"D:/Thesis app/participants/3 مرضى/33/انا")

print("=== Affected .mov ===")
a = analyze_trial(str(ROOT / "Affected .mov"), affected_side="right", trial_role="pre", camera_view="oblique")
print(f"SPARC: {a['sparc']:.3f}")
print(f"Reach amp (SW): {a.get('reach_amplitude_sw'):.3f}")
print(f"Native amp (SW): {a.get('native_reach_amplitude_sw')}")
print(f"Movement time: {a.get('movement_time_sec'):.3f} s")
print(f"Peak velocity: {a.get('peak_velocity_cm_s'):.1f} cm/s")
print(f"Trunk ratio: {a.get('trunk_ratio')}")
print(f"Window: {a.get('sparc_window_onset_frame')}-{a.get('sparc_window_offset_frame')}")
print(f"Camera view: {a.get('camera_view')}")

print("\n=== Healthy.MOV ===")
h = analyze_trial(str(ROOT / "Healthy.MOV"), affected_side="left", trial_role="healthy", camera_view="oblique")
print(f"SPARC: {h['sparc']:.3f}")
print(f"Reach amp (SW): {h.get('reach_amplitude_sw'):.3f}")
print(f"Native amp (SW): {h.get('native_reach_amplitude_sw')}")
print(f"Movement time: {h.get('movement_time_sec'):.3f} s")
print(f"Peak velocity: {h.get('peak_velocity_cm_s'):.1f} cm/s")
print(f"Trunk ratio: {h.get('trunk_ratio')}")
print(f"Window: {h.get('sparc_window_onset_frame')}-{h.get('sparc_window_offset_frame')}")
print(f"Camera view: {h.get('camera_view')}")

print(f"\n=== Comparison ===")
print(f"Affected SPARC: {a['sparc']:.3f}")
print(f"Healthy SPARC: {h['sparc']:.3f}")
if h['sparc'] >= a['sparc']:
    print("Healthy smoother than affected (expected)")
else:
    print("Affected appears smoother than healthy")
