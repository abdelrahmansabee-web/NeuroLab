"""Quick test: MediaPipe world vs image elbow angles on kurusal healthy."""
import sys
sys.path.insert(0, r"D:\Thesis app\NeuroLab\R an")
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from extract_pose_csv_robust import get_pose_landmarker, preprocess_frame, LANDMARK_NAMES

VIDEO = r"d:\Thesis app\participants\kurusal\reaching\healthy side.mp4"


def angle_3pts(a, b, c):
    v1 = a - b
    v2 = c - b
    m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if m1 < 1e-9 or m2 < 1e-9:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (m1 * m2), -1, 1))))


def lm_xyz(lm):
    return np.array([lm.x, lm.y, lm.z], dtype=float)


def lm_norm(lm, w, h):
    return np.array([lm.x * w, lm.y * h, lm.z * w], dtype=float)


cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
det = get_pose_landmarker(None)

world_angles = {"left": [], "right": []}
image_angles = {"left": [], "right": []}
frame_i = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    if frame_i < 170 or frame_i > 220:
        frame_i += 1
        continue
    rgb = preprocess_frame(frame, use_clahe=True)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res = det.detect_for_video(mp_img, int(frame_i * 1000 / fps))
    if res.pose_world_landmarks and res.pose_landmarks:
        wl = res.pose_world_landmarks[0]
        il = res.pose_landmarks[0]
        idx = {n: i for i, n in enumerate(LANDMARK_NAMES)}
        for side in ["LEFT", "RIGHT"]:
            s, e, wri = idx[f"{side}_SHOULDER"], idx[f"{side}_ELBOW"], idx[f"{side}_WRIST"]
            world_angles[side.lower()].append(angle_3pts(lm_xyz(wl[s]), lm_xyz(wl[e]), lm_xyz(wl[wri])))
            image_angles[side.lower()].append(
                angle_3pts(lm_norm(il[s], w, h), lm_norm(il[e], w, h), lm_norm(il[wri], w, h))
            )
    frame_i += 1

cap.release()
det.close()

for side in ["left", "right"]:
    w_a = np.array(world_angles[side])
    i_a = np.array(image_angles[side])
    print(
        f"{side:5s} WORLD mean={np.nanmean(w_a):.1f} range={np.nanmin(w_a):.1f}-{np.nanmax(w_a):.1f} | "
        f"IMAGE mean={np.nanmean(i_a):.1f} range={np.nanmin(i_a):.1f}-{np.nanmax(i_a):.1f}"
    )
