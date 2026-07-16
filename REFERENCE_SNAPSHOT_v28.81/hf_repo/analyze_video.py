# -*- coding: utf-8 -*-
"""
 analyze_video.py

 Literature-compatible kinematic analysis for a single reach video.
 Locks camera view, affected side, and analysis parameters so results are
 comparable across patients.

 Usage:
   python analyze_video.py --video path/to/video.mov --side right --view oblique --label pre --out report.json

 Required literature protocol:
   - Camera: smartphone on tripod, fixed distance, fixed height, do NOT move it.
   - View: sagittal (side) of the reaching arm is best; if frontal/oblique, use the SAME view for all videos.
   - Task: one clear reach to a target, then return. No talking, no extra movements.
   - Duration: 3–8 seconds per reach. Crop to the reach if the video is longer.
   - Lighting: bright, even, no shadows.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add hf_repo to path if running from elsewhere
REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import numpy as np
from stroke_kinematic_pipeline import analyze_trial, interpret_sparc


def main():
    parser = argparse.ArgumentParser(description="Analyze one reach video with locked literature parameters.")
    parser.add_argument("--video", required=True, help="Path to video file.")
    parser.add_argument("--side", required=True, choices=["left", "right"], help="Side being analyzed.")
    parser.add_argument("--view", required=True, choices=["frontal", "oblique", "sagittal"], help="Camera view.")
    parser.add_argument("--label", default="trial", help="Trial label (pre/post/healthy/affected).")
    parser.add_argument("--crop-start", type=float, default=None, help="Start time in seconds (optional).")
    parser.add_argument("--crop-end", type=float, default=None, help="End time in seconds (optional).")
    parser.add_argument("--out", default=None, help="Output JSON path.")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    result = analyze_trial(
        str(video_path),
        affected_side=args.side,
        camera_view=args.view,
        trial_role=args.label,
    )

    # Build a clean report with finite values rounded
    def _r(v, ndigits=4):
        if v is None or not np.isfinite(float(v)):
            return None
        return round(float(v), ndigits)

    sparc_val = result.get("sparc")
    interpretation = interpret_sparc(sparc_val) if sparc_val is not None and np.isfinite(float(sparc_val)) else None

    report = {
        "video": str(video_path),
        "label": args.label,
        "side": args.side,
        "camera_view": args.view,
        "sparc": _r(sparc_val, 4),
        "sparc_interpretation": interpretation.get("rating") if isinstance(interpretation, dict) else None,
        "reach_amplitude_sw": _r(result.get("reach_amplitude_sw"), 3),
        "native_reach_amplitude_sw": _r(result.get("native_reach_amplitude_sw"), 3),
        "movement_time_sec": _r(result.get("movement_time_sec"), 3),
        "peak_velocity_cm_s": _r(result.get("peak_velocity_cm_s"), 2),
        "trunk_ratio": _r(result.get("trunk_ratio"), 4),
        "sparc_window": f"{result.get('sparc_window_onset_frame')}-{result.get('sparc_window_offset_frame')}",
        "fs_hz": result.get("fs_hz"),
        "native_fs_hz": result.get("native_fs_hz"),
        "sparc_method": result.get("sparc_method"),
        "valid_for_comparison": bool(
            result.get("reach_amplitude_sw") is not None
            and result.get("reach_amplitude_sw") >= 0.12
            and result.get("movement_time_sec") is not None
            and 0.5 <= result.get("movement_time_sec") <= 5.0
        ),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved report to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
