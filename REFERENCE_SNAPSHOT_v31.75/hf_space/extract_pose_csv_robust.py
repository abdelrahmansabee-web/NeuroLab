#!/usr/bin/env python3
"""
أفضل طريقة لاستخراج CSV من فيديو باستخدام MediaPipe PoseLandmarker
مصممة لتكون قوية جداً تحت ظروف صعبة (إضاءة ضعيفة، زاوية جانبية، ملابس، خلفية معقدة...)

المميزات:
- يستخدم MediaPipe PoseLandmarker (الإصدار الحديث)
- معالجة مسبقة للإطارات (CLAHE + تحسين التباين)
- عتبات منخفضة للكشف في الظروف الصعبة
- حفظ الـ Visibility لكل نقطة
- تصفية + استيفاء (interpolation) للنقاط الضعيفة
- دعم معالجة الجانب الأيسر فقط أو كل الجسم
- تقرير جودة لكل فيديو

استخدام:
    python extract_pose_csv_robust.py video.mp4 --output patient_pre.csv
    python extract_pose_csv_robust.py video.mp4 --output patient_pre.csv --clahe --smooth
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _resolve_model_path(model_path: Optional[str] = None) -> Path:
    if model_path:
        p = Path(model_path)
        if p.exists():
            return p
    candidates = [
        Path(__file__).resolve().parent.parent / "backend" / "models" / "pose_landmarker_heavy.task",
        Path(__file__).resolve().parent / "models" / "pose_landmarker_heavy.task",
        Path("/home/user/models/pose_landmarker_heavy.task"),
        Path("/home/user/models/pose_landmarker.task"),
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Pose landmarker model not found. Place pose_landmarker_heavy.task in backend/models/"
    )


DEFAULT_MODEL_PATH = str(_resolve_model_path())

ROBUST_OPTIONS = {
    # استخدم النموذج الكامل لأعلى دقة
    "model_asset_path": DEFAULT_MODEL_PATH,
    "running_mode": vision.RunningMode.VIDEO,
    "num_poses": 1,
    # عتبات منخفضة = يكتشف حتى في الإضاءة الضعيفة والزوايا الجانبية
    "min_pose_detection_confidence": 0.35,
    "min_pose_presence_confidence": 0.35,
    "min_tracking_confidence": 0.40,
}

# أسماء الـ 33 نقطة (نفس ترتيب MediaPipe)
LANDMARK_NAMES = [
    'NOSE', 'LEFT_EYE_INNER', 'LEFT_EYE', 'LEFT_EYE_OUTER',
    'RIGHT_EYE_INNER', 'RIGHT_EYE', 'RIGHT_EYE_OUTER',
    'LEFT_EAR', 'RIGHT_EAR',
    'MOUTH_LEFT', 'MOUTH_RIGHT',
    'LEFT_SHOULDER', 'RIGHT_SHOULDER',
    'LEFT_ELBOW', 'RIGHT_ELBOW',
    'LEFT_WRIST', 'RIGHT_WRIST',
    'LEFT_PINKY', 'RIGHT_PINKY',
    'LEFT_INDEX', 'RIGHT_INDEX',
    'LEFT_THUMB', 'RIGHT_THUMB',
    'LEFT_HIP', 'RIGHT_HIP',
    'LEFT_KNEE', 'RIGHT_KNEE',
    'LEFT_ANKLE', 'RIGHT_ANKLE',
    'LEFT_HEEL', 'RIGHT_HEEL',
    'LEFT_FOOT_INDEX', 'RIGHT_FOOT_INDEX'
]

def create_landmark_columns(legacy_format: bool = False) -> List[str]:
    """إنشاء أسماء الأعمدة بنفس صيغة ملفاتك الحالية + world coords (meters)."""
    cols = ['frame', 'time']
    for name in LANDMARK_NAMES:
        cols.extend([f"{name}_X", f"{name}_Y", f"{name}_Z"])
        if not legacy_format:
            cols.extend([f"{name}_VISIBILITY", f"{name}_WX", f"{name}_WY", f"{name}_WZ"])
    return cols

def preprocess_frame(frame: np.ndarray, use_clahe: bool = True) -> np.ndarray:
    """
    معالجة مسبقة قوية للإطار (مهمة جداً في الظروف الصعبة)
    """
    # 1. تحويل إلى RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    if not use_clahe:
        return rgb
    
    # 2. CLAHE على قناة الإضاءة (Y) لتحسين التباين في الإضاءة الضعيفة
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    
    enhanced = cv2.merge([l, a, b])
    rgb = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
    
    # 3. تحسين خفيف للحدة (اختياري)
    # kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    # rgb = cv2.filter2D(rgb, -1, kernel)
    
    return rgb

def get_pose_landmarker(model_path: str = DEFAULT_MODEL_PATH, legacy_format: bool = False) -> vision.PoseLandmarker:
    """إنشاء كاشف قوي"""
    path = _resolve_model_path(model_path)
    if sys.platform == "win32":
        with open(path, "rb") as f:
            model_buffer = f.read()
        base_options = python.BaseOptions(model_asset_buffer=model_buffer)
    else:
        base_options = python.BaseOptions(model_asset_path=str(path))
    running_mode = vision.RunningMode.IMAGE if legacy_format else vision.RunningMode.VIDEO
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=running_mode,
        num_poses=ROBUST_OPTIONS["num_poses"],
        min_pose_detection_confidence=ROBUST_OPTIONS["min_pose_detection_confidence"],
        min_pose_presence_confidence=ROBUST_OPTIONS["min_pose_presence_confidence"],
        min_tracking_confidence=ROBUST_OPTIONS["min_tracking_confidence"],
    )
    return vision.PoseLandmarker.create_from_options(options)

def interpolate_landmarks(df: pd.DataFrame, max_gap: int = 8) -> pd.DataFrame:
    """
    استيفاء خطي للنقاط الضعيفة أو المفقودة (مهم جداً)
    يعمل فقط على الأعمدة الرقمية.
    """
    numeric_cols = [c for c in df.columns if c not in ['frame', 'time']]
    
    # استبدل القيم المنخفضة جداً (تحت 0.2 visibility) بـ NaN
    for col in numeric_cols:
        if '_VISIBILITY' in col:
            vis_col = col
            base = col.replace('_VISIBILITY', '')
            x_col = f"{base}_X"
            y_col = f"{base}_Y"
            z_col = f"{base}_Z"
            
            # إذا كانت الـ visibility منخفضة → اجعل X,Y,Z = NaN
            low_vis = df[vis_col] < 0.25
            df.loc[low_vis, [x_col, y_col, z_col]] = np.nan
    
    # استيفاء خطي
    df[numeric_cols] = df[numeric_cols].interpolate(method='linear', limit=max_gap, limit_direction='both')
    
    # املأ الباقي بـ forward/backward fill
    df[numeric_cols] = df[numeric_cols].ffill().bfill()
    
    return df

def extract_pose_to_csv(
    video_path: str,
    output_csv: str,
    model_path: str = DEFAULT_MODEL_PATH,
    use_clahe: bool = True,
    smooth: bool = True,
    max_interpolate_gap: int = 6,
    target_fps: Optional[int] = None,
    show_progress: bool = True,
    legacy_format: bool = False,
    save_intermediate_frames: bool = False,
    intermediate_dir: Optional[str] = None,
) -> Dict:
    """
    الدالة الرئيسية - أقوى طريقة حالياً لاستخراج الـ landmarks

    legacy_format=True: يعيد نفس سلوك pose_extractor.py الأصلي (IMAGE mode،
    frame يبدأ من 1، time = idx/fps، لا VISIBILITY/WORLD، alpha smoothing 0.65).

    When save_intermediate_frames=True, sampled RGB frames used for pose
    detection are saved under intermediate_dir/frames as QA artifacts.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"الفيديو غير موجود: {video_path}")

    print(f"🎥 جاري معالجة: {video_path.name}")

    # افتح الفيديو
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("لا يمكن فتح الفيديو")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # Phone videos often stored landscape with portrait content — rotate to upright.
    rotate_cw = width > height * 1.15
    if rotate_cw:
        width, height = height, width

    if target_fps and target_fps < fps:
        frame_step = max(1, int(fps / target_fps))
    else:
        frame_step = 1

    # Intermediate outputs directory
    inter_dir: Optional[Path] = None
    frames_dir: Optional[Path] = None
    if save_intermediate_frames:
        inter_dir = Path(intermediate_dir) if intermediate_dir else Path(output_csv).parent / (Path(output_csv).stem + "_intermediate")
        inter_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = inter_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

    # إعداد الكاشف
    detector = get_pose_landmarker(model_path, legacy_format=legacy_format)
    landmark_cols = create_landmark_columns(legacy_format=legacy_format)

    data = []
    frame_idx = 0
    processed = 0
    timestamp_ms = 0
    step_ms = int(1000 / fps) if fps > 0 else 33

    start_time = time.time()
    prev_smooth = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step != 0:
            frame_idx += 1
            timestamp_ms += step_ms
            continue

        if rotate_cw:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        # === حفظ الإطار الوسيط (اختياري) ===
        if frames_dir is not None and processed % max(1, int(fps)) == 0:
            try:
                cv2.imwrite(str(frames_dir / f"frame_{processed:06d}.jpg"), frame)
            except Exception:
                pass

        # === المعالجة المسبقة القوية ===
        processed_frame = preprocess_frame(frame, use_clahe=False if legacy_format else use_clahe)

        # تحويل إلى MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=processed_frame)

        if legacy_format:
            # سلوك pose_extractor.py الأصلي: IMAGE mode + frame يبدأ من 1 + time = idx/fps
            result = detector.detect(mp_image)
            row_frame = processed + 1
            row_time = round(processed / fps, 5)
        else:
            result = detector.detect_for_video(mp_image, timestamp_ms)
            row_frame = frame_idx
            row_time = timestamp_ms / 1000.0

        row = {'frame': row_frame, 'time': row_time}

        if result.pose_landmarks and len(result.pose_landmarks) > 0:
            landmarks = result.pose_landmarks[0]  # أول شخص فقط
            raw = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)

            if legacy_format:
                if prev_smooth is None:
                    prev_smooth = raw.copy()
                else:
                    alpha = 0.65
                    prev_smooth = alpha * prev_smooth + (1.0 - alpha) * raw
                coords = prev_smooth
                for i, name in enumerate(LANDMARK_NAMES):
                    row[f"{name}_X"] = float(coords[i, 0])
                    row[f"{name}_Y"] = float(coords[i, 1])
                    row[f"{name}_Z"] = float(coords[i, 2])
            else:
                world = (
                    result.pose_world_landmarks[0]
                    if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0
                    else None
                )
                for i, name in enumerate(LANDMARK_NAMES):
                    lm = landmarks[i]
                    row[f"{name}_X"] = float(lm.x)
                    row[f"{name}_Y"] = float(lm.y)
                    row[f"{name}_Z"] = float(lm.z)
                    row[f"{name}_VISIBILITY"] = float(lm.visibility)
                    if world is not None:
                        wlm = world[i]
                        row[f"{name}_WX"] = float(wlm.x)
                        row[f"{name}_WY"] = float(wlm.y)
                        row[f"{name}_WZ"] = float(wlm.z)
                    else:
                        row[f"{name}_WX"] = np.nan
                        row[f"{name}_WY"] = np.nan
                        row[f"{name}_WZ"] = np.nan
        else:
            # لا يوجد كشف → املأ بـ NaN
            for name in LANDMARK_NAMES:
                row[f"{name}_X"] = np.nan
                row[f"{name}_Y"] = np.nan
                row[f"{name}_Z"] = np.nan
                if not legacy_format:
                    row[f"{name}_VISIBILITY"] = 0.0
                    row[f"{name}_WX"] = np.nan
                    row[f"{name}_WY"] = np.nan
                    row[f"{name}_WZ"] = np.nan
            if legacy_format and prev_smooth is not None:
                # في الـ legacy كان بيسيب الفجوة NaN ثم interpolation بعدين
                pass

        data.append(row)
        processed += 1
        timestamp_ms += step_ms * frame_step
        frame_idx += 1

        if show_progress and processed % 30 == 0:
            progress = (frame_idx / total_frames) * 100 if total_frames > 0 else 0
            print(f"   {processed} إطار ({progress:.1f}%)", end='\r')

    cap.release()
    detector.close()

    if not data:
        raise RuntimeError("لم يتم استخراج أي بيانات")

    # تحويل إلى DataFrame
    df = pd.DataFrame(data, columns=landmark_cols)

    # حفظ CSV خام قبل الاستيفاء (وسيط)
    raw_intermediate_path: Optional[Path] = None
    if inter_dir is not None:
        raw_intermediate_path = inter_dir / "raw_landmarks.csv"
        df.to_csv(raw_intermediate_path, index=False)

    # === التصفية والاستيفاء (مهم جداً للظروف الصعبة) ===
    if smooth and not legacy_format:
        print("\n🔄 جاري الاستيفاء وتنعيم النقاط الضعيفة...")
        df = interpolate_landmarks(df, max_gap=max_interpolate_gap)
    elif legacy_format:
        # legacy: interpolation خطي بسيط للفجوات القصيرة، بدون refine
        numeric_cols = [c for c in df.columns if c not in ['frame', 'time']]
        df[numeric_cols] = df[numeric_cols].interpolate(method='linear', limit=8, limit_direction='both')
        df[numeric_cols] = df[numeric_cols].ffill().bfill()

    # حفظ
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    # حفظ CSV بعد الاستيفاء (وسيط)
    filtered_intermediate_path: Optional[Path] = None
    if inter_dir is not None:
        filtered_intermediate_path = inter_dir / "filtered_landmarks.csv"
        df.to_csv(filtered_intermediate_path, index=False)

    duration = time.time() - start_time

    # تقرير جودة
    report = generate_quality_report(df, video_path.name, duration, fps, legacy_format=legacy_format)
    report["csv_path"] = str(output_path)
    report["fps"] = round(fps, 2)
    report["orientation_corrected"] = rotate_cw
    report["frame_width_px"] = width
    report["frame_height_px"] = height
    report["legacy_format"] = legacy_format
    if inter_dir is not None:
        report["intermediate_dir"] = str(inter_dir)
    if raw_intermediate_path is not None:
        report["raw_landmarks_csv"] = str(raw_intermediate_path)
    if filtered_intermediate_path is not None:
        report["filtered_landmarks_csv"] = str(filtered_intermediate_path)
    if frames_dir is not None:
        report["frames_dir"] = str(frames_dir)

    print(f"\n✅ تم الحفظ: {output_path}")
    print(f"   الإطارات المستخرجة: {len(df)}")
    print(f"   المدة: {duration:.1f} ثانية")
    avg_vis = report.get('avg_visibility_shoulder')
    if avg_vis is not None:
        print(f"   متوسط الـ Visibility (LEFT_SHOULDER): {avg_vis:.3f}")

    return report

def generate_quality_report(df: pd.DataFrame, video_name: str, duration: float, fps: float, legacy_format: bool = False) -> Dict:
    """تقرير جودة سريع"""
    report = {
        "video": video_name,
        "frames": len(df),
        "duration_sec": round(duration, 2),
        "fps": round(fps, 1),
    }

    # متوسط الـ visibility للنقاط المهمة
    important = ['LEFT_SHOULDER', 'LEFT_HIP', 'LEFT_ELBOW', 'LEFT_WRIST', 'RIGHT_SHOULDER', 'RIGHT_ELBOW', 'RIGHT_WRIST']
    vis_values = []
    for name in important:
        vis_col = f"{name}_VISIBILITY"
        if vis_col in df.columns:
            avg_vis = float(df[vis_col].mean())
            report[f"avg_visibility_{name.lower()}"] = round(avg_vis, 3)
            vis_values.append(avg_vis)

    # نسبة الإطارات التي تم كشفها بثقة جيدة
    if 'LEFT_SHOULDER_VISIBILITY' in df.columns:
        good = (df['LEFT_SHOULDER_VISIBILITY'] > 0.6).mean()
        report["percent_good_detection"] = round(good * 100, 1)
        report["avg_visibility_shoulder"] = round(float(df['LEFT_SHOULDER_VISIBILITY'].mean()), 3)
    else:
        report["percent_good_detection"] = None
        report["avg_visibility_shoulder"] = None

    if vis_values:
        report["mean_keypoint_visibility"] = round(float(np.mean(vis_values)), 3)
        report["min_keypoint_visibility"] = round(float(np.min(vis_values)), 3)

    return report

# ==================== واجهة سطر الأوامر ====================
def main():
    parser = argparse.ArgumentParser(
        description="استخراج landmarks قوي جداً من فيديو (الأفضل حالياً)"
    )
    parser.add_argument("video", help="مسار الفيديو")
    parser.add_argument("--output", "-o", required=True, help="اسم ملف CSV الناتج")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="مسار نموذج MediaPipe")
    parser.add_argument("--no-clahe", action="store_true", help="تعطيل تحسين التباين CLAHE")
    parser.add_argument("--no-smooth", action="store_true", help="تعطيل الاستيفاء والتنعيم")
    parser.add_argument("--target-fps", type=int, default=None, help="تقليل معدل الإطارات")
    parser.add_argument("--max-gap", type=int, default=6, help="أقصى فجوة للاستيفاء")

    parser.add_argument("--legacy", action="store_true", help="استخدم صيغة pose_extractor.py الأصلية (IMAGE mode، لا CLAHE، لا world coords)")
    parser.add_argument("--save-intermediate-frames", action="store_true", help="حفظ الإطارات الوسيطة المستخدمة في الكشف")
    parser.add_argument("--intermediate-dir", type=str, default=None, help="مجلد حفظ الملفات الوسيطة")

    args = parser.parse_args()

    extract_pose_to_csv(
        video_path=args.video,
        output_csv=args.output,
        model_path=args.model,
        use_clahe=not args.no_clahe,
        smooth=not args.no_smooth,
        max_interpolate_gap=args.max_gap,
        target_fps=args.target_fps,
        legacy_format=args.legacy,
        save_intermediate_frames=args.save_intermediate_frames,
        intermediate_dir=args.intermediate_dir,
    )

if __name__ == "__main__":
    main()