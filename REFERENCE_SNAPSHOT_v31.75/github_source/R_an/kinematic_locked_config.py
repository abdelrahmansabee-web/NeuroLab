# -*- coding: utf-8 -*-
"""
Locked kinematic analysis settings — SPARC + trunk (v17 trunk path ratio).

Do not change window selection or trunk_ratio definition without updating
test_kinematic_locked.py and re-validating all three reference patients.
"""
from __future__ import annotations

LOCKED_CODE_VERSION = "stroke-kinematic-v23-reach-only"

# SPARC/trunk logic frozen at v17; elbow changes in v18 must not alter these.
SPARC_TRUNK_LOGIC_VERSION = "stroke-kinematic-v17-trunk-path-ratio"

LOCKED_SPARC_TRUNK = {
    "sparc_method": "bell_30pct_outbound",
    "trunk_metric": "trunk_path_ratio",
    "kin_window": "kinematic_reach_window",
    "sparc_window": "outbound_reach_window",
}
