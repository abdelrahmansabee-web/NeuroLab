import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import json
from stroke_kinematic_pipeline import analyze_patient_kinematic_triad

PART = Path(r"D:/Thesis app/participants/murat")

# Use a locked camera view for all three to make them comparable
VIEW = "oblique"

result = analyze_patient_kinematic_triad(
    str(PART / "pre.mp4"),
    str(PART / "post.mp4"),
    str(PART / "healthy side.mp4"),
    pre_side="right",
    post_side="right",
    healthy_side="left",
    pre_video=str(PART / "pre.mp4"),
    post_video=str(PART / "post.mp4"),
    healthy_video=str(PART / "healthy side.mp4"),
    camera_view=VIEW,
)

print("\n=== MURAT ANALYSIS ===")
print(f"Locked camera view: {VIEW}")
for label in ["pre", "post", "healthy"]:
    t = result[label]
    print(f"\n{label.upper()}:")
    print(f"  SPARC: {t['sparc']:.3f}")
    print(f"  SPARC matched: {t.get('sparc_matched')}")
    print(f"  Interpretation: {t.get('sparc_interpretation', {}).get('rating')}")
    print(f"  Reach amplitude (SW): {t.get('reach_amplitude_sw'):.3f}")
    print(f"  Native amplitude (SW): {t.get('native_reach_amplitude_sw')}")
    print(f"  Movement time: {t.get('movement_time_sec'):.3f} s")
    print(f"  Peak velocity: {t.get('peak_velocity_cm_s'):.1f} cm/s")
    print(f"  Trunk ratio: {t.get('trunk_ratio'):.4f}")
    print(f"  Window: {t.get('sparc_window_onset_frame')}-{t.get('sparc_window_offset_frame')}")

print(f"\nComparison valid: {result.get('sparc_comparison_valid')}")
print(f"Issues: {result.get('sparc_comparison_issues')}")
print(f"Warnings: {result.get('sparc_comparison_warnings')}")
print(f"Target amplitude (matched): {result.get('sparc_matched_target_amplitude_sw')}")

# Save summary
out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / "murat_summary.json"
summary = {
    "patient": "murat",
    "locked_camera_view": VIEW,
    "pre": {k: v for k, v in result["pre"].items() if k in ["sparc", "sparc_matched", "sparc_interpretation", "reach_amplitude_sw", "native_reach_amplitude_sw", "movement_time_sec", "peak_velocity_cm_s", "trunk_ratio", "sparc_window_onset_frame", "sparc_window_offset_frame"]},
    "post": {k: v for k, v in result["post"].items() if k in ["sparc", "sparc_matched", "sparc_interpretation", "reach_amplitude_sw", "native_reach_amplitude_sw", "movement_time_sec", "peak_velocity_cm_s", "trunk_ratio", "sparc_window_onset_frame", "sparc_window_offset_frame"]},
    "healthy": {k: v for k, v in result["healthy"].items() if k in ["sparc", "sparc_matched", "sparc_interpretation", "reach_amplitude_sw", "native_reach_amplitude_sw", "movement_time_sec", "peak_velocity_cm_s", "trunk_ratio", "sparc_window_onset_frame", "sparc_window_offset_frame"]},
    "sparc_comparison_valid": result.get("sparc_comparison_valid"),
    "sparc_comparison_issues": result.get("sparc_comparison_issues"),
    "sparc_comparison_warnings": result.get("sparc_comparison_warnings"),
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
print(f"\nSaved summary to: {out}")
