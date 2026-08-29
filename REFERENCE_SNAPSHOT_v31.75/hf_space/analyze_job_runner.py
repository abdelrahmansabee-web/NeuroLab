# -*- coding: utf-8 -*-
"""CPU-heavy video analyze pipeline — imported by analyze_worker.py only (no FastAPI)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np  # noqa: F401 — used by downstream kinematics

BASE_DIR = Path(__file__).resolve().parent
_RAN_DIR = BASE_DIR.parent / "R an" if (BASE_DIR.parent / "R an" / "extract_pose_csv_robust.py").exists() else BASE_DIR
if str(_RAN_DIR) not in sys.path:
    sys.path.insert(0, str(_RAN_DIR))

DEPLOY_VERSION = "29.25"


def _resolve_metric_scale(patient_height_cm: str, video_path: Path) -> float:
    """Ethics/manuscript kinematics use normalized ratios & angles — not ZoeDepth cm scale."""
    _ = video_path
    if patient_height_cm and str(patient_height_cm).strip().lower() not in ("", "auto", "unknown"):
        try:
            return float(patient_height_cm) * 0.255 / 100.0
        except Exception:
            pass
    return 0.0


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


DATA_DIR = _resolve_data_dir()
OUTPUT_DIR = DATA_DIR / "outputs"
MODEL_DIR = BASE_DIR / "models"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)
POSE_MODEL_FILE = MODEL_DIR / "pose_landmarker_heavy.task"
ANALYZE_JOBS_DIR = OUTPUT_DIR / "analyze_jobs"

for d in (OUTPUT_DIR, MODEL_DIR, ANALYZE_JOBS_DIR, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _job_file(job_id: str) -> Path:
    return ANALYZE_JOBS_DIR / f"{job_id}.json"


def set_job_progress(
    job_id: str,
    pct: float,
    step: str,
    done: bool = False,
    error: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    info = {
        "pct": min(100.0, max(0.0, round(float(pct), 1))),
        "step": step,
        "done": done,
        "error": error,
        "result": result,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        dest = _job_file(job_id)
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(info, default=str), encoding="utf-8")
        tmp.replace(dest)
    except Exception as exc:
        print(f"Job persist warning ({job_id}): {exc}", flush=True)


def ensure_pose_model() -> bool:
    if POSE_MODEL_FILE.exists() and POSE_MODEL_FILE.stat().st_size > 1_000_000:
        return True
    try:
        tmp = POSE_MODEL_FILE.with_suffix(".task.tmp")
        urllib.request.urlretrieve(POSE_MODEL_URL, tmp)
        tmp.replace(POSE_MODEL_FILE)
        return POSE_MODEL_FILE.exists() and POSE_MODEL_FILE.stat().st_size > 1_000_000
    except Exception as e:
        print(f"Pose model download failed: {e}", flush=True)
        return False


def _overlay_cache_path_for_csv(csv_path: Path) -> Path:
    base_stem = csv_path.stem.replace("_raw_pose", "")
    return OUTPUT_DIR / f"{base_stem}_overlay.json"


def _probe_video_rotation_angle(video_path: Path) -> int:
    from video_orientation import probe_rotation_deg

    return int(probe_rotation_deg(video_path) or 0)


def _auto_rotate_video_with_ffmpeg(video_path: Path) -> Optional[Path]:
    from unified_validation_renderer import _find_ffmpeg

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None
    angle = _probe_video_rotation_angle(video_path)
    if angle == 0:
        return None
    transpose_map = {90: "1", 180: "1,1", 270: "2"}
    if angle not in transpose_map:
        return None
    rotated_path = video_path.with_name(video_path.stem + "_rotated" + video_path.suffix)
    vf = f"transpose={transpose_map[angle]}"
    cmd = [
        ffmpeg, "-y", "-noautorotate", "-i", str(video_path),
        "-vf", vf,
        "-metadata:s:v:0", "rotate=0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an",
        str(rotated_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
    if result.returncode != 0 or not rotated_path.exists() or rotated_path.stat().st_size < 1000:
        return None
    return rotated_path


def _ensure_playable_mp4(video_path: Path) -> Path:
    if video_path.suffix.lower() == ".mp4":
        return video_path
    try:
        from unified_validation_renderer import _find_ffmpeg

        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return video_path
        mp4_path = video_path.with_suffix(".mp4")
        cmd = [
            ffmpeg, "-y", "-i", str(video_path),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an",
            str(mp4_path),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        if result.returncode != 0 or not mp4_path.exists():
            return video_path
        return mp4_path
    except Exception:
        return video_path


def _downscale_video_for_analysis(video_path: Path, max_w: int = 1280, max_h: int = 720) -> Path:
    try:
        from unified_validation_renderer import _find_ffmpeg

        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return video_path
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return video_path
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        if w <= max_w and h <= max_h:
            return video_path
        out = video_path.with_name(f"{video_path.stem}_analyze720p{video_path.suffix}")
        if out.exists() and out.stat().st_size > 5000:
            return out
        vf = f"scale='min({max_w},iw)':'min({max_h},ih)':force_original_aspect_ratio=decrease"
        cmd = [
            ffmpeg, "-y", "-noautorotate", "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an",
            str(out),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        if result.returncode != 0 or not out.exists():
            return video_path
        return out
    except Exception:
        return video_path


def _check_clinical_plausibility(analysis: dict, phase: str, resolved_arm: str) -> dict:
    warnings: List[str] = []
    checks: Dict[str, Any] = {}
    metrics = analysis.get("metrics", {}) if isinstance(analysis.get("metrics"), dict) else {}
    sparc = metrics.get("sparc")
    if sparc is not None and not (-6.0 <= float(sparc) <= 1.0):
        warnings.append(f"SPARC ({sparc:.3f}) outside literature-typical range [-6, 1].")
    return {
        "clinical_plausibility_checks": checks,
        "clinical_warnings": warnings,
        "requires_review": bool(warnings),
    }


def sync_analyze_pipeline(
    video_path: Path,
    base_name: str,
    phase: str,
    resolved_arm: str,
    quality_report: Dict[str, Any],
    cutoff: float,
    order: int,
    legacy: bool,
    save_intermediate: bool,
    trial_count: str,
    best_trial_metric: str,
    clinical_task: str,
    patient_height_cm: str,
    original_filename: str,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    def _prog(pct: float, step: str) -> None:
        if job_id:
            set_job_progress(job_id, pct, step)

    _prog(12, "Preparing video…")
    from mediapipe_csv_extractor import extract_from_video
    from kinematics_analyzer import analyze_reach_and_wipe

    try:
        video_path = _ensure_playable_mp4(video_path)
    except Exception as exc:
        print(f"MP4 conversion skipped: {exc}")

    try:
        rotated_path = _auto_rotate_video_with_ffmpeg(video_path)
        if rotated_path and rotated_path.exists():
            video_path = rotated_path
    except Exception as exc:
        print(f"Video auto-rotation skipped: {exc}")

    video_path = _downscale_video_for_analysis(video_path)

    _prog(14, "Checking pose model…")
    if not ensure_pose_model():
        return {"error": f"Pose model missing: {POSE_MODEL_FILE}", "status": 503}

    csv_path = OUTPUT_DIR / f"{base_name}.csv"
    intermediate_dir = str(OUTPUT_DIR / f"{base_name}_intermediates")
    extract_arm = resolved_arm if resolved_arm in ("left", "right") else "auto"
    _prog(20, "Extracting pose landmarks…")
    try:
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
    except Exception as e:
        return {"error": f"Extraction crash: {str(e)}", "status": 500}

    effective_arm = resolved_arm
    if effective_arm not in ("left", "right"):
        detected = (report.get("affected_side") or "").lower()
        if detected in ("left", "right"):
            effective_arm = detected
            conf = report.get("side_detection_confidence")
            print(
                f"Auto-detected arm: {effective_arm}"
                + (f" (confidence={conf})" if conf is not None else ""),
                flush=True,
            )

    frames_detected = int(report.get("frames", 0))
    fps = float(report.get("fps", 30.0))
    analysis_csv_path = csv_path
    raw_pose_csv = report.get("raw_pose_csv")
    if raw_pose_csv:
        raw_pose_p = Path(raw_pose_csv)
        if raw_pose_p.exists():
            analysis_csv_path = raw_pose_p

    _prog(58, "Computing kinematics…")
    metric_scale = _resolve_metric_scale(patient_height_cm, video_path)

    _prog(62, "Running movement analysis…")
    analysis = analyze_reach_and_wipe(
        file_path=str(analysis_csv_path),
        cutoff_frequency=cutoff,
        filter_order=order,
        affected_side=effective_arm if effective_arm in ("left", "right") else "auto",
        metric_scale=metric_scale,
        trial_count=int(trial_count or 1),
        best_trial_metric=best_trial_metric or "sparc",
        phase_name=phase.upper(),
        camera_view="auto",
        video_path=str(video_path),
        clinical_task=clinical_task,
    )
    if isinstance(analysis, dict) and analysis.get("error"):
        return {"error": analysis["error"], "status": 400}

    validation_video = report.get("validation_video")
    if validation_video and not (OUTPUT_DIR / validation_video).exists():
        validation_video = None

    mot_filename = None
    mot_name = base_name + "_ik.mot"
    if (OUTPUT_DIR / mot_name).exists():
        mot_filename = mot_name

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

    plausibility = _check_clinical_plausibility(analysis, phase, effective_arm)
    if isinstance(analysis, dict):
        analysis["video_filename"] = video_path.name
        for k in (
            "orientation_corrected",
            "pose_rotation_applied",
            "frame_width_px",
            "frame_height_px",
        ):
            if report.get(k) is not None:
                analysis[k] = report[k]
        if effective_arm in ("left", "right"):
            analysis.setdefault("side_analyzed", effective_arm)
            analysis.setdefault("affected_side", effective_arm)
        if report.get("side_detection_confidence") is not None:
            analysis.setdefault("side_detection_confidence", report.get("side_detection_confidence"))
            analysis.setdefault("side_detection_method", report.get("side_detection_method"))
            analysis.setdefault("side_detection_scores", report.get("side_detection_scores"))
    analysis_json_path = OUTPUT_DIR / f"{base_name}_analysis.json"
    try:
        with analysis_json_path.open("w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, default=str)
    except Exception as exc:
        print(f"Warning: could not save analysis JSON: {exc}")

    _prog(92, "Building validation overlay…")
    try:
        from overlay_data import build_overlay_data

        target_fs = float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", 60.0)))
        overlay_arm = (
            analysis.get("side_analyzed")
            if analysis.get("side_analyzed") in ("left", "right")
            else (effective_arm if effective_arm in ("left", "right") else "auto")
        )
        ov = build_overlay_data(
            str(analysis_csv_path),
            analysis,
            overlay_arm,
            target_fs,
            str(video_path),
        )
        if not ov.get("error"):
            cache_path = _overlay_cache_path_for_csv(Path(analysis_csv_path))
            cache_path.write_text(json.dumps(ov, default=str), encoding="utf-8")
        else:
            print(f"Overlay prebuild: {ov.get('error')}", flush=True)
    except Exception as exc:
        print(f"Overlay prebuild warning: {exc}", flush=True)

    _prog(95, "Finalizing results…")
    if isinstance(quality_report, dict):
        quality_report = dict(quality_report)
        quality_report.setdefault("warnings", [])
        if clinical_task and clinical_task != "study_reach_grasp":
            quality_report["warnings"] = list(quality_report.get("warnings") or []) + [
                "Multi-phase ADL task: analysis takes longer than reach-only on HF CPU."
            ]

    response = {
        "success": True,
        "phase": phase,
        "frames_detected": frames_detected,
        "total_frames": frames_detected,
        "fps": round(fps, 2),
        "csv_filename": Path(analysis_csv_path).name,
        "video_filename": video_path.name,
        "analysis_json": analysis_json_path.name,
        "trc_filename": None,
        "mot_filename": mot_filename,
        "validation_video": validation_video,
        "unified_validation_video": None,
        "unified_validation_video_b64": None,
        "overlay_data_url": f"/overlay-data/{Path(analysis_csv_path).name}",
        "overlay_cache_file": _overlay_cache_path_for_csv(Path(analysis_csv_path)).name,
        "validation_summary": None,
        "quality_report": quality_report,
        "legacy_format": legacy,
        "intermediate_files": {
            "raw_pose_csv": report.get("raw_pose_csv"),
            "filtered_landmarks_csv": report.get("filtered_landmarks_csv"),
            "resampled_landmarks_csv": report.get("resampled_landmarks_csv"),
            "intermediate_dir": report.get("intermediate_dir"),
            "quality_json": report.get("quality_json"),
        },
        **plausibility,
        **_pipeline_meta(),
        **analysis,
    }
    return {"response": response}


def execute_analyze_job(job_id: str, raw: Dict[str, Any]) -> None:
    set_job_progress(job_id, 10, "Analysis worker started…")
    pipeline_kwargs = {
        "video_path": Path(raw["video_path"]),
        "base_name": raw["base_name"],
        "phase": raw["phase"],
        "resolved_arm": raw["resolved_arm"],
        "quality_report": raw.get("quality_report") or {},
        "cutoff": float(raw["cutoff"]),
        "order": int(raw["order"]),
        "legacy": bool(raw["legacy"]),
        "save_intermediate": bool(raw["save_intermediate"]),
        "trial_count": raw.get("trial_count", "1"),
        "best_trial_metric": raw.get("best_trial_metric", "sparc"),
        "clinical_task": raw.get("clinical_task", "study_reach_grasp"),
        "patient_height_cm": raw.get("patient_height_cm", "auto"),
        "original_filename": raw.get("original_filename", "video"),
    }
    out = sync_analyze_pipeline(**pipeline_kwargs, job_id=job_id)
    if out.get("error"):
        set_job_progress(job_id, 0, "Analysis failed", done=True, error=str(out["error"]))
    else:
        set_job_progress(job_id, 100, "Done", done=True, result=out["response"])
