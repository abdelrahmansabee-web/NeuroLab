# NeuroLab Reference Snapshot — v28.81

**Date:** 2026-07-16  
**Branch/Tag:** `v28.81` (see Git tags in both repos)  
**Purpose:** This folder is a frozen copy of the analysis and validation-video code that is currently deployed. If the analysis or the validation overlay video breaks, copy the files from this snapshot back to their original locations and redeploy.

---

## 1. How to revert

Each file below is copied at the exact path it has in the project. To revert a broken file:

```powershell
Copy-Item "D:\Thesis app\NeuroLab\REFERENCE_SNAPSHOT_v28.81\hf_repo\main.py" "D:\Thesis app\NeuroLab\hf_repo\main.py" -Force
```

Or use the Git tags:

- **HF Space backend:** `git checkout v28.81` inside `D:\Thesis app\NeuroLab\hf_repo`
- **Parent project:** `git checkout v28.81` inside `D:\Thesis app\NeuroLab`

Then rebuild the frontend (`npm run build` in `frontend/`) and copy `frontend/build` into `hf_repo/frontend/build` before pushing.

---

## 2. Validation video pipeline (how it works)

### 2.1. Backend

1. **Upload conversion:** uploaded videos are converted to H.264 MP4 with `imageio-ffmpeg` so every browser can play them.
2. **Analysis endpoint:** `POST /analyze` in `main.py` runs the full kinematics pipeline and writes:
   - a landmarks CSV (e.g. `*_landmarks.csv`)
   - a cleaned CSV (e.g. `*_cleaned.csv`)
   - an analysis JSON file
3. **Overlay data endpoint:** `GET /overlay-data/{csv_filename}` in `main.py` calls `overlay_data.build_overlay_data(...)`.
   - Reads the raw pose CSV (or the cleaned CSV if raw is missing).
   - Resamples all landmarks to a uniform `target_fs` (default 60 Hz).
   - Smooths the 2-D points with a 7-frame centered moving average.
   - Computes, per frame:
     - `speed` — hand/wrist speed (px/s)
     - `elbow_angle` — angle at the elbow using shoulder-elbow-wrist vectors
     - `shoulder_elevation_norm` — affected shoulder height above shoulder midpoint, normalized by shoulder width (or frame height if width unknown)
     - `trunk_displacement_norm` — trunk lateral displacement from onset, normalized by shoulder width
   - Detects movement window via `unified_kinematics._movement_window` using speed and elbow angle.
   - Clips speed to zero outside the movement window.
   - Exports a compact JSON with `frames`, `metrics`, `velocity_profile`, `elbow_angle_profile`, `trunk_x_profile`, `peak_frames`, `start_palm`, `end_palm`.
4. **Fallback server renderer:** `POST /unified-validation` uses `unified_validation_renderer.py` to create a side-by-side MP4. This is the old path; the live UI uses the client-side overlay instead.

### 2.2. Frontend

The component is `ValidationOverlayPlayer.js`.

- Loads the original processed MP4 from `/video/{filename}`.
- Loads the overlay JSON from `/overlay-data/{csv_filename}`.
- On every `requestAnimationFrame`, it draws onto a `<canvas>` that sits exactly on top of the video:
  - Full skeleton (bilateral arms, torso, hips, knees, ankles, nose).
  - Affected arm highlighted in cyan.
  - Hand trajectory (palm path) during the movement window.
  - Start/end palm markers.
  - A glass-style metrics panel on the right side with:
    - Movement time
    - Peak elbow angular velocity (deg/s)
    - Straightness
    - Number of velocity peaks (NVP)
    - Pause time / stops
    - Trunk ratio
    - Shoulder elevation
    - SPARC
- Metrics are computed in `computeOverlayMetrics(overlayData)` using the same overlay frames that the table uses. This is the **single source of truth** for the validation table.
- **Auto-scale:** the metrics panel is drawn at a fixed logical size (≈200×360 px) and then scaled down if the video is too small, so the panel never overflows the frame.
- **Media controls** are auto-rendered (Play/Pause, frame step, time, seek, speed 0.5–2×, fullscreen, download) and styled in glass/cyan.

### 2.3. Key metric formulas (validation overlay)

Taken from `computeOverlayMetrics` in `ValidationOverlayPlayer.js`:

- **Peak elbow angular velocity:** max over movement window of `|elbow_angle[i] - elbow_angle[i-1]| / dt`.
- **Movement time:** `time[endIdx] - time[startIdx]`.
- **Pause time:** total time when `speed < 5% of hand peak speed` inside the movement window.
- **Stops:** number of transitions from above to below that speed threshold.
- **Straightness:** `displacement(start_palm, end_palm) / path_length_along_palm`, clamped to 1.
- **Trunk ratio:** `|trunk_x[end] - trunk_x[start]| / palm_displacement`, clamped to 1.
- **Shoulder elevation:** max of `shoulder_elevation_norm` inside the movement window.
- **NVP:** number of peaks in the hand speed profile (from `overlay_data` or analysis dict).

The backend overlay builder computes `shoulder_elevation_norm` as:

```text
shoulder_mid_y_px = (left_shoulder_y + right_shoulder_y) / 2
shoulder_elevation_px = shoulder_mid_y_px - affected_shoulder_y_px
shoulder_elevation_norm = shoulder_elevation_px / shoulder_width_px   (or / frame_h if width unknown)
```

---

## 3. Analysis pipeline (how it works)

### 3.1. Entry point

`POST /analyze` in `main.py`:

- Accepts a video file and optional fields: `affected_side`, `cm_per_px`, `shoulder_width_cm`, `velocity_threshold_px_s`, etc.
- Saves the upload to `DATA_DIR/uploads`.
- Converts it to H.264 MP4 in `DATA_DIR/outputs`.
- Runs the pose + kinematics pipeline.
- Returns a `job_id` for async progress; result is fetched via `/analyze-result/{job_id}`.
- Synchronous alternative: `POST /analyze-sync`.
- CSV-only alternative: `POST /analyze-csv`.

### 3.2. Core modules

- `stroke_kinematic_pipeline.py` — high-level orchestration of an entire trial.
- `unified_kinematics.py` — canonical landmark loader, speed/velocity profile, movement-window detection, NVP computation.
- `kinematics_analyzer.py` — detailed kinematic metrics (elbow angle, shoulder elevation, trunk displacement, straightness, etc.).
- `neurolab_kinematics.py` / `neuro_kinematics.py` — additional metric derivations.
- `robust_reach_analysis.py` — reach-specific robustness heuristics.
- `landmark_tracker_enhance.py` / `extract_pose_csv_robust.py` — pose detection and CSV extraction.
- `analyze_video.py` — legacy analysis entry point.
- `compare_trials.py` / `compare_trials_graph.py` — trial comparison utilities.

### 3.3. Output analysis dict

The dict returned by `/analyze-result` contains keys such as:

`movement_time_sec`, `peak_velocity_px_s`, `time_to_peak_velocity_sec`, `nvp`, `straightness`, `pause_time_sec`, `number_of_stops`, `elbow_angle_mean_deg`, `elbow_angle_range_deg`, `shoulder_elevation_norm`, `trunk_ratio`, `sparc`, `hand_displacement_px`, `hand_displacement_cm`, `hand_displacement_norm`, `shoulder_elevation_cm`, `shoulder_elevation_abs_px`, `shoulder_width_px`, `shoulder_width_cm`, `cm_per_px`, `analysis_fs_hz`, `side_analyzed`, `affected_side`, `velocity_profile`.

---

## 4. Snapshot file list

This snapshot now contains **all** backend Python files and **all** frontend `src`/`public` files from v28.81, not just the highlights. Below are the most important ones.

| Key file | Original location | Why it matters |
|----------|-------------------|----------------|
| `hf_repo/main.py` | `hf_repo/main.py` | FastAPI app, `/analyze`, `/overlay-data`, `/video`, `/unified-validation`, static file serving, CSP |
| `hf_repo/overlay_data.py` | `hf_repo/overlay_data.py` | Builds per-frame overlay JSON used by the validation video |
| `hf_repo/unified_validation_renderer.py` | `hf_repo/unified_validation_renderer.py` | Server-side fallback validation renderer |
| `hf_repo/kinematics_analyzer.py` | `hf_repo/kinematics_analyzer.py` | Core kinematic metric calculations |
| `hf_repo/neurolab_kinematics.py` | `hf_repo/neurolab_kinematics.py` | Additional metric derivations |
| `hf_repo/neuro_kinematics.py` | `hf_repo/neuro_kinematics.py` | More metric derivations |
| `hf_repo/unified_kinematics.py` | `hf_repo/unified_kinematics.py` | Canonical landmarks, speed, movement window, NVP |
| `hf_repo/stroke_kinematic_pipeline.py` | `hf_repo/stroke_kinematic_pipeline.py` | High-level analysis pipeline |
| `hf_repo/robust_reach_analysis.py` | `hf_repo/robust_reach_analysis.py` | Reach analysis robustness |
| `hf_repo/landmark_tracker_enhance.py` | `hf_repo/landmark_tracker_enhance.py` | Landmark tracking enhancements |
| `hf_repo/extract_pose_csv_robust.py` | `hf_repo/extract_pose_csv_robust.py` | CSV extraction |
| `hf_repo/mediapipe_csv_extractor.py` | `hf_repo/mediapipe_csv_extractor.py` | MediaPipe CSV extraction |
| `hf_repo/compare_trials.py` | `hf_repo/compare_trials.py` | Trial comparison |
| `hf_repo/compare_trials_graph.py` | `hf_repo/compare_trials_graph.py` | Trial comparison graphs |
| `hf_repo/analyze_video.py` | `hf_repo/analyze_video.py` | Legacy analysis entry |
| `hf_repo/auth.py` | `hf_repo/auth.py` | Authentication & MFA (v28.81) |
| `hf_repo/security.py` | `hf_repo/security.py` | Encryption, rate limiting, audit logging |
| `hf_repo/requirements.txt` | `hf_repo/requirements.txt` | Python dependencies |
| `hf_repo/Dockerfile` | `hf_repo/Dockerfile` | HF Space build image |
| `frontend/src/ValidationOverlayPlayer.js` | `frontend/src/ValidationOverlayPlayer.js` | Validation overlay canvas player |
| `frontend/src/App.js` | `frontend/src/App.js` | Main app including validation video section and charts |
| `frontend/src/AuthGate.jsx` | `frontend/src/AuthGate.jsx` | Login/MFA gate (v28.81) |
| `frontend/src/analysisPlan.js` | `frontend/src/analysisPlan.js` | Analysis plan logic |
| `frontend/src/patientImport.js` | `frontend/src/patientImport.js` | Patient import logic |
| `frontend/public/index.html` | `frontend/public/index.html` | HTML shell with version meta tag |
| `hf_repo/robust_reach_analysis.py` | `hf_repo/robust_reach_analysis.py` | Reach analysis robustness |
| `hf_repo/landmark_tracker_enhance.py` | `hf_repo/landmark_tracker_enhance.py` | Landmark tracking enhancements |
| `hf_repo/extract_pose_csv_robust.py` | `hf_repo/extract_pose_csv_robust.py` | CSV extraction |
| `hf_repo/compare_trials.py` | `hf_repo/compare_trials.py` | Trial comparison |
| `hf_repo/compare_trials_graph.py` | `hf_repo/compare_trials_graph.py` | Trial comparison graphs |
| `hf_repo/analyze_video.py` | `hf_repo/analyze_video.py` | Legacy analysis entry |
| `hf_repo/requirements.txt` | `hf_repo/requirements.txt` | Python dependencies (includes `pyotp`, `qrcode` as of v28.81) |
| `hf_repo/Dockerfile` | `hf_repo/Dockerfile` | HF Space build image |
| `frontend/src/ValidationOverlayPlayer.js` | `frontend/src/ValidationOverlayPlayer.js` | Validation overlay canvas player |
| `frontend/src/App.js` | `frontend/src/App.js` | Main app including validation video section and charts |
| `frontend/src/AuthGate.jsx` | `frontend/src/AuthGate.jsx` | Login/MFA gate (v28.81) |
| `frontend/public/index.html` | `frontend/public/index.html` | HTML shell with version meta tag |

---

## 5. Deployment checklist after revert

1. Replace the broken files from this snapshot.
2. If `frontend/src` changed, rebuild: `npm run build` in `frontend/`.
3. Copy `frontend/build` to `hf_repo/frontend/build`.
4. Commit in `hf_repo` and push to `https://huggingface.co/spaces/AbdelrahmanSabee/neurolab.git`.
5. Update the `hf_repo` submodule pointer in the parent repo and push to GitHub.
6. Wait for the HF Space build to finish (free tier can be slow).

---

*This snapshot was created automatically. Do not edit the files in this folder; copy them out when needed.*
