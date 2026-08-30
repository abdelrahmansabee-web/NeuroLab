"""Archive one clinic patient in the same section order as the NeuroLab app."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

# Same order as NAV_ITEMS / the clinic sidebar (excluding report/analysis/users).
PROGRAM_SECTIONS = (
    "demographics",
    "ipaq",
    "vas",
    "vams",
    "motorchange",
    "kgia",
    "wmft",
    "kinematics",
)

META_KEYS = ("_id", "_savedAt", "_hasPre", "_hasPost", "patientKey")


def patient_drive_key(patient: Dict[str, Any]) -> str:
    from drive_persist import _sanitize

    if not isinstance(patient, dict):
        return "unknown"
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    pid = str(demo.get("participantId") or patient.get("_id") or patient.get("patientKey") or "unknown").strip()
    label = str(demo.get("name") or demo.get("fullName") or "").strip()
    if label:
        return _sanitize(f"{pid}_{label}")[:120] or "unknown"
    return _sanitize(pid)[:120] or "unknown"


def program_patient_record(patient: Dict[str, Any]) -> Dict[str, Any]:
    """Return the patient object with the same keys/order as the clinic form."""
    src = patient if isinstance(patient, dict) else {}
    out: Dict[str, Any] = {}
    for key in META_KEYS:
        if key in src:
            out[key] = src[key]
    for section in PROGRAM_SECTIONS:
        value = src.get(section)
        out[section] = value if isinstance(value, dict) else {}
    demo = out["demographics"] if isinstance(out.get("demographics"), dict) else {}
    if not out.get("patientKey"):
        out["patientKey"] = str(demo.get("participantId") or src.get("_id") or "").strip()
    return out


def files_for_patient(patient: Dict[str, Any]) -> List[tuple[str, bytes, str]]:
    rec = program_patient_record(patient)
    payload: List[tuple[str, bytes, str]] = [
        (
            "patient.json",
            json.dumps(rec, ensure_ascii=False, indent=2).encode("utf-8"),
            "data",
        ),
        (
            "_program_layout.json",
            json.dumps(
                {
                    "matchesApp": True,
                    "sections": list(PROGRAM_SECTIONS),
                    "files": ["patient.json"]
                    + [f"{i:02d}_{name}.json" for i, name in enumerate(PROGRAM_SECTIONS, 1)],
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            "data",
        ),
    ]
    for index, section in enumerate(PROGRAM_SECTIONS, 1):
        payload.append(
            (
                f"{index:02d}_{section}.json",
                json.dumps(rec.get(section) or {}, ensure_ascii=False, indent=2).encode("utf-8"),
                "data",
            )
        )
    return payload


def parse_patients_payload(raw: Any) -> List[Dict[str, Any]]:
    data = raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            data = json.loads(bytes(raw).decode("utf-8"))
        except Exception:
            return []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return []
    if isinstance(data, dict):
        if isinstance(data.get("patients"), list):
            data = data["patients"]
        elif isinstance(data.get("stroke_rehab_patients_v6"), (str, list, dict)):
            nested = data.get("stroke_rehab_patients_v6")
            return parse_patients_payload(nested)
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, dict)]


def archive_patients(patients: Iterable[Any], *, user_id: int = 1) -> Dict[str, Any]:
    from drive_persist import upload_named_files

    result: Dict[str, Any] = {"ok": False, "patients": []}
    tmp_root = Path(tempfile.mkdtemp(prefix="nl-patient-archive-"))
    uploaded = 0
    try:
        for patient in patients:
            if not isinstance(patient, dict):
                continue
            key = patient_drive_key(patient)
            named = []
            for name, content, sub in files_for_patient(patient):
                path = tmp_root / key / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                named.append((name, path, sub))
            saved = upload_named_files(key, named, user_id=user_id)
            result["patients"].append({"patientKey": key, "drive": saved})
            if saved.get("ok"):
                uploaded += 1
        result["ok"] = uploaded > 0
        result["uploaded"] = uploaded
        return result
    finally:
        try:
            import shutil

            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


def archive_from_data_dir(data_dir: Path, *, user_id: int = 1) -> Dict[str, Any]:
    patients: List[Dict[str, Any]] = []
    patients_dir = Path(data_dir) / "patients"
    if patients_dir.is_dir():
        for path in sorted(patients_dir.glob("*.json")):
            try:
                raw = path.read_text(encoding="utf-8")
                if raw.startswith("enc:"):
                    continue
                patients.extend(parse_patients_payload(raw))
            except Exception:
                continue
    dump = Path(data_dir) / "ipad_localstorage" / "latest.json"
    if dump.is_file():
        try:
            patients.extend(parse_patients_payload(dump.read_bytes()))
        except Exception:
            pass
    return archive_patients(patients, user_id=user_id)
