# -*- coding: utf-8 -*-
"""
Locked kinematic analysis settings — SPARC + trunk (v24 literature-backed).

v24 changes (literature-aligned):
  - SPARC window: Balasubramanian 5% peak-velocity threshold (was 30% bell).
  - Reach window: uniform algorithm for healthy/pre/post with amplitude matching
    to the healthy reference on native coordinates before upsampling.
  - Movement time / peak velocity now use the same SPARC window.
  - Forward-reach cap excludes return/wipe/correction phases from SPARC.

Re-validated patients: murat, kurusal, zeinab.
"""
from __future__ import annotations

LOCKED_CODE_VERSION = "stroke-kinematic-v24-literature-5pct"

SPARC_TRUNK_LOGIC_VERSION = "stroke-kinematic-v24-literature-5pct"

LOCKED_SPARC_TRUNK = {
    "sparc_method": "literature_5pct",
    "trunk_metric": "trunk_path_ratio",
    "kin_window": "literature_matched_window",
    "sparc_window": "literature_5pct_reach_window",
    "window_profile": "uniform",
    "amplitude_matching": True,
    "amplitude_matching_gate": {"max_ratio": 2.0, "min_amplitude_sw": 0.30},
    "forward_reach_cap": True,
}
