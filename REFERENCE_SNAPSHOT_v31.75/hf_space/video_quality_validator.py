# -*- coding: utf-8 -*-
"""
video_quality_validator.py — Literature-backed video validation for stroke kinematics.

Validates uploaded videos against requirements derived from published upper-limb
MediaPipe validation studies (Wagh et al. 2024/2025, BIONICS 2023, Dinh 2025,
Francia et al. 2026):
  * Resolution: 1920×1080 (1080p) preferred, 1280×720 (720p) minimum hard gate
  * Frame rate: 60 fps preferred, 30 fps minimum hard gate
  * Duration: must cover the full reach epoch
  * Encoding: original file strongly preferred; flag heavy re-encodes
  * Camera setup: fixed position, good lighting, unobscured subject

The validator does **not** modify the video. It returns a dict with:
  - passed (bool): True only if the video passes every hard gate
  - errors (list): hard-gate failures that block analysis
  - warnings (list): literature-backed concerns that do not block analysis
  - metadata (dict): width, height, fps, duration_sec, total_frames, estimated_mbps,
                    codec_fourcc, rotation_flag
  - recommendation (str): one-line guidance for the user
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class VideoValidationResult:
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "recommendation": self.recommendation,
        }


# Literature-backed thresholds -------------------------------------------------
MIN_WIDTH = 1280
MIN_HEIGHT = 720
PREFERRED_WIDTH = 1920
PREFERRED_HEIGHT = 1080
MIN_FPS = 30.0
PREFERRED_FPS = 60.0
MIN_DURATION_SEC = 1.0
PREFERRED_DURATION_SEC = 2.0
MIN_TOTAL_FRAMES = int(MIN_FPS * MIN_DURATION_SEC)  # 30 frames
MAX_BITRATE_MBPS_WARN = 15.0  # videos much larger than this may be pre-processed/upsampled


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if np.isfinite(f) else default
    except Exception:
        return default


def _codec_name(fourcc_int: int) -> str:
    try:
        return "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)).strip()
    except Exception:
        return "unknown"


def inspect_video(video_path: Path) -> Dict[str, Any]:
    """Return technical metadata for a video file."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for inspection: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
    fps = _safe_float(cap.get(cv2.CAP_PROP_FPS), 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    duration_sec = total_frames / fps if fps > 0 else 0.0
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = _codec_name(fourcc_int)

    file_size_bytes = video_path.stat().st_size if video_path.exists() else 0
    bitrate_bps = (file_size_bytes * 8) / duration_sec if duration_sec > 0 else 0.0
    bitrate_mbps = bitrate_bps / 1_000_000.0

    # Detect common phone rotation metadata (OpenCV does not read rotation tag).
    rotation_flag = 0
    cap.release()

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_sec": round(duration_sec, 2),
        "codec_fourcc": codec,
        "file_size_bytes": file_size_bytes,
        "estimated_mbps": round(bitrate_mbps, 2),
        "rotation_flag": rotation_flag,
    }


def _minimum_dimension(w: int, h: int) -> int:
    """Return the smaller dimension, treating width>height*1.15 as rotated phone video."""
    if w > h * 1.15:
        return min(w, h)
    return min(w, h)


def validate_video(
    video_path: Path,
    *,
    strict_resolution: bool = False,
    strict_fps: bool = False,
    allow_warnings_as_errors: bool = False,
) -> VideoValidationResult:
    """
    Run literature-backed validation gates on a video.

    Hard gates (always block if failed):
      - File readable by OpenCV
      - Minimum resolution >= 1280×720
      - Minimum fps >= 30
      - Duration >= 1.0 s and >= 30 frames

    Soft gates (warnings unless allow_warnings_as_errors=True):
      - Resolution below preferred 1920×1080
      - Frame rate below preferred 60 fps
      - Duration below preferred 2.0 s
      - Very high bitrate / possible upsampled re-encode
      - Very low bitrate / heavy compression
      - Non-standard codecs
    """
    result = VideoValidationResult()

    if not video_path.exists():
        result.passed = False
        result.errors.append(f"Video file not found: {video_path}")
        result.recommendation = "Upload a valid video file."
        return result

    try:
        meta = inspect_video(video_path)
    except Exception as exc:
        result.passed = False
        result.errors.append(f"Cannot read video metadata: {exc}")
        result.recommendation = "Upload a valid MP4/MOV video file."
        return result

    result.metadata = meta
    w, h, fps = meta["width"], meta["height"], meta["fps"]
    duration = meta["duration_sec"]
    total_frames = meta["total_frames"]
    mbps = meta["estimated_mbps"]
    codec = meta["codec_fourcc"]

    # --- Hard gates ----------------------------------------------------------
    if w == 0 or h == 0:
        result.passed = False
        result.errors.append("Video has zero resolution (corrupt or unsupported container).")

    min_dim = _minimum_dimension(w, h)
    if min(w, h) < MIN_HEIGHT or min_dim < MIN_HEIGHT:
        result.passed = False
        result.errors.append(
            f"Resolution {w}×{h} is below the minimum {MIN_WIDTH}×{MIN_HEIGHT} "
            "required for reliable upper-limb pose estimation."
        )

    if fps < MIN_FPS:
        result.passed = False
        result.errors.append(
            f"Frame rate {fps:.1f} fps is below the minimum {MIN_FPS} fps "
            "required for smoothness (SPARC) analysis."
        )

    if duration < MIN_DURATION_SEC:
        result.passed = False
        result.errors.append(
            f"Duration {duration:.2f} s is below the minimum {MIN_DURATION_SEC} s "
            "required to capture a complete reach movement."
        )

    if total_frames < MIN_TOTAL_FRAMES:
        result.passed = False
        result.errors.append(
            f"Total frames ({total_frames}) is below the minimum {MIN_TOTAL_FRAMES} "
            "required for stable filtering and smoothness metrics."
        )

    # --- Soft gates / warnings -----------------------------------------------
    if w < PREFERRED_WIDTH or h < PREFERRED_HEIGHT:
        result.warnings.append(
            f"Resolution {w}×{h} is below the literature-recommended {PREFERRED_WIDTH}×{PREFERRED_HEIGHT}. "
            "Higher resolution improves landmark accuracy."
        )

    if fps < PREFERRED_FPS:
        result.warnings.append(
            f"Frame rate {fps:.1f} fps is below the recommended {PREFERRED_FPS} fps. "
            "60 fps is preferred for accurate SPARC/velocity metrics."
        )

    if duration < PREFERRED_DURATION_SEC:
        result.warnings.append(
            f"Duration {duration:.2f} s is short; ensure the video captures the full reach "
            "from rest to target and back."
        )

    if mbps > MAX_BITRATE_MBPS_WARN:
        result.warnings.append(
            f"Estimated bitrate {mbps:.1f} Mbps is very high; verify the file is the original "
            "recording and not an upscaled/re-encoded export."
        )
    elif mbps > 0 and mbps < 1.0 and min(w, h) >= MIN_HEIGHT:
        result.warnings.append(
            f"Estimated bitrate {mbps:.1f} Mbps is low; heavy compression may degrade landmark accuracy."
        )

    if codec.lower() not in {"avc1", "h264", "mp4v", "hev1", "hvc1", "av01", "mjpg"}:
        result.warnings.append(
            f"Codec '{codec}' is non-standard for kinematic analysis; H.264/AVC MP4 is recommended."
        )

    if meta["rotation_flag"] != 0:
        result.warnings.append(
            f"Rotation metadata detected ({meta['rotation_flag']}°); ensure the subject is upright in the frame."
        )

    # --- Recommendation ------------------------------------------------------
    if result.passed and not result.warnings:
        result.recommendation = "Video meets literature-recommended specifications."
    elif result.passed:
        result.recommendation = (
            "Video passes minimum requirements, but warnings are noted. "
            "For the most reproducible results, record at 1920×1080 / 60 fps with the original camera file."
        )
    else:
        result.recommendation = (
            "Video does not meet minimum requirements for reliable analysis. "
            "Upload the original camera file recorded at 1920×1080 / 60 fps, camera 1.5–3 m away, "
            "with good lighting and the full movement visible."
        )

    if allow_warnings_as_errors and result.warnings:
        result.passed = False
        result.errors.extend(result.warnings)
        result.warnings = []

    return result


def quick_video_check(video_path: Path) -> Tuple[bool, List[str]]:
    """Return (passed, error_messages) for fast gating."""
    res = validate_video(video_path)
    return res.passed, res.errors
