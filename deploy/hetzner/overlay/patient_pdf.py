"""Build one clinical PDF per patient for the Drive backup folder."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from patient_drive_archive import PROGRAM_SECTIONS, patient_drive_key, program_patient_record

SECTION_TITLES = {
    "demographics": "Demographics",
    "ipaq": "IPAQ",
    "vas": "Pain Scale (VAS)",
    "vams": "Mood Scale (VAMS-4)",
    "motorchange": "Muscle Control",
    "kgia": "Motor Imagery (KVIQ)",
    "wmft": "Wolf Motor Function (WMFT)",
    "kinematics": "Video Kinematics",
}

DEMO_LABELS = {
    "participantId": "Study ID",
    "name": "Name",
    "fullName": "Full name",
    "age": "Age",
    "sex": "Sex",
    "group": "Group",
    "strokeType": "Stroke type",
    "side": "Affected side",
    "timeSinceStroke": "Time since stroke (months)",
    "mas": "MAS",
    "mrc": "MRC",
    "height": "Height (cm)",
    "shoulderWidth": "Shoulder width (cm)",
}

SEX = {"1": "Male", "2": "Female"}
STROKE = {"1": "Ischemic", "2": "Hemorrhagic"}
SIDE = {"1": "Left", "2": "Right"}
GROUP = {"1": "AOMI", "2": "Control"}


def patient_pdf_filename(patient: Dict[str, Any]) -> str:
    return f"{patient_drive_key(patient)}.pdf"


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _demo_value(key: str, value: Any) -> str:
    raw = _plain(value)
    if not raw:
        return "—"
    if key == "sex":
        return SEX.get(raw, raw)
    if key == "strokeType":
        return STROKE.get(raw, raw)
    if key == "side":
        return SIDE.get(raw, raw)
    if key == "group":
        return GROUP.get(raw, raw)
    if key == "age":
        return f"{raw} yrs"
    if key == "timeSinceStroke":
        return f"{raw} m"
    return raw


def _flatten(value: Any, prefix: str = "") -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).startswith("_"):
                continue
            label = f"{prefix}{key}" if prefix else str(key)
            rows.extend(_flatten(item, f"{label} / "))
        return rows
    if isinstance(value, list):
        if not value:
            return [(prefix.rstrip(" /"), "—")] if prefix else []
        for index, item in enumerate(value, 1):
            rows.extend(_flatten(item, f"{prefix}{index} / "))
        return rows
    text = _plain(value)
    if not text:
        return []
    return [(prefix.rstrip(" /"), text)]


def patient_pdf_lines(patient: Dict[str, Any]) -> List[str]:
    rec = program_patient_record(patient)
    demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
    name = _plain(demo.get("name") or demo.get("fullName") or patient_drive_key(patient))
    pid = _plain(demo.get("participantId") or rec.get("_id") or "")
    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "Stroke Rehabilitation Research Platform",
        "Clinical Assessment Report",
        f"Date: {stamped}",
        f"Patient: {name}",
        f"Study ID: {pid or '—'}",
        "",
        "Demographics",
        "------------",
    ]
    for key, label in DEMO_LABELS.items():
        if key in demo and _plain(demo.get(key)):
            lines.append(f"{label}: {_demo_value(key, demo.get(key))}")
    for key, value in demo.items():
        if key in DEMO_LABELS or str(key).startswith("_"):
            continue
        if _plain(value):
            lines.append(f"{key}: {_plain(value)}")
    for section in PROGRAM_SECTIONS:
        if section == "demographics":
            continue
        rows = _flatten(rec.get(section) or {})
        lines.extend(["", SECTION_TITLES.get(section, section), "-" * len(SECTION_TITLES.get(section, section))])
        if not rows:
            lines.append("No data")
            continue
        for label, value in rows[:80]:
            lines.append(f"{label}: {value}")
    return lines


def _latin1(text: str) -> str:
    table = str.maketrans(
        {
            "ş": "s",
            "Ş": "S",
            "ğ": "g",
            "Ğ": "G",
            "ı": "i",
            "İ": "I",
            "ç": "c",
            "Ç": "C",
            "ö": "o",
            "Ö": "O",
            "ü": "u",
            "Ü": "U",
        }
    )
    return (text or "").translate(table).encode("latin-1", "replace").decode("latin-1")


def _escape_pdf(text: str) -> str:
    return _latin1(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_text_pdf(lines: List[str], *, title: str = "NeuroLab Report") -> bytes:
    """Minimal one-column PDF. Helvetica only; no extra packages."""
    width, height = 595, 842
    left, top, bottom = 48, 800, 48
    leading = 13
    per_page = max(1, int((top - bottom) / leading))
    pages: List[List[str]] = []
    chunk: List[str] = []
    for line in lines or [""]:
        wrapped = _wrap_line(line, 92)
        for part in wrapped or [""]:
            chunk.append(part)
            if len(chunk) >= per_page:
                pages.append(chunk)
                chunk = []
    if chunk or not pages:
        pages.append(chunk or [""])

    objects: List[bytes] = [b""]
    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects) - 1

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: List[int] = []
    for page_lines in pages:
        y = top
        cmds = ["BT", "/F1 11 Tf", f"{left} {y} Td"]
        for index, line in enumerate(page_lines):
            if index:
                cmds.append(f"0 -{leading} Td")
            cmds.append(f"({_escape_pdf(line)}) Tj")
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1", "replace")
        content_id = add(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        page_ids.append(
            add(
                (
                    f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {width} {height}] "
                    f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
                ).encode("latin-1")
            )
        )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1")
    )
    for pid in page_ids:
        objects[pid] = objects[pid].replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("latin-1"))
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))
    safe_title = _escape_pdf(title)[:120]
    info_id = add(f"<< /Title ({safe_title}) /Producer (NeuroLab) >>".encode("latin-1"))

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, payload in enumerate(objects):
        if index == 0:
            offsets.append(0)
            continue
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("latin-1"))
        out.extend(payload)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for index in range(1, len(objects)):
        out.extend(f"{offsets[index]:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects)} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(out)


def _wrap_line(text: str, width: int) -> List[str]:
    raw = (text or "").replace("\r", "")
    if not raw:
        return [""]
    words = raw.split(" ")
    lines: List[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def build_patient_pdf(patient: Dict[str, Any]) -> bytes:
    lines = patient_pdf_lines(patient)
    return render_text_pdf(lines, title=patient_pdf_filename(patient))
