"""Metric scale estimator via ZoeDepth.

Computes shoulder_width (in meters) from the first video frame where
MediaPipe detects both shoulders, using monocular metric depth from ZoeDepth.
The result can be used to convert normalized kinematic values to cm.
"""
import cv2
import torch
import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
import mediapipe as mp

# Lazy-loaded globals
_proc = None
_model = None

def _load_model():
    global _proc, _model
    if _model is not None:
        return
    print("[depth] Loading ZoeDepth (first call only)...")
    _proc = AutoImageProcessor.from_pretrained("Intel/zoedepth-nyu")
    _model = AutoModelForDepthEstimation.from_pretrained("Intel/zoedepth-nyu")
    _model.eval()

def estimate_shoulder_width_m(video_path: str, hfov_deg: float = 65.0) -> float:
    """
    Returns shoulder width in meters, or 0.0 if estimation fails.
    Uses MediaPipe Pose to locate shoulders, ZoeDepth for metric depth.
    """
    _load_model()
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        min_detection_confidence=0.5,
    )

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Try frames at 10% intervals until we find both shoulders
    result = 0.0
    for pct in [0.10, 0.25, 0.40, 0.55, 0.70, 0.85]:
        fid = int(total * pct)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
        ret, frame = cap.read()
        if not ret:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks = pose.process(rgb)

        if not landmarks or not landmarks.pose_landmarks:
            continue

        lm = landmarks.pose_landmarks.landmark
        ls = lm[11]; rs = lm[12]

        # Require reasonable visibility
        if ls.visibility < 0.5 or rs.visibility < 0.5:
            continue
        # Require landmarks to be inside frame
        w, h = float(width), float(height)
        ls_x, ls_y = ls.x * w, ls.y * h
        rs_x, rs_y = rs.x * w, rs.y * h
        if not (0 < ls_x < w and 0 < ls_y < h and 0 < rs_x < w and 0 < rs_y < h):
            continue

        # ── Run ZoeDepth depth map ──
        pil_img = Image.fromarray(rgb)
        inputs = _proc(pil_img, return_tensors="pt")
        with torch.no_grad():  # noqa: F821
            outputs = _model(**inputs)
        pp = _proc.post_process_depth_estimation(
            outputs, source_sizes=[(pil_img.height, pil_img.width)]
        )
        depth = pp[0]["predicted_depth"].numpy()

        # Depth at shoulder pixels
        def _d(x, y):
            ix = max(0, min(depth.shape[1]-1, int(round(x))))
            iy = max(0, min(depth.shape[0]-1, int(round(y))))
            return float(depth[iy, ix])

        d_ls = _d(ls_x, ls_y)
        d_rs = _d(rs_x, rs_y)

        if d_ls < 0.3 or d_rs < 0.3 or d_ls > 10 or d_rs > 10:
            continue  # unreasonable depth

        # ── Approximate camera intrinsics ──
        fx = w / (2 * np.tan(np.radians(hfov_deg / 2)))
        fy = fx
        cx, cy = w / 2, h / 2

        def _3d(x, y, d):
            return np.array([(x - cx) * d / fx, (y - cy) * d / fy, d])

        p_ls = _3d(ls_x, ls_y, d_ls)
        p_rs = _3d(rs_x, rs_y, d_rs)
        sw = float(np.linalg.norm(p_ls - p_rs))

        if 0.25 < sw < 0.80:  # plausible shoulder width (25-80 cm)
            result = sw
            print(f"[depth] shoulder_width={sw:.3f}m at frame {fid}")
            break

    cap.release()
    pose.close()

    if result == 0.0:
        print("[depth] WARNING: could not estimate shoulder width, falling back to 0.0")
    return result
