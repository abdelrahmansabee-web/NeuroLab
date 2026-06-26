# ============================================================
# Stroke Rehab Platform - Backend Server v1.0
# FastAPI + MediaPipe Pose Landmarker + Reach&Wipe Analyzer
# ============================================================

import os
import re
import json
import shutil
import traceback
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Local imports
from pose_extractor import extract_pose_from_video
from kinematics_analyzer import analyze_reach_and_wipe
from depth_estimator import estimate_shoulder_width_m


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
async def serve_index():
    path = FRONTEND_BUILD / "index.html"
    if not path.exists():
        return JSONResponse({"error": "Frontend build not found"}, status_code=404)
    
    content = path.read_text(encoding="utf-8")
    # Total Wipeout: Replace every possible variation of localhost/127.0.0.1
    content = content.replace("http://localhost:8000", "window.location.origin")
    content = content.replace("http://127.0.0.1:8000", "window.location.origin")
    content = content.replace("`http://${window.location.hostname}:8000`", "window.location.origin")
    content = content.replace("localhost:8000", "window.location.origin")
    content = content.replace("127.0.0.1:8000", "window.location.origin")
    
    return HTMLResponse(content=content, status_code=200)


@app.get("/static/{rest_of_path:path}")
async def serve_static(rest_of_path: str):
    file_path = FRONTEND_BUILD / "static" / rest_of_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404)



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
        print(f"🔬 Step 1: Extracting pose from {video.filename}...")
        try:
            extraction_result = extract_pose_from_video(
                video_path=str(video_path),
                output_dir=str(OUTPUT_DIR),
                base_name=base_name,
                model_dir=str(MODEL_DIR),
            )
        except Exception as e:
            print(f"❌ CRITICAL EXTRACTION ERROR: {e}")
            return JSONResponse(status_code=500, content={"error": f"Extraction crash: {str(e)}"})

        if not extraction_result.get("success"):
            error_msg = extraction_result.get("error", "Pose extraction failed")
            print(f"\n EXTRACTION ERROR: {error_msg}\n")
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

        print(f"✅ Pose extraction done - {frames_detected}/{total_frames} frames\n")

        # ── 4. Metric scale: user shoulder width > height*0.255 > ZoeDepth > 0 ────
        metric_scale = 0.0
        if shoulder_width_cm and shoulder_width_cm != "auto":
            metric_scale = float(shoulder_width_cm) / 100.0
            print(f" Using user shoulder width: {shoulder_width_cm} cm (-> {metric_scale:.3f} m)")
        elif patient_height_cm and patient_height_cm != "auto":
            h_cm = float(patient_height_cm)
            sw_est = h_cm * 0.255
            metric_scale = sw_est / 100.0
            print(f" Estimated from height x 0.255: {h_cm} cm -> {sw_est:.1f} cm (-> {metric_scale:.3f} m)")
        else:
            print("📏 Estimating metric scale via ZoeDepth...")
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    print("   Submitting ZoeDepth task to thread pool...")
                    fut = pool.submit(estimate_shoulder_width_m, str(video_path))
                    print("   Waiting for result (timeout=30s)...")
                    metric_scale = fut.result(timeout=30)
                    print(f"   ZoeDepth succeeded: {metric_scale:.3f}m")
            except concurrent.futures.TimeoutError:
                print("   TIMEOUT: depth estimation took >30s, skipping")
                metric_scale = 0.0
            except Exception as e:
                print(f"   ZoeDepth CRASH: {e}")
                metric_scale = 0.0

        if metric_scale > 0:
            print(f"   metric_scale = {metric_scale:.3f} m ({metric_scale*100:.1f} cm)")
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
            print(f"\n ANALYSIS ERROR: {analysis['error']}\n")
            return JSONResponse(
                status_code=400,
                content={"error": analysis["error"]},
            )

        print("✅ Analysis complete\n")

        video_2d_name = Path(video_2d_path).name
        mot_filename = None
        try:
            print(" Running OpenSim IK skipped (pipeline disabled)...")
            # run_opensim(str(csv_path), output_dir=str(OUTPUT_DIR), copy_to_desktop=False)
            mot_name = Path(csv_path).stem + "_ik.mot"
            if (OUTPUT_DIR / mot_name).exists():
                mot_filename = mot_name
                print(f"   IK .mot saved: {mot_name}")
        except Exception as e:
            print(f"   OpenSim IK skipped: {e}")

        response = {
            "success": True,
            "phase": phase,
            "frames_detected": frames_detected,
            "total_frames": total_frames,
            "fps": round(fps, 2),
            "csv_filename":       Path(csv_path).name,
            "trc_filename":       Path(trc_path).name,
            "mot_filename":       mot_filename,
            "validation_video":   video_2d_name,
            **analysis,
        }

        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"},
        )


# ─── Analyze CSV only (skip pose extraction) ────────────────────────────

@app.post("/analyze-csv")
async def analyze_csv(
    csv: UploadFile = File(...),
    phase: str = Form("pre"),
    affected_side: str = Form("auto"),
    cutoff_frequency: str = Form("6.0"),
    filter_order: str = Form("4"),
    metric_scale: str = Form("0.0"),
    shoulder_width_cm: str = Form("auto"),
    patient_height_cm: str = Form("auto"),
):
    """Upload a CSV + run kinematic analysis + OpenSim IK (skip video pose extraction).
    Optional metric_scale (meters) or shoulder_width_cm to get cm values.
    Priority: shoulder_width_cm > height*0.255 > metric_scale > 0 (normalized only).
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
        print(f"{'='*60}\n")

        cutoff = float(cutoff_frequency)
        order = int(filter_order)
        ms = 0.0
        if shoulder_width_cm and shoulder_width_cm != "auto":
            ms = float(shoulder_width_cm) / 100.0
            print(f" Using user shoulder width: {shoulder_width_cm} cm")
        elif patient_height_cm and patient_height_cm != "auto":
            sw_est = float(patient_height_cm) * 0.255
            ms = sw_est / 100.0
            print(f" Estimated from height x 0.255: {sw_est:.1f} cm")
        elif metric_scale and float(metric_scale) > 0:
            ms = float(metric_scale)

        analysis = analyze_reach_and_wipe(
            file_path=str(csv_path),
            cutoff_frequency=cutoff,
            filter_order=order,
            affected_side=affected_side,
            metric_scale=ms,
        )

        if isinstance(analysis, dict) and analysis.get("error"):
            return JSONResponse(status_code=400, content={"error": analysis["error"]})

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

        response = {
            "success": True,
            "phase": phase,
            "csv_filename": csv_path.name,
            "mot_filename": mot_filename,
            **analysis,
        }
        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


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


@app.get("/download-mot/{filename}")
def download_mot(filename: str):
    return _send_file(OUTPUT_DIR, filename, "text/plain")


@app.get("/download-json/{filename}")
def download_json(filename: str):
    return _send_file(OUTPUT_DIR, filename, "application/json")


# ─── Additional Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check with model status."""
    model_path = MODEL_DIR / "pose_landmarker_heavy.task"
    return {
        "status": "ok",
        "service": "Stroke Rehab Backend",
        "version": "1.0.0",
        "models": {
            "pose_landmarker": model_path.exists(),
        },
        "uptime": datetime.now().isoformat(),
    }


@app.get("/debug-video")
def debug_video():
    try:
        import cv2
        video_files = list(UPLOAD_DIR.glob("*"))
        if not video_files:
            return {"error": "No video files in uploads"}
        video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest = video_files[0]
        cap = cv2.VideoCapture(str(latest))
        if not cap.isOpened():
            return {"error": f"Cannot open {latest.name}"}
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        rotation = cap.get(cv2.CAP_PROP_ORIENTATION_META)
        ret, frame = cap.read()
        actual_h, actual_w = frame.shape[:2] if ret else (0, 0)
        cap.release()
        return {
            "file": latest.name,
            "width": w,
            "height": h,
            "actual_width": actual_w,
            "actual_height": actual_h,
            "fps": fps,
            "frames": frames,
            "rotation_meta": rotation,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug-csv")
def debug_csv():
    try:
        import pandas as pd
        import numpy as np
        csv_files = list(OUTPUT_DIR.glob("pre_*.csv"))
        if not csv_files:
            return {"error": "No CSV files in outputs"}
        csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest = csv_files[0]
        df = pd.read_csv(latest)
        key_cols = ["LEFT_WRIST_X", "LEFT_WRIST_Y", "RIGHT_WRIST_X", "RIGHT_WRIST_Y",
                     "LEFT_SHOULDER_X", "LEFT_SHOULDER_Y", "RIGHT_SHOULDER_X", "RIGHT_SHOULDER_Y",
                     "LEFT_HIP_X", "LEFT_HIP_Y", "RIGHT_HIP_X", "RIGHT_HIP_Y",
                     "LEFT_ELBOW_X", "LEFT_ELBOW_Y", "RIGHT_ELBOW_X", "RIGHT_ELBOW_Y"]
        existing = [c for c in key_cols if c in df.columns]
        stats = {
            "file": latest.name,
            "rows": len(df),
        }
        for c in existing:
            vals = df[c].values
            stats[c] = {
                "mean": round(float(vals.mean()), 6),
                "std": round(float(vals.std()), 6),
                "min": round(float(vals.min()), 6),
                "max": round(float(vals.max()), 6),
            }
        stats["first_5_rows"] = df.head(5).to_dict(orient="records")
        stats["row_100"] = df.iloc[100].to_dict() if len(df) > 100 else None
        stats["row_400"] = df.iloc[400].to_dict() if len(df) > 400 else None
        stats["row_700"] = df.iloc[700].to_dict() if len(df) > 700 else None
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.post("/statistics")
async def run_statistics(body: dict):
    """
    Statistical analysis endpoint.
    Expects JSON:
    {
      "group_a": [[val1, val2, ...], ...],  // each inner array = one variable
      "group_b": [[val1, val2, ...], ...],
      "variable_names": ["var1", "var2", ...],
      "paired": false,
      "test_type": "auto"  // "auto", "parametric", "nonparametric"
    }
    Returns p-values, effect sizes, and normality flags.
    """
    try:
        from scipy import stats as sp_stats
        import numpy as np

        ga = body.get("group_a", [])
        gb = body.get("group_b", [])
        names = body.get("variable_names", [f"var{i}" for i in range(len(ga))])
        paired = body.get("paired", False)
        test_type = body.get("test_type", "auto")

        if not ga or not gb:
            raise HTTPException(status_code=400, detail="group_a and group_b are required")

        results = []
        for i in range(len(ga)):
            a = np.array(ga[i], dtype=float)
            b = np.array(gb[i], dtype=float)
            name = names[i] if i < len(names) else f"var{i}"

            # Normality
            norm_a = sp_stats.shapiro(a).pvalue > 0.05 if len(a) >= 3 else None
            norm_b = sp_stats.shapiro(b).pvalue > 0.05 if len(b) >= 3 else None
            both_normal = (norm_a is True and norm_b is True) if test_type == "auto" else (test_type == "parametric")

            # Choose test
            if both_normal:
                if paired and len(a) == len(b):
                    t_stat, p_val = sp_stats.ttest_rel(a, b)
                    d = np.mean(a - b) / np.std(a - b, ddof=1) if np.std(a - b, ddof=1) > 0 else 0
                    test_used = "Paired t-test"
                else:
                    t_stat, p_val = sp_stats.ttest_ind(a, b, equal_var=False)
                    pooled = np.sqrt((np.var(a, ddof=1) * (len(a) - 1) + np.var(b, ddof=1) * (len(b) - 1)) / (len(a) + len(b) - 2))
                    d = (np.mean(a) - np.mean(b)) / pooled if pooled > 0 else 0
                    test_used = "Welch t-test"
                es_type = "Cohen's d"
            else:
                if paired and len(a) == len(b):
                    t_stat, p_val = sp_stats.wilcoxon(a, b)
                    z = sp_stats.norm.ppf(1 - p_val / 2) if p_val < 1 else 0
                    d = z / np.sqrt(len(a)) if len(a) > 0 else 0
                    test_used = "Wilcoxon signed-rank"
                else:
                    t_stat, p_val = sp_stats.mannwhitneyu(a, b, alternative="two-sided")
                    n_total = len(a) + len(b)
                    z = sp_stats.norm.ppf(1 - p_val / 2) if p_val < 1 else 0
                    d = z / np.sqrt(n_total) if n_total > 0 else 0
                    test_used = "Mann-Whitney U"
                es_type = "Rank-biserial r"

            results.append({
                "variable": name,
                "test": test_used,
                "statistic": round(float(t_stat), 4),
                "p_value": round(float(p_val), 4),
                "effect_size": round(float(d), 4),
                "effect_type": es_type,
                "normal_a": bool(norm_a) if norm_a is not None else None,
                "normal_b": bool(norm_b) if norm_b is not None else None,
                "mean_a": round(float(np.mean(a)), 3),
                "mean_b": round(float(np.mean(b)), 3),
                "sd_a": round(float(np.std(a, ddof=1)), 3),
                "sd_b": round(float(np.std(b, ddof=1)), 3),
                "n_a": int(len(a)),
                "n_b": int(len(b)),
            })

        return {"results": results}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))






# ─── Static Frontend (for single-port / remote/ngrok access) ──────────
FRONTEND_BUILD = Path(__file__).resolve().parent / "frontend" / "build"
if FRONTEND_BUILD.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="frontend")
    print(f"Frontend : {FRONTEND_BUILD} (mounted at /)")

# ─── Run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Stroke Rehab Backend Starting...")
    print(f"URL      : http://localhost:8000")
    print(f"API Docs : http://localhost:8000/docs")
    print("="*60 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
