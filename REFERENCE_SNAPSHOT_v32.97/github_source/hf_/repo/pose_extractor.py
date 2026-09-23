import cv2
import csv
import os
import numpy as np
import mediapipe as mp
from pathlib import Path
import traceback

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10)
]

# MediaPipe Pose landmark index → readable name
LANDMARK_NAMES = {
    0: "NOSE",
    1: "LEFT_EYE_INNER", 2: "LEFT_EYE", 3: "LEFT_EYE_OUTER",
    4: "RIGHT_EYE_INNER", 5: "RIGHT_EYE", 6: "RIGHT_EYE_OUTER",
    7: "LEFT_EAR", 8: "RIGHT_EAR",
    9: "MOUTH_LEFT", 10: "MOUTH_RIGHT",
    11: "LEFT_SHOULDER", 12: "RIGHT_SHOULDER",
    13: "LEFT_ELBOW", 14: "RIGHT_ELBOW",
    15: "LEFT_WRIST", 16: "RIGHT_WRIST",
    17: "LEFT_PINKY", 18: "RIGHT_PINKY",
    19: "LEFT_INDEX", 20: "RIGHT_INDEX",
    21: "LEFT_THUMB", 22: "RIGHT_THUMB",
    23: "LEFT_HIP", 24: "RIGHT_HIP",
    25: "LEFT_KNEE", 26: "RIGHT_KNEE",
    27: "LEFT_ANKLE", 28: "RIGHT_ANKLE",
    29: "LEFT_HEEL", 30: "RIGHT_HEEL",
    31: "LEFT_FOOT_INDEX", 32: "RIGHT_FOOT_INDEX",
}


def draw_skeleton(image, landmarks, width, height):
    points = []
    for lm in landmarks:
        x = int(lm.x * width)
        y = int(lm.y * height)
        points.append((x, y))

    for connection in POSE_CONNECTIONS:
        start_idx, end_idx = connection
        if start_idx < len(points) and end_idx < len(points):
            cv2.line(image, points[start_idx], points[end_idx], (0, 255, 0), 2)

    for point in points:
        cv2.circle(image, point, 4, (0, 0, 255), -1)

    return image


def extract_pose_from_video(video_path, output_dir, base_name, model_dir):
    try:
        output_dir = Path(output_dir)
        model_path = Path(model_dir) / 'pose_landmarker_heavy.task'

        if not model_path.exists():
            return {"success": False, "error": f"Model not found at {model_path}"}

        # MediaPipe C++ on Windows has a known bug resolving absolute file paths.
        # Load the model into memory and pass it as a buffer to bypass path handling.
        src = Path(model_dir) / 'pose_landmarker_heavy.task'
        if not src.exists():
            return {"success": False, "error": f"Model not found at {src}"}
        with open(str(src), 'rb') as f:
            model_buffer = f.read()
        base_options = mp.tasks.BaseOptions(model_asset_buffer=model_buffer, delegate=mp.tasks.BaseOptions.Delegate.CPU)

        csv_path = output_dir / f"{base_name}.csv"
        trc_path = output_dir / f"{base_name}.trc"
        video_2d_path = output_dir / f"{base_name}_2d.mp4"

        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarker = mp.tasks.vision.PoseLandmarker
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=VisionRunningMode.IMAGE
        )

        with PoseLandmarker.create_from_options(options) as landmarker:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"success": False, "error": "Cannot open video file"}

            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

            landmarks_all = []
            frames_detected = 0
            prev_smooth = None
            width = height = 0
            out_2d = None

            print(f"Detecting landmarks in {total_frames} frames...")

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                h, w = frame.shape[:2]
                if w > h:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                    h, w = w, h
                if out_2d is None:
                    width, height = w, h
                    out_2d = cv2.VideoWriter(str(video_2d_path), fourcc, fps, (w, h))

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                detection_result = landmarker.detect(mp_image)

                if detection_result.pose_landmarks:
                    frames_detected += 1
                    landmarks = detection_result.pose_landmarks[0]
                    raw = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)

                    if prev_smooth is None:
                        prev_smooth = raw.copy()
                    else:
                        alpha = 0.65
                        prev_smooth = alpha * prev_smooth + (1.0 - alpha) * raw

                    row = prev_smooth.flatten().tolist()
                    landmarks_all.append(row)

                    points = []
                    for i in range(33):
                        x = int(prev_smooth[i, 0] * width)
                        y = int(prev_smooth[i, 1] * height)
                        points.append((x, y))
                    for connection in POSE_CONNECTIONS:
                        s, e = connection
                        if s < len(points) and e < len(points):
                            cv2.line(frame, points[s], points[e], (0, 255, 0), 2)
                    for p in points:
                        cv2.circle(frame, p, 4, (0, 0, 255), -1)
                else:
                    landmarks_all.append([np.nan] * 99)

                out_2d.write(frame)

            cap.release()
            if out_2d is not None:
                out_2d.release()

            print(f"Detected pose in {frames_detected}/{total_frames} frames")

            if len(landmarks_all) == 0:
                return {"success": False, "error": "No frames were processed"}

            header = ["frame", "time"]
            for i in range(33):
                name = LANDMARK_NAMES[i]
                header.extend([f"{name}_X", f"{name}_Y", f"{name}_Z"])

            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for idx, row in enumerate(landmarks_all):
                    t = idx / fps
                    writer.writerow([idx + 1, round(t, 5)] + [round(v, 6) if not np.isnan(v) else "" for v in row])

            num_frames = len(landmarks_all)
            with open(trc_path, "w") as f:
                f.write("PathFileType\t4\t(X/Y/Z)\t" + trc_path.name + "\n")
                f.write("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n")
                f.write(f"{fps}\t{fps}\t{num_frames}\t33\tm\t{fps}\t1\t{num_frames}\n")
                f.write("Frame#\tTime\t" + "\t".join([f"{LANDMARK_NAMES[i]}" for i in range(33)]) + "\n")
                f.write("\t\t" + "\t".join([f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(33)]) + "\n")
                for i, row in enumerate(landmarks_all):
                    t = i / fps
                    line = f"{i+1}\t{t:.5f}\t"
                    line += "\t".join([f"{v:.5f}" if not np.isnan(v) else "0" for v in row])
                    f.write(line + "\n")

            print("Files saved: CSV, TRC, 2D video")

            return {
                "success": True,
                "csv_path": str(csv_path),
                "trc_path": str(trc_path),
                "video_2d_path": str(video_2d_path),
                "video_3d_path": str(video_2d_path),
                "frames_detected": frames_detected,
                "total_frames": total_frames,
                "fps": fps,
            }

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}