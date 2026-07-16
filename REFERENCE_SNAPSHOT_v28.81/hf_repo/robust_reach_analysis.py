#!/usr/bin/env python3
"""
================================================================================
ROBUST & CONSISTENT CROSS-BODY REACH ANALYSIS
================================================================================
هذا هو التحليل الموحد والمظبوط 100% الذي يعمل على أي فيديو/CSV
بغض النظر عن تاريخ التسجيل أو ظروف التصوير.

المميزات:
- يستخدم نفس الحسابات دائماً (deterministic)
- يركز على الجانب الأيسر فقط (Cross-Body Reach)
- تصفية ذكية للإطارات الضعيفة (بناءً على Visibility)
- كشف مرحلة الحركة (Reach Phase Detection)
- إحصائيات قوية (median + IQR)
- مؤشر جودة موحد + تقرير ثقة
- يعمل على أي CSV ناتج من extract_pose_csv_robust.py

الاستخدام:
    from robust_reach_analysis import analyze_reach_csv
    results = analyze_reach_csv("pre_robust.csv", name="PRE")
    print(results)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# ==================== إعدادات ثابتة (لا تغيرها أبداً) ====================
MIN_VISIBILITY = 0.45          # أقل visibility مقبولة
REACH_PHASE_THRESHOLD = 0.35   # نسبة حركة اليد لاعتبارها مرحلة وصول
TRUNK_COMPENSATION_LIMIT = 60  # أقصى زاوية جذع للحساب

# أوزان مؤشر الجودة (ثابتة)
QUALITY_WEIGHTS = {
    'trunk': 0.40,
    'shoulder': 0.25,
    'elbow': 0.15,
    'smoothness': 0.20
}

# ==================== دوال الحساب الأساسية (ثابتة) ====================

def calculate_trunk_flexion(shoulder_x: float, shoulder_y: float,
                            hip_x: float, hip_y: float) -> float:
    """زاوية انحناء الجذع (0° = مستقيم، أعلى = أسوأ)"""
    vec = np.array([shoulder_x - hip_x, shoulder_y - hip_y])
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        return 0.0
    cos = np.dot(vec / norm, [0, -1])
    angle = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
    return float(np.clip(angle, 0, 90))

def calculate_shoulder_elevation(hip_x, hip_y, shoulder_x, shoulder_y,
                                 elbow_x, elbow_y) -> float:
    """زاوية ارتفاع الكتف (أعلى = أفضل)"""
    v1 = np.array([hip_x - shoulder_x, hip_y - shoulder_y])
    v2 = np.array([elbow_x - shoulder_x, elbow_y - shoulder_y])
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n < 1e-6:
        return 0.0
    cos = np.dot(v1, v2) / n
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))

def calculate_elbow_extension(shoulder_x, shoulder_y, elbow_x, elbow_y,
                              wrist_x, wrist_y) -> float:
    """تمدد المرفق (180° = ممدود كامل، أقل = منثني)"""
    v1 = np.array([shoulder_x - elbow_x, shoulder_y - elbow_y])
    v2 = np.array([wrist_x - elbow_x, wrist_y - elbow_y])
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n < 1e-6:
        return 90.0
    cos = np.dot(v1, v2) / n
    angle = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
    return float(np.clip(angle, 0, 180))

def compute_path_smoothness(wrist_positions: np.ndarray) -> float:
    """سلاسة مسار اليد (1.0 = مثالي)"""
    if len(wrist_positions) < 3:
        return 0.0
    
    diffs = np.diff(wrist_positions, axis=0)
    path_length = np.sum(np.linalg.norm(diffs, axis=1))
    displacement = np.linalg.norm(wrist_positions[-1] - wrist_positions[0])
    
    if path_length < 1e-6:
        return 1.0
    
    straightness = displacement / path_length
    
    speeds = np.linalg.norm(diffs, axis=1)
    if len(speeds) > 1 and speeds.mean() > 1e-6:
        cv = speeds.std() / (speeds.mean() + 1e-6)
        speed_smooth = 1.0 / (1.0 + cv)
    else:
        speed_smooth = straightness
    
    return float((straightness + speed_smooth) / 2)

# ==================== كشف مرحلة الحركة ====================

def detect_reach_phase(df: pd.DataFrame) -> pd.DataFrame:
    """
    يكتشف مرحلة الوصول الفعلية (عندما تتحرك اليد للأمام بشكل واضح).
    يتجاهل البداية والنهاية الساكنتين.
    """
    if 'LEFT_WRIST_X' not in df.columns:
        return df
    
    wrist_x = df['LEFT_WRIST_X'].values
    if len(wrist_x) < 5:
        df['is_reach_phase'] = True
        return df
    
    # حركة تراكمية
    cumulative = np.abs(np.cumsum(np.diff(wrist_x, prepend=wrist_x[0])))
    total_range = cumulative.max() - cumulative.min() if len(cumulative) > 1 else 0
    
    if total_range < 0.01:
        df['is_reach_phase'] = True
        return df
    
    # نعتبر الإطارات التي فيها حركة بين 10% و 90% من المدى
    reach_mask = (cumulative > total_range * 0.10) & (cumulative < total_range * 0.90)
    df['is_reach_phase'] = reach_mask
    
    # إذا كان عدد الإطارات في مرحلة الوصول قليل جداً، نأخذ كل شيء
    if reach_mask.sum() < 5:
        df['is_reach_phase'] = True
    
    return df

# ==================== التحليل الرئيسي ====================

def analyze_reach_csv(csv_path: str, name: str = "UNKNOWN",
                      min_visibility: float = MIN_VISIBILITY) -> Dict[str, Any]:
    """
    التحليل الموحد والمظبوط لأي ملف CSV.
    يرجع نتائج متسقة 100% بغض النظر عن مصدر الفيديو.
    """
    df = pd.read_csv(csv_path)
    
    required = ['LEFT_SHOULDER_X', 'LEFT_SHOULDER_Y',
                'LEFT_HIP_X', 'LEFT_HIP_Y',
                'LEFT_ELBOW_X', 'LEFT_ELBOW_Y',
                'LEFT_WRIST_X', 'LEFT_WRIST_Y']
    
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"error": f"أعمدة مفقودة: {missing}", "name": name}
    
    # === 1. تصفية الإطارات حسب الجودة ===
    if 'LEFT_SHOULDER_VISIBILITY' in df.columns:
        good_vis = (df['LEFT_SHOULDER_VISIBILITY'] >= min_visibility) & \
                   (df['LEFT_HIP_VISIBILITY'] >= min_visibility) if 'LEFT_HIP_VISIBILITY' in df.columns else True
        df_filtered = df[good_vis].copy()
    else:
        df_filtered = df.copy()
    
    if len(df_filtered) < 8:
        df_filtered = df.copy()  # fallback
    
    # === 2. كشف مرحلة الحركة ===
    df_filtered = detect_reach_phase(df_filtered)
    reach_df = df_filtered[df_filtered.get('is_reach_phase', True)].copy()
    
    if len(reach_df) < 5:
        reach_df = df_filtered
    
    # === 3. حساب المقاييس لكل إطار ===
    trunk_vals = []
    shoulder_vals = []
    elbow_vals = []
    wrist_pos = []
    
    for _, row in reach_df.iterrows():
        try:
            trunk = calculate_trunk_flexion(
                row['LEFT_SHOULDER_X'], row['LEFT_SHOULDER_Y'],
                row['LEFT_HIP_X'], row['LEFT_HIP_Y']
            )
            shoulder = calculate_shoulder_elevation(
                row['LEFT_HIP_X'], row['LEFT_HIP_Y'],
                row['LEFT_SHOULDER_X'], row['LEFT_SHOULDER_Y'],
                row['LEFT_ELBOW_X'], row['LEFT_ELBOW_Y']
            )
            elbow = calculate_elbow_extension(
                row['LEFT_SHOULDER_X'], row['LEFT_SHOULDER_Y'],
                row['LEFT_ELBOW_X'], row['LEFT_ELBOW_Y'],
                row['LEFT_WRIST_X'], row['LEFT_WRIST_Y']
            )
            
            trunk_vals.append(trunk)
            shoulder_vals.append(shoulder)
            elbow_vals.append(elbow)
            wrist_pos.append([row['LEFT_WRIST_X'], row['LEFT_WRIST_Y']])
        except:
            continue
    
    if len(trunk_vals) < 3:
        return {"error": "بيانات غير كافية", "name": name}
    
    trunk = np.array(trunk_vals)
    shoulder = np.array(shoulder_vals)
    elbow = np.array(elbow_vals)
    wrist_pos = np.array(wrist_pos)
    
    # === 4. إحصائيات قوية (Median + IQR) ===
    def robust_stats(arr):
        return {
            'median': float(np.median(arr)),
            'mean': float(np.mean(arr)),
            'p25': float(np.percentile(arr, 25)),
            'p75': float(np.percentile(arr, 75)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'std': float(np.std(arr))
        }
    
    trunk_stats = robust_stats(trunk)
    shoulder_stats = robust_stats(shoulder)
    elbow_stats = robust_stats(elbow)
    
    # === 5. سلاسة المسار ===
    smoothness = compute_path_smoothness(wrist_pos)
    
    # === 6. درجة التعويض ===
    compensation = min(trunk_stats['max'] / TRUNK_COMPENSATION_LIMIT, 1.0)
    
    # === 7. مؤشر الجودة الشامل (ثابت) ===
    trunk_score = max(0.0, (TRUNK_COMPENSATION_LIMIT - trunk_stats['median']) / TRUNK_COMPENSATION_LIMIT)
    shoulder_score = min(shoulder_stats['max'] / 180.0, 1.0)
    elbow_score = min(elbow_stats['median'] / 180.0, 1.0)
    
    quality_index = (
        trunk_score * QUALITY_WEIGHTS['trunk'] +
        shoulder_score * QUALITY_WEIGHTS['shoulder'] +
        elbow_score * QUALITY_WEIGHTS['elbow'] +
        smoothness * QUALITY_WEIGHTS['smoothness']
    )
    
    # === 8. تقرير جودة البيانات ===
    data_quality = {
        'total_frames': len(df),
        'used_frames': len(reach_df),
        'reach_phase_frames': len(reach_df),
        'avg_visibility_shoulder': float(df['LEFT_SHOULDER_VISIBILITY'].mean()) if 'LEFT_SHOULDER_VISIBILITY' in df.columns else 1.0,
        'percent_good_frames': float((df.get('LEFT_SHOULDER_VISIBILITY', pd.Series([1]*len(df))) >= min_visibility).mean() * 100),
    }
    
    # === 9. النتيجة النهائية (موحدة دائماً) ===
    result = {
        'name': name,
        'data_quality': data_quality,
        
        # === المقاييس الرئيسية (استخدم هذه دائماً) ===
        'trunk_flexion_median': round(trunk_stats['median'], 2),
        'trunk_flexion_max': round(trunk_stats['max'], 2),
        'trunk_flexion_iqr': round(trunk_stats['p75'] - trunk_stats['p25'], 2),
        
        'shoulder_elevation_max': round(shoulder_stats['max'], 2),
        'elbow_extension_median': round(elbow_stats['median'], 2),
        'elbow_extension_max': round(elbow_stats['max'], 2),
        
        'smoothness_score': round(smoothness, 3),
        'compensation_score': round(compensation, 3),
        'reach_quality_index': round(quality_index, 3),
        
        # إضافي للمقارنة
        'trunk_flexion_mean': round(trunk_stats['mean'], 2),
        'elbow_extension_mean': round(elbow_stats['mean'], 2),
    }
    
    return result

def compare_videos(csv_paths: list, names: list = None) -> pd.DataFrame:
    """
    مقارنة موحدة بين عدة فيديوهات (تعطي جدول متسق دائماً).
    """
    if names is None:
        names = [f"Video_{i}" for i in range(len(csv_paths))]
    
    results = []
    for path, name in zip(csv_paths, names):
        res = analyze_reach_csv(path, name=name)
        results.append(res)
    
    # تحويل إلى DataFrame جميل
    rows = []
    for r in results:
        if 'error' in r:
            continue
        row = {
            'Name': r['name'],
            'Frames': r['data_quality']['used_frames'],
            'Trunk_Median': r['trunk_flexion_median'],
            'Trunk_Max': r['trunk_flexion_max'],
            'Trunk_IQR': r['trunk_flexion_iqr'],
            'Shoulder_Max': r['shoulder_elevation_max'],
            'Elbow_Median': r['elbow_extension_median'],
            'Smoothness': r['smoothness_score'],
            'Compensation': r['compensation_score'],
            'Quality_Index': r['reach_quality_index'],
            'Data_Quality_%': round(r['data_quality']['percent_good_frames'], 1)
        }
        rows.append(row)
    
    return pd.DataFrame(rows)

# ==================== مثال استخدام ====================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        name = sys.argv[2] if len(sys.argv) > 2 else "TEST"
        result = analyze_reach_csv(csv_file, name=name)
        print("\n" + "="*70)
        print(f"نتيجة التحليل الموحد: {name}")
        print("="*70)
        for k, v in result.items():
            if k != 'data_quality':
                print(f"{k:25}: {v}")
        print("="*70)
    else:
        print("استخدام: python robust_reach_analysis.py file.csv [اسم]")
        print("أو استخدم الدالة analyze_reach_csv() في كودك")