# -*- coding: utf-8 -*-
"""Shared video rotation / stream size probes (ffprobe + ffmpeg stderr fallback)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def _find_ffprobe() -> str | None:
    for name in ("ffprobe", "ffprobe.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _find_ffmpeg() -> str | None:
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            return p
    try:
        from unified_validation_renderer import _find_ffmpeg as _uv_ff

        return _uv_ff()
    except Exception:
        return None


def _normalize_angle_deg(angle: float) -> int:
    a = int(round(float(angle))) % 360
    if a < 0:
        a = (360 + a) % 360
    return a


def probe_rotation_deg(video_path: Path | str) -> int:
    """Degrees clockwise to apply to raw pixels for upright display (0, 90, 180, 270)."""
    path = Path(video_path)
    if not path.exists():
        return 0

    ffprobe = _find_ffprobe()
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:stream_side_data=rotation:stream_tags=rotate",
                "-show_entries",
                "stream_tags=rotate",
                "-of",
                "json",
                str(path),
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                streams = data.get("streams") or []
                if streams:
                    st = streams[0]
                    tags = st.get("tags") or {}
                    if tags.get("rotate") not in (None, "", "0"):
                        return _normalize_angle_deg(float(tags["rotate"]))
                    for sd in st.get("side_data_list") or []:
                        if sd.get("rotation") not in (None, "", "0"):
                            return _normalize_angle_deg(float(sd["rotation"]))
        except Exception:
            pass

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return 0
    cmd = [ffmpeg, "-hide_banner", "-i", str(path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
    output = result.stderr or result.stdout or ""
    for pat in (
        r"rotate\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        r"displaymatrix: rotation of (-?\d+(?:\.\d+)?)",
        r"Display Matrix.*?rotation of (-?\d+(?:\.\d+)?)",
    ):
        m = re.search(pat, output, re.IGNORECASE)
        if m:
            return _normalize_angle_deg(float(m.group(1)))
    return 0


def probe_stream_size(video_path: Path | str) -> Tuple[float, float]:
    path = Path(video_path)
    if not path.exists():
        return 1920.0, 1080.0
    ffprobe = _find_ffprobe()
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(path),
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                streams = (json.loads(result.stdout).get("streams") or [{}])
                w = float(streams[0].get("width") or 1920)
                h = float(streams[0].get("height") or 1080)
                return w, h
        except Exception:
            pass
    return 1920.0, 1080.0


def display_frame_size(video_path: Path | str, orientation_deg: int) -> Tuple[float, float]:
    w, h = probe_stream_size(video_path)
    if orientation_deg in (90, 270):
        return h, w
    return w, h
