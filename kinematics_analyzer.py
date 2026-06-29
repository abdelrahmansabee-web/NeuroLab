# API bridge → R an/stroke_kinematic_pipeline.py

import sys
import traceback
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent
_RAN = _ROOT.parent / "R an" if (_ROOT.parent / "R an" / "stroke_kinematic_pipeline.py").exists() else _ROOT
if str(_RAN) not in sys.path:
    sys.path.insert(0, str(_RAN))

from stroke_kinematic_pipeline import analyze_stroke_kinematic_csv  # noqa: E402


def analyze_reach_and_wipe(
    file_path: str,
    cutoff_frequency: float = 4.0,
    filter_order: int = 4,
    affected_side: str = "auto",
    metric_scale: float = 0.0,
    sex: str = "unknown",
    trial_count: int = 1,
    best_trial_metric: str = "sparc",
    phase_name: str = "UNKNOWN",
    camera_view: str = "auto",
    frame_width: int = 1920,
    frame_height: int = 1080,
    velocity_threshold_px_s: float = 5.0,
    video_path: Optional[str] = None,
) -> dict:
    """Run view-agnostic stroke kinematic pipeline (SPARC + 5 secondary vars)."""
    try:
        r = analyze_stroke_kinematic_csv(
            file_path,
            affected_side=affected_side,
            metric_scale=metric_scale,
            frame_width=frame_width,
            frame_height=frame_height,
            velocity_threshold_px_s=velocity_threshold_px_s,
            name=phase_name or Path(file_path).stem,
            camera_view=camera_view,
            video_path=video_path,
        )
        if r.get("error"):
            return {"error": r["error"]}

        # Legacy aliases for downstream scripts / older exports
        r["smoothness_pause_pct"] = None  # deprecated
        r["total_trunk_palm_ratio"] = r.get("trunk_ratio")
        r["total_duration_s"] = r.get("movement_time_sec")
        r["total_peak_velocity"] = r.get("peak_velocity_cm_s") or r.get("peak_velocity_px_s")
        r["total_max_elbow_deg"] = r.get("elbow_angle_max")
        r["hand_disp_sw"] = r.get("hand_displacement_norm")
        r["lat_range_sw"] = r.get("hand_displacement_norm")
        r["duration"] = r.get("movement_time_sec")
        return r
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def analyze_neuro_phase(
    video_path: str,
    phase: str = "pre",
    stroke_side: str = "auto",
) -> dict:
    """Run neuro_kinematics.py on one video (table calibration + MediaPipe)."""
    try:
        from neuro_kinematics import (
            analyze_single_phase,
            kinematic_values_to_api,
            AffectedSideDetector,
        )

        affected = None
        healthy = None
        if stroke_side and stroke_side.lower() in ("left", "right"):
            affected = stroke_side.lower()
            healthy = "right" if affected == "left" else "left"

        kv, meta = analyze_single_phase(
            video_path,
            phase=phase,
            affected_side=affected,
            healthy_side=healthy,
        )
        out = kinematic_values_to_api(kv, side=meta.get("side_analyzed", affected or "right"))
        out["side_detection"] = meta
        out["phase"] = phase
        return out
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


def analyze_neuro_session(
    healthy_path: str,
    post_path: str,
    pre_path: str,
) -> dict:
    """Run full Pre/Post/Healthy session via neuro_kinematics.analyze_patient_session."""
    try:
        from neuro_kinematics import (
            analyze_single_phase,
            kinematic_values_to_api,
        )

        # Detect affected side from pre video
        pre_kv, pre_meta = analyze_single_phase(pre_path, phase="pre")
        affected = pre_meta.get("affected_side")
        healthy = pre_meta.get("healthy_side")

        # Analyze post and healthy using the detected sides
        post_kv, _ = analyze_single_phase(
            post_path, phase="post", affected_side=affected, healthy_side=healthy
        )
        healthy_kv, _ = analyze_single_phase(
            healthy_path, phase="healthy", affected_side=affected, healthy_side=healthy
        )

        # Build comparison results
        from neuro_kinematics import compare_conditions
        comparison = compare_conditions(healthy_kv, post_kv, pre_kv)

        return {
            "comparison": comparison,
            "side_detection": pre_meta,
            "pre": kinematic_values_to_api(pre_kv, affected or "right"),
            "post": kinematic_values_to_api(post_kv, affected or "right"),
            "healthy": kinematic_values_to_api(healthy_kv, healthy or "left"),
            "baseline": kinematic_values_to_api(healthy_kv, healthy or "left"),
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
