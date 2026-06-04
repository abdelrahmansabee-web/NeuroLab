"""Simulate full upload + analysis with metric depth."""
import sys, json, shutil
from pathlib import Path
from datetime import datetime
from pose_extractor import extract_pose_from_video
from depth_estimator import estimate_shoulder_width_m
from kinematics_analyzer import analyze_reach_and_wipe

VID  = Path(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline.MOV")
OUT  = Path(__file__).parent / "outputs"
UPL  = Path(__file__).parent / "uploads"
OUT.mkdir(exist_ok=True); UPL.mkdir(exist_ok=True)

print("=" * 60)
print("SIMULATING FULL PIPELINE (baseline, affected_side=auto)")
print("=" * 60)

# Save video to uploads/
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
base = f"test_{ts}_baseline"
dst = UPL / f"{base}.MOV"
shutil.copy2(str(VID), str(dst))
print(f"Video copied → {dst}")

# Pose extraction
ext = extract_pose_from_video(str(dst), str(OUT), base, str(Path(__file__).parent / "models"))
if not ext.get("success"):
    print(f"ERROR: {ext.get('error')}")
    sys.exit(1)
csv_path = ext["csv_path"]
print(f"CSV → {csv_path}")

# Depth
sw = estimate_shoulder_width_m(str(dst))
print(f"Depth → shoulder_width = {sw:.4f}m")

# Analysis
ana = analyze_reach_and_wipe(csv_path, affected_side="auto", metric_scale=sw)
print(f"\nRESULTS (side={ana.get('side_analyzed')}):")
for k in ["total_path_length","total_path_length_cm","total_lat_range_norm","total_lat_range_cm",
           "shoulder_width_norm","shoulder_width_cm","arm_length_norm","arm_length_cm",
           "total_trunk_palm_ratio","smoothness_pause_pct","total_duration_s"]:
    if k in ana:
        print(f"  {k}: {ana[k]}")
print()
