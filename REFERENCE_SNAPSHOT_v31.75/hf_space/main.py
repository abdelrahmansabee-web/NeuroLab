# Stroke Rehab Platform — FastAPI + R an robust reach pipeline
# ============================================================

import base64
import os
import re
import json
import shutil
import subprocess
import sys
import traceback
import concurrent.futures
import uuid
import asyncio
from typing import Optional, Any, List, Dict
from pathlib import Path
from datetime import datetime

print("STARTUP: stdlib imports ok", flush=True)

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

print("STARTUP: fastapi imports ok", flush=True)

try:
    import auth
    from auth import router as auth_router, get_current_user, PATIENTS_DIR, JWT_SECRET
    from security import encrypt_json_to_str, decrypt_json_from_str, WAFMiddleware
    print("STARTUP: auth module loaded", flush=True)
except Exception as _auth_exc:
    print("STARTUP: auth module failed to load:", _auth_exc, flush=True)
    auth_router = None
    get_current_user = None
    PATIENTS_DIR = None
    JWT_SECRET = None
    encrypt_json_to_str = None
    decrypt_json_from_str = None
    WAFMiddleware = None

_BASE = Path(__file__).resolve().parent
_RAN_DIR = _BASE.parent / "R an" if (_BASE.parent / "R an" / "extract_pose_csv_robust.py").exists() else _BASE
if str(_RAN_DIR) not in sys.path:
    sys.path.insert(0, str(_RAN_DIR))

DEPLOY_VERSION = "29.24"
DEPLOY_SHA_FILE = _BASE / "DEPLOY_SHA.txt"


# — Paths —
BASE_DIR = Path(__file__).parent.resolve()
_build_candidates = [
    BASE_DIR / "frontend" / "build",          # HF Docker / hf_repo layout
    BASE_DIR.parent / "frontend" / "build",   # monorepo: backend/../frontend/build
]
FRONTEND_BUILD = next((p for p in _build_candidates if p.exists()), _build_candidates[0])


def _resolve_data_dir() -> Path:
    env = os.environ.get("NEUROLAB_DATA_DIR")
    candidates = [Path(env)] if env else []
    candidates += [Path("/data/neurolab"), BASE_DIR / "data"]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    fallback = BASE_DIR / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DATA_DIR   = _resolve_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
MODEL_DIR  = BASE_DIR / "models"
PATIENTS_FILE = DATA_DIR / "patients.json"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)
POSE_MODEL_FILE = MODEL_DIR / "pose_landmarker_heavy.task"

for d in [UPLOAD_DIR, OUTPUT_DIR, MODEL_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# In-memory job progress cache; authoritative copy is on disk for multi-worker + subprocess.
job_progress: Dict[str, Dict[str, Any]] = {}
ANALYZE_JOBS_DIR = OUTPUT_DIR / "analyze_jobs"


def _job_file(job_id: str) -> Path:
    return ANALYZE_JOBS_DIR / f"{job_id}.json"


def _persist_job(job_id: str, info: Dict[str, Any]) -> None:
    job_progress[job_id] = info
    try:
        ANALYZE_JOBS_DIR.mkdir(parents=True, exist_ok=True)
        dest = _job_file(job_id)
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(info, default=str), encoding="utf-8")
        tmp.replace(dest)
    except Exception as exc:
        print(f"Job persist warning ({job_id}): {exc}", flush=True)


def _load_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Always prefer on-disk job state (subprocess worker updates the JSON file)."""
    path = _job_file(job_id)
    if path.exists():
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
            job_progress[job_id] = info
            return info
        except Exception:
            pass
    return job_progress.get(job_id)


def _set_job_progress(job_id: str, pct: float, step: str, done: bool = False, error: Optional[str] = None, result: Optional[Dict[str, Any]] = None):
    _persist_job(
        job_id,
        {
            "pct": min(100.0, max(0.0, round(float(pct), 1))),
            "step": step,
            "done": done,
            "error": error,
            "result": result,
            "updated_at": datetime.now().isoformat(),
        },
    )


# In-memory unified-validation background job store.
uv_jobs: Dict[str, Dict[str, Any]] = {}


def _cleanup_old_jobs(max_age_minutes: int = 30):
    now = datetime.now()
    cutoff_keys = []
    for job_id, info in list(job_progress.items()):
        try:
            updated = datetime.fromisoformat(info.get("updated_at", "2000-01-01T00:00:00"))
            if (now - updated).total_seconds() > max_age_minutes * 60:
                cutoff_keys.append(job_id)
        except Exception:
            cutoff_keys.append(job_id)
    for k in cutoff_keys:
        job_progress.pop(k, None)
        try:
            _job_file(k).unlink(missing_ok=True)
            (ANALYZE_JOBS_DIR / f"{k}_kwargs.json").unlink(missing_ok=True)
        except Exception:
            pass
    uv_cutoff_keys = []
    for job_id, info in list(uv_jobs.items()):
        try:
            updated = datetime.fromisoformat(info.get("updated_at", "2000-01-01T00:00:00"))
            if (now - updated).total_seconds() > max_age_minutes * 60:
                uv_cutoff_keys.append(job_id)
        except Exception:
            uv_cutoff_keys.append(job_id)
    for k in uv_cutoff_keys:
        uv_jobs.pop(k, None)


def ensure_pose_model() -> bool:
    """Download MediaPipe pose model if missing (HF / fresh deploy)."""
    print(f"STARTUP: ensure_pose_model checking {POSE_MODEL_FILE}", flush=True)
    if POSE_MODEL_FILE.exists() and POSE_MODEL_FILE.stat().st_size > 1_000_000:
        print("STARTUP: pose model already present", flush=True)
        return True
    try:
        import urllib.request
        print(f"Downloading pose model — {POSE_MODEL_FILE}", flush=True)
        tmp = POSE_MODEL_FILE.with_suffix(".task.tmp")
        urllib.request.urlretrieve(POSE_MODEL_URL, tmp)
        tmp.replace(POSE_MODEL_FILE)
        ok = POSE_MODEL_FILE.exists() and POSE_MODEL_FILE.stat().st_size > 1_000_000
        print(f"Pose model ready: {ok} ({POSE_MODEL_FILE.stat().st_size if ok else 0} bytes)", flush=True)
        return ok
    except Exception as e:
        traceback.print_exc()
        print(f"Pose model download failed: {e}", flush=True)
        return False


def _check_clinical_plausibility(
    analysis: dict,
    phase: str,
    resolved_arm: str,
) -> dict:
    """Lightweight post-hoc clinical plausibility checks for a single analysis.

    These are sanity checks, not strict pass/fail gates, because real clinical
    variability exists. They flag values that warrant human review.
    """
    warnings: List[str] = []
    checks = {
        "sparc_present": False,
        "trunk_ratio_present": False,
        "movement_time_present": False,
        "peak_velocity_present": False,
        "reach_distance_present": False,
        "sparc_plausible": None,
        "post_sparc_not_worse_than_pre": None,
        "peak_velocity_positive": None,
        "movement_time_positive": None,
        "trunk_ratio_in_range": None,
    }

    metrics = analysis.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    sparc = metrics.get("sparc")
    trunk_ratio = metrics.get("trunk_ratio")
    movement_time = metrics.get("movement_time")
    peak_velocity = metrics.get("peak_velocity")
    reach_distance = metrics.get("reach_distance")

    if sparc is not None:
        checks["sparc_present"] = True
        checks["sparc_plausible"] = bool(-6.0 <= float(sparc) <= 1.0)
        if not checks["sparc_plausible"]:
            warnings.append(f"SPARC ({sparc:.3f}) outside literature-typical range [-6, 1].")

    if trunk_ratio is not None:
        checks["trunk_ratio_present"] = True
        checks["trunk_ratio_in_range"] = bool(0.0 <= float(trunk_ratio) <= 1.0)
        if not checks["trunk_ratio_in_range"]:
            warnings.append(f"Trunk ratio ({trunk_ratio:.3f}) outside [0, 1].")

    if movement_time is not None:
        checks["movement_time_present"] = True
        checks["movement_time_positive"] = bool(0.1 <= float(movement_time) <= 30.0)
        if not checks["movement_time_positive"]:
            warnings.append(f"Movement time ({movement_time:.3f} s) outside plausible range [0.1, 30].")

    if peak_velocity is not None:
        checks["peak_velocity_present"] = True
        checks["peak_velocity_positive"] = bool(0.0 < float(peak_velocity) < 500.0)
        if not checks["peak_velocity_positive"]:
            warnings.append(f"Peak velocity ({peak_velocity:.2f} cm/s) outside plausible range (0, 500).")

    if reach_distance is not None:
        checks["reach_distance_present"] = True
        if not (0.05 <= float(reach_distance) <= 1.0):
            warnings.append(f"Reach distance ({reach_distance:.3f} m) outside plausible range [0.05, 1.0].")

    return {
        "clinical_plausibility_checks": checks,
        "clinical_warnings": warnings,
        "requires_review": bool(warnings),
    }


# — App Init —
app = FastAPI(
    title="Stroke Rehab Backend",
    description="Pose extraction + Kinematic analysis for Reach & Wipe task",
    version=DEPLOY_VERSION,
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "font-src 'self' data:; connect-src 'self' https://cdn.jsdelivr.net https://tessdata.projectnaptha.com; "
        "worker-src 'self' https://cdn.jsdelivr.net blob:; "
        "frame-ancestors 'self' https://huggingface.co https://*.huggingface.co https://*.hf.space; "
        "base-uri 'self'; form-action 'self';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    return response

if auth_router is not None:
    app.include_router(auth_router)
    print("STARTUP: auth router included", flush=True)

# WAF upload/size blocking disabled — clinical videos must reach /analyze unblocked.
# (security.py encrypt helpers still used by auth.)
@app.on_event("startup")
async def _startup_ensure_models():
    print("STARTUP: running startup event", flush=True)

    # Heavy/optional work is delayed so the app passes HF health checks immediately.
    async def _background_init():
        await asyncio.sleep(5)
        if auth_router is not None:
            try:
                await asyncio.wait_for(asyncio.to_thread(auth._init_db), timeout=10.0)
                print("STARTUP: auth DB initialized", flush=True)
            except Exception as e:
                print("STARTUP: auth DB init failed:", e, flush=True)
            try:
                await asyncio.wait_for(asyncio.to_thread(ensure_pose_model), timeout=30.0)
                print("STARTUP: pose model ready", flush=True)
            except Exception as e:
                print("STARTUP: pose model init failed:", e, flush=True)
            try:
                await asyncio.wait_for(asyncio.to_thread(auth.init_auth), timeout=60.0)
                print("STARTUP: auth init done", flush=True)
            except Exception as e:
                print("STARTUP: auth init failed:", e, flush=True)
        print("STARTUP: background init done", flush=True)

    asyncio.create_task(_background_init())
    print("STARTUP: startup event done (app ready for health checks)", flush=True)


# — Endpoints —

@app.get("/")
async def serve_index():
    path = FRONTEND_BUILD / "index.html"
    if not path.exists():
        return JSONResponse({"error": "Frontend build not found"}, status_code=404)

    no_cache = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    # HF Spaces: serve file directly (fast, non-blocking); no localhost rewrite needed.
    if os.environ.get("SPACE_ID") or os.environ.get("SYSTEM") == "spaces":
        return FileResponse(path, headers=no_cache)

    content = path.read_text(encoding="utf-8")
    content = content.replace("http://localhost:8000", "window.location.origin")
    content = content.replace("http://127.0.0.1:8000", "window.location.origin")
    content = content.replace("`http://${window.location.hostname}:8000`", "window.location.origin")
    content = content.replace("localhost:8000", "window.location.origin")
    content = content.replace("127.0.0.1:8000", "window.location.origin")

    return HTMLResponse(content=content, status_code=200, headers=no_cache)


@app.get("/static/{rest_of_path:path}")
async def serve_static(rest_of_path: str):
    file_path = FRONTEND_BUILD / "static" / rest_of_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404)




def _normalize_patients_data(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        pts = data.get("patients")
        if isinstance(pts, list):
            return pts
    return []


def _patients_file_for_user(user: Optional[dict]) -> Path:
    if get_current_user and user:
        return PATIENTS_DIR / f"{user['id']}.json"
    return PATIENTS_FILE


def _read_patients_file(file: Path) -> list:
    if not file.exists():
        return []
    try:
        raw = file.read_text(encoding="utf-8")
        if raw.startswith("enc:") and JWT_SECRET and decrypt_json_from_str:
            data = decrypt_json_from_str(raw, JWT_SECRET)
        else:
            data = json.loads(raw)
        return _normalize_patients_data(data)
    except Exception:
        return []


def _write_patients_file(file: Path, patients: list) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    if JWT_SECRET and encrypt_json_to_str:
        file.write_text(encrypt_json_to_str(patients, JWT_SECRET), encoding="utf-8")
    else:
        file.write_text(json.dumps(patients, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/patients")
async def api_get_patients(user: dict = Depends(get_current_user) if get_current_user else None):
    return _read_patients_file(_patients_file_for_user(user))


def _auto_rotate_video_with_ffmpeg(video_path: Path) -> Optional[Path]:
    """
    Detect and apply rotation metadata from phone/tablet videos using ffmpeg.
    Returns the path to the rotated video, or None if no rotation is needed.
    """
    import re
    from unified_validation_renderer import _find_ffmpeg

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None

    import re
    cmd = [ffmpeg, "-hide_banner", "-i", str(video_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
    output = result.stderr or result.stdout or ""

    angle = 0
    m = re.search(r'rotate\s*[:=]\s*(\-?\d+(?:\.\d+)?)', output, re.IGNORECASE)
    if m:
        angle = int(float(m.group(1))) % 360
    else:
        m = re.search(r'displaymatrix:\s*rotation\s*(-?\d+(?:\.\d+)?)', output)
        if m:
            angle = int(float(m.group(1))) % 360
        else:
            m = re.search(r'rotation\s+(-?\d+(?:\.\d+)?)\s*deg', output)
            if m:
                angle = int(float(m.group(1))) % 360

    # Only re-encode when rotation metadata exists. Landscape without metadata is left
    # as-is (avoids multi-minute libx264 re-encode on HF CPU that looked like a hang at 8%).
    if angle == 0:
        return None

    # Map clockwise rotation angle to ffmpeg transpose value on the RAW stored
    # frame (ffmpeg auto-rotation is disabled so the metadata isn't applied
    # twice).  transpose values: 0=90CCW+vertflip, 1=90CW, 2=90CCW, 3=90CW+vertflip
    # A video with rotate=90 metadata is stored on its side; rotating it 90°
    # clockwise produces an upright portrait clip.
    transpose_map = {90: "1", 180: "1,1", 270: "2"}
    if angle not in transpose_map:
        return None

    rotated_path = video_path.with_name(video_path.stem + "_rotated" + video_path.suffix)
    vf = f"transpose={transpose_map[angle]}"
    cmd = [
        ffmpeg, "-y", "-noautorotate", "-i", str(video_path),
        "-vf", vf,
        "-metadata:s:v:0", "rotate=0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an",
        str(rotated_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
    if result.returncode != 0 or not rotated_path.exists() or rotated_path.stat().st_size < 1000:
        print(f"ffmpeg rotation failed: {result.stderr[:500]}")
        return None
    return rotated_path


def _ensure_playable_mp4(video_path: Path) -> Path:
    """
    Convert any uploaded video to an H.264 MP4 so the browser can play it inline.
    Already-MP4 files are left as-is to avoid unnecessary re-encoding.
    """
    if video_path.suffix.lower() == ".mp4":
        return video_path
    try:
        from unified_validation_renderer import _find_ffmpeg
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            print("ffmpeg not found; leaving video in original format")
            return video_path
        mp4_path = video_path.with_suffix(".mp4")
        cmd = [
            ffmpeg, "-y", "-i", str(video_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an",
            str(mp4_path),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        if result.returncode != 0 or not mp4_path.exists() or mp4_path.stat().st_size < 1000:
            print(f"MP4 conversion failed: {result.stderr[:500]}")
            return video_path
        return mp4_path
    except Exception as exc:
        print(f"MP4 conversion exception: {exc}")
        return video_path


from analyze_job_runner import sync_analyze_pipeline as _sync_analyze_pipeline


async def _save_upload_streaming(upload: UploadFile, dest: Path, job_id: Optional[str] = None) -> None:
    """Stream upload to disk without blocking the event loop (other tabs/requests stay alive)."""
    chunks = 0
    with dest.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            chunks += 1
            if job_id and chunks % 4 == 0:
                _set_job_progress(job_id, min(7.0, 2.0 + chunks * 0.4), "Receiving video…")


def _start_analyze_job(job_id: str, pipeline_kwargs: Dict[str, Any]) -> None:
    ANALYZE_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    kw_path = ANALYZE_JOBS_DIR / f"{job_id}_kwargs.json"
    serializable = dict(pipeline_kwargs)
    serializable["video_path"] = str(pipeline_kwargs["video_path"])
    kw_path.write_text(json.dumps(serializable, default=str), encoding="utf-8")
    _set_job_progress(job_id, 9.5, "Starting analysis worker…")
    worker_script = BASE_DIR / "analyze_worker.py"
    log_path = ANALYZE_JOBS_DIR / f"{job_id}_worker.log"
    try:
        log_f = log_path.open("w", encoding="utf-8")
    except Exception:
        log_f = subprocess.DEVNULL
    subprocess.Popen(
        [sys.executable, str(worker_script), job_id, str(kw_path)],
        cwd=str(BASE_DIR),
        start_new_session=True,
        close_fds=os.name != "nt",
        stdout=log_f if log_f != subprocess.DEVNULL else subprocess.DEVNULL,
        stderr=subprocess.STDOUT if log_f != subprocess.DEVNULL else subprocess.DEVNULL,
    )


def _write_upload_to_disk(upload: UploadFile, dest: Path) -> None:
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)


def _run_analysis_job(
    job_id: str,
    video_path: Path,
    phase: str,
    resolved_arm: str,
    quality_report: Dict[str, Any],
    cutoff: float,
    order: int,
    legacy: bool,
    save_intermediate: bool,
    metric_scale: float,
    clinical_task: str = "study_reach_grasp",
):
    """Run the full analysis pipeline and update job_progress."""
    base_name = f"{phase}_{video_path.stem}"
    csv_path = OUTPUT_DIR / f"{base_name}.csv"
    try:
        _set_job_progress(job_id, 5, "Saving uploaded video...")

        _set_job_progress(job_id, 12, "Extracting pose landmarks...")
        intermediate_dir = str(OUTPUT_DIR / f"{base_name}_intermediates")
        ensure_pose_model()
        from mediapipe_csv_extractor import extract_from_video
        from kinematics_analyzer import analyze_reach_and_wipe

        extract_arm = resolved_arm if resolved_arm in ("left", "right") else "auto"
        report = extract_from_video(
            video_path=str(video_path),
            output_csv=str(csv_path),
            model_path=str(POSE_MODEL_FILE),
            affected_side=extract_arm,
            camera_view="auto",
            use_clahe=not legacy,
            max_interpolate_gap=8,
            butterworth_cutoff_hz=cutoff,
            butterworth_order=order,
            save_raw_pose=True,
            show_progress=True,
            legacy_format=legacy,
            save_intermediate_frames=save_intermediate,
            intermediate_dir=intermediate_dir,
            save_resampled=save_intermediate,
        )
        frames_detected = int(report.get("frames", 0))
        fps = float(report.get("fps", 30.0))
        analysis_csv_path = csv_path
        raw_pose_csv = report.get("raw_pose_csv")
        if raw_pose_csv:
            raw_pose_p = Path(raw_pose_csv)
            if raw_pose_p.exists():
                analysis_csv_path = raw_pose_p

        effective_arm = resolved_arm
        if effective_arm not in ("left", "right"):
            detected = (report.get("affected_side") or "").lower()
            if detected in ("left", "right"):
                effective_arm = detected

        _set_job_progress(job_id, 55, "Computing kinematics...")
        analysis = analyze_reach_and_wipe(
            file_path=str(analysis_csv_path),
            cutoff_frequency=cutoff,
            filter_order=order,
            affected_side=effective_arm if effective_arm in ("left", "right") else "auto",
            metric_scale=metric_scale,
            phase_name=phase.upper(),
            camera_view="auto",
            video_path=str(video_path),
            clinical_task=clinical_task,
        )
        if isinstance(analysis, dict) and analysis.get("error"):
            _set_job_progress(job_id, 0, "Analysis failed", done=True, error=analysis["error"])
            return

        _set_job_progress(job_id, 80, "Rendering validation video (deferred)...")
        unified_validation_video = None
        unified_validation_video_b64 = None
        validation_summary = None

        _set_job_progress(job_id, 95, "Finalizing results...")
        response = {
            "success": True,
            "phase": phase,
            "frames_detected": frames_detected,
            "total_frames": frames_detected,
            "fps": round(fps, 2),
            "csv_filename": Path(analysis_csv_path).name,
            "video_filename": video_path.name,
            "trc_filename": None,
            "mot_filename": None,
            "validation_video": report.get("validation_video"),
            "unified_validation_video": unified_validation_video,
            "unified_validation_video_b64": unified_validation_video_b64,
            "validation_summary": validation_summary,
            "quality_report": quality_report,
            "legacy_format": legacy,
            "intermediate_files": {
                "raw_pose_csv": report.get("raw_pose_csv"),
                "filtered_landmarks_csv": report.get("filtered_landmarks_csv"),
                "resampled_landmarks_csv": report.get("resampled_landmarks_csv"),
                "intermediate_dir": report.get("intermediate_dir"),
                "quality_json": report.get("quality_json"),
            },
            **analysis,
        }
        _set_job_progress(job_id, 100, "Done", done=True, result=response)
    except Exception as exc:
        traceback.print_exc()
        _set_job_progress(job_id, 0, "Error", done=True, error=str(exc))


@app.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    phase: str = Form("pre"),
    arm_type: str = Form("paretic"),
    affected_side: str = Form("auto"),
    stroke_side: str = Form("auto"),
    trial_count: str = Form("1"),
    best_trial_metric: str = Form("sparc"),
    patient_height_cm: str = Form("auto"),

    cutoff_frequency: str = Form("4.0"),
    filter_order: str = Form("4"),
    legacy_format: str = Form("false"),
    save_intermediates: str = Form("false"),
    clinical_task: str = Form("study_reach_grasp"),
):
    from stroke_kinematic_pipeline import resolve_analysis_arm
    from video_quality_validator import validate_video

    try:
        # — 1. Save uploaded video —
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = video.filename.replace(" ", "_")
        base_name = f"{phase}_{timestamp}_{Path(safe_name).stem}"
        video_path = UPLOAD_DIR / f"{base_name}{Path(safe_name).suffix}"

        _cleanup_old_jobs()
        job_id = uuid.uuid4().hex
        _set_job_progress(job_id, 1, "Receiving video…")
        await _save_upload_streaming(video, video_path, job_id)

        print(f"\n{'='*60}")
        print(f"New analysis request (async job {job_id})")
        print(f"   Video : {video.filename}")
        print(f"   Phase : {phase}")
        resolved_arm = resolve_analysis_arm(phase, stroke_side, affected_side)
        print(f"   Arm   : {resolved_arm} (stroke_side={stroke_side}, requested={affected_side})")
        print(f"{'='*60}\n")

        if resolved_arm not in ("left", "right"):
            print("   Arm will be auto-detected from video kinematics.", flush=True)

        def _run_quality_validation() -> Dict[str, Any]:
            try:
                validation_result = validate_video(video_path)
                qr = validation_result.to_dict()
                qr["passed"] = True
                if validation_result.errors and not validation_result.warnings:
                    qr["warnings"] = validation_result.errors[:]
                elif validation_result.errors:
                    qr["warnings"] = validation_result.errors[:] + qr.get("warnings", [])
                qr["errors"] = []
                return qr
            except Exception as exc:
                return {"passed": True, "warnings": [f"Validation skipped: {exc}"]}

        quality_report = await asyncio.to_thread(_run_quality_validation)
        print(f"Video quality report (non-blocking): {quality_report}")

        # — 3. Parse params —
        try:
            cutoff = float(cutoff_frequency)
        except Exception:
            cutoff = 4.0
        try:
            order = int(filter_order)
        except Exception:
            order = 4
        legacy = (legacy_format or "true").lower() in ("true", "1", "yes", "on")
        save_intermediate = (save_intermediates or "true").lower() in ("true", "1", "yes", "on")

        _set_job_progress(job_id, 9, "Starting analysis worker…")
        pipeline_kwargs = {
            "video_path": video_path,
            "base_name": base_name,
            "phase": phase,
            "resolved_arm": resolved_arm,
            "quality_report": quality_report,
            "cutoff": cutoff,
            "order": order,
            "legacy": legacy,
            "save_intermediate": save_intermediate,
            "trial_count": trial_count,
            "best_trial_metric": best_trial_metric,
            "clinical_task": clinical_task,
            "patient_height_cm": patient_height_cm,
            "original_filename": video.filename or "video",
        }
        _start_analyze_job(job_id, pipeline_kwargs)

        return {
            "async": True,
            "job_id": job_id,
            "message": "Analysis started — poll /analyze-progress/{job_id}",
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"},
        )


@app.get("/analyze-progress/{job_id}")
async def analyze_progress(job_id: str):
    info = _load_job(job_id) or {"pct": 0, "step": "Waiting...", "done": False}
    return {
        "job_id": job_id,
        "pct": info.get("pct", 0),
        "step": info.get("step", ""),
        "done": info.get("done", False),
        "error": info.get("error"),
    }


@app.get("/analyze-result/{job_id}")
async def analyze_result_get(job_id: str):
    return await analyze_result(job_id)


@app.post("/analyze-result/{job_id}")
async def analyze_result(job_id: str):
    info = _load_job(job_id)
    if not info:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if info.get("error"):
        return JSONResponse(status_code=400, content={"error": info["error"]})
    if not info.get("done"):
        return {"done": False, "pct": info.get("pct", 0), "step": info.get("step", "")}
    return info.get("result", {"done": True})


# Synchronous analyze kept as canonical endpoint.
@app.post("/analyze-sync")
async def analyze_video_sync(
    video: UploadFile = File(...),
    phase: str = Form("pre"),
    arm_type: str = Form("paretic"),
    affected_side: str = Form("auto"),
    stroke_side: str = Form("auto"),
    trial_count: str = Form("1"),
    best_trial_metric: str = Form("sparc"),
    patient_height_cm: str = Form("auto"),

    cutoff_frequency: str = Form("4.0"),
    filter_order: str = Form("4"),
    legacy_format: str = Form("false"),
    save_intermediates: str = Form("false"),
    clinical_task: str = Form("study_reach_grasp"),
):
    """Blocking analyze — waits for full pipeline (legacy clients)."""
    from stroke_kinematic_pipeline import resolve_analysis_arm
    from video_quality_validator import validate_video

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = video.filename.replace(" ", "_")
        base_name = f"{phase}_{timestamp}_{Path(safe_name).stem}"
        video_path = UPLOAD_DIR / f"{base_name}{Path(safe_name).suffix}"
        await asyncio.to_thread(_write_upload_to_disk, video, video_path)
        resolved_arm = resolve_analysis_arm(phase, stroke_side, affected_side)
        if resolved_arm not in ("left", "right"):
            print("Arm will be auto-detected from video kinematics.", flush=True)
        try:
            validation_result = validate_video(video_path)
            quality_report = validation_result.to_dict()
            quality_report["passed"] = True
            quality_report["errors"] = []
        except Exception as exc:
            quality_report = {"passed": True, "warnings": [f"Validation skipped: {exc}"]}
        try:
            cutoff = float(cutoff_frequency)
        except Exception:
            cutoff = 4.0
        try:
            order = int(filter_order)
        except Exception:
            order = 4
        legacy = (legacy_format or "true").lower() in ("true", "1", "yes", "on")
        save_intermediate = (save_intermediates or "true").lower() in ("true", "1", "yes", "on")
        pipeline_out = await asyncio.to_thread(
            _sync_analyze_pipeline,
            video_path,
            base_name,
            phase,
            resolved_arm,
            quality_report,
            cutoff,
            order,
            legacy,
            save_intermediate,
            trial_count,
            best_trial_metric,
            clinical_task,
            patient_height_cm,
            video.filename or "video",
        )
        if pipeline_out.get("error"):
            return JSONResponse(
                status_code=int(pipeline_out.get("status", 500)),
                content={"error": pipeline_out["error"]},
            )
        return pipeline_out["response"]
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


@app.post("/analyze-csv")
async def analyze_csv(
    csv: UploadFile = File(...),
    phase: str = Form("pre"),
    affected_side: str = Form("auto"),
    stroke_side: str = Form("auto"),
    cutoff_frequency: str = Form("4.0"),
    filter_order: str = Form("4"),
    metric_scale: str = Form("0.0"),

    patient_height_cm: str = Form("auto"),
    trial_count: str = Form("1"),
    best_trial_metric: str = Form("sparc"),
    clinical_task: str = Form("study_reach_grasp"),
):
    from stroke_kinematic_pipeline import resolve_analysis_arm
    from kinematics_analyzer import analyze_reach_and_wipe

    """Upload a CSV + run kinematic analysis (skip video pose extraction).
    Optional metric_scale (meters) or patient height to get cm values.
    Priority: height*0.255 > metric_scale > 0 (normalized only).
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = csv.filename.replace(" ", "_")
        base_name = f"{phase}_{timestamp}_{Path(safe_name).stem}"
        csv_path = OUTPUT_DIR / f"{base_name}.csv"

        with csv_path.open("wb") as f:
            shutil.copyfileobj(csv.file, f)
        print(f"\n{'='*60}")
        print(f"CSV analysis: {csv.filename} -> {csv_path.name}")
        resolved_arm = resolve_analysis_arm(phase, stroke_side, affected_side)
        print(f"Arm: {resolved_arm} (phase={phase}, stroke_side={stroke_side})")
        print(f"{'='*60}\n")

        cutoff = float(cutoff_frequency)
        order = int(filter_order)
        ms = 0.0
        if patient_height_cm and patient_height_cm != "auto":
            sw_est = float(patient_height_cm) * 0.255
            ms = sw_est / 100.0
            print(f" Estimated from height x 0.255: {sw_est:.1f} cm")
        elif metric_scale and float(metric_scale) > 0:
            ms = float(metric_scale)

        analysis = analyze_reach_and_wipe(
            file_path=str(csv_path),
            cutoff_frequency=cutoff,
            filter_order=order,
            affected_side=resolved_arm,
            metric_scale=ms,
            trial_count=int(trial_count or 1),
            best_trial_metric=best_trial_metric or "sparc",
            phase_name=phase.upper(),
            camera_view="auto",
            clinical_task=clinical_task,
        )

        if isinstance(analysis, dict) and analysis.get("error"):
            return JSONResponse(status_code=400, content={"error": analysis["error"]})

        if isinstance(analysis, dict):
            side = analysis.get("side_analyzed")
            if side in ("left", "right"):
                analysis.setdefault("affected_side", side)

        mot_filename = None
        try:
            print(" Running OpenSim IK skipped (pipeline disabled)...")
            # run_opensim(str(csv_path), output_dir=str(OUTPUT_DIR), copy_to_desktop=False)
            mot_name = base_name + "_ik.mot"
            if (OUTPUT_DIR / mot_name).exists():
                mot_filename = mot_name
                print(f"   IK .mot saved: {mot_name}")
        except Exception as e:
            print(f"   OpenSim IK skipped: {e}")

        def _pipeline_meta() -> dict:
            try:
                from kinematic_locked_config import LOCKED_CODE_VERSION, LOCKED_SPARC_TRUNK  # noqa: WPS433

                return {
                    "backend_version": DEPLOY_VERSION,
                    "pipeline": "reach_only_v24_locked",
                    "pipeline_version": LOCKED_CODE_VERSION,
                    "trunk_metric": LOCKED_SPARC_TRUNK.get("trunk_metric", "trunk_path_ratio"),
                }
            except Exception as exc:
                return {"backend_version": DEPLOY_VERSION, "pipeline_error": str(exc)}

        analysis_json_path = OUTPUT_DIR / f"{base_name}_analysis.json"
        try:
            with analysis_json_path.open("w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, default=str)
        except Exception as exc:
            print(f"Warning: could not save analysis JSON: {exc}")

        response = {
            "success": True,
            "phase": phase,
            "csv_filename": csv_path.name,
            "video_filename": video_path.name,
            "analysis_json": analysis_json_path.name,
            "mot_filename": mot_filename,
            **_pipeline_meta(),
            **analysis,
        }
        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


# — Unified validation video —

def _run_uv_generation(job_id: str, csv_path: Path, video_path: Path, rotation: str):
    """Background worker for unified validation video generation."""
    from unified_validation_renderer import render_unified_validation_video

    try:
        uv_jobs[job_id]["status"] = "analyzing"
        uv_jobs[job_id]["updated_at"] = datetime.now().isoformat()

        # Prefer the official analysis saved by /analyze so the validation video
        # overlay matches the results table exactly. Fall back to recomputing if
        # the JSON is missing (ephemeral filesystem) or unreadable.
        analysis = None
        base_stem = video_path.stem.replace("_rotated", "")
        candidate_json = OUTPUT_DIR / f"{base_stem}_analysis.json"
        if not candidate_json.exists():
            csv_stem = csv_path.stem.replace("_raw_pose", "")
            candidate_json = OUTPUT_DIR / f"{csv_stem}_analysis.json"
        if candidate_json.exists():
            try:
                with candidate_json.open("r", encoding="utf-8") as f:
                    analysis = json.load(f)
                print(f"UV worker loaded official analysis from {candidate_json.name}")
            except Exception as exc:
                print(f"UV worker failed to load analysis JSON: {exc}; recomputing...")
                analysis = None

        if analysis is None:
            from stroke_kinematic_pipeline import analyze_stroke_kinematic_csv
            analysis = analyze_stroke_kinematic_csv(str(csv_path), video_path=str(video_path))
            if analysis.get("error"):
                uv_jobs[job_id].update({"status": "failed", "error": analysis["error"], "done": True, "updated_at": datetime.now().isoformat()})
                return

        out_name = f"{csv_path.stem}_unified_validation.mp4"
        out_path = OUTPUT_DIR / out_name
        uv_jobs[job_id]["status"] = "rendering"
        uv_jobs[job_id]["updated_at"] = datetime.now().isoformat()
        uv_result = render_unified_validation_video(
            video_path=str(video_path),
            output_path=str(out_path),
            analysis=analysis,
            landmarks_csv=str(csv_path),
            force_rotation=rotation,
            resolution="native",
            panel_width=480,
        )
        validation_summary = uv_result.get("summary") if isinstance(uv_result, dict) else None
        uv_path = uv_result.get("path") if isinstance(uv_result, dict) else str(uv_result)
        if uv_path and Path(uv_path).exists() and Path(uv_path).stat().st_size > 1000:
            uv_jobs[job_id].update({
                "status": "done",
                "done": True,
                "unified_validation_video": out_name,
                "download_url": f"/download/{out_name}",
                "validation_summary": validation_summary,
                "updated_at": datetime.now().isoformat(),
            })
        else:
            uv_jobs[job_id].update({"status": "failed", "error": "Rendered video file is missing or empty", "done": True, "updated_at": datetime.now().isoformat()})
    except Exception as exc:
        traceback.print_exc()
        uv_jobs[job_id].update({"status": "failed", "error": str(exc), "done": True, "updated_at": datetime.now().isoformat()})


@app.post("/unified-validation")
async def unified_validation(
    csv_filename: str = Form(...),
    video_filename: str = Form(...),
    rotation: str = Form("auto"),
):
    """
    Queue unified validation video generation and return a job id.
    The frontend polls /unified-validation-status/{job_id} until done.
    """
    try:
        csv_path = OUTPUT_DIR / csv_filename
        if csv_path.name.endswith("_raw_pose.csv"):
            cleaned_name = csv_path.name.replace("_raw_pose.csv", ".csv")
            cleaned_candidate = csv_path.with_name(cleaned_name)
            if cleaned_candidate.exists():
                csv_path = cleaned_candidate

        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        search_dirs = [UPLOAD_DIR, OUTPUT_DIR]
        video_path = None
        for folder in search_dirs:
            candidate = folder / video_filename
            if candidate.exists():
                video_path = candidate
                break
            suffix = Path(video_filename).suffix.lower()
            if suffix:
                for candidate2 in folder.glob(f"*{suffix}"):
                    if candidate2.name.lower().endswith(video_filename.lower()):
                        video_path = candidate2
                        break
                if video_path:
                    break
        if not video_path or not video_path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": f"Video not found: {video_filename}. HF Space storage is ephemeral — please re-upload and re-analyze the video."},
            )

        job_id = str(uuid.uuid4())
        uv_jobs[job_id] = {
            "status": "queued",
            "done": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        # Run in a background thread so the HTTP response returns immediately.
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run_uv_generation, job_id, csv_path, video_path, rotation)
        return {"success": True, "job_id": job_id, "status": "queued"}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


def _resolve_overlay_video_path(csv_path: Path, analysis: Optional[Dict[str, Any]]) -> Optional[Path]:
    """Find the original video that matches the given CSV in uploads or outputs."""
    # Prefer an explicit filename stored in the analysis JSON.
    video_filename = None
    if analysis:
        video_filename = analysis.get("video_filename")
    if video_filename:
        for folder in (UPLOAD_DIR, OUTPUT_DIR):
            candidate = folder / video_filename
            if candidate.exists():
                return candidate
            suffix = Path(video_filename).suffix.lower()
            if suffix:
                for candidate2 in folder.glob(f"*{suffix}"):
                    if candidate2.name.lower().endswith(video_filename.lower()):
                        return candidate2
    # Otherwise try to infer from the CSV name.
    from table_calibrator import find_video_for_csv

    candidate = find_video_for_csv(str(csv_path))
    if candidate and candidate.exists():
        return candidate
    # Last resort: look for any video with a matching stem in uploads/outputs.
    stem = csv_path.stem.replace("_landmarks", "").replace("_raw_pose", "").replace("_analysis", "")
    for folder in (UPLOAD_DIR, OUTPUT_DIR):
        for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            candidate = folder / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None


def _overlay_cache_path_for_csv(csv_path: Path) -> Path:
    base_stem = csv_path.stem.replace("_raw_pose", "")
    return OUTPUT_DIR / f"{base_stem}_overlay.json"


def _build_and_cache_overlay(csv_path: Path, analysis: dict, video_path: Optional[Path]) -> Optional[dict]:
    from overlay_data import build_overlay_data

    target_fs = float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", 60.0)))
    overlay_arm = analysis.get("side_analyzed")
    if overlay_arm not in ("left", "right"):
        overlay_arm = analysis.get("affected_side")
    if overlay_arm not in ("left", "right"):
        overlay_arm = "auto"
    data = build_overlay_data(
        str(csv_path),
        analysis,
        overlay_arm,
        target_fs,
        str(video_path) if video_path else None,
    )
    if data.get("error"):
        print(f"Overlay build failed: {data['error']}")
        return None
    cache_path = _overlay_cache_path_for_csv(csv_path)
    try:
        cache_path.write_text(json.dumps(data, default=str), encoding="utf-8")
    except Exception as exc:
        print(f"Overlay cache write failed: {exc}")
    return data


def _overlay_cache_stale(cached: dict, analysis: Optional[Dict[str, Any]], video_path: Optional[Path]) -> bool:
    """Discard cached overlay when it was built for a different served video file."""
    if int(cached.get("overlay_version") or 0) < 36:
        return True
    want = (analysis or {}).get("video_filename")
    if not want and video_path:
        want = video_path.name
    got = cached.get("overlay_video_filename")
    if not got and cached.get("debug_video_path"):
        got = Path(str(cached["debug_video_path"])).name
    if want and got and str(want) != str(got):
        return True
    if analysis:
        want_side = (analysis.get("side_analyzed") or analysis.get("affected_side") or "").lower()
        got_side = (cached.get("affected_side") or "").lower()
        if want_side in ("left", "right") and got_side in ("left", "right") and want_side != got_side:
            return True
    return False


@app.get("/overlay-data/{csv_filename}")
async def get_overlay_data(csv_filename: str):
    """
    Return lightweight per-frame landmarks and metrics for browser-side
    validation video overlay rendering.
    """
    from overlay_data import build_overlay_data

    try:
        csv_path = OUTPUT_DIR / csv_filename
        if csv_path.name.endswith("_raw_pose.csv"):
            cleaned_name = csv_path.name.replace("_raw_pose.csv", ".csv")
            cleaned_candidate = csv_path.with_name(cleaned_name)
            if cleaned_candidate.exists():
                csv_path = cleaned_candidate
        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        cache_path = _overlay_cache_path_for_csv(csv_path)

        analysis = None
        base_stem = csv_path.stem.replace("_raw_pose", "")
        candidate_json = OUTPUT_DIR / f"{base_stem}_analysis.json"
        if candidate_json.exists():
            try:
                with candidate_json.open("r", encoding="utf-8") as f:
                    analysis = json.load(f)
            except Exception as exc:
                print(f"Overlay data could not load analysis JSON: {exc}")

        video_path = _resolve_overlay_video_path(csv_path, analysis)

        if cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as f:
                    cached = json.load(f)
                if not cached.get("error") and not _overlay_cache_stale(cached, analysis, video_path):
                    cached["version"] = DEPLOY_VERSION
                    return JSONResponse(content=cached)
                if cached.get("error"):
                    pass
                else:
                    print(f"Overlay cache stale for {csv_path.name}, rebuilding")
            except Exception as exc:
                print(f"Overlay cache read failed, rebuilding: {exc}")

        target_fs = float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", 60.0))) if analysis else 60.0

        overlay_arm = "auto"
        if analysis:
            overlay_arm = analysis.get("side_analyzed") or analysis.get("affected_side") or "auto"
        if overlay_arm not in ("left", "right"):
            overlay_arm = "auto"

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            build_overlay_data,
            str(csv_path),
            analysis,
            overlay_arm,
            target_fs,
            str(video_path) if video_path else None,
        )
        if data.get("error"):
            return JSONResponse(status_code=500, content={"error": data["error"]})
        data["version"] = DEPLOY_VERSION
        try:
            cache_path.write_text(json.dumps(data, default=str), encoding="utf-8")
        except Exception as exc:
            print(f"Overlay cache write failed: {exc}")
        return JSONResponse(content=data)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


@app.get("/overlay-coord-diag/{csv_filename}")
async def get_overlay_coord_diagnostic(csv_filename: str):
    """
    Run overlay coordinate diagnostic: scores none / portrait_to_landscape /
    landscape_to_portrait and optionally renders a side-by-side debug JPEG.
    """
    from overlay_coord_diag import run_overlay_coord_diagnostic

    try:
        csv_path = OUTPUT_DIR / csv_filename
        if csv_path.name.endswith("_raw_pose.csv"):
            cleaned_name = csv_path.name.replace("_raw_pose.csv", ".csv")
            cleaned_candidate = csv_path.with_name(cleaned_name)
            if cleaned_candidate.exists():
                csv_path = cleaned_candidate
        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        analysis = None
        base_stem = csv_path.stem.replace("_raw_pose", "")
        candidate_json = OUTPUT_DIR / f"{base_stem}_analysis.json"
        if candidate_json.exists():
            try:
                with candidate_json.open("r", encoding="utf-8") as f:
                    analysis = json.load(f)
            except Exception as exc:
                print(f"Coord diag could not load analysis JSON: {exc}")

        video_path = _resolve_overlay_video_path(csv_path, analysis)
        loop = asyncio.get_event_loop()
        diag = await loop.run_in_executor(
            None,
            run_overlay_coord_diagnostic,
            str(csv_path),
            str(video_path) if video_path else None,
            analysis,
            str(OUTPUT_DIR),
        )
        if diag.get("error"):
            return JSONResponse(status_code=500, content={"error": diag["error"]})
        img_name = Path(str(diag.get("diag_image", ""))).name if diag.get("diag_image") else None
        if img_name:
            diag["diag_image_url"] = f"/download/{img_name}"
        diag["version"] = DEPLOY_VERSION
        return JSONResponse(content=diag)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


@app.get("/unified-validation-status/{job_id}")
async def unified_validation_status(job_id: str):
    info = uv_jobs.get(job_id)
    if not info:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return {
        "status": info.get("status"),
        "done": info.get("done", False),
        "error": info.get("error"),
        "unified_validation_video": info.get("unified_validation_video"),
        "download_url": info.get("download_url"),
        "validation_summary": info.get("validation_summary"),
    }


# — Download Endpoints —

def _send_file(folder: Path, filename: str, media_type: str):
    fp = folder / filename
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return FileResponse(path=str(fp), filename=filename, media_type=media_type)


def _send_file_any(folders: List[Path], filename: str, media_type: str):
    for folder in folders:
        fp = folder / filename
        if fp.exists():
            # For downloads, set Content-Disposition so browser saves the file.
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            return FileResponse(
                path=str(fp),
                filename=filename,
                media_type=media_type,
                headers=headers,
            )
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.get("/download/{filename}")
async def download_file(filename: str):
    """Return file as a downloadable attachment.

    Wraps FileResponse so the browser/PWA treats the response as a download
    rather than an inline resource.
    """
    for folder in [OUTPUT_DIR, UPLOAD_DIR]:
        fp = folder / filename
        if fp.exists():
            media = "video/mp4" if filename.lower().endswith(".mp4") else "application/octet-stream"
            disp = "inline" if media == "video/mp4" else "attachment"
            return FileResponse(
                path=str(fp),
                filename=filename,
                media_type=media,
                headers={
                    "Content-Disposition": f'{disp}; filename="{filename}"',
                    "Content-Type": media,
                },
            )
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.get("/video/{filename}")
async def serve_video(filename: str):
    """Return video for inline playback."""
    for folder in [OUTPUT_DIR, UPLOAD_DIR]:
        fp = folder / filename
        if fp.exists():
            return FileResponse(
                path=str(fp),
                filename=filename,
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                },
            )
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.head("/video/{filename}")
async def head_video(filename: str):
    """HEAD support for video streaming (needed by some proxies/CDNs)."""
    for folder in [OUTPUT_DIR, UPLOAD_DIR]:
        fp = folder / filename
        if fp.exists():
            return Response(
                headers={
                    "Content-Type": "video/mp4",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(fp.stat().st_size),
                }
            )
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.get("/csv/{filename}")
async def serve_csv(filename: str):
    return _send_file(OUTPUT_DIR, filename, "text/csv")


@app.get("/patients")
async def get_patients(user: dict = Depends(get_current_user) if get_current_user else None):
    return _read_patients_file(_patients_file_for_user(user))


@app.post("/api/patients")
async def save_patients(body: dict, user: dict = Depends(get_current_user) if get_current_user else None):
    try:
        patients = _normalize_patients_data(body)
        _write_patients_file(_patients_file_for_user(user), patients)
        return {"success": True, "count": len(patients)}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/study-analysis")
async def study_analysis_endpoint(body: dict):
    try:
        from study_analysis import run_study_analysis, format_report

        tmp = OUTPUT_DIR / f"study_input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        results = run_study_analysis(tmp)
        return {"success": True, "results": results}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    """Parse a NeuroLab Clinical Assessment Report PDF server-side.

    Returns the same patient-object shape produced by the frontend
    patientImport.js parser.
    """
    try:
        from pdf_import_parser import extract_pdf_text, parse_clinical_report_pdf

        contents = await file.read()
        text = extract_pdf_text(contents)
        patient = parse_clinical_report_pdf(text)
        return {
            "success": True,
            "patient": patient,
            "extracted_text": text,
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )


@app.post("/api/ocr-pdf")
async def ocr_pdf(file: UploadFile = File(...)):
    """Server-side OCR fallback for scanned/image PDFs.

    Uses Tesseract + pdf2image to extract text from the first pages.
    Supports English, Turkish, and Arabic text.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        contents = await file.read()
        images = convert_from_bytes(contents, first_page=1, last_page=10, dpi=300)
        texts = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="eng+tur+ara")
            if text:
                texts.append(text)
        full_text = "\n".join(texts)
        return {"success": True, "text": full_text}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )


@app.get("/debug-pdf")
async def debug_pdf_page():
    """Simple HTML form to test PDF parsing without rebuilding the frontend."""
    html = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>NeuroLab PDF Parser Debug</title>
<style>
body { font-family: ui-sans-serif, system-ui, sans-serif; background:#121820; color:#e2e8f0; padding:2rem; }
input[type=file] { margin:1rem 0; color:#fff; }
pre { background:#0f172a; padding:1rem; border-radius:.5rem; overflow:auto; max-height:60vh; }
.card { background:#1e293b; border:1px solid #334155; border-radius:.5rem; padding:1rem; margin-top:1rem; }
</style>
</head>
<body>
<h1>NeuroLab PDF Import Debug</h1>
<p>Upload the Clinical Assessment Report PDF. The page will show the raw extracted text and the parsed fields.</p>
<form id="form" enctype="multipart/form-data">
<input type="file" id="file" name="file" accept=".pdf">
<button type="submit">Parse PDF</button>
</form>
<div id="result"></div>
<script>
document.getElementById('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('file').files[0];
  if (!file) return alert('Choose a PDF');
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/parse-pdf', { method: 'POST', body: fd });
  const data = await res.json();
  const out = document.getElementById('result');
  if (data.error) {
    out.innerHTML = '<div class="card"><h3>Error</h3><pre>' + JSON.stringify(data, null, 2) + '</pre></div>';
    return;
  }
  out.innerHTML =
    '<div class="card"><h3>Parsed patient</h3><pre>' + JSON.stringify(data.patient, null, 2) + '</pre></div>' +
    '<div class="card"><h3>Extracted text</h3><pre>' + (data.extracted_text || '').replace(/</g,'&lt;') + '</pre></div>';
});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    return {"status": "ok", "version": DEPLOY_VERSION}


# Serve root-level static files from the frontend build directory
# (pdf.worker.min.js, manifest.json, favicon.ico, logos, bg.jpg, etc.)
# IMPORTANT: keep this catch-all route LAST so it does not shadow API endpoints.
@app.get("/{file_name}")
async def serve_build_root(file_name: str):
    if file_name in ("index.html",):
        raise HTTPException(status_code=404)
    file_path = FRONTEND_BUILD / file_name
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)

