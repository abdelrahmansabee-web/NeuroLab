#!/usr/bin/env python3
"""
أداة سريعة لتقييم جودة ملف CSV بعد الاستخراج
تساعدك تعرف إذا كان الاستخراج جيد أم فيه مشاكل
"""
import pandas as pd
import numpy as np
from pathlib import Path

IMPORTANT_LANDMARKS = ['LEFT_SHOULDER', 'LEFT_HIP', 'LEFT_ELBOW', 'LEFT_WRIST']

def validate_csv(csv_path: str):
    df = pd.read_csv(csv_path)
    print(f"\n📊 تقييم جودة: {Path(csv_path).name}")
    print(f"   عدد الإطارات: {len(df)}")

    # 1. Visibility analysis
    print("\n1. متوسط الـ Visibility للنقاط المهمة:")
    for lm in IMPORTANT_LANDMARKS:
        col = f"{lm}_VISIBILITY"
        if col in df.columns:
            avg = df[col].mean()
            good = (df[col] > 0.6).mean() * 100
            status = "✅ جيد" if avg > 0.65 else ("⚠️ متوسط" if avg > 0.45 else "❌ ضعيف")
            print(f"   {lm:15} : avg={avg:.3f}   |   >0.6 = {good:.1f}%   {status}")

    # 2. Missing data after interpolation
    print("\n2. نسبة القيم المفقودة (NaN) بعد الاستيفاء:")
    for lm in IMPORTANT_LANDMARKS:
        for axis in ['_X', '_Y']:
            col = f"{lm}{axis}"
            if col in df.columns:
                nan_pct = df[col].isna().mean() * 100
                if nan_pct > 5:
                    print(f"   {col:18} : {nan_pct:.1f}% NaN  ← مشكلة")

    # 3. Range check (should be roughly 0-1 for normalized)
    print("\n3. نطاق القيم (يجب أن يكون قريب من 0-1):")
    for lm in ['LEFT_SHOULDER', 'LEFT_HIP']:
        for axis in ['_X', '_Y']:
            col = f"{lm}{axis}"
            if col in df.columns:
                mn, mx = df[col].min(), df[col].max()
                print(f"   {col:18} : [{mn:.3f}, {mx:.3f}]")

    # 4. Motion range (Wrist travel)
    if 'LEFT_WRIST_X' in df.columns and 'LEFT_WRIST_Y' in df.columns:
        wx = df['LEFT_WRIST_X']
        wy = df['LEFT_WRIST_Y']
        disp = np.sqrt( (wx.iloc[-1] - wx.iloc[0])**2 + (wy.iloc[-1] - wy.iloc[0])**2 )
        print(f"\n4. مسافة حركة اليد المباشرة: {disp:.3f} (أكبر = حركة أوضح)")

    print("\n" + "="*60)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python validate_csv_quality.py file.csv")
    else:
        validate_csv(sys.argv[1])