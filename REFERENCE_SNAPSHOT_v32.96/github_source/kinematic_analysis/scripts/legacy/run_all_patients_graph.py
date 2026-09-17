import sys
from pathlib import Path

sys.path.insert(0, r"D:\Thesis app\NeuroLab\hf_repo")

import json
import subprocess

PART = Path(r"D:/Thesis app/participants")

patients = [
    {
        "id": "murat",
        "healthy": (PART / "murat" / "healthy side.mp4", "left"),
        "pre": (PART / "murat" / "pre.mp4", "right"),
        "post": (PART / "murat" / "post.mp4", "right"),
        "view": "oblique",
    },
    {
        "id": "kurusal",
        "healthy": (PART / "kurusal" / "baseline_20260617_143108_healthy_side.csv", "right"),
        "pre": (PART / "kurusal" / "pre_20260617_142855_pre.csv", "left"),
        "post": (PART / "kurusal" / "post_20260617_142949_post.csv", "left"),
        "view": "oblique",
    },
    {
        "id": "zeinab",
        "healthy": (PART / "mediapipe" / "movs" / "zeyneb" / "baseline_20260603_165330_baseline.csv", "right"),
        "pre": (PART / "mediapipe" / "movs" / "zeyneb" / "pre_20260603_165439_pre.csv", "left"),
        "post": (PART / "mediapipe" / "movs" / "zeyneb" / "post_20260603_165651_post.csv", "left"),
        "view": "oblique",
    },
    {
        "id": "33_ana",
        "healthy": (PART / "3 مرضى" / "33" / "انا" / "Healthy.MOV", "left"),
        "affected": (PART / "3 مرضى" / "33" / "انا" / "Affected .mov", "right"),
        "view": "oblique",
    },
]

results = {}
for p in patients:
    pid = p["id"]
    healthy_path, healthy_side = p["healthy"]
    results[pid] = {}
    for label in ["pre", "post", "affected"]:
        if label not in p:
            continue
        aff_path, aff_side = p[label]
        out = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / f"graph_{pid}_{label}.json"
        cmd = [
            sys.executable, "compare_trials_graph.py",
            "--healthy", str(healthy_path),
            "--affected", str(aff_path),
            "--healthy-side", healthy_side,
            "--affected-side", aff_side,
            "--label", label,
            "--view", p["view"],
            "--out", str(out),
        ]
        print(f"\nRunning {pid} {label}...")
        subprocess.run(cmd, cwd=r"D:\Thesis app\NeuroLab\hf_repo", check=True)
        with open(out, "r", encoding="utf-8") as f:
            r = json.load(f)
        results[pid][label] = {
            "sparc": r[label].get("sparc"),
            "njc": r[label].get("normalized_jerk_cost"),
            "njc_pct": r["relative_to_healthy_percent"].get("normalized_jerk_cost"),
            "path_straightness": r[label].get("path_straightness_index"),
            "path_straightness_pct": r["relative_to_healthy_percent"].get("path_straightness_index"),
            "cv_speed": r[label].get("cv_speed"),
            "cv_speed_pct": r["relative_to_healthy_percent"].get("cv_speed"),
            "reach_amp_sw": r[label].get("reach_amplitude_sw"),
            "reach_amp_pct": r["relative_to_healthy_percent"].get("reach_amplitude_sw"),
            "movement_time": r[label].get("movement_time_sec"),
            "movement_time_pct": r["relative_to_healthy_percent"].get("movement_time_sec"),
            "peak_velocity_pct": r[label].get("peak_velocity_pct"),
            "trunk_ratio": r[label].get("trunk_ratio"),
            "trunk_ratio_pct": r["relative_to_healthy_percent"].get("trunk_ratio"),
            "trunk_cheat_ratio": r[label].get("trunk_cheat_ratio"),
            "trunk_cheat_ratio_pct": r["relative_to_healthy_percent"].get("trunk_cheat_ratio"),
            "shoulder_elevation_cm": r[label].get("shoulder_elevation_cm"),
            "shoulder_elevation_pct": r["relative_to_healthy_percent"].get("shoulder_elevation_cm"),
            "hand_displacement_cm": r[label].get("hand_displacement_cm"),
            "hand_displacement_pct": r["relative_to_healthy_percent"].get("hand_displacement_cm"),
            "elbow_angle_deg": r[label].get("elbow_angle_deg"),
            "elbow_angle_pct": r["relative_to_healthy_percent"].get("elbow_angle_deg"),
        }

# Print summary table
print("\n" + "="*160)
print(f"{'Patient':<12} {'Label':<8} {'SPARC':<10} {'NJC':<15} {'NJC%':<8} {'PSI':<8} {'PSI%':<8} {'CV%':<8} {'PV%':<8} {'TR%':<8} {'HD%':<8} {'SE%':<8} {'EA%':<8}")
print("="*160)
for pid, labels in results.items():
    for label, v in labels.items():
        print(f"{pid:<12} {label:<8} {v['sparc']:<10} {str(v['njc']):<15} {str(v['njc_pct']):<8} {str(v['path_straightness']):<8} {str(v['path_straightness_pct']):<8} {str(v['cv_speed_pct']):<8} {str(v['peak_velocity_pct']):<8} {str(v['trunk_ratio_pct']):<8} {str(v['hand_displacement_pct']):<8} {str(v['shoulder_elevation_pct']):<8} {str(v['elbow_angle_pct']):<8}")

# Save all
out_all = Path(r"C:\Users\acer\AppData\Local\Temp\opencode") / "all_patients_graph_metrics.json"
with open(out_all, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nSaved all results to: {out_all}")
