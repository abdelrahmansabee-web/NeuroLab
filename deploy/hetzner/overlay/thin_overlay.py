"""Shrink overlay JSON so iPad Safari does not freeze on a 2–3 MB payload."""
from __future__ import annotations

import math
from typing import Any, Dict, List


def thin_overlay_payload(data: Dict[str, Any], max_frames: int = 360) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data
    frames = data.get("frames")
    if not isinstance(frames, list) or len(frames) <= max_frames:
        return data
    stride = max(2, int(math.ceil(len(frames) / float(max_frames))))
    out = dict(data)
    out["frames"] = frames[::stride]
    out["overlay_frame_stride"] = stride
    out["overlay_frames_full"] = len(frames)
    for key in ("velocity_profile", "elbow_angle_profile", "trunk_x_profile", "tremor_profile"):
        prof = out.get(key)
        if not isinstance(prof, dict):
            continue
        t_vals: List[Any] = prof.get("t") or []
        v_vals: List[Any] = prof.get("v") or []
        if isinstance(t_vals, list) and t_vals:
            out[key] = {"t": t_vals[::stride], "v": v_vals[::stride] if isinstance(v_vals, list) else v_vals}
    return out
