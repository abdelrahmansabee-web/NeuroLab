"""Metric scale estimator via ZoeDepth.

Computes shoulder_width (in meters) from the first video frame where
MediaPipe detects both shoulders, using monocular metric depth from ZoeDepth.
The result can be used to convert normalized kinematic values to cm.
"""
import cv2
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Lazy-loaded globals
_proc = None
_model = None
_pose_landmarker = None

def _load_model():
    global _proc, _model
    if _model is not None:
        return
    print("[depth] Loading ZoeDepth (first call only)...")
    _proc = AutoImageProcessor.from_pretrained("Intel/zoedepth-nyu")
    _model = AutoModelForDepthEstimation.from_pretrained("Intel/zoedepth-nyu")
    _model.eval()

def _load_pose_landmarker(model_dir):
    global _pose_landmarker
    if _pose_landmarker is not None:
        return
    print("[depth] Loading PoseLandmarker (Tasks API)...")
    model_path = Path(model_dir) / "pose_landmarker_heavy.task"
    if not model_path.exists():
        raise FileNotFoundError(f"Pose model not found at {model_path}")
    with open(str(model_path), "rb") as f:
        model_buffer = f.read()
    base_options = python.BaseOptions(model_asset_buffer=model_buffer, delegate=python.BaseOptions.Delegate.CPU)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE
    )
    _pose_landmarker = vision.PoseLandmarker.create_from_options(options)

def estimate_shoulder_width_m(video_path: str, model_dir: str = None, hfov_deg: float = 65.0) -> float:
    """
    Returns shoulder width in meters, or 0.0 if estimation fails.
    Uses MediaPipe Pose via Tasks API to locate shoulders, ZoeDepth for metric depth.
    """
    _load_model()
    if model_dir is None:
        model_dir = str(Path(__file__).resolve().parent / "models")
    _load_pose_landmarker(model_dir)
    mp_image_format = mp.ImageFormat.SRGB

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    result = 0.0
    for pct in [0.10, 0.25, 0.40, 0.55, 0.70, 0.85]:
        fid = int(total * pct)
        print(f"[depth] trying frame {fid}/{total} ({pct*100:.0f}%)")
        cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
        ret, frame = cap.read()
        if not ret:
            print(f"[depth]  frame {fid}: read failed")
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp_image_format, data=rgb)
        detection = _pose_landmarker.detect(mp_image)

        if not detection.pose_landmarks:
            print(f"[depth]  frame {fid}: no pose")
            continue

        lm = detection.pose_landmarks[0]
        ls = lm[11]; rs = lm[12]

        if ls.visibility < 0.5 or rs.visibility < 0.5:
            print(f"[depth]  frame {fid}: shoulder visibility {ls.visibility:.2f}/{rs.visibility:.2f}")
            continue
        w, h = float(width), float(height)
        ls_x, ls_y = ls.x * w, ls.y * h
        rs_x, rs_y = rs.x * w, rs.y * h
        if not (0 < ls_x < w and 0 < ls_y < h and 0 < rs_x < w and 0 < rs_y < h):
            print(f"[depth]  frame {fid}: shoulders outside frame")
            continue

        print(f"[depth]  frame {fid}: running ZoeDepth...")
        pil_img = Image.fromarray(rgb)
        inputs = _proc(pil_img, return_tensors="pt")
        with torch.no_grad():
            outputs = _model(**inputs)
        pp = _proc.post_process_depth_estimation(
            outputs, source_sizes=[(pil_img.height, pil_img.width)]
        )
        depth = pp[0]["predicted_depth"].numpy()

        def _d(x, y):
            ix = max(0, min(depth.shape[1]-1, int(round(x))))
            iy = max(0, min(depth.shape[0]-1, int(round(y))))
            return float(depth[iy, ix])

        d_ls = _d(ls_x, ls_y)
        d_rs = _d(rs_x, rs_y)
        print(f"[depth]  depth ls={d_ls:.3f}m rs={d_rs:.3f}m")

        if d_ls < 0.3 or d_rs < 0.3 or d_ls > 10 or d_rs > 10:
            print(f"[depth]  depth out of range, skipping")
            continue

        fx = w / (2 * np.tan(np.radians(hfov_deg / 2)))
        fy = fx
        cx, cy = w / 2, h / 2

        def _3d(x, y, d):
            return np.array([(x - cx) * d / fx, (y - cy) * d / fy, d])

        p_ls = _3d(ls_x, ls_y, d_ls)
        p_rs = _3d(rs_x, rs_y, d_rs)
        sw = float(np.linalg.norm(p_ls - p_rs))
        print(f"[depth]  shoulder width = {sw:.3f}m")

        if 0.25 < sw < 0.80:
            result = sw
            print(f"[depth] shoulder_width={sw:.3f}m at frame {fid}")
            break

    cap.release()

    if result == 0.0:
        print("[depth] WARNING: could not estimate shoulder width, falling back to 0.0")
    return result
