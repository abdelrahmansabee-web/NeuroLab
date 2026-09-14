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
    clinical_task: str = "study_reach_grasp",
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
            clinical_task=clinical_task,
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
