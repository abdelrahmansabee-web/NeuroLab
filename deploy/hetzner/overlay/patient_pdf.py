"""Clinical Assessment Report PDF — same title/sections as the clinic Export PDF."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from patient_drive_archive import PROGRAM_SECTIONS, patient_drive_key, program_patient_record

SEX = {"1": "Male", "2": "Female"}
STROKE = {"1": "Ischemic", "2": "Hemorrhagic"}
SIDE = {"1": "Left", "2": "Right"}
GROUP = {"1": "AOMI", "2": "Control"}

VAS_ITEMS = (
    ("rest", "Pain at Rest"),
    ("activity", "Pain During Activity"),
    ("night", "Night Pain"),
)
VAMS_ITEMS = (
    ("happy", "VAMS Happy"),
    ("sad", "VAMS Sad"),
    ("calm", "VAMS Calm"),
    ("tense", "VAMS Tense"),
)
MOTOR_ITEMS = (
    ("control", "pre", "How much do you feel you can control your muscles?"),
    ("difference", "post", "How much do you feel a difference in muscle control?"),
)


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


def _cell(value: Any) -> str:
    text = _plain(value)
    return text if text else "—"


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


def _delta(pre: str, post: str) -> str:
    try:
        left = float(pre)
        right = float(post)
    except (TypeError, ValueError):
        return "—"
    diff = right - left
    if diff == 0:
        return "0.00"
    return f"{diff:+.2f}"


def _pair(section: Dict[str, Any], key: str) -> Tuple[str, str]:
    item = section.get(key)
    if isinstance(item, dict):
        return _cell(item.get("pre")), _cell(item.get("post"))
    return "—", "—"


def _table(lines: List[str], title: str, rows: List[Tuple[str, str, str, str]]) -> None:
    lines.extend(["", title])
    lines.append("Metric / Task                  Pre      Post     Change")
    if not rows:
        lines.append("No data")
        return
    for metric, pre, post, change in rows:
        label = (metric or "—")[:28].ljust(28)
        lines.append(f"{label}  {pre:<8} {post:<8} {change}")


def patient_pdf_lines(patient: Dict[str, Any]) -> List[str]:
    rec = program_patient_record(patient)
    demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
    name = _plain(demo.get("name") or demo.get("fullName") or patient_drive_key(patient))
    pid = _plain(demo.get("participantId") or rec.get("_id") or "")
    stamped = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = [
        "Stroke Rehabilitation Research Platform",
        "Clinical Assessment Report",
        stamped,
        "",
        name or "Participant",
        f"ID: {pid}" if pid else "ID: —",
        "",
        f"Age: {_demo_value('age', demo.get('age'))}    "
        f"Sex: {_demo_value('sex', demo.get('sex'))}    "
        f"Stroke: {_demo_value('strokeType', demo.get('strokeType'))}",
        f"Side: {_demo_value('side', demo.get('side'))}    "
        f"TSS: {_demo_value('timeSinceStroke', demo.get('timeSinceStroke'))}    "
        f"Group: {_demo_value('group', demo.get('group'))}",
        f"MAS: {_cell(demo.get('mas'))}    MRC: {_cell(demo.get('mrc'))}",
    ]

    vas = rec.get("vas") if isinstance(rec.get("vas"), dict) else {}
    vas_rows = []
    for key, label in VAS_ITEMS:
        pre, post = _pair(vas, key)
        vas_rows.append((label, pre, post, _delta(pre, post)))
    _table(lines, "Pain Scale (VAS)", vas_rows)

    vams = rec.get("vams") if isinstance(rec.get("vams"), dict) else {}
    vams_rows = []
    for key, label in VAMS_ITEMS:
        pre, post = _pair(vams, key)
        vams_rows.append((label, pre, post, _delta(pre, post)))
    _table(lines, "Mood Scale (VAMS-4)", vams_rows)

    motor = rec.get("motorchange") if isinstance(rec.get("motorchange"), dict) else {}
    motor_rows = []
    for key, phase, label in MOTOR_ITEMS:
        val = _cell(motor.get(key))
        pre = val if phase == "pre" else "—"
        post = val if phase == "post" else "—"
        motor_rows.append((label, pre, post, "—"))
    _table(lines, "Muscle Control Scale", motor_rows)

    kgia = rec.get("kgia") if isinstance(rec.get("kgia"), dict) else {}
    kgia_rows = []
    for key, item in kgia.items():
        if str(key).startswith("_"):
            continue
        if isinstance(item, dict):
            pre = _cell(item.get("once") or item.get("pre"))
            post = _cell(item.get("sonra") or item.get("post"))
        else:
            pre, post = _cell(item), "—"
        kgia_rows.append((str(key), pre, post, _delta(pre, post)))
    _table(lines, "Motor Imagery (KVIQ)", kgia_rows[:40])

    wmft = rec.get("wmft") if isinstance(rec.get("wmft"), dict) else {}
    wmft_rows = []
    if "score" in wmft and not any(isinstance(wmft.get(k), dict) for k in wmft if k != "score"):
        wmft_rows.append(("WMFT score", _cell(wmft.get("score")), "—", "—"))
    for key, item in wmft.items():
        if str(key).startswith("_") or key == "score":
            continue
        if not isinstance(item, dict):
            wmft_rows.append((str(key), _cell(item), "—", "—"))
            continue
        pre = item.get("pre") if isinstance(item.get("pre"), dict) else {}
        post = item.get("post") if isinstance(item.get("post"), dict) else {}
        pre_t, post_t = _cell(pre.get("time")), _cell(post.get("time"))
        pre_r, post_r = _cell(pre.get("rating")), _cell(post.get("rating"))
        wmft_rows.append((f"{key} — Time (sec)", pre_t, post_t, _delta(pre_t, post_t)))
        wmft_rows.append((f"{key} — Ability (0-5)", pre_r, post_r, _delta(pre_r, post_r)))
    _table(lines, "Wolf Motor Function (WMFT)", wmft_rows[:40])

    kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
    if kin:
        lines.extend(["", "Video Kinematic Analysis"])
        for phase in ("pre", "post", "baseline", "healthy"):
            block = kin.get(phase)
            if not isinstance(block, dict) or not block:
                continue
            label = "Healthy side" if phase in ("baseline", "healthy") else phase.capitalize()
            lines.append(f"{label}: data recorded")

    lines.extend(["", "Stroke Rehab Platform  |  Confidential"])
    _ = PROGRAM_SECTIONS
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


def render_text_pdf(lines: List[str], *, title: str = "Clinical Assessment Report") -> bytes:
    """Valid PDF-1.4 that iPad Drive / Files can open."""
    width, height = 595, 842
    left, top, bottom = 48, 800, 48
    leading = 13
    per_page = max(1, int((top - bottom) / leading))
    pages: List[List[str]] = []
    chunk: List[str] = []
    for line in lines or [""]:
        for part in _wrap_line(line, 92) or [""]:
            chunk.append(part)
            if len(chunk) >= per_page:
                pages.append(chunk)
                chunk = []
    if chunk or not pages:
        pages.append(chunk or [""])

    objects: List[Optional[bytes]] = [None]

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
    add(f"<< /Title ({safe_title}) /Producer (NeuroLab Clinical Report) >>".encode("latin-1"))

    out = bytearray(b"%PDF-1.4\n%\x80\x80\x80\x80\n")
    offsets = [0] * len(objects)
    for index in range(1, len(objects)):
        offsets[index] = len(out)
        out.extend(f"{index} 0 obj\n".encode("latin-1"))
        out.extend(objects[index] or b"<< >>")
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for index in range(1, len(objects)):
        out.extend(f"{offsets[index]:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects)} /Root {catalog_id} 0 R /Info {len(objects) - 1} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(out)


def build_patient_pdf(patient: Dict[str, Any]) -> bytes:
    name = _plain(
        (patient.get("demographics") or {}).get("name")
        if isinstance(patient.get("demographics"), dict)
        else ""
    )
    return render_text_pdf(
        patient_pdf_lines(patient),
        title=f"Clinical Assessment Report — {name or patient_drive_key(patient)}",
    )
