"""
Stroke Kinematics AI Engine v7.0 - Final Production Backend
============================================================
FastAPI backend for video-based kinematic analysis of stroke rehabilitation.
Uses MediaPipe Pose for landmark extraction and computes 14 biomechanical variables.
"""

import os
import time
import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from scipy.signal import butter, filtfilt, find_peaks
import mediapipe as mp

# ─── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Stroke Kinematics AI Engine",
    version="7.0",
    description="Video-based kinematic analysis for stroke rehabilitation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "static_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=OUTPUT_DIR), name="static")

# ─── Constants ───────────────────────────────────────────────────────────────

LANDMARKS_DICT = {
    0: 'Nose', 1: 'L_Eye_Inner', 2: 'L_Eye', 3: 'L_Eye_Outer',
    4: 'R_Eye_Inner', 5: 'R_Eye', 6: 'R_Eye_Outer',
    7: 'L_Ear', 8: 'R_Ear', 9: 'Mouth_L', 10: 'Mouth_R',
    11: 'L_Shoulder', 12: 'R_Shoulder', 13: 'L_Elbow',
    14: 'R_Elbow', 15: 'L_Wrist', 16: 'R_Wrist',
    17: 'L_Pinky', 18: 'R_Pinky', 19: 'L_Index', 20: 'R_Index',
    21: 'L_Thumb', 22: 'R_Thumb', 23: 'L_Hip', 24: 'R_Hip',
    25: 'L_Knee', 26: 'R_Knee', 27: 'L_Ankle', 28: 'R_Ankle',
    29: 'L_Heel', 30: 'R_Heel', 31: 'L_Foot_Index', 32: 'R_Foot_Index'
}

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (15, 17), (15, 19), (15, 21), (16, 18), (16, 20), (16, 22),
    (17, 19), (18, 20)
]

# ─── Signal Processing Utilities ─────────────────────────────────────────────

def butter_lowpass(data: np.ndarray, cutoff: float = 3.0, fs: float = 30.0, order: int = 4) -> np.ndarray:
    """Apply zero-phase Butterworth low-pass filter."""
    if len(data) < (order * 3 + 1):
        return data
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    if normal_cutoff >= 1.0:
        normal_cutoff = 0.99
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)


def compute_sparc(speed_profile: np.ndarray, fs: float, padlevel: int = 4, fc: float = 10.0, amp_th: float = 0.05) -> float:
    """
    Compute SPARC (Spectral Arc Length) smoothness metric.
    More negative = less smooth. Closer to 0 = smoother movement.
    """
    speed_profile = np.array(speed_profile, dtype=float)
    if len(speed_profile) < 4 or np.max(np.abs(speed_profile)) == 0:
        return 0.0

    speed_profile = speed_profile / np.max(np.abs(speed_profile))
    N = len(speed_profile)
    nfft = int(pow(2, np.ceil(np.log2(N)) + padlevel))
    V = np.fft.fft(speed_profile, nfft)
    V_mag = np.abs(V)[:nfft // 2]
    f = np.arange(0, nfft // 2) * (fs / nfft)

    fc_idx = np.where(f <= fc)[0]
    if len(fc_idx) == 0:
        return 0.0
    f = f[fc_idx]
    V_mag = V_mag[fc_idx]

    max_v = np.max(V_mag)
    if max_v == 0:
        return 0.0
    V_mag = V_mag / max_v

    indices = np.where(V_mag >= amp_th)[0]
    fc_val = max(f[indices[-1]], 0.25) if len(indices) > 0 else f[-1]

    cutoff_idx = np.where(f <= fc_val)[0]
    if len(cutoff_idx) < 2:
        return 0.0
    f = f[cutoff_idx]
    V_mag = V_mag[cutoff_idx]

    df_f = f[1] - f[0]
    if df_f == 0:
        return 0.0
    dV = np.diff(V_mag) / df_f

    return float(-np.sum(np.sqrt((1.0 / fc_val) ** 2 + dV ** 2) * df_f))


def calc_elbow_angle(row: pd.Series, side: str) -> float:
    """Calculate 3D elbow angle from shoulder-elbow-wrist landmarks."""
    ba = np.array([
        row[f'{side}_Shoulder_X'] - row[f'{side}_Elbow_X'],
        row[f'{side}_Shoulder_Y'] - row[f'{side}_Elbow_Y'],
        row[f'{side}_Shoulder_Z'] - row[f'{side}_Elbow_Z']
    ])
    bc = np.array([
        row[f'{side}_Wrist_X'] - row[f'{side}_Elbow_X'],
        row[f'{side}_Wrist_Y'] - row[f'{side}_Elbow_Y'],
        row[f'{side}_Wrist_Z'] - row[f'{side}_Elbow_Z']
    ])
    norm_product = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6
    cos_angle = np.clip(np.dot(ba, bc) / norm_product, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


# ─── Auto-Segmentation ──────────────────────────────────────────────────────

def auto_segment(speed_3d: np.ndarray, fps: int, total_frames: int):
    """
    Automatically segment movement into onset, reaching, wiping, and return phases.
    Returns (onset, reach_end, wipe_end, return_end) frame indices.
    """
    peak_speed = np.max(speed_3d)
    if peak_speed == 0:
        n = total_frames
        return 10, int(n * 0.35), int(n * 0.75), n - 5

    # Onset: first frame where speed exceeds 5% of peak
    onset_idx = np.where(speed_3d > peak_speed * 0.05)[0]
    onset = int(onset_idx[0]) if len(onset_idx) > 0 else 10

    # Find speed valleys for phase transitions
    min_gap = max(int(0.3 * fps), 3)
    valleys = []
    for i in range(1, len(speed_3d) - 1):
        if (speed_3d[i] < speed_3d[i - 1] and
            speed_3d[i] < speed_3d[i + 1] and
            speed_3d[i] < peak_speed * 0.5):
            if i > onset and (len(valleys) == 0 or i - valleys[-1] > min_gap):
                valleys.append(i)

    reach_end = valleys[0] if len(valleys) > 0 else int(total_frames * 0.35)
    wipe_end = valleys[-1] if len(valleys) > 1 else int(total_frames * 0.75)
    return_end = total_frames - 5

    # Sanity checks
    if wipe_end <= reach_end:
        wipe_end = reach_end + 10
    if return_end <= wipe_end:
        return_end = wipe_end + 10
    if return_end >= total_frames:
        return_end = total_frames - 1

    return onset, reach_end, wipe_end, return_end


# ─── Video Processing Pipeline ───────────────────────────────────────────────

def extract_landmarks(video_path: str, fps_override: int = None):
    """Extract MediaPipe pose landmarks from video frames."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Cannot open video file")

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    if fps_override:
        fps = fps_override
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        model_complexity=2,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    raw_data = []
    trc_data = []
    frames_for_video = []
    frame_idx = 1

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)
        time_stamp = (frame_idx - 1) / fps
        csv_row = [frame_idx, time_stamp]
        trc_row = [frame_idx, time_stamp]

        # Prepare skeleton canvas
        black_canvas = np.zeros((height, width, 3), dtype=np.uint8)

        if results.pose_world_landmarks and results.pose_landmarks:
            world_lm = results.pose_world_landmarks.landmark
            norm_lm = results.pose_landmarks.landmark

            for i in range(33):
                csv_row.extend([world_lm[i].x, world_lm[i].y, world_lm[i].z, world_lm[i].visibility])
                trc_row.extend([world_lm[i].x, -world_lm[i].y, -world_lm[i].z])

            # Draw on original frame
            mp.solutions.drawing_utils.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
            )

            # Draw skeleton on black canvas
            for conn in POSE_CONNECTIONS:
                s = norm_lm[conn[0]]
                e = norm_lm[conn[1]]
                x1, y1 = int(s.x * width), int(s.y * height)
                x2, y2 = int(e.x * width), int(e.y * height)
                if (0 <= x1 < width and 0 <= y1 < height and
                    0 <= x2 < width and 0 <= y2 < height):
                    cv2.line(black_canvas, (x1, y1), (x2, y2), (255, 120, 0), 3)

            for lm in norm_lm:
                cx, cy = int(lm.x * width), int(lm.y * height)
                if 0 <= cx < width and 0 <= cy < height:
                    cv2.circle(black_canvas, (cx, cy), 5, (0, 255, 255), -1)
        else:
            for _ in range(33):
                csv_row.extend([0.0, 0.0, 0.0, 0.0])
                trc_row.extend([0.0, 0.0, 0.0])

        raw_data.append(csv_row)
        trc_data.append(trc_row)
        frames_for_video.append((frame, black_canvas))
        frame_idx += 1

    cap.release()
    pose.close()

    return raw_data, trc_data, frames_for_video, fps, width, height


def create_validation_video(frames: list, fps: int, width: int, height: int, output_path: str):
    """Create side-by-side validation video (original + skeleton)."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width * 2, height))

    for original, skeleton in frames:
        composite = np.hstack((original, skeleton))
        out.write(composite)

    out.release()


def compute_kinematics(df: pd.DataFrame, side: str, fps: int):
    """Compute all 14+ biomechanical variables from landmark dataframe."""
    total_frames = len(df)

    # Filter wrist and shoulder signals
    sh_x = butter_lowpass(df[f'{side}_Shoulder_X'].values, 3.0, fps)
    sh_y = butter_lowpass(df[f'{side}_Shoulder_Y'].values, 3.0, fps)
    wr_x = butter_lowpass(df[f'{side}_Wrist_X'].values, 3.0, fps)
    wr_y = butter_lowpass(df[f'{side}_Wrist_Y'].values, 3.0, fps)
    wr_z = butter_lowpass(df[f'{side}_Wrist_Z'].values, 3.0, fps)

    # Trunk center
    trunk_x = (df['L_Shoulder_X'] + df['R_Shoulder_X'] + df['L_Hip_X'] + df['R_Hip_X']) / 4
    trunk_y = (df['L_Shoulder_Y'] + df['R_Shoulder_Y'] + df['L_Hip_Y'] + df['R_Hip_Y']) / 4
    trunk_x_filt = butter_lowpass(trunk_x.values, 3.0, fps)
    trunk_y_filt = butter_lowpass(trunk_y.values, 3.0, fps)

    # Shoulder width for normalization
    median_sw = np.sqrt(
        (df['R_Shoulder_X'] - df['L_Shoulder_X']) ** 2 +
        (df['R_Shoulder_Y'] - df['L_Shoulder_Y']) ** 2
    ).median()
    if median_sw == 0 or np.isnan(median_sw):
        median_sw = 1.0

    # 3D wrist velocity
    dx = np.diff(wr_x, prepend=wr_x[0])
    dy = np.diff(wr_y, prepend=wr_y[0])
    dz = np.diff(wr_z, prepend=wr_z[0])
    speed_3d = np.sqrt(dx ** 2 + dy ** 2 + dz ** 2) * fps

    # Auto-segment
    onset, reach_end, wipe_end, return_end = auto_segment(speed_3d, fps, total_frames)

    # ── Temporal Variables ──
    onset_time = round(onset / fps, 3)
    reaching_duration = round((reach_end - onset) / fps, 3)
    wiping_duration = round((wipe_end - reach_end) / fps, 3)
    total_duration = round((return_end - onset) / fps, 3)

    # ── Spatial Variables ──
    reach_path = float(np.sum(np.sqrt(
        dx[onset:reach_end] ** 2 + dy[onset:reach_end] ** 2 + dz[onset:reach_end] ** 2
    )))
    wipe_path = float(np.sum(np.sqrt(
        dx[reach_end:wipe_end] ** 2 + dy[reach_end:wipe_end] ** 2 + dz[reach_end:wipe_end] ** 2
    )))

    # ── Compensation Variables ──
    trunk_slice_x = trunk_x_filt[reach_end:wipe_end]
    trunk_slice_y = trunk_y_filt[reach_end:wipe_end]

    if len(trunk_slice_x) > 0 and len(trunk_slice_y) > 0:
        trunk_disp = float(np.sqrt(
            (trunk_slice_x.max() - trunk_slice_x.min()) ** 2 +
            (trunk_slice_y.max() - trunk_slice_y.min()) ** 2
        ) / median_sw)
    else:
        trunk_disp = 0.0

    shoulder_angle = np.degrees(np.arctan2(
        df['R_Shoulder_Y'] - df['L_Shoulder_Y'],
        df['R_Shoulder_X'] - df['L_Shoulder_X']
    ))
    trunk_rot_slice = shoulder_angle.iloc[reach_end:wipe_end]
    trunk_rot = float(trunk_rot_slice.max() - trunk_rot_slice.min()) if len(trunk_rot_slice) > 0 else 0.0

    # Shoulder compensation duration
    sh_disp = np.sqrt(
        (sh_x - sh_x[0:max(onset, 1)].mean()) ** 2 +
        (sh_y - sh_y[0:max(onset, 1)].mean()) ** 2
    )
    comp_region = sh_disp[onset:return_end]
    comp_frames = int(np.sum(comp_region > 0.04))

    # ── Joint Kinematics ──
    df['elbow_3d'] = df.apply(lambda row: calc_elbow_angle(row, side), axis=1)
    elbow_slice = df['elbow_3d'].iloc[onset:reach_end]
    if len(elbow_slice) > 1:
        elbow_range = round(float(elbow_slice.max() - elbow_slice.iloc[0]), 1)
    else:
        elbow_range = 0.0

    # ── Smoothness ──
    sparc_reach = compute_sparc(speed_3d[onset:reach_end], fps)
    sparc_full = compute_sparc(speed_3d[onset:return_end], fps)

    peak_speed = np.max(speed_3d) if np.max(speed_3d) > 0 else 1.0
    peaks_r, _ = find_peaks(speed_3d[onset:reach_end], prominence=peak_speed * 0.1)
    peaks_w, _ = find_peaks(speed_3d[reach_end:wipe_end], prominence=peak_speed * 0.1)

    return {
        "onset_time": onset_time,
        "reaching_duration": reaching_duration,
        "wiping_duration": wiping_duration,
        "total_duration": total_duration,
        "reaching_path_length": round(reach_path, 3),
        "reaching_path_normalized": round(reach_path / median_sw, 3),
        "wiping_path_length": round(wipe_path, 3),
        "wiping_path_normalized": round(wipe_path / median_sw, 3),
        "trunk_displacement": round(trunk_disp, 3),
        "trunk_rotation": round(trunk_rot, 2),
        "elbow_extension_range": elbow_range,
        "shoulder_compensation": round(comp_frames / fps, 3),
        "shoulder_displacement_extent": round(float(sh_disp.max() / median_sw), 3),
        "sparc_reaching": round(sparc_reach, 2),
        "sparc_full": round(sparc_full, 2),
        "nvp_reaching": int(max(1, len(peaks_r))),
        "nvp_wiping": int(max(2, len(peaks_w))),
        "frame_count": total_frames,
        "fps": fps,
        "segmentation": {
            "onset": onset,
            "reach_end": reach_end,
            "wipe_end": wipe_end,
            "return_end": return_end
        }
    }


def save_csv(df: pd.DataFrame, phase: str) -> str:
    """Save landmark CSV and return filename."""
    filename = f"motion_{phase}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(filepath, index=False)
    return filename


def save_trc(trc_data: list, fps: int, total_frames: int, phase: str) -> str:
    """Save TRC file (OpenSim compatible) and return filename."""
    filename = f"motion_{phase}.trc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    lines = [
        "PathFileType\t4\t(X/Y/Z)\toutput_motion.trc\n",
        f"DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n",
        f"{fps}\t{fps}\t{total_frames}\t33\tm\t{fps}\t1\t{total_frames}\n",
        "Frame#\tTime\t" + "\t\t\t".join(LANDMARKS_DICT.values()) + "\t\t\n",
        "\t\t" + "\t".join([f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(33)]) + "\n",
        "\n"
    ]

    for r in trc_data:
        line = f"{int(r[0])}\t{r[1]:.4f}\t" + "\t".join([f"{val:.5f}" for val in r[2:]]) + "\n"
        lines.append(line)

    with open(filepath, "w") as f:
        f.write("".join(lines))

    return filename


# ─── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for frontend connection test."""
    return {"status": "ok", "version": "7.0", "engine": "mediapipe"}


@app.post("/process-kinematics")
async def process_kinematics(
    file: UploadFile = File(...),
    side: str = Query("R", description="Affected side: R or L"),
    phase: str = Query("pre", description="Phase: pre, during, or post")
):
    """
    Main processing endpoint.
    Accepts a video file, extracts pose landmarks, computes biomechanical variables,
    generates validation video, and returns all results.
    """
    # Validate inputs
    side_char = "R" if str(side).upper() in ["R", "RIGHT"] else "L"
    phase_str = str(phase).lower()
    if phase_str not in ["pre", "during", "post"]:
        raise HTTPException(status_code=400, detail="Phase must be 'pre', 'during', or 'post'")

    # Save uploaded video temporarily
    timestamp = str(int(time.time()))
    temp_path = f"temp_{phase_str}_{timestamp}_{file.filename}"

    try:
        content = await file.read()
        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        # Step 1: Extract landmarks
        raw_data, trc_data, frames, fps, width, height = extract_landmarks(temp_path)

        if not raw_data:
            raise HTTPException(status_code=400, detail="No frames could be processed from the video")

        # Step 2: Build DataFrame
        headers = ['Frame', 'Time_sec']
        for name in LANDMARKS_DICT.values():
            headers.extend([f'{name}_X', f'{name}_Y', f'{name}_Z', f'{name}_Visibility'])

        df = pd.DataFrame(raw_data, columns=headers)
        df = df.interpolate(method='linear').fillna(0.0)

        # Step 3: Compute kinematics
        metrics = compute_kinematics(df, side_char, fps)

        # Step 4: Save outputs
        csv_filename = save_csv(df, phase_str)
        trc_filename = save_trc(trc_data, fps, len(df), phase_str)

        validation_filename = f"validation_{phase_str}_{timestamp}.mp4"
        validation_path = os.path.join(OUTPUT_DIR, validation_filename)
        create_validation_video(frames, fps, width, height, validation_path)

        # Step 5: Build response
        base_url = "http://localhost:8000"

        return JSONResponse(content={
            "success": True,
            "phase": phase_str,
            "side": side_char,
            "metrics": {
                "onset_time": str(metrics["onset_time"]),
                "reaching_duration": str(metrics["reaching_duration"]),
                "wiping_duration": str(metrics["wiping_duration"]),
                "total_duration": str(metrics["total_duration"]),
                "reaching_path_length": str(metrics["reaching_path_length"]),
                "reaching_path_normalized": str(metrics["reaching_path_normalized"]),
                "wiping_path_length": str(metrics["wiping_path_length"]),
                "wiping_path_normalized": str(metrics["wiping_path_normalized"]),
                "trunk_displacement": str(metrics["trunk_displacement"]),
                "trunk_rotation": str(metrics["trunk_rotation"]),
                "elbow_extension_range": str(metrics["elbow_extension_range"]),
                "shoulder_compensation": str(metrics["shoulder_compensation"]),
                "shoulder_displacement_extent": str(metrics["shoulder_displacement_extent"]),
                "sparc_reaching": str(metrics["sparc_reaching"]),
                "sparc_full": str(metrics["sparc_full"]),
                "nvp_reaching": str(metrics["nvp_reaching"]),
                "nvp_wiping": str(metrics["nvp_wiping"]),
            },
            "meta": {
                "frame_count": metrics["frame_count"],
                "fps": metrics["fps"],
                "segmentation": metrics["segmentation"]
            },
            "links": {
                "csv": f"{base_url}/static/{csv_filename}",
                "trc": f"{base_url}/static/{trc_filename}",
                "video": f"{base_url}/static/{validation_filename}"
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  Stroke Kinematics AI Engine v7.0")
    print("  Starting on http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
