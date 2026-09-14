# -*- coding: utf-8 -*-
"""
Multi-phase clinical task analysis (reach → grasp → drink/brush → return).

Uses chronological movement bouts from palm speed; metrics per phase match study kinematics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from motion_invariants import _list_segments, palm_image_speed

CLINICAL_TASKS: Dict[str, Dict[str, Any]] = {
    "study_reach_grasp": {
        "label_en": "Reach to grasp (study protocol)",
        "label_tr": "Reach to grasp (çalışma)",
        "phase_ids": ["reach_grasp"],
        "multi_bout": False,
    },
    "forearm_pronation_supination": {
        "label_en": "Forearm pronation / supination",
        "label_tr": "Forearm pronation / supination",
        "phase_ids": ["forearm_rotation"],
        "multi_bout": False,
        "window_signal": "forearm_rotation",
        "expected_rom_deg": [40, 180],
    },
    "shoulder_abduction_active": {
        "label_en": "Active shoulder abduction",
        "label_tr": "Active shoulder abduction",
        "phase_ids": ["shoulder_abduction"],
        "multi_bout": False,
        "window_signal": "shoulder_abduction",
        "expected_rom_deg": [30, 120],
    },
    "fine_motor_pincer": {
        "label_en": "Fine motor — pincer / pinch",
        "label_tr": "Fine motor — pincer / pinch",
        "phase_ids": ["pincer_pinch"],
        "multi_bout": False,
        "window_signal": "pinch_aperture",
        "expected_rom_sw": [0.02, 0.35],
    },
    "reach_grasp_drink_return": {
        "label_en": "Reach → grasp → drink → return",
        "label_tr": "Reach → grasp → drink → return",
        "phase_ids": ["reach_grasp", "transport_drink", "return"],
        "multi_bout": True,
    },
    "reach_grasp_brush_return": {
        "label_en": "Reach → grasp → brush teeth → return",
        "label_tr": "Reach → grasp → brush → return",
        "phase_ids": ["reach_grasp", "transport_brush", "return"],
        "multi_bout": True,
    },
}


def resolve_clinical_movement_window(
    clinical_task: str,
    *,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float],
    opp_shoulder_x: Optional[np.ndarray],
    opp_shoulder_y: Optional[np.ndarray],
    index_x: Optional[np.ndarray],
    index_y: Optional[np.ndarray],
    pinky_x: Optional[np.ndarray],
    pinky_y: Optional[np.ndarray],
    thumb_x: Optional[np.ndarray],
    thumb_y: Optional[np.ndarray],
    hand3d: Optional[Dict],
    arm3d: Optional[Dict],
    arm_world: Optional[Dict] = None,
    hand_world: Optional[Dict] = None,
    affected_side: str = "auto",
    velocity_threshold: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Task-specific movement window (max-ROM segment on joint or pinch signal).
    Returns {start, end, rom, expected_rom, window_signal} or None for default reach window.
    """
    task_key = (clinical_task or "study_reach_grasp").strip().lower()
    spec = CLINICAL_TASKS.get(task_key, {})
    signal_name = spec.get("window_signal")
    if not signal_name:
        return None

    from movement_profile import find_peak_rom_window

    n = len(palm_x)
    full_end = max(0, n - 1)
    signal = np.full(n, np.nan)

    if signal_name == "forearm_rotation":
        if hand_world is not None and arm_world is not None:
            from movement_profile import _forearm_rotation_series

            try:
                signal = _forearm_rotation_series(
                    arm_world["elbow_x"], arm_world["elbow_y"], arm_world["elbow_z"],
                    arm_world["wrist_x"], arm_world["wrist_y"], arm_world["wrist_z"],
                    hand_world["index_x"], hand_world["index_y"], hand_world["index_z"],
                    hand_world["pinky_x"], hand_world["pinky_y"], hand_world["pinky_z"],
                    0, full_end,
                )
            except (KeyError, TypeError):
                pass
        if not np.any(np.isfinite(signal)) and hand3d and arm3d:
            from movement_profile import _forearm_rotation_series

            signal = _forearm_rotation_series(
                arm3d["elbow_x"], arm3d["elbow_y"], arm3d["elbow_z"],
                arm3d["wrist_x"], arm3d["wrist_y"], arm3d["wrist_z"],
                hand3d["index_x"], hand3d["index_y"], hand3d["index_z"],
                hand3d["pinky_x"], hand3d["pinky_y"], hand3d["pinky_z"],
                0, full_end,
            )

    elif signal_name == "shoulder_abduction":
        if hand_world is not None and arm_world is not None and "left_shoulder_x" in hand_world:
            from movement_profile import _shoulder_abduction_world_series

            signal = _shoulder_abduction_world_series(affected_side, hand_world, arm_world, 0, full_end)
        elif opp_shoulder_x is not None and opp_shoulder_y is not None:
            from movement_profile import _shoulder_abduction_series

            signal = _shoulder_abduction_series(
                opp_shoulder_x, opp_shoulder_y, shoulder_x, shoulder_y, elbow_x, elbow_y, 0, full_end,
            )

    elif signal_name == "pinch_aperture":
        if hand3d is not None and "index_tip_x" in hand3d and "thumb_tip_x" in hand3d:
            signal = np.hypot(
                hand3d["index_tip_x"] - hand3d["thumb_tip_x"],
                hand3d["index_tip_y"] - hand3d["thumb_tip_y"],
            )
        elif index_x is not None and thumb_x is not None and index_y is not None and thumb_y is not None:
            signal = np.hypot(index_x - thumb_x, index_y - thumb_y)
        sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
        if np.isfinite(sw) and sw > 0:
            signal = signal / sw

    if not np.any(np.isfinite(signal)):
        spd = palm_image_speed(palm_x, palm_y, fs)
        segs = _list_segments(
            spd, palm_x, palm_y, fs, velocity_threshold, min_segment_frames=max(8, int(0.15 * fs)),
        )
        if segs:
            s, e = int(segs[0]["start"]), int(segs[0]["end"])
            return {
                "start": s,
                "end": e,
                "rom": None,
                "window_signal": signal_name,
                "window_fallback": "palm_speed",
                "expected_rom_deg": spec.get("expected_rom_deg"),
                "expected_rom_sw": spec.get("expected_rom_sw"),
            }
        return None

    s, e, rom = find_peak_rom_window(signal, fs, min_duration_s=0.2)
    return {
        "start": s,
        "end": e,
        "rom": round(float(rom), 2) if np.isfinite(rom) else None,
        "window_signal": signal_name,
        "expected_rom_deg": spec.get("expected_rom_deg"),
        "expected_rom_sw": spec.get("expected_rom_sw"),
    }


def _segment_metrics(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float],
    start: int,
    end: int,
    camera_view: str,
    arm3d: Optional[Dict],
    trunk_ratio: float,
    trunk_cheat: float,
    velocity_threshold: float,
    opp_shoulder_x: Optional[np.ndarray] = None,
    opp_shoulder_y: Optional[np.ndarray] = None,
    index_x: Optional[np.ndarray] = None,
    index_y: Optional[np.ndarray] = None,
    pinky_x: Optional[np.ndarray] = None,
    pinky_y: Optional[np.ndarray] = None,
    thumb_x: Optional[np.ndarray] = None,
    thumb_y: Optional[np.ndarray] = None,
    hand3d: Optional[Dict] = None,
    arm_world: Optional[Dict] = None,
    hand_world: Optional[Dict] = None,
    affected_side: str = "auto",
    clinical_task: Optional[str] = None,
) -> Dict[str, Any]:
    from movement_profile import build_movement_profile

    prof = build_movement_profile(
        palm_x=palm_x,
        palm_y=palm_y,
        wrist_x=wrist_x,
        wrist_y=wrist_y,
        elbow_x=elbow_x,
        elbow_y=elbow_y,
        shoulder_x=shoulder_x,
        shoulder_y=shoulder_y,
        trunk_x=trunk_x,
        trunk_y=trunk_y,
        fs=fs,
        shoulder_width=shoulder_width,
        start_idx=int(start),
        end_idx=int(end),
        camera_view=camera_view,
        arm3d=arm3d,
        trunk_ratio=trunk_ratio,
        trunk_cheat_ratio=trunk_cheat,
        velocity_threshold=velocity_threshold,
        opp_shoulder_x=opp_shoulder_x,
        opp_shoulder_y=opp_shoulder_y,
        index_x=index_x,
        index_y=index_y,
        pinky_x=pinky_x,
        pinky_y=pinky_y,
        thumb_x=thumb_x,
        thumb_y=thumb_y,
        hand3d=hand3d,
        arm_world=arm_world,
        hand_world=hand_world,
        affected_side=affected_side,
        clinical_task=clinical_task,
    )
    return prof


def _reclassify_transport_pauses_as_functional(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Mouth/face hold is functional time — do not count as path pause."""
    m = dict(metrics or {})
    total = m.get("pause_time_sec_total")
    if total is None:
        total = m.get("pause_time_sec")
    stops_total = m.get("number_of_stops_total")
    if stops_total is None:
        stops_total = m.get("number_of_stops")
    try:
        total_f = float(total) if total is not None else 0.0
    except (TypeError, ValueError):
        total_f = 0.0
    try:
        stops_i = int(stops_total) if stops_total is not None else 0
    except (TypeError, ValueError):
        stops_i = 0
    m["pause_time_sec_total"] = round(total_f, 3)
    m["number_of_stops_total"] = stops_i
    m["grasp_dwell_sec"] = round(total_f, 3)
    m["grasp_dwell_stops"] = stops_i
    m["pause_time_sec"] = 0.0
    m["number_of_stops"] = 0
    m["terminal_dwell_excluded"] = True
    m["functional_hold_phase"] = True
    return m


def _pick_phase_windows(
    segments: List[Dict[str, float]],
    phase_ids: List[str],
) -> List[Tuple[str, int, int]]:
    """Map movement bouts to named phases (chronological)."""
    if not segments:
        return []
    segs = sorted(segments, key=lambda s: s["start"])
    n = len(segs)
    out: List[Tuple[str, int, int]] = []

    if len(phase_ids) == 1:
        s = segs[0]
        return [(phase_ids[0], int(s["start"]), int(s["end"]))]

    if n == 1:
        s = segs[0]
        return [(phase_ids[0], int(s["start"]), int(s["end"]))]

    if n == 2:
        out.append((phase_ids[0], int(segs[0]["start"]), int(segs[0]["end"])))
        out.append((phase_ids[-1], int(segs[1]["start"]), int(segs[1]["end"])))
        return out

    # 3+ bouts: first = reach, last = return, middle merged = transport
    transport_id = phase_ids[1] if len(phase_ids) > 2 else phase_ids[1]
    out.append((phase_ids[0], int(segs[0]["start"]), int(segs[0]["end"])))
    mid_start = int(segs[1]["start"])
    mid_end = int(segs[-2]["end"])
    out.append((transport_id, mid_start, mid_end))
    out.append((phase_ids[-1], int(segs[-1]["start"]), int(segs[-1]["end"])))
    return out


def _count_sip_bouts_in_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    start: int,
    end: int,
    velocity_threshold: float = 5.0,
    metrics: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Estimate mouth approaches (sips) in a transport window.

    Uses distinct palm-speed bouts; falls back to mouth-hold count from pause splits.
    Extra sips must NOT inflate primary reach-window NVP/pause.
    """
    start = int(max(0, start))
    end = int(max(start, end))
    n = len(palm_x)
    if end >= n:
        end = n - 1
    if end <= start or fs <= 0:
        return 1

    spd_full = palm_image_speed(palm_x, palm_y, fs)
    segs = _list_segments(
        spd_full,
        palm_x,
        palm_y,
        fs,
        velocity_threshold,
        min_segment_frames=max(6, int(0.15 * fs)),
    )
    in_win = [s for s in segs if int(s["end"]) >= start and int(s["start"]) <= end]
    from_speed = len(in_win)

    from_holds = 0
    if metrics:
        for key in ("grasp_dwell_stops", "number_of_stops_total", "number_of_stops"):
            try:
                v = int(metrics.get(key) or 0)
                if v > from_holds:
                    from_holds = v
            except (TypeError, ValueError):
                pass

    return max(1, from_speed, from_holds)


def _palm_lift_height_sw(
    palm_y: np.ndarray,
    start: int,
    end: int,
    shoulder_width: Optional[float],
) -> Dict[str, Any]:
    """
    Vertical rise of the palm during a phase (table → peak height).

    Image y increases downward, so a lift reduces palm_y.
    Height is reported in shoulder-width units (SW).
    """
    start = int(max(0, start))
    end = int(max(start, end))
    n = len(palm_y)
    if end >= n:
        end = n - 1
    if end <= start:
        return {}
    seg = np.asarray(palm_y[start : end + 1], dtype=float)
    if not np.any(np.isfinite(seg)):
        return {}
    # Baseline near phase onset (table / start of lift)
    head = seg[: max(1, min(len(seg), max(3, len(seg) // 8)))]
    base = float(np.nanmedian(head))
    peak = float(np.nanmin(seg))  # highest point in image coords
    if not np.isfinite(base) or not np.isfinite(peak):
        return {}
    rise_px = float(base - peak)  # positive when hand rises
    if rise_px < 0:
        rise_px = 0.0
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    out: Dict[str, Any] = {
        "lift_height_px": round(rise_px, 2),
    }
    if np.isfinite(sw) and sw > 0:
        out["lift_height_sw"] = round(rise_px / sw, 4)
    return out


def _phase_nvp(phases_out: List[Dict[str, Any]], phase_id: str) -> Optional[int]:
    ph = next((p for p in (phases_out or []) if p.get("id") == phase_id), None)
    if not ph:
        return None
    m = ph.get("metrics") or {}
    try:
        v = m.get("nvp")
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _task_completion_fields(
    spec: Dict[str, Any],
    phases_out: List[Dict[str, Any]],
    movement_bouts: int,
) -> Dict[str, Any]:
    """Hierarchical flags: completion vs reach-window smoothness."""
    expected = list(spec.get("phase_ids") or ["reach_grasp"])
    detected = [p.get("id") for p in (phases_out or []) if p.get("id")]
    complete = bool(expected) and all(pid in detected for pid in expected)
    if spec.get("multi_bout") and not detected:
        complete = False
    ratio = (len(detected) / float(len(expected))) if expected else None
    if ratio is not None:
        ratio = round(min(1.0, float(ratio)), 3)
    reach = next((p for p in (phases_out or []) if p.get("id") == "reach_grasp"), None)
    if reach is None and phases_out:
        reach = phases_out[0]
    reach_m = (reach or {}).get("metrics") or {}
    grasp_dwell = reach_m.get("grasp_dwell_sec")
    grasp_stops = reach_m.get("grasp_dwell_stops")
    sip_bout_count = None
    # Mouth/face hold during transport is functional time, not path pause.
    functional_extra = 0.0
    transport = next(
        (p for p in (phases_out or []) if str(p.get("id") or "").startswith("transport_")),
        None,
    )
    ret = next((p for p in (phases_out or []) if p.get("id") == "return"), None)
    nvp_reach = reach_m.get("nvp")
    nvp_transport = None
    nvp_return = None
    lift_height_sw = None
    lift_height_px = None
    if transport:
        tm = transport.get("metrics") or {}
        try:
            if tm.get("nvp") is not None:
                nvp_transport = int(tm["nvp"])
        except (TypeError, ValueError):
            pass
        if tm.get("lift_height_sw") is not None:
            lift_height_sw = tm.get("lift_height_sw")
        if tm.get("lift_height_px") is not None:
            lift_height_px = tm.get("lift_height_px")
        sc = tm.get("sip_bout_count")
        try:
            if sc is not None:
                sip_bout_count = max(int(sip_bout_count or 0), int(sc))
        except (TypeError, ValueError):
            pass
        t = tm.get("pause_time_sec_total")
        if t is None:
            t = tm.get("pause_time_sec")
        try:
            if t is not None and np.isfinite(float(t)):
                functional_extra += float(t)
        except (TypeError, ValueError):
            pass
    if ret:
        rm = ret.get("metrics") or {}
        try:
            if rm.get("nvp") is not None:
                nvp_return = int(rm["nvp"])
        except (TypeError, ValueError):
            pass

    # Also scan other transport phases for sip/functional (brush)
    for p in phases_out or []:
        pid = str(p.get("id") or "")
        if not pid.startswith("transport_"):
            continue
        if transport is not None and p is transport:
            continue
        m = p.get("metrics") or {}
        sc = m.get("sip_bout_count")
        try:
            if sc is not None:
                sip_bout_count = max(int(sip_bout_count or 0), int(sc))
        except (TypeError, ValueError):
            pass
        t = m.get("pause_time_sec_total")
        if t is None:
            t = m.get("pause_time_sec")
        try:
            if t is not None and np.isfinite(float(t)):
                functional_extra += float(t)
        except (TypeError, ValueError):
            pass

    nvp_parts = []
    for v in (nvp_reach, nvp_transport, nvp_return):
        if v is not None:
            try:
                nvp_parts.append(int(v))
            except (TypeError, ValueError):
                pass
    nvp_total = int(sum(nvp_parts)) if nvp_parts else None

    path_pause_parts = []
    path_stops_parts = []
    for p in phases_out or []:
        pid = str(p.get("id") or "")
        if pid.startswith("transport_"):
            continue
        m = p.get("metrics") or {}
        if m.get("pause_time_sec") is not None:
            try:
                path_pause_parts.append(float(m["pause_time_sec"]))
            except (TypeError, ValueError):
                pass
        if m.get("number_of_stops") is not None:
            try:
                path_stops_parts.append(int(m["number_of_stops"]))
            except (TypeError, ValueError):
                pass

    out = {
        "task_complete": bool(complete),
        "task_completion_ratio": ratio,
        "expected_phase_ids": expected,
        "completed_phase_ids": detected,
        "nvp_reach": nvp_reach,
        "nvp_transport": nvp_transport,
        "nvp_drink": nvp_transport if transport and str(transport.get("id")) == "transport_drink" else None,
        "nvp_return": nvp_return,
        "nvp_total": nvp_total,
        "lift_height_sw": lift_height_sw,
        "lift_height_px": lift_height_px,
        "drink_lift_height_sw": lift_height_sw if transport and str(transport.get("id")) == "transport_drink" else None,
        "straightness_reach": reach_m.get("straightness"),
        "pause_time_sec_reach": reach_m.get("pause_time_sec"),
        "number_of_stops_reach": reach_m.get("number_of_stops"),
        "grasp_dwell_sec": grasp_dwell,
        "grasp_dwell_stops": grasp_stops,
        "sip_bout_count": int(sip_bout_count) if sip_bout_count is not None else None,
        "nvp_excludes_sip_bouts": True,
        "primary_smoothness_window": "reach_grasp",
        "functional_hold_sec": round(float(grasp_dwell or 0.0) + functional_extra, 3)
        if (grasp_dwell is not None or functional_extra > 0)
        else None,
        "reach_window_start_frame": reach.get("start_frame") if reach else None,
        "reach_window_end_frame": reach.get("end_frame") if reach else None,
        "movement_bouts_detected": int(movement_bouts),
    }
    if path_pause_parts:
        out["pause_time_sec_path"] = round(sum(path_pause_parts), 3)
        out["number_of_stops_path"] = int(sum(path_stops_parts))
    return out


def analyze_clinical_task_phases(
    *,
    clinical_task: str,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float],
    camera_view: str = "unknown",
    arm3d: Optional[Dict] = None,
    trunk_ratio: float = float("nan"),
    trunk_cheat: float = float("nan"),
    velocity_threshold: float = 5.0,
    primary_reach_start: Optional[int] = None,
    primary_reach_end: Optional[int] = None,
    opp_shoulder_x: Optional[np.ndarray] = None,
    opp_shoulder_y: Optional[np.ndarray] = None,
    index_x: Optional[np.ndarray] = None,
    index_y: Optional[np.ndarray] = None,
    pinky_x: Optional[np.ndarray] = None,
    pinky_y: Optional[np.ndarray] = None,
    thumb_x: Optional[np.ndarray] = None,
    thumb_y: Optional[np.ndarray] = None,
    hand3d: Optional[Dict] = None,
    arm_world: Optional[Dict] = None,
    hand_world: Optional[Dict] = None,
    affected_side: str = "auto",
) -> Dict[str, Any]:
    task_key = (clinical_task or "study_reach_grasp").strip().lower()
    spec = CLINICAL_TASKS.get(task_key, CLINICAL_TASKS["study_reach_grasp"])

    def _seg_kw():
        return dict(
            opp_shoulder_x=opp_shoulder_x,
            opp_shoulder_y=opp_shoulder_y,
            index_x=index_x,
            index_y=index_y,
            pinky_x=pinky_x,
            pinky_y=pinky_y,
            thumb_x=thumb_x,
            thumb_y=thumb_y,
            hand3d=hand3d,
            arm_world=arm_world,
            hand_world=hand_world,
            affected_side=affected_side,
            clinical_task=task_key,
        )

    phase_labels = {
        "reach_grasp": "Reach & grasp",
        "transport_drink": "Transport to mouth (drink)",
        "transport_brush": "Transport to mouth (brush)",
        "return": "Return to rest",
        "forearm_rotation": "Forearm pronation / supination",
        "shoulder_abduction": "Shoulder abduction",
        "pincer_pinch": "Pincer pinch",
    }

    task_window = resolve_clinical_movement_window(
        task_key,
        palm_x=palm_x,
        palm_y=palm_y,
        wrist_x=wrist_x,
        wrist_y=wrist_y,
        elbow_x=elbow_x,
        elbow_y=elbow_y,
        shoulder_x=shoulder_x,
        shoulder_y=shoulder_y,
        trunk_x=trunk_x,
        trunk_y=trunk_y,
        fs=fs,
        shoulder_width=shoulder_width,
        opp_shoulder_x=opp_shoulder_x,
        opp_shoulder_y=opp_shoulder_y,
        index_x=index_x,
        index_y=index_y,
        pinky_x=pinky_x,
        pinky_y=pinky_y,
        thumb_x=thumb_x,
        thumb_y=thumb_y,
        hand3d=hand3d,
        arm3d=arm3d,
        arm_world=arm_world,
        hand_world=hand_world,
        affected_side=affected_side,
        velocity_threshold=velocity_threshold,
    )

    if not spec.get("multi_bout"):
        if task_window is not None:
            s, e = int(task_window["start"]), int(task_window["end"])
        elif primary_reach_start is not None and primary_reach_end is not None:
            s, e = int(primary_reach_start), int(primary_reach_end)
        else:
            spd = palm_image_speed(palm_x, palm_y, fs)
            segs = _list_segments(
                spd, palm_x, palm_y, fs, velocity_threshold, min_segment_frames=max(8, int(0.15 * fs))
            )
            if segs:
                s, e = int(segs[0]["start"]), int(segs[0]["end"])
            else:
                s, e = 0, max(0, len(palm_x) - 1)
        m = _segment_metrics(
            palm_x, palm_y, wrist_x, wrist_y, elbow_x, elbow_y, shoulder_x, shoulder_y,
            trunk_x, trunk_y,
            fs, shoulder_width, s, e, camera_view, arm3d, trunk_ratio, trunk_cheat, velocity_threshold,
            **_seg_kw(),
        )
        phase_label = phase_labels.get(spec["phase_ids"][0], "Movement")
        out_phase = {
            "id": spec["phase_ids"][0],
            "label": phase_label,
            "start_frame": s,
            "end_frame": e,
            "duration_sec": round((e - s + 1) / fs, 3) if fs else None,
            "metrics": m,
        }
        if task_window is not None:
            out_phase["task_window"] = task_window
            if task_window.get("expected_rom_deg"):
                lo, hi = task_window["expected_rom_deg"]
                rom = task_window.get("rom")
                if rom is not None:
                    out_phase["expected_rom_ok"] = bool(lo <= float(rom) <= hi)
        return {
            "clinical_task": task_key,
            "clinical_task_label": spec["label_en"],
            "task_phases": [out_phase],
            "movement_bouts_detected": 1,
            "task_movement_window": task_window,
            **_task_completion_fields(spec, [out_phase], 1),
        }

    spd = palm_image_speed(palm_x, palm_y, fs)
    segments = _list_segments(
        spd, palm_x, palm_y, fs, velocity_threshold, min_segment_frames=max(8, int(0.2 * fs))
    )
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else 50.0
    segments = [s for s in segments if s["dur"] >= 0.25 and (s["disp"] / sw) >= 0.04]

    windows = _pick_phase_windows(segments, spec["phase_ids"])
    phases_out: List[Dict[str, Any]] = []
    for pid, s, e in windows:
        m = _segment_metrics(
            palm_x, palm_y, wrist_x, wrist_y, elbow_x, elbow_y, shoulder_x, shoulder_y,
            trunk_x, trunk_y,
            fs, shoulder_width, s, e, camera_view, arm3d, trunk_ratio, trunk_cheat, velocity_threshold,
            **_seg_kw(),
        )
        if str(pid).startswith("transport_"):
            # Count sips BEFORE reclassifying all pauses as functional hold.
            m["sip_bout_count"] = _count_sip_bouts_in_window(
                palm_x, palm_y, fs, s, e, velocity_threshold=velocity_threshold, metrics=m,
            )
            m = _reclassify_transport_pauses_as_functional(m)
            m["sip_bout_count"] = m.get("sip_bout_count") or 1
            # Table → peak height the patient achieves during drink/brush transport.
            m.update(_palm_lift_height_sw(palm_y, s, e, shoulder_width))
        phases_out.append({
            "id": pid,
            "label": phase_labels.get(pid, pid.replace("_", " ")),
            "start_frame": s,
            "end_frame": e,
            "duration_sec": round((e - s + 1) / fs, 3) if fs else None,
            "metrics": m,
        })

    return {
        "clinical_task": task_key,
        "clinical_task_label": spec["label_en"],
        "task_phases": phases_out,
        "movement_bouts_detected": len(segments),
        **_task_completion_fields(spec, phases_out, len(segments)),
    }
