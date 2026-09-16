"""One Drive slot per document kind in a patient folder.

PDF, baked validation video, original analysis clip, overlay JSON, and
kinematics JSON each keep a single canonical name. Re-export updates that
file in place; leftover dated / alias names of the same kind are trash.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

_PHASES = ("pre", "post", "healthy", "baseline")


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


def _norm_phase(phase: str) -> str:
    p = (phase or "").strip().lower()
    if p in ("baseline", "healthy", "healthy_side"):
        return "healthy"
    if p in ("pre", "post"):
        return p
    return ""


def _norm_stem(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _file_person_stem(filename: str) -> str:
    """Name portion of ``{digits}_{Name}.pdf``; empty when the file is untagged."""
    stem = Path(filename or "").stem
    head, _, rest = stem.partition("_")
    if head.isdigit() and rest:
        return rest
    return ""


def _folder_person_stem(folder_key: str) -> str:
    stem = Path(folder_key or "").stem
    head, _, rest = stem.partition("_")
    if head.isdigit() and rest:
        return rest
    return stem


def _basename(name: str) -> str:
    return Path((name or "").replace("\\", "/").split("/")[-1]).name


def document_kind(name: str) -> Optional[str]:
    """Stable slot id: clinic_report, pre_validation, pre_validation_original, …"""
    raw = _basename(name)
    if not raw:
        return None
    lower = raw.lower()
    stem = Path(lower).stem

    if lower.endswith(".pdf"):
        return "clinic_report"

    if lower.endswith(".json"):
        for phase in _PHASES:
            np = _norm_phase(phase)
            if stem in (f"{phase}_validation_overlay", f"{np}_validation_overlay"):
                return f"{np}_validation_overlay"
            if stem in (f"{phase}_kinematics", f"{np}_kinematics"):
                return f"{np}_kinematics"
        if stem.endswith("_validation_overlay"):
            np = _norm_phase(stem[: -len("_validation_overlay")])
            return f"{np}_validation_overlay" if np else None
        if stem.endswith("_kinematics"):
            np = _norm_phase(stem[: -len("_kinematics")])
            return f"{np}_kinematics" if np else None
        return None

    if not lower.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return None

    if stem.endswith("_validation_original") or (
        stem.endswith("_original") and not stem.endswith("_validation_original")
    ):
        base = stem[: -len("_validation_original")] if stem.endswith("_validation_original") else stem[: -len("_original")]
        np = _norm_phase(base)
        return f"{np}_validation_original" if np else None

    for phase in _PHASES:
        np = _norm_phase(phase)
        aliases = (
            f"{phase}_validation",
            f"{phase}_validation_unified",
            f"{phase}_unified_validation",
            f"{np}_validation",
            f"{np}_validation_unified",
            f"{np}_unified_validation",
        )
        if stem in aliases:
            return f"{np}_validation"
    return None


def canonical_name(
    kind: str,
    patient_key: str = "",
    uploaded_name: str = "",
) -> Optional[str]:
    kind = (kind or "").strip().lower()
    if not kind:
        return None
    if kind == "clinic_report":
        key = _sanitize(patient_key)[:120]
        if key:
            return f"{key}.pdf"
        stem = Path(_basename(uploaded_name)).stem
        low = stem.lower()
        if low.startswith("report_") or low in ("clinic_report", "report"):
            return "clinic_report.pdf"
        return f"{_sanitize(stem) or 'report'}.pdf"
    if kind.endswith("_validation_original"):
        phase = kind[: -len("_validation_original")]
        return f"{phase}_validation_original.mp4"
    if kind.endswith("_validation_overlay"):
        phase = kind[: -len("_validation_overlay")]
        return f"{phase}_validation_overlay.json"
    if kind.endswith("_kinematics"):
        phase = kind[: -len("_kinematics")]
        return f"{phase}_kinematics.json"
    if kind.endswith("_validation"):
        phase = kind[: -len("_validation")]
        return f"{phase}_validation.mp4"
    return None


def canonicalize_upload_name(name: str, patient_key: str = "") -> Optional[str]:
    """Map any alias / dated export name onto the single Drive slot for that kind."""
    kind = document_kind(name)
    if not kind:
        return None
    return canonical_name(kind, patient_key=patient_key, uploaded_name=name)


def is_foreign_person_pdf(filename: str, folder_key: str) -> bool:
    """True when a PDF is tagged as a different person than this patient folder."""
    if not str(filename or "").lower().endswith(".pdf"):
        return False
    file_stem = _file_person_stem(filename)
    if not file_stem:
        return False
    want = _norm_stem(_folder_person_stem(folder_key))
    if not want or len(want) < 3:
        return False
    return _norm_stem(file_stem) != want


def should_trash_as_alias(
    child_name: str,
    keep_name: str,
    *,
    folder_key: str = "",
    keep_id: str = "",
    child_id: str = "",
) -> bool:
    if keep_id and child_id and keep_id == child_id:
        return False
    child = _basename(child_name)
    keep = _basename(keep_name)
    if not child or not keep:
        return False
    kind = document_kind(keep)
    if not kind or document_kind(child) != kind:
        return False
    if kind == "clinic_report" and is_foreign_person_pdf(child, folder_key):
        return False
    if child == keep:
        return bool(keep_id and child_id and child_id != keep_id)
    return True


def same_kind_alias_examples(kind: str, patient_key: str = "") -> Tuple[str, ...]:
    """Human-facing leftover names that collapse into ``kind`` (tests / restore)."""
    kind = (kind or "").strip().lower()
    if kind == "clinic_report":
        key = _sanitize(patient_key)[:120] or "clinic_report"
        return (
            f"{key}.pdf",
            "clinic_report.pdf",
            "report.pdf",
            "report_115_patient_2026-09-14.pdf",
        )
    if kind.endswith("_validation_original"):
        phase = kind[: -len("_validation_original")]
        return (
            f"{phase}_validation_original.mp4",
            f"{phase}_original.mp4",
        )
    if kind.endswith("_validation_overlay"):
        phase = kind[: -len("_validation_overlay")]
        return (f"{phase}_validation_overlay.json",)
    if kind.endswith("_kinematics"):
        phase = kind[: -len("_kinematics")]
        return (f"{phase}_kinematics.json",)
    if kind.endswith("_validation"):
        phase = kind[: -len("_validation")]
        return (
            f"{phase}_validation.mp4",
            f"{phase}_validation.webm",
            f"{phase}_validation_unified.mp4",
            f"{phase}_validation_unified.webm",
        )
    return ()
