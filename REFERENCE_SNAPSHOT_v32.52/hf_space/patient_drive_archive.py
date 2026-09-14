"""Archive one clinic patient in the same section order as the NeuroLab app."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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


def patient_study_id(patient: Dict[str, Any]) -> str:
    if not isinstance(patient, dict):
        return ""
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    raw = demo.get("participantId")
    if raw is None or raw == "":
        return ""
    text = str(raw).strip()
    try:
        # Normalize 101 / "101" / 101.0 → "101" so merge keys match.
        as_int = int(float(text))
        if str(as_int) == text or abs(float(text) - as_int) < 1e-9:
            return str(as_int)
    except (TypeError, ValueError):
        pass
    return text


def _normalize_patient_name(name: str) -> str:
    import re

    return re.sub(r"\s+", " ", (name or "").strip().lower())


def patient_display_name(patient: Dict[str, Any]) -> str:
    if not isinstance(patient, dict):
        return ""
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    return str(demo.get("name") or demo.get("fullName") or "").strip()


def _study_id_number(patient: Dict[str, Any]) -> Optional[int]:
    raw = patient_study_id(patient)
    if not raw:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def prefer_name_merge_target(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer Study ID in the clinic 101+ series when collapsing same-name rows."""
    if not isinstance(a, dict):
        return b if isinstance(b, dict) else {}
    if not isinstance(b, dict):
        return a
    ia = _study_id_number(a)
    ib = _study_id_number(b)
    a101 = ia is not None and 101 <= ia < 100_000_000
    b101 = ib is not None and 101 <= ib < 100_000_000
    if a101 != b101:
        return a if a101 else b
    if a101 and b101 and ia != ib:
        return a if ia <= ib else b  # type: ignore[operator]
    return prefer_patient(a, b)


def merge_same_name_patients(patients: Iterable[Any]) -> List[Dict[str, Any]]:
    """Collapse active rows that share the same display name (legacy Study-ID forks)."""
    src = [p for p in (patients or []) if isinstance(p, dict)]
    archived = [p for p in src if p.get("_archived")]
    active = [p for p in src if not p.get("_archived")]
    groups: Dict[str, List[Dict[str, Any]]] = {}
    no_name: List[Dict[str, Any]] = []
    for patient in active:
        key = _normalize_patient_name(patient_display_name(patient))
        if not key:
            no_name.append(patient)
            continue
        groups.setdefault(key, []).append(patient)
    out: List[Dict[str, Any]] = list(no_name)
    for group in groups.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        keep = group[0]
        for other in group[1:]:
            keep = prefer_name_merge_target(keep, other)
        merged = keep
        for other in group:
            if other is keep:
                continue
            merged = prefer_patient(merged, other)
        keep_sid = patient_study_id(keep)
        demo = merged.get("demographics") if isinstance(merged.get("demographics"), dict) else {}
        merged = {
            **merged,
            "_id": keep.get("_id") or merged.get("_id"),
            "demographics": {
                **demo,
                **({"participantId": keep_sid} if keep_sid else {}),
                **({"name": patient_display_name(keep)} if patient_display_name(keep) else {}),
            },
        }
        out.append(merged)
    return out + archived


def patient_drive_key(patient: Dict[str, Any]) -> str:
    from drive_persist import _sanitize

    if not isinstance(patient, dict):
        return "unknown"
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    pid = patient_study_id(patient) or str(
        patient.get("_id") or patient.get("patientKey") or "unknown"
    ).strip()
    label = str(demo.get("name") or demo.get("fullName") or "").strip()
    if label:
        return _sanitize(f"{pid}_{label}")[:120] or "unknown"
    return _sanitize(pid)[:120] or "unknown"


def patient_merge_key(patient: Dict[str, Any]) -> str:
    """Same person = same Study ID (not Drive folder name, not random _id)."""
    pid = patient_study_id(patient)
    if pid:
        return pid
    return patient_drive_key(patient)


def _section_filled(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _patient_recency_score(patient: Dict[str, Any]) -> float:
    ts = 0.0
    raw = patient.get("_savedAt")
    if isinstance(raw, str) and raw:
        try:
            from datetime import datetime

            ts = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = 0.0
    filled = sum(1 for key in PROGRAM_SECTIONS if _section_filled(patient.get(key)))
    if patient.get("_hasPre"):
        filled += 0.25
    if patient.get("_hasPost"):
        filled += 0.25
    return filled * 1e13 + ts


def prefer_patient(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the richer/newer record; fill empty sections from the other."""
    if not isinstance(a, dict):
        return b if isinstance(b, dict) else {}
    if not isinstance(b, dict):
        return a
    keep, other = (a, b) if _patient_recency_score(a) >= _patient_recency_score(b) else (b, a)
    out: Dict[str, Any] = {**other, **keep}
    demo_keep = keep.get("demographics") if isinstance(keep.get("demographics"), dict) else {}
    demo_other = other.get("demographics") if isinstance(other.get("demographics"), dict) else {}
    out["demographics"] = {**demo_other, **demo_keep}
    for key in PROGRAM_SECTIONS:
        if key == "demographics":
            continue
        if key == "kinematics":
            out["kinematics"] = _merge_kinematics(keep.get("kinematics"), other.get("kinematics"))
            continue
        if _section_filled(keep.get(key)):
            out[key] = keep[key]
        elif _section_filled(other.get(key)):
            out[key] = other[key]
    out["_id"] = keep.get("_id") or other.get("_id")
    out["_hasPre"] = bool(keep.get("_hasPre") or other.get("_hasPre"))
    out["_hasPost"] = bool(keep.get("_hasPost") or other.get("_hasPost"))
    # Prefer a real ISO timestamp over null/Invalid.
    keep_ts = keep.get("_savedAt")
    other_ts = other.get("_savedAt")
    if Date_parse_ok(keep_ts) and Date_parse_ok(other_ts):
        out["_savedAt"] = keep_ts if _patient_recency_score(keep) >= _patient_recency_score(other) else other_ts
    elif Date_parse_ok(keep_ts):
        out["_savedAt"] = keep_ts
    elif Date_parse_ok(other_ts):
        out["_savedAt"] = other_ts
    arts_keep = keep.get("_driveArtifacts") if isinstance(keep.get("_driveArtifacts"), dict) else {}
    arts_other = other.get("_driveArtifacts") if isinstance(other.get("_driveArtifacts"), dict) else {}
    if arts_keep or arts_other:
        out["_driveArtifacts"] = {**arts_other, **arts_keep}
    if keep.get("_archived") or other.get("_archived"):
        out["_archived"] = bool(keep.get("_archived") and other.get("_archived"))
    return out


def _merge_kinematics(a: Any, b: Any) -> Dict[str, Any]:
    ka = a if isinstance(a, dict) else {}
    kb = b if isinstance(b, dict) else {}
    out = {**kb, **ka}
    ar_a = ka.get("analysisResults") if isinstance(ka.get("analysisResults"), dict) else {}
    ar_b = kb.get("analysisResults") if isinstance(kb.get("analysisResults"), dict) else {}
    phases = set(ar_a) | set(ar_b)
    if phases:
        merged_ar: Dict[str, Any] = {}
        for phase in phases:
            pa = ar_a.get(phase) if isinstance(ar_a.get(phase), dict) else {}
            pb = ar_b.get(phase) if isinstance(ar_b.get(phase), dict) else {}
            # Prefer the denser phase metrics.
            merged_ar[phase] = pa if len(pa) >= len(pb) else pb
            if pa and pb and len(pa) == len(pb):
                merged_ar[phase] = {**pb, **pa}
            elif pa and pb:
                denser, thinner = (pa, pb) if len(pa) >= len(pb) else (pb, pa)
                merged_ar[phase] = {**thinner, **denser}
        out["analysisResults"] = merged_ar
    for key in ("result_pre", "result_post", "result_baseline", "status_pre", "status_post", "status_baseline"):
        if not out.get(key) and kb.get(key):
            out[key] = kb[key]
        if not out.get(key) and ka.get(key):
            out[key] = ka[key]
    return out


def Date_parse_ok(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        from datetime import datetime

        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


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
    """One PDF per patient. Drive folders must not receive JSON or extras."""
    from patient_pdf import build_patient_pdf, patient_pdf_filename

    rec = program_patient_record(patient)
    name = patient_pdf_filename(rec)
    return [(name, build_patient_pdf(rec), "")]


def decrypt_patients_text(raw: str) -> Optional[Any]:
    """Decrypt HF disk patients (`enc:…`) using the same key as security.py."""
    if not isinstance(raw, str) or not raw.startswith("enc:"):
        return None
    secret = (os.environ.get("JWT_SECRET") or os.environ.get("NEUROLAB_JWT_SECRET") or "").strip()
    if not secret:
        print("encrypted patients skipped: JWT_SECRET missing", flush=True)
        return None
    try:
        from security import decrypt_json_from_str

        return decrypt_json_from_str(raw, secret)
    except Exception:
        pass
    try:
        import base64

        from cryptography.fernet import Fernet
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"neurolab_static_salt_v1",
            iterations=200000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return json.loads(Fernet(key).decrypt(raw[4:].encode("utf-8")).decode("utf-8"))
    except Exception as exc:
        print(f"encrypted patients decrypt failed: {exc}", flush=True)
        return None


def load_patients_file(path: Path) -> List[Dict[str, Any]]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    if raw.startswith("enc:"):
        data = decrypt_patients_text(raw)
        if data is None:
            return []
        return parse_patients_payload(data)
    return parse_patients_payload(raw)


def merge_patients(*groups: Iterable[Any]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for group in groups:
        for patient in group or []:
            if not isinstance(patient, dict):
                continue
            key = patient_merge_key(patient)
            if not key:
                continue
            if key not in by_key:
                order.append(key)
                by_key[key] = patient
            else:
                by_key[key] = prefer_patient(by_key[key], patient)
    return [by_key[key] for key in order]


def load_program_patients(data_dir: Path) -> List[Dict[str, Any]]:
    """Patients from the clinic program copies on disk (Home Screen sync / patients.json)."""
    groups: List[List[Dict[str, Any]]] = []
    patients_dir = Path(data_dir) / "patients"
    if patients_dir.is_dir():
        for path in sorted(patients_dir.glob("*.json")):
            loaded = load_patients_file(path)
            if loaded:
                groups.append(loaded)
    for extra in (
        Path(data_dir) / "patients.json",
        Path(data_dir) / "ipad_localstorage" / "latest.json",
    ):
        if extra.is_file():
            loaded = load_patients_file(extra)
            if loaded:
                groups.append(loaded)
    root = Path(data_dir)
    for path in sorted(root.glob("neurolab_patients_*.json")):
        loaded = load_patients_file(path)
        if loaded:
            groups.append(loaded)
    return merge_patients(*groups)


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
            if patient.get("_archived"):
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
    return archive_patients(load_program_patients(Path(data_dir)), user_id=user_id)


_SKIP_DRIVE_FOLDERS = frozenset(
    {
        "archive",
        "_system",
        "excel",
        "excels",
        "team_patients",
        "videos",
        "reports",
        "data",
    }
)


def parse_patient_folder_name(folder_name: str) -> Optional[Dict[str, str]]:
    """Parse clinic Drive folder names like ``115_Ahmet_sever`` → study id + name."""
    import re

    raw = (folder_name or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if lower in _SKIP_DRIVE_FOLDERS:
        return None
    if re.fullmatch(r"u\d+", lower):
        return None
    m = re.match(r"^(\d+)(?:[_.\-\s]+(.+))?$", raw)
    if not m:
        return None
    pid = m.group(1)
    label = (m.group(2) or "").replace("_", " ").replace(".", " ").strip()
    label = re.sub(r"\s+", " ", label)
    return {"participantId": pid, "name": label}


def skeleton_patient_from_folder(
    folder_name: str,
    *,
    modified_time: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    parsed = parse_patient_folder_name(folder_name)
    if not parsed:
        return None
    pid = parsed["participantId"]
    name = parsed.get("name") or ""
    saved = _iso_from_drive_time(modified_time)
    return {
        "_id": f"drive_{pid}",
        "_savedAt": saved,
        "_restoredFromDrive": True,
        "demographics": {
            "participantId": pid,
            **({"name": name} if name else {}),
        },
        "ipaq": {},
        "vas": {},
        "vams": {},
        "motorchange": {},
        "kgia": {},
        "wmft": {},
        "kinematics": {},
        "_driveArtifacts": {},
    }


def _iso_from_drive_time(raw: Optional[str]) -> str:
    from datetime import datetime, timezone

    text = (raw or "").strip()
    if text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z"
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _download_drive_bytes(service, file_id: str) -> bytes:
    return service.files().get_media(fileId=file_id).execute() or b""


def _patient_from_pdf_bytes(raw: bytes) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        from pdf_import_parser import extract_pdf_text, normalize_restored_patient, parse_clinical_report_pdf

        text = extract_pdf_text(raw)
        if not (text or "").strip():
            return None
        patient = parse_clinical_report_pdf(text)
        if isinstance(patient, dict):
            patient = normalize_restored_patient(patient)
            patient["_restoredFromDrive"] = True
            return patient
    except Exception as exc:
        print(f"Drive PDF restore parse skipped: {exc}", flush=True)
    return None


def _phase_from_kinematics_filename(name: str) -> Optional[str]:
    lower = (name or "").lower()
    stem = Path(lower).stem
    for phase in ("pre", "post", "healthy", "baseline"):
        if stem == f"{phase}_kinematics" or stem.endswith(f"_{phase}_kinematics"):
            return "baseline" if phase in ("healthy", "baseline") else phase
    return None


def _apply_kinematics_snapshot(patient: Dict[str, Any], phase: str, payload: Any) -> None:
    if not isinstance(patient, dict) or not isinstance(payload, dict):
        return
    # Snapshots may be the metrics dict itself, or wrapped.
    metrics = payload
    for key in ("metrics", "result", "analysisResults", "kinematics"):
        nested = payload.get(key)
        if isinstance(nested, dict) and nested:
            if key == "analysisResults" and isinstance(nested.get(phase), dict):
                metrics = nested[phase]
            elif key != "analysisResults":
                metrics = nested
            break
    if phase in payload and isinstance(payload[phase], dict):
        metrics = payload[phase]
    if not isinstance(metrics, dict) or not metrics:
        return
    kin = patient.get("kinematics") if isinstance(patient.get("kinematics"), dict) else {}
    analysis = kin.get("analysisResults") if isinstance(kin.get("analysisResults"), dict) else {}
    analysis[phase] = {**(analysis.get(phase) or {}), **metrics}
    kin["analysisResults"] = analysis
    kin[f"result_{phase}"] = {**(kin.get(f"result_{phase}") or {}), **metrics}
    kin[f"status_{phase}"] = "completed"
    patient["kinematics"] = kin
    if phase == "pre":
        patient["_hasPre"] = True
    elif phase == "post":
        patient["_hasPost"] = True


def _enrich_patient_from_folder_contents(
    service,
    folder_item: Dict[str, Any],
    skeleton: Dict[str, Any],
    *,
    parse_pdfs: bool,
    pdf_budget: List[int],
    max_pdfs: int,
) -> Dict[str, Any]:
    """Merge PDF + *_kinematics.json + validation media flags from one Drive patient folder."""
    from drive_persist import ALLOWED_VALIDATION_VIDEOS

    enriched = dict(skeleton)
    folder_name = folder_item.get("name") or ""
    folder_id = folder_item.get("id")
    modified = folder_item.get("modifiedTime")
    artifacts: Dict[str, Any] = dict(enriched.get("_driveArtifacts") or {})
    latest_mod = modified

    if not folder_id:
        enriched["_savedAt"] = _iso_from_drive_time(modified)
        return enriched

    try:
        contents = _list_direct_children_safe(service, folder_id)
    except Exception as exc:
        print(f"Drive folder list ({folder_name}): {exc}", flush=True)
        enriched["_savedAt"] = _iso_from_drive_time(modified)
        return enriched

    pdf_item = None
    for child in contents:
        cname = (child.get("name") or "").strip()
        clower = cname.lower()
        if child.get("modifiedTime") and (not latest_mod or str(child["modifiedTime"]) > str(latest_mod)):
            latest_mod = child.get("modifiedTime")
        if clower.endswith(".pdf") and child.get("id"):
            if pdf_item is None or clower.startswith(folder_name.lower()[:8]):
                pdf_item = child
        phase = _phase_from_kinematics_filename(cname)
        if phase and child.get("id"):
            try:
                raw = _download_drive_bytes(service, child["id"])
                payload = json.loads(raw.decode("utf-8"))
                _apply_kinematics_snapshot(enriched, phase, payload)
                artifacts[f"{phase}_kinematics"] = True
            except Exception as exc:
                print(f"Drive kinematics JSON ({folder_name}/{cname}): {exc}", flush=True)
        if clower in ALLOWED_VALIDATION_VIDEOS or (
            clower.endswith((".mp4", ".webm")) and "validation" in clower
        ):
            if "pre" in clower:
                artifacts["pre_validation"] = cname
                enriched["_hasPre"] = True
            elif "post" in clower:
                artifacts["post_validation"] = cname
                enriched["_hasPost"] = True
            elif "healthy" in clower or "baseline" in clower:
                artifacts["healthy_validation"] = cname

    if parse_pdfs and pdf_item and pdf_budget[0] < max_pdfs:
        try:
            raw = _download_drive_bytes(service, pdf_item["id"])
            parsed = _patient_from_pdf_bytes(raw)
            pdf_budget[0] += 1
            if parsed:
                enriched = prefer_patient(parsed, enriched)
                artifacts["pdf"] = pdf_item.get("name")
                # Keep Study ID / name from folder when PDF parse misses them.
                demo = enriched.get("demographics") if isinstance(enriched.get("demographics"), dict) else {}
                sk_demo = skeleton.get("demographics") or {}
                if not demo.get("participantId") and sk_demo.get("participantId"):
                    demo = {**demo, "participantId": sk_demo["participantId"]}
                if not demo.get("name") and sk_demo.get("name"):
                    demo = {**demo, "name": sk_demo["name"]}
                enriched["demographics"] = demo
        except Exception as exc:
            print(f"Drive folder PDF restore ({folder_name}): {exc}", flush=True)

    try:
        from pdf_import_parser import normalize_restored_patient

        enriched = normalize_restored_patient(enriched)
    except Exception:
        pass

    enriched["_driveArtifacts"] = artifacts
    enriched["_restoredFromDrive"] = True
    # Never leave Invalid Date — prefer newest Drive file time.
    existing = enriched.get("_savedAt")
    if not existing or existing in ("None", "null") or not Date_parse_ok(existing):
        enriched["_savedAt"] = _iso_from_drive_time(latest_mod or modified)
    return enriched


def _list_direct_children_safe(service, folder_id: str):
    from drive_persist import _list_direct_children

    return _list_direct_children(service, folder_id)


def _collect_json_snapshots(service, folder_id: str, *, depth: int = 0, max_depth: int = 3) -> List[Dict[str, Any]]:
    """Recursively find neurolab_patients_*.json under NeuroLab/RAED backup trees."""
    found: List[Dict[str, Any]] = []
    if depth > max_depth or not folder_id:
        return found
    try:
        children = _list_direct_children_safe(service, folder_id)
    except Exception:
        return found
    from drive_persist import FOLDER_MIME

    for item in children:
        name = (item.get("name") or "").strip()
        mime = item.get("mimeType") or ""
        if mime == FOLDER_MIME:
            lower = name.lower()
            if lower in _SKIP_DRIVE_FOLDERS and lower not in ("_system",):
                # Still descend into u* / Archive / nested backup aliases.
                if not (lower.startswith("u") or lower in ("archive", "_system", "neurolab_backups", "raed_ai_backups")):
                    continue
            if depth < max_depth and item.get("id"):
                found.extend(_collect_json_snapshots(service, item["id"], depth=depth + 1, max_depth=max_depth))
            continue
        if name.startswith("neurolab_patients_") and name.endswith(".json") and item.get("id"):
            try:
                raw = _download_drive_bytes(service, item["id"])
                loaded = parse_patients_payload(raw)
                if loaded:
                    # Stamp savedAt from Drive file when missing.
                    mt = item.get("modifiedTime")
                    for p in loaded:
                        if isinstance(p, dict) and not Date_parse_ok(p.get("_savedAt")):
                            p["_savedAt"] = _iso_from_drive_time(mt)
                    found.extend(loaded)
            except Exception as exc:
                print(f"Drive snapshot restore skipped ({name}): {exc}", flush=True)
        elif name in ("patients.json", "stroke_rehab_patients_v6.json") and item.get("id"):
            try:
                raw = _download_drive_bytes(service, item["id"])
                loaded = parse_patients_payload(raw)
                if loaded:
                    found.extend(loaded)
            except Exception as exc:
                print(f"Drive patients.json skip ({name}): {exc}", flush=True)
    return found


def _excel_patients_from_drive(service, root_id: str) -> List[Dict[str, Any]]:
    """Rehydrate kinematic analysisResults from RAED_AI_Backups/Excel/*.xlsx."""
    from drive_persist import EXCEL_FOLDER_NAME, FOLDER_MIME

    patients: List[Dict[str, Any]] = []
    try:
        children = _list_direct_children_safe(service, root_id)
    except Exception:
        return patients
    excel_id = None
    for item in children:
        if (item.get("mimeType") or "") == FOLDER_MIME and (item.get("name") or "").strip().lower() in (
            EXCEL_FOLDER_NAME.lower(),
            "excels",
        ):
            excel_id = item.get("id")
            break
    if not excel_id:
        return patients

    try:
        files = _list_direct_children_safe(service, excel_id)
    except Exception:
        return patients

    by_pid: Dict[str, Dict[str, Any]] = {}
    for item in files:
        name = (item.get("name") or "").strip()
        lower = name.lower()
        if not (lower.endswith(".xlsx") or lower.endswith(".xls") or lower.endswith(".csv")):
            continue
        if not item.get("id"):
            continue
        try:
            raw = _download_drive_bytes(service, item["id"])
            rows = _read_excel_rows(raw, name)
        except Exception as exc:
            print(f"Drive Excel read ({name}): {exc}", flush=True)
            continue
        task_id = Path(name).stem
        for row in rows:
            pid = str(row.get("ID") or row.get("participantId") or row.get("ParticipantId") or "").strip()
            if not pid:
                continue
            try:
                pid = str(int(float(pid)))
            except (TypeError, ValueError):
                pass
            rec = by_pid.get(pid)
            if not rec:
                rec = skeleton_patient_from_folder(f"{pid}_excel") or {
                    "_id": f"drive_{pid}",
                    "_savedAt": _iso_from_drive_time(item.get("modifiedTime")),
                    "demographics": {"participantId": pid},
                    "kinematics": {},
                }
                by_pid[pid] = rec
            demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
            if row.get("Group") not in (None, "") and not demo.get("group"):
                demo["group"] = str(int(float(row["Group"]))) if str(row["Group"]).replace(".", "", 1).isdigit() else str(row["Group"])
            if row.get("Age") not in (None, "") and not demo.get("age"):
                demo["age"] = str(row["Age"]).rstrip("0").rstrip(".") if isinstance(row["Age"], float) else str(row["Age"])
            rec["demographics"] = {**demo, "participantId": pid}
            kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
            analysis = kin.get("analysisResults") if isinstance(kin.get("analysisResults"), dict) else {}
            for phase, suffix in (("pre", "_Pre"), ("post", "_Post"), ("baseline", "_Healthy")):
                metrics: Dict[str, Any] = dict(analysis.get(phase) or {})
                for col, val in row.items():
                    col_s = str(col)
                    if not col_s.endswith(suffix):
                        continue
                    key = col_s[: -len(suffix)]
                    if val is None or val == "":
                        continue
                    try:
                        metrics[key] = float(val)
                    except (TypeError, ValueError):
                        metrics[key] = val
                if metrics:
                    metrics.setdefault("clinical_task", task_id)
                    analysis[phase] = metrics
                    kin[f"result_{phase}"] = metrics
                    kin[f"status_{phase}"] = "completed"
                    if phase == "pre":
                        rec["_hasPre"] = True
                    elif phase == "post":
                        rec["_hasPost"] = True
            if analysis:
                kin["analysisResults"] = analysis
                rec["kinematics"] = kin
            rec["_restoredFromDrive"] = True
            if not Date_parse_ok(rec.get("_savedAt")):
                rec["_savedAt"] = _iso_from_drive_time(item.get("modifiedTime"))
    return list(by_pid.values())


def _read_excel_rows(raw: bytes, name: str) -> List[Dict[str, Any]]:
    import io

    lower = (name or "").lower()
    if lower.endswith(".csv"):
        import csv

        text = raw.decode("utf-8-sig", errors="replace")
        return list(csv.DictReader(io.StringIO(text)))
    try:
        import pandas as pd

        df = pd.read_excel(io.BytesIO(raw))
        return df.where(pd.notnull(df), None).to_dict(orient="records")
    except Exception:
        # openpyxl may be missing; try xlrd/csv fallback via pandas engine guess already failed
        raise


def restore_patients_from_clinic_drive(
    *,
    parse_pdfs: bool = True,
    max_pdfs: int = 120,
) -> Dict[str, Any]:
    """Rebuild program patients from NeuroLab_Backups / RAED_AI_Backups.

    Prefer full JSON snapshots when present; always enrich from patient folders
    (PDF + kinematics JSON + validation media) and Excel/ task workbooks.
    """
    from drive_persist import FOLDER_MIME, _build_service, _sa_list_service

    out: Dict[str, Any] = {
        "ok": False,
        "patients": [],
        "source": "folders",
        "folderCount": 0,
        "pdfParsed": 0,
        "jsonSnapshots": 0,
        "excelPatients": 0,
        "error": None,
    }
    service = None
    folder_id = ""
    try:
        service, folder_id = _build_service()
        if service is None:
            service, folder_id = _sa_list_service()
    except Exception as exc:
        out["error"] = str(exc)[:300]
        return out
    if service is None or not folder_id:
        out["error"] = "drive_unavailable"
        return out

    snapshot_patients: List[Dict[str, Any]] = []
    folder_patients: List[Dict[str, Any]] = []
    excel_patients: List[Dict[str, Any]] = []
    pdf_budget = [0]

    try:
        children = _list_direct_children_safe(service, folder_id)
    except Exception as exc:
        out["error"] = str(exc)[:300]
        return out

    # Recursive JSON snapshot search (root + u* + Archive + nested backups).
    try:
        snapshot_patients = _collect_json_snapshots(service, folder_id, depth=0, max_depth=3)
        # Count unique snapshot files approximately via patient batch sizes.
        out["jsonSnapshots"] = 1 if snapshot_patients else 0
        # Re-count files more accurately by scanning top-level names.
        snap_files = 0
        for item in children:
            n = (item.get("name") or "")
            if n.startswith("neurolab_patients_") and n.endswith(".json"):
                snap_files += 1
        if snap_files:
            out["jsonSnapshots"] = max(out["jsonSnapshots"], snap_files)
    except Exception as exc:
        print(f"Drive snapshot crawl: {exc}", flush=True)

    patient_folders = [
        item
        for item in children
        if (item.get("mimeType") or "") == FOLDER_MIME
        and parse_patient_folder_name(item.get("name") or "")
    ]
    out["folderCount"] = len(patient_folders)

    for item in patient_folders:
        folder_name = item.get("name") or ""
        skeleton = skeleton_patient_from_folder(
            folder_name, modified_time=item.get("modifiedTime")
        )
        if not skeleton:
            continue
        enriched = _enrich_patient_from_folder_contents(
            service,
            item,
            skeleton,
            parse_pdfs=parse_pdfs,
            pdf_budget=pdf_budget,
            max_pdfs=max_pdfs,
        )
        folder_patients.append(enriched)

    out["pdfParsed"] = pdf_budget[0]

    try:
        excel_patients = _excel_patients_from_drive(service, folder_id)
        out["excelPatients"] = len(excel_patients)
    except Exception as exc:
        print(f"Drive Excel restore: {exc}", flush=True)

    # Normalize snapshot kinematics too.
    try:
        from pdf_import_parser import normalize_restored_patient

        snapshot_patients = [
            normalize_restored_patient(p) if isinstance(p, dict) else p for p in snapshot_patients
        ]
    except Exception:
        pass

    merged = merge_patients(snapshot_patients, folder_patients, excel_patients)
    merged = merge_same_name_patients(merged)
    # Final pass: ensure every record has a valid ISO _savedAt.
    for p in merged:
        if isinstance(p, dict) and not Date_parse_ok(p.get("_savedAt")):
            p["_savedAt"] = _iso_from_drive_time(None)
    out["patients"] = merged
    out["ok"] = True
    out["source"] = (
        "json+folders+excel"
        if snapshot_patients and excel_patients
        else "json+folders"
        if snapshot_patients
        else "folders+excel"
        if excel_patients
        else "folders"
    )
    return out
