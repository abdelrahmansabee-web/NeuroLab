import sys
sys.path.insert(0, r'D:\Thesis app\NeuroLab\hf_repo')
from mediapipe_csv_extractor import extract_from_video
from stroke_kinematic_pipeline import analyze_stroke_kinematic_csv
from pathlib import Path
import cv2

base = Path(r'D:\Thesis app\participants\3 مرضى')
model = r'D:\Thesis app\NeuroLab\hf_repo\models\pose_landmarker_heavy.task'

patients = [
    ('زينب 1', 'زينب', {
        'Pre.mov': 'left',
        'Post.mov': 'left',
        'Healthy side.mov': 'right',
    }),
    ('كوروسال 1', '', {
        'pre.mp4': 'left',
        'post.mp4': 'left',
        'healthy side.mp4': 'right',
    }),
    ('مورات 1', '', {
        'pre.mp4': 'right',
        'post.mp4': 'right',
        'healthy side.mp4': 'left',
    }),
]

for patient, sub, files in patients:
    folder = base / patient / sub if sub else base / patient
    print(f'\n========== {patient} ==========')
    for fname, side in files.items():
        video = folder / fname
        if not video.exists():
            print(f'[MISSING] {fname}')
            continue
        out = str(folder / f"{Path(fname).stem}_legacy.csv")
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        print(f'\n--- {fname} ({w}x{h}, {frames}fr, {fps:.2f}fps) ---')
        report = extract_from_video(str(video), out, model_path=model, affected_side=side, camera_view='auto', legacy_format=True)
        raw = report.get('raw_pose_csv') or out
        r = analyze_stroke_kinematic_csv(raw, affected_side=side)
        print('sparc', r.get('sparc'), 'trunk', r.get('trunk_ratio'), 'shoulder', r.get('shoulder_elevation_norm'), 'mt', r.get('movement_time_sec'), 'pv_cm', r.get('peak_velocity_cm_s'))
