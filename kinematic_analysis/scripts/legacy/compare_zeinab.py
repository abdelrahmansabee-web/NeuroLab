import sys
sys.path.insert(0, r'D:\Thesis app\NeuroLab\hf_repo')
from stroke_kinematic_pipeline import analyze_stroke_kinematic_csv
from pathlib import Path

folder = Path(r'D:\Thesis app\participants\3 مرضى\زينب 1\زينب')
original_csvs = [
    (r'D:\Thesis app\participants\mediapipe\movs\zeyneb\pre_20260603_165439_pre.csv', 'left'),
    (r'D:\Thesis app\participants\mediapipe\movs\zeyneb\post_20260603_165651_post.csv', 'left'),
    (r'D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline_20260603_165330_baseline.csv', 'right'),
]

print('=== Original CSVs ===')
for csv, side in original_csvs:
    r = analyze_stroke_kinematic_csv(csv, affected_side=side)
    print(Path(csv).name, 'sparc', r.get('sparc'), 'trunk', r.get('trunk_ratio'), 'mt', r.get('movement_time_sec'), 'pv_cm', r.get('peak_velocity_cm_s'))

print('\n=== Zeinab 1 videos (legacy) ===')
legacy_csvs = [
    (folder / 'Pre_legacy_raw_pose.csv', 'left'),
    (folder / 'Post_legacy_raw_pose.csv', 'left'),
    (folder / 'Healthy side_legacy_raw_pose.csv', 'right'),
]
for csv, side in legacy_csvs:
    r = analyze_stroke_kinematic_csv(str(csv), affected_side=side)
    print(csv.name, 'sparc', r.get('sparc'), 'trunk', r.get('trunk_ratio'), 'mt', r.get('movement_time_sec'), 'pv_cm', r.get('peak_velocity_cm_s'))
