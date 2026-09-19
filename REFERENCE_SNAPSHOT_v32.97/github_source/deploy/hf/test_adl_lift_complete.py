"""ADL drink completion must stay Complete when speed bouts collapse to 1–2."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SPACE = Path("/tmp/hf-compare/hf-space")
for p in (ROOT, SPACE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

stub = types.ModuleType("motion_invariants")
stub._list_segments = lambda *a, **k: []
stub.palm_image_speed = lambda *a, **k: np.array([])
sys.modules.setdefault("motion_invariants", stub)

from adl_task_phases import (  # noqa: E402
    CLINICAL_TASKS,
    _lift_split_windows,
    _pick_phase_windows,
    _task_completion_fields,
)


def test_one_slow_drink_bout_splits_into_three_phases():
    fs = 30.0
    n = 90
    t = np.arange(n)
    palm_y = np.full(n, 220.0)
    # reach (frames 10–28), lift to mouth (28–50), return (50–80)
    palm_y[10:28] = 220.0 - np.linspace(0, 8, 18)
    palm_y[28:50] = 212.0 - np.linspace(0, 55, 22)
    palm_y[50:80] = 157.0 + np.linspace(0, 60, 30)
    sw = 80.0
    windows = _lift_split_windows(
        palm_y, 8, 82, fs, sw, CLINICAL_TASKS["reach_grasp_drink_return"]["phase_ids"]
    )
    ids = [w[0] for w in windows]
    assert ids == ["reach_grasp", "transport_drink", "return"], ids
    assert windows[0][1] < windows[1][1] < windows[2][1]


def test_two_speed_bouts_are_not_left_incomplete():
    spec = CLINICAL_TASKS["reach_grasp_drink_return"]
    segs = [
        {"start": 10, "end": 40, "dur": 1.0, "disp": 20},
        {"start": 55, "end": 80, "dur": 0.8, "disp": 18},
    ]
    windows = _pick_phase_windows(segs, spec["phase_ids"])
    assert [w[0] for w in windows] == ["reach_grasp", "return"]
    phases = [
        {"id": "reach_grasp", "metrics": {}},
        {"id": "return", "metrics": {"lift_height_sw": 0.18, "lift_height_px": 22.0}},
    ]
    fields = _task_completion_fields(spec, phases, 2)
    assert fields["task_complete"] is True
    assert "transport_drink" in fields["completed_phase_ids"]


if __name__ == "__main__":
    test_one_slow_drink_bout_splits_into_three_phases()
    test_two_speed_bouts_are_not_left_incomplete()
    print("ok")
