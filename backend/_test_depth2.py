"""Step 2: Map MediaPipe landmarks to metric depth → get shoulder width in meters.
Uses re-upload to get fresh pose landmarks CSV."""
import cv2, torch, numpy as np
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
from pathlib import Path
import mediapipe as mp

VID = Path(r"D:\Thesis app\participants\mediapipe\movs\zeyneb\baseline.MOV")
assert VID.exists()

# ── Load ZoeDepth ──
print("Loading ZoeDepth...")
proc = AutoImageProcessor.from_pretrained("Intel/zoedepth-nyu")
model = AutoModelForDepthEstimation.from_pretrained("Intel/zoedepth-nyu")
model.eval()

# ── Load MediaPipe Pose ──
print("Loading MediaPipe Pose...")
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=2,
    enable_segmentation=False,
    min_detection_confidence=0.5,
)

# ── Grab frame ~50 (full body visible) ──
cap = cv2.VideoCapture(str(VID))
cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
ret, frame = cap.read()
cap.release(); assert ret
H, W = frame.shape[:2]
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(rgb)

# ── Run MediaPipe ──
results = pose.process(rgb)
pose.close()

if not results.pose_landmarks:
    print("ERROR: No pose detected!")
    exit()

lm = results.pose_landmarks.landmark
# MediaPipe landmarks: 11=left_shoulder, 12=right_shoulder
h, w = frame.shape[:2]
def lm_px(idx):
    return lm[idx].x * w, lm[idx].y * h

ls_x, ls_y = lm_px(11)  # left_shoulder
rs_x, rs_y = lm_px(12)  # right_shoulder
nose_x, nose_y = lm_px(0)
print(f"Nose:           ({nose_x:.0f}, {nose_y:.0f})")
print(f"Left shoulder:  ({ls_x:.0f}, {ls_y:.0f})")
print(f"Right shoulder: ({rs_x:.0f}, {rs_y:.0f})")

# ── Run ZoeDepth ──
inputs = proc(pil_img, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
pp = proc.post_process_depth_estimation(outputs, source_sizes=[(pil_img.height, pil_img.width)])
depth = pp[0]["predicted_depth"].numpy()

def depth_at(x, y):
    ix, iy = int(round(x)), int(round(y))
    ix = max(0, min(depth.shape[1]-1, ix))
    iy = max(0, min(depth.shape[0]-1, iy))
    return float(depth[iy, ix])

d_rs = depth_at(rs_x, rs_y)
d_ls = depth_at(ls_x, ls_y)
print(f"\nRight shoulder depth: {d_rs:.3f} m")
print(f"Left shoulder depth:  {d_ls:.3f} m")
print(f"Nose depth:           {depth_at(nose_x, nose_y):.3f} m")
print(f"Depth range all:      {depth.min():.3f} – {depth.max():.3f} m")

# ── Approximate camera intrinsics (65° HFOV) ──
import numpy as np
hfov = 65
fx = W / (2 * np.tan(np.radians(hfov/2)))
fy = fx
cx, cy = W/2, H/2

def pixel_to_3d(x, y, d):
    return np.array([(x - cx) * d / fx, (y - cy) * d / fy, d])

p_rs = pixel_to_3d(rs_x, rs_y, d_rs)
p_ls = pixel_to_3d(ls_x, ls_y, d_ls)
shoulder_width_m = float(np.linalg.norm(p_rs - p_ls))

print(f"\nRight shoulder 3D: ({p_rs[0]:.3f}, {p_rs[1]:.3f}, {p_rs[2]:.3f})")
print(f"Left shoulder 3D:  ({p_ls[0]:.3f}, {p_ls[1]:.3f}, {p_ls[2]:.3f})")
print(f"Shoulder width:    {shoulder_width_m:.3f} m = {shoulder_width_m*100:.1f} cm")

