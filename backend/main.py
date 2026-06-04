# ============================================================
# Stroke Rehab Platform - Backend Server v1.0
# FastAPI + MediaPipe Pose Landmarker + Reach&Wipe Analyzer
# ============================================================

import os
import shutil
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Local imports
from pose_extractor import extract_pose_from_video
from kinematics_analyzer import analyze_reach_and_wipe
from depth_estimator import estimate_shoulder_width_m
# from viz_3d import create_3d_animation  # replaced by frontend interactive viewer

# ─── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
MODEL_DIR  = BASE_DIR / "models"

for d in [UPLOAD_DIR, OUTPUT_DIR, MODEL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── App Init ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Stroke Rehab Backend",
    description="Pose extraction + Kinematic analysis for Reach & Wipe task",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "✅ Server is running",
        "service": "Stroke Rehab Backend",
        "version": "1.0.0",
    }


@app.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    phase: str = Form("pre"),
    arm_type: str = Form("paretic"),
    affected_side: str = Form("auto"),
    trial_count: str = Form("3"),
    best_trial_metric: str = Form("sparc"),
    patient_height_cm: str = Form("auto"),
    shoulder_width_cm: str = Form("auto"),
    cutoff_frequency: str = Form("6.0"),
    filter_order: str = Form("4"),
):
    try:
        # ── 1. Save uploaded video ─────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = video.filename.replace(" ", "_")
        base_name = f"{phase}_{timestamp}_{Path(safe_name).stem}"
        video_path = UPLOAD_DIR / f"{base_name}{Path(safe_name).suffix}"

        with video_path.open("wb") as f:
            shutil.copyfileobj(video.file, f)

        print(f"\n{'='*60}")
        print(f"📥 New analysis request")
        print(f"   Video : {video.filename}")
        print(f"   Phase : {phase}")
        print(f"{'='*60}\n")

        # ── 2. Parse params ────────────────────────────────────────
        try:
            cutoff = float(cutoff_frequency)
        except Exception:
            cutoff = 6.0
        try:
            order = int(filter_order)
        except Exception:
            order = 4

        # ── 3. Extract pose ────────────────────────────────────────
        extraction_result = extract_pose_from_video(
            video_path=str(video_path),
            output_dir=str(OUTPUT_DIR),
            base_name=base_name,
            model_dir=str(MODEL_DIR),
        )

        if not extraction_result.get("success"):
            error_msg = extraction_result.get("error", "Pose extraction failed")
            print(f"\n❌ EXTRACTION ERROR: {error_msg}\n")
            return JSONResponse(
                status_code=400,
                content={"error": error_msg},
            )

        csv_path      = extraction_result["csv_path"]
        trc_path      = extraction_result["trc_path"]
        video_2d_path = extraction_result["video_2d_path"]
        video_3d_path = extraction_result["video_3d_path"]
        frames_detected = extraction_result["frames_detected"]
        total_frames    = extraction_result["total_frames"]
        fps             = extraction_result["fps"]

        print(f"✅ Pose extraction done — {frames_detected}/{total_frames} frames\n")

        # ── 4. Metric depth estimation ─────────────────────────────
        print("📏 Estimating metric scale via ZoeDepth...")
        try:
            metric_scale = estimate_shoulder_width_m(str(video_path))
        except Exception:
            metric_scale = 0.0
        if metric_scale > 0:
            print(f"   shoulder_width = {metric_scale:.3f} m ({metric_scale*100:.1f} cm)")
        else:
            print("   WARNING: metric scale unavailable, using normalized values")

        # ── 5. Kinematic analysis ──────────────────────────────────
        print(f"🔬 Running kinematic analysis (affected_side={affected_side})...")
        analysis = analyze_reach_and_wipe(
            file_path=csv_path,
            cutoff_frequency=cutoff,
            filter_order=order,
            affected_side=affected_side,
            metric_scale=metric_scale,
        )

        if isinstance(analysis, dict) and analysis.get("error"):
            print(f"\n❌ ANALYSIS ERROR: {analysis['error']}\n")
            return JSONResponse(
                status_code=400,
                content={"error": analysis["error"]},
            )

        print("✅ Analysis complete\n")

        response = {
            "success": True,
            "phase": phase,
            "frames_detected": frames_detected,
            "total_frames": total_frames,
            "fps": round(fps, 2),
            "csv_filename":       Path(csv_path).name,
            "trc_filename":       Path(trc_path).name,
            "validation_video":   Path(video_2d_path).name,
            **analysis,
        }

        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"},
        )


# ─── Download Endpoints ──────────────────────────────────────────────────

def _send_file(folder: Path, filename: str, media_type: str):
    fp = folder / filename
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return FileResponse(path=str(fp), filename=filename, media_type=media_type)


@app.get("/download-csv/{filename}")
def download_csv(filename: str):
    return _send_file(OUTPUT_DIR, filename, "text/csv")


@app.get("/download-trc/{filename}")
def download_trc(filename: str):
    return _send_file(OUTPUT_DIR, filename, "text/plain")


@app.get("/download-video/{filename}")
def download_video_2d(filename: str):
    return _send_file(OUTPUT_DIR, filename, "video/mp4")


@app.get("/download-3d/{filename}")
def download_video_3d(filename: str):
    return _send_file(OUTPUT_DIR, filename, "video/mp4")


@app.get("/download-json/{filename}")
def download_json(filename: str):
    return _send_file(OUTPUT_DIR, filename, "application/json")


# ─── Run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀  Stroke Rehab Backend Starting...")
    print(f"🌐  URL      : http://localhost:8000")
    print(f"📘  API Docs : http://localhost:8000/docs")
    print("="*60 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)