"""Unit test: depth_estimator standalone."""
from depth_estimator import estimate_shoulder_width_m

sw = estimate_shoulder_width_m(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline.MOV")
print(f"\nResult: shoulder_width = {sw:.4f} m = {sw*100:.1f} cm")
