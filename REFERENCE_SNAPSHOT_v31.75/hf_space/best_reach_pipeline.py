#!/usr/bin/env python3
"""
================================================================================
BEST REACH ANALYSIS PIPELINE (الأفضل والأكثر موثوقية)
================================================================================
يجمع بين:
1. استخراج CSV بأعلى جودة ممكنة (robust extraction)
2. تحليل موحد ومظبوط 100% (robust analysis)

استخدم هذا السكريبت دائماً للحصول على نتائج متسقة.

أمثلة:
    python best_reach_pipeline.py pre.mp4 --name PRE
    python best_reach_pipeline.py post.mp4 --name POST --output post_robust.csv
    python best_reach_pipeline.py baseline.mp4 --name BASELINE --no-extract  # لو عندك CSV جاهز
"""

import sys
from pathlib import Path
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# استيراد الوحدات التي أنشأناها
try:
    from extract_pose_csv_robust import extract_pose_to_csv
    from robust_reach_analysis import analyze_reach_csv
except ImportError:
    print("❌ تأكد أن الملفات التالية موجودة في نفس المجلد:")
    print("   - extract_pose_csv_robust.py")
    print("   - robust_reach_analysis.py")
    sys.exit(1)

def run_full_pipeline(video_path: str, name: str = "UNKNOWN", 
                      output_csv: str = None,
                      force_reextract: bool = False) -> dict:
    """
    الـ pipeline الكامل: استخراج + تحليل
    """
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"❌ الفيديو غير موجود: {video_path}")
        return {"error": "video not found"}

    if output_csv is None:
        output_csv = video_path.stem + "_robust.csv"

    output_csv = Path(output_csv)

    # === الخطوة 1: استخراج (إلا لو المستخدم طلب تخطي) ===
    if force_reextract or not output_csv.exists():
        print(f"\n🔄 استخراج CSV بأعلى جودة...")
        report = extract_pose_to_csv(
            video_path=str(video_path),
            output_csv=str(output_csv),
            use_clahe=True,
            smooth=True,
            max_interpolate_gap=8,
            show_progress=True
        )
        print(f"✅ تم الحفظ: {output_csv}")
    else:
        print(f"📁 استخدام ملف CSV موجود: {output_csv}")

    # === الخطوة 2: التحليل الموحد ===
    print(f"\n📊 تشغيل التحليل الموحد والمظبوط...")
    result = analyze_reach_csv(str(output_csv), name=name)

    # === عرض النتائج بشكل جميل ===
    print("\n" + "="*75)
    print(f"✅ نتائج التحليل الموحد - {name}")
    print("="*75)

    print(f"\n📌 المقاييس الأساسية (استخدم هذه دائماً):")
    print(f"   Trunk Flexion (Median)   : {result['trunk_flexion_median']:6.2f}°   ← الأهم")
    print(f"   Trunk Flexion (Max)      : {result['trunk_flexion_max']:6.2f}°")
    print(f"   Trunk Flexion (IQR)      : {result['trunk_flexion_iqr']:6.2f}°   (استقرار)")
    print(f"   Elbow Extension (Median) : {result['elbow_extension_median']:6.2f}°")
    print(f"   Shoulder Elevation (Max) : {result['shoulder_elevation_max']:6.2f}°")
    print(f"   Smoothness               : {result['smoothness_score']:.3f}")
    print(f"   Compensation             : {result['compensation_score']:.3f}")
    print(f"   Reach Quality Index      : {result['reach_quality_index']:.3f}")

    print(f"\n📈 جودة البيانات:")
    dq = result['data_quality']
    print(f"   إطارات مستخدمة          : {dq['used_frames']} / {dq['total_frames']}")
    print(f"   متوسط Visibility (كتف)   : {dq['avg_visibility_shoulder']:.3f}")
    print(f"   نسبة الإطارات الجيدة     : {dq['percent_good_frames']:.1f}%")

    print("\n" + "="*75)
    print("💡 التوصية: استخدم دائماً 'trunk_flexion_median' + 'elbow_extension_median'")
    print("="*75)

    return result

def main():
    parser = argparse.ArgumentParser(
        description="أفضل pipeline لاستخراج + تحليل Cross-Body Reach (موحد 100%)"
    )
    parser.add_argument("video", help="مسار الفيديو")
    parser.add_argument("--name", "-n", default="UNKNOWN", help="اسم الحالة (PRE / POST / BASELINE)")
    parser.add_argument("--output", "-o", default=None, help="اسم ملف CSV الناتج")
    parser.add_argument("--no-extract", action="store_true", 
                        help="تخطي الاستخراج واستخدام CSV موجود (يجب أن يكون --output موجود)")
    parser.add_argument("--csv", help="استخدام CSV جاهز مباشرة (يتخطى الاستخراج)")

    args = parser.parse_args()

    if args.csv:
        # استخدام CSV مباشرة
        result = analyze_reach_csv(args.csv, name=args.name)
        print("\n" + "="*75)
        print(f"✅ نتائج التحليل الموحد من CSV - {args.name}")
        print("="*75)
        print(f"Trunk Median : {result['trunk_flexion_median']:.2f}°")
        print(f"Elbow Median : {result['elbow_extension_median']:.2f}°")
        print(f"Quality Index: {result['reach_quality_index']:.3f}")
    else:
        run_full_pipeline(
            video_path=args.video,
            name=args.name,
            output_csv=args.output,
            force_reextract=not args.no_extract
        )

if __name__ == "__main__":
    main()