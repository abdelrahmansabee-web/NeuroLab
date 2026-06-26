# -*- coding: utf-8 -*-
"""Regression: SPARC + trunk ordering for Murat, Kurusal, Zeinab (v17 logic)."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

RAN = Path(__file__).resolve().parent
sys.path.insert(0, str(RAN))

from kinematic_locked_config import LOCKED_CODE_VERSION, SPARC_TRUNK_LOGIC_VERSION  # noqa: E402
from stroke_kinematic_pipeline import analyze_patient_kinematic_triad  # noqa: E402

PART = Path(r"D:/Thesis app/participants")

PATIENTS = [
    {
        "id": "murat",
        "trials": [
            ("pre", PART / "murat" / "pre.mp4", "right"),
            ("post", PART / "murat" / "post.mp4", "right"),
            ("healthy", PART / "murat" / "healthy side.mp4", "left"),
        ],
    },
    {
        "id": "kurusal",
        "trials": [
            ("pre", PART / "kurusal" / "pre_20260617_142855_pre.csv", "left"),
            ("post", PART / "kurusal" / "post_20260617_142949_post.csv", "left"),
            ("healthy", PART / "kurusal" / "baseline_20260617_143108_healthy_side.csv", "right"),
        ],
    },
    {
        "id": "zeinab",
        "trials": [
            ("pre", PART / "mediapipe/movs/zeyneb/pre_20260603_165439_pre.csv", "left"),
            ("post", PART / "mediapipe/movs/zeyneb/post_20260603_165651_post.csv", "left"),
            ("healthy", PART / "mediapipe/movs/zeyneb/baseline_20260603_165330_baseline.csv", "right"),
        ],
    },
]


def _run_patient(patient: dict) -> dict:
    out_dir = RAN.parent / "backend" / "outputs" / patient["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for label, source, side in patient["trials"]:
        if not source.exists():
            if pytest is not None:
                pytest.skip(f"Missing source for {patient['id']}/{label}: {source}")
            raise FileNotFoundError(f"Missing source for {patient['id']}/{label}: {source}")
        if source.suffix.lower() == ".csv":
            paths[label] = (str(source), side)
        else:
            csv_path = out_dir / f"{label}_landmarks.csv"
            if not csv_path.exists():
                if pytest is not None:
                    pytest.skip(f"Missing extracted CSV for {patient['id']}/{label}")
                raise FileNotFoundError(f"Missing extracted CSV for {patient['id']}/{label}")
            paths[label] = (str(csv_path), side)
    pre_p, pre_s = paths["pre"]
    post_p, post_s = paths["post"]
    hel_p, hel_s = paths["healthy"]
    return analyze_patient_kinematic_triad(
        pre_p, post_p, hel_p,
        pre_side=pre_s, post_side=post_s, healthy_side=hel_s,
    )


if pytest is not None:
    @pytest.mark.parametrize("patient", PATIENTS, ids=[p["id"] for p in PATIENTS])
    def test_sparc_trunk_order_param(patient: dict) -> None:
        test_sparc_trunk_order(patient)


def test_sparc_trunk_order(patient: dict) -> None:
    result = _run_patient(patient)
    pre, post, hel = result["pre"], result["post"], result["healthy"]
    assert pre["sparc_method"] == "bell_30pct_outbound"
    assert pre.get("trunk_path_ratio") is not None

    sp_pre, sp_post, sp_h = float(pre["sparc"]), float(post["sparc"]), float(hel["sparc"])
    tr_pre, tr_post, tr_h = float(pre["trunk_ratio"]), float(post["trunk_ratio"]), float(hel["trunk_ratio"])

    assert sp_h > sp_post > sp_pre, f"{patient['id']} SPARC order: H={sp_h} Post={sp_post} Pre={sp_pre}"
    assert tr_pre > tr_post > tr_h, f"{patient['id']} trunk order: Pre={tr_pre} Post={tr_post} H={tr_h}"


def test_locked_version_tag() -> None:
    assert LOCKED_CODE_VERSION.startswith("stroke-kinematic-v")
    assert SPARC_TRUNK_LOGIC_VERSION == "stroke-kinematic-v17-trunk-path-ratio"


if __name__ == "__main__":
    for p in PATIENTS:
        test_sparc_trunk_order(p)
    test_locked_version_tag()
    print("OK: SPARC + trunk locked regression passed for all patients.")
