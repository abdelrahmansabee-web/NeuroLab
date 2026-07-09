import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")
sys.stdout.reconfigure(encoding="utf-8")

from stroke_kinematic_pipeline import analyze_patient_kinematic_triad

PART = Path(r"D:/Thesis app/participants")
result = analyze_patient_kinematic_triad(
    str(PART / "kurusal" / "pre_20260617_142855_pre.csv"),
    str(PART / "kurusal" / "post_20260617_142949_post.csv"),
    str(PART / "kurusal" / "baseline_20260617_143108_healthy_side.csv"),
    pre_side="left", post_side="left", healthy_side="right",
)

for label in ["pre", "post", "healthy"]:
    r = result[label]
    print(f"\n{label.upper()}:")
    print(f"  sparc={r['sparc']:.4f}, matched={r.get('sparc_matched')}")
    print(f"  reach_amplitude_sw={r.get('reach_amplitude_sw')}")
    print(f"  native_reach_amplitude_sw={r.get('native_reach_amplitude_sw')}")
    print(f"  reach_window={r.get('reach_window_onset_frame')}-{r.get('reach_window_offset_frame')}")
    print(f"  sparc_window={r.get('sparc_window_onset_frame')}-{r.get('sparc_window_offset_frame')}")
    print(f"  movement_time={r.get('movement_time_sec')}")

print(f"\ncomparison_valid={result.get('sparc_comparison_valid')}")
print(f"comparison_issues={result.get('sparc_comparison_issues')}")
print(f"target_amplitude={result.get('sparc_matched_target_amplitude_sw')}")
