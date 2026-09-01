"""Active vs archived clinic patients (Study ID + analysis exports)."""
from __future__ import annotations

from typing import Any, Dict, List


def is_archived_patient(patient: Any) -> bool:
    return isinstance(patient, dict) and bool(patient.get("_archived"))


def active_patients(patients: List[Any] | None) -> List[Dict[str, Any]]:
    return [p for p in (patients or []) if isinstance(p, dict) and not is_archived_patient(p)]


def study_id_number(patient: Dict[str, Any]) -> int:
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    try:
        return int(str(demo.get("participantId") or "").strip())
    except ValueError:
        return 10**9


def reorder_study_ids(patients: List[Any] | None, start: int = 101) -> List[Dict[str, Any]]:
    src = [p for p in (patients or []) if isinstance(p, dict)]
    active = [p for p in src if not is_archived_patient(p)]
    archived = [p for p in src if is_archived_patient(p)]
    active.sort(key=lambda p: (study_id_number(p), str(p.get("_savedAt") or ""), str(p.get("_id") or "")))
    out: List[Dict[str, Any]] = []
    for i, patient in enumerate(active):
        demo = dict(patient.get("demographics") or {})
        demo["participantId"] = str(start + i)
        next_p = dict(patient)
        next_p["demographics"] = demo
        out.append(next_p)
    out.extend(archived)
    return out
