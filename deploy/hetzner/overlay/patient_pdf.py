"""Clinical Assessment Report PDF — same metrics/labels as the clinic Export Report."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from patient_drive_archive import PROGRAM_SECTIONS, patient_drive_key, program_patient_record

MISSING = "\u2014"

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
KGIA_MOVEMENTS = (
    "Neck forward–backward flexion",
    "Shoulder elevation (shrug)",
    "Forward arm raise",
    "Elbow flexion",
    "Thumb-to-finger opposition",
    "Forward trunk lean",
    "Knee extension",
    "Hip abduction",
    "Foot tapping",
    "Foot external rotation",
)
KGIA_TYPES = (("gorsel", "Visual"), ("kinestetik", "Kinesthetic"))
WMFT_ITEMS = (
    (1, "Hand to Table (front)"),
    (2, "Hand to Box (front)"),
    (3, "Extend Elbow (no weight)"),
    (4, "Lift Can (front)"),
)
IPAQ_ACTS = (
    ("high", "High intensity (running, heavy work)", 8.0),
    ("medium", "Moderate intensity (brisk walking, housework)", 4.0),
    ("light", "Light activity (slow walking, daily movements)", 3.3),
    ("sitting", "Total daily sitting time", 0.0),
    ("extra", "Additional (cycling, swimming, etc.)", 4.0),
)
KINEMATIC_VARS = (
    ("nvp", "Number of Velocity Peaks (NVP)", "count", "lower"),
    ("straightness", "Path straightness", "ratio", "higher"),
    ("pause_time_sec", "Pause time", "s", "lower"),
    ("number_of_stops", "Number of stops", "count", "lower"),
    ("trunk_ratio", "Trunk ratio", "ratio", "lower"),
    ("shoulder_elevation_norm", "Shoulder elevation (norm)", "ratio", "lower"),
    ("shoulder_elevation_table_ratio", "Shoulder elevation / table", "ratio", "lower"),
    ("shoulder_elevation_palm_ratio", "Shoulder elevation / palm anchor", "ratio", "lower"),
    ("elbow_angle_mean_deg", "Elbow angle (mean)", "deg", "none"),
    ("movement_time_sec", "Movement time", "s", "lower"),
    ("peak_elbow_ang_vel_deg_s", "Peak elbow angular velocity", "deg/s", "higher"),
)

# jsPDF / glass badge colors
COLOR_VAS = (225, 29, 72)
COLOR_VAMS = (14, 165, 233)
COLOR_MOTOR = (16, 185, 129)
COLOR_KVIQ = (13, 148, 136)
COLOR_WMFT = (14, 165, 233)
COLOR_KIN = (244, 63, 94)
COLOR_IPAQ = (14, 165, 233)
COLOR_TEAL = (13, 148, 136)
COLOR_HEADER = (15, 23, 42)
COLOR_MUTED = (100, 116, 139)
COLOR_LINE = (226, 232, 240)
COLOR_ROW = (248, 250, 252)
COLOR_GREEN = (22, 163, 74)
COLOR_RED = (220, 38, 38)

PAGE_W = 595.0
PAGE_H = 842.0
MARGIN = 40.0
CONTENT_W = PAGE_W - 2 * MARGIN
COL_METRIC = 300.0
COL_PRE = 58.0
COL_POST = 58.0
COL_CHANGE = 70.0


def patient_pdf_filename(patient: Dict[str, Any]) -> str:
    return f"{patient_drive_key(patient)}.pdf"


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()


def _cell(value: Any) -> str:
    text = _plain(value)
    return text if text else MISSING


def _demo_value(key: str, value: Any) -> str:
    raw = _plain(value)
    if not raw:
        return MISSING
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
        return f"{raw} months"
    return raw


def _delta(pre: str, post: str) -> str:
    try:
        left = float(pre)
        right = float(post)
    except (TypeError, ValueError):
        return MISSING
    diff = right - left
    if diff == 0:
        return "0.00"
    return f"{diff:+.2f}"


def _pair(section: Dict[str, Any], key: str, pre_key: str = "pre", post_key: str = "post") -> Tuple[str, str]:
    item = section.get(key)
    if isinstance(item, dict):
        return _cell(item.get(pre_key)), _cell(item.get(post_key))
    return MISSING, MISSING


def _lower_is_better(name: str) -> bool:
    n = (name or "").lower()
    return any(
        token in n
        for token in ("pain", "anxiety", "distress", "fear", "confusion", "sad", "fatigue", "tension", "tense")
    )


def _improving(pre: str, post: str, metric: str, *, lower: Optional[bool] = None) -> Optional[bool]:
    try:
        left = float(pre)
        right = float(post)
    except (TypeError, ValueError):
        return None
    if left == right:
        return None
    if lower is None:
        lower = _lower_is_better(metric)
    return left > right if lower else right > left


def _has_value(*cells: str) -> bool:
    return any(cell != MISSING and cell != "" for cell in cells)


def _tool_interp(tool: str, rows: Sequence[Dict[str, Any]]) -> str:
    items = [r for r in rows if r.get("delta") != MISSING]
    if tool == "VAS":
        imp = sum(1 for r in items if r.get("improving") is True)
        wors = sum(1 for r in items if r.get("improving") is False)
        if imp and not wors:
            return "Pain decreased"
        if wors and not imp:
            return "Pain increased"
        if imp and wors:
            return "Mixed pain results"
        return "Pain stable" if items or any(_has_value(r["pre"], r["post"]) for r in rows) else ""
    if tool == "VAMS":
        pos_up = sum(1 for r in items if any(n in r["metric"] for n in ("Happy", "Calm")) and r.get("improving"))
        neg_down = sum(1 for r in items if any(n in r["metric"] for n in ("Sad", "Tense")) and r.get("improving"))
        parts = []
        if pos_up:
            parts.append("Positive mood improved")
        if neg_down:
            parts.append("Negative mood decreased")
        return ", ".join(parts) or ("Mood stable" if items else "")
    if tool == "Muscle Control":
        pre_val = next((r["pre"] for r in rows if r["pre"] != MISSING), "")
        post_val = next((r["post"] for r in rows if r["post"] != MISSING), "")
        try:
            if float(post_val) > float(pre_val):
                return "Muscle control improved"
            if float(post_val) < float(pre_val):
                return "Muscle control declined"
        except (TypeError, ValueError):
            pass
        return "Muscle control stable" if pre_val or post_val else ""
    if tool == "KVIQ":
        imp = sum(1 for r in items if r.get("improving"))
        tot = len(items)
        if tot and imp > tot / 2:
            return "Imagery improved in most items"
        if imp:
            return "Imagery improved in some items"
        return "Imagery stable" if tot else ""
    if tool == "WMFT":
        time_rows = [r for r in items if "Time" in r["metric"]]
        rate_rows = [r for r in items if "Rating" in r["metric"]]
        parts = []
        if any(r.get("improving") for r in time_rows):
            parts.append("Faster task time")
        if any(r.get("improving") is False for r in time_rows):
            parts.append("Slower task time")
        if any(r.get("improving") for r in rate_rows):
            parts.append("Functional ability improved")
        if any(r.get("improving") is False for r in rate_rows):
            parts.append("Functional ability declined")
        if not parts and items:
            parts.append("No notable change in WMFT")
        return ", ".join(parts)
    if tool == "Kinematics":
        imp = sum(1 for r in items if r.get("improving"))
        tot = len(items)
        if tot and imp > tot / 2:
            return "Kinematics improved"
        if imp:
            return "Kinematics partially improved"
        return "Kinematics stable" if tot else ""
    return ""


def build_summary_rows(patient: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Same rows as frontend buildSummaryRows() in App.js."""
    rec = program_patient_record(patient)
    rows: List[Dict[str, Any]] = []

    vas = rec.get("vas") if isinstance(rec.get("vas"), dict) else {}
    for key, label in VAS_ITEMS:
        pre, post = _pair(vas, key)
        rows.append(
            {
                "tool": "VAS",
                "metric": label,
                "pre": pre,
                "post": post,
                "delta": _delta(pre, post),
                "improving": _improving(pre, post, label),
            }
        )

    vams = rec.get("vams") if isinstance(rec.get("vams"), dict) else {}
    for key, label in VAMS_ITEMS:
        pre, post = _pair(vams, key)
        rows.append(
            {
                "tool": "VAMS",
                "metric": label,
                "pre": pre,
                "post": post,
                "delta": _delta(pre, post),
                "improving": _improving(pre, post, label),
            }
        )

    motor = rec.get("motorchange") if isinstance(rec.get("motorchange"), dict) else {}
    for key, phase, label in MOTOR_ITEMS:
        val = _cell(motor.get(key))
        pre = val if phase == "pre" else MISSING
        post = val if phase == "post" else MISSING
        rows.append({"tool": "Muscle Control", "metric": label, "pre": pre, "post": post, "delta": MISSING, "improving": None})

    kgia = rec.get("kgia") if isinstance(rec.get("kgia"), dict) else {}
    for index, movement in enumerate(KGIA_MOVEMENTS):
        for type_key, type_en in KGIA_TYPES:
            pre, post = _pair(kgia, f"{index}_{type_key}", "once", "sonra")
            if pre == MISSING and post == MISSING:
                pre, post = _pair(kgia, f"{index}_{type_key}")
            metric = f"{type_en}: {movement}"
            rows.append(
                {
                    "tool": "KVIQ",
                    "metric": metric,
                    "pre": pre,
                    "post": post,
                    "delta": _delta(pre, post),
                    "improving": _improving(pre, post, metric, lower=False),
                }
            )

    wmft = rec.get("wmft") if isinstance(rec.get("wmft"), dict) else {}
    for task_id, label in WMFT_ITEMS:
        item = wmft.get(task_id)
        if item is None:
            item = wmft.get(str(task_id))
        if not isinstance(item, dict):
            item = {}
        pre = item.get("pre") if isinstance(item.get("pre"), dict) else {}
        post = item.get("post") if isinstance(item.get("post"), dict) else {}
        pre_t, post_t = _cell(pre.get("time")), _cell(post.get("time"))
        pre_r, post_r = _cell(pre.get("rating")), _cell(post.get("rating"))
        time_metric = f"{label} — Time (sec)"
        rate_metric = f"{label} — Ability Rating (0–5)"
        rows.append(
            {
                "tool": "WMFT",
                "metric": time_metric,
                "pre": pre_t,
                "post": post_t,
                "delta": _delta(pre_t, post_t),
                "improving": _improving(pre_t, post_t, time_metric, lower=True),
            }
        )
        rows.append(
            {
                "tool": "WMFT",
                "metric": rate_metric,
                "pre": pre_r,
                "post": post_r,
                "delta": _delta(pre_r, post_r),
                "improving": _improving(pre_r, post_r, rate_metric, lower=False),
            }
        )

    kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
    pre_kin = kin.get("pre") if isinstance(kin.get("pre"), dict) else {}
    post_kin = kin.get("post") if isinstance(kin.get("post"), dict) else {}
    for key, label, _unit, direction in KINEMATIC_VARS:
        pre, post = _cell(pre_kin.get(key)), _cell(post_kin.get(key))
        rows.append(
            {
                "tool": "Kinematics",
                "metric": label,
                "pre": pre,
                "post": post,
                "delta": _delta(pre, post),
                "improving": _improving(pre, post, label, lower=(direction == "lower")),
            }
        )
    _ = PROGRAM_SECTIONS
    return rows


def _ipaq_rows(patient: Dict[str, Any]) -> List[Tuple[str, str, str, str, str, str]]:
    rec = program_patient_record(patient)
    ipaq = rec.get("ipaq") if isinstance(rec.get("ipaq"), dict) else {}
    out = []
    for key, label, met in IPAQ_ACTS:
        item = ipaq.get(key) if isinstance(ipaq.get(key), dict) else {}
        gun = _plain(item.get("gun"))
        sure = _plain(item.get("sure"))
        if not gun and not sure:
            continue
        try:
            tot = float(gun or 0) * float(sure or 0)
        except (TypeError, ValueError):
            tot = 0.0
        met_min = tot * met
        out.append((label, gun or "0", sure or "0", f"{tot:.0f}", f"{met:g}", f"{met_min:.0f}"))
    return out


def patient_pdf_lines(patient: Dict[str, Any]) -> List[str]:
    rec = program_patient_record(patient)
    demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
    name = _plain(demo.get("name") or demo.get("fullName") or patient_drive_key(patient))
    pid = _plain(demo.get("participantId") or rec.get("_id") or "")
    group = _demo_value("group", demo.get("group"))
    group_title = "AOMI Group" if group == "AOMI" else ("Control Group" if group == "Control" else "Clinical Assessment Report")
    stamped = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = [
        group_title,
        "Clinical Assessment Report",
        stamped,
        "",
        name or "Participant",
        f"ID: {pid}" if pid else f"ID: {MISSING}",
        "",
        f"Age: {_demo_value('age', demo.get('age'))}",
        f"Sex: {_demo_value('sex', demo.get('sex'))}",
        f"Stroke Type: {_demo_value('strokeType', demo.get('strokeType'))}",
        f"Affected Side: {_demo_value('side', demo.get('side'))}",
        f"Time Since Stroke: {_demo_value('timeSinceStroke', demo.get('timeSinceStroke'))}",
        f"MAS: {_cell(demo.get('mas'))}",
        f"MRC: {_cell(demo.get('mrc'))}",
    ]

    tool_meta = {
        "VAS": "Pain Scale (VAS)",
        "VAMS": "Mood Scale (VAMS-4)",
        "Muscle Control": "Muscle Control Scale",
        "KVIQ": "Motor Imagery (KVIQ)",
        "WMFT": "Wolf Motor Function (WMFT)",
        "Kinematics": "Kinematic Analysis",
    }
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in build_summary_rows(patient):
        grouped.setdefault(row["tool"], []).append(row)

    ipaq_rows = _ipaq_rows(patient)
    if ipaq_rows:
        lines.extend(["", "Physical Activity (IPAQ)", "Activity  Days/wk  Min/day  Total min/wk  MET  MET-min/wk"])
        for row in ipaq_rows:
            lines.append("  ".join(row))

    for tool in ("VAS", "VAMS", "Muscle Control", "KVIQ", "WMFT", "Kinematics"):
        trows = grouped.get(tool) or []
        if not any(_has_value(r["pre"], r["post"]) for r in trows):
            continue
        lines.extend(["", tool_meta[tool], "Metric / Task                  Pre      Post     Change"])
        display = trows
        if tool == "Muscle Control":
            pre_val = next((r["pre"] for r in trows if r["pre"] != MISSING), MISSING)
            post_val = next((r["post"] for r in trows if r["post"] != MISSING), MISSING)
            display = [
                {
                    "metric": "Felt Difference",
                    "pre": pre_val,
                    "post": post_val,
                    "delta": _delta(pre_val, post_val),
                    "improving": _improving(pre_val, post_val, "Muscle Control", lower=False),
                }
            ]
        for row in display:
            lines.append(f"{row['metric']}  {row['pre']}  {row['post']}  {row['delta']}")
        note = _tool_interp(tool, trows)
        if note:
            lines.append(note)

    kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
    phases = [p for p in ("pre", "post", "baseline", "healthy") if isinstance(kin.get(p), dict) and kin.get(p)]
    if phases:
        lines.extend(["", "Video Kinematic Analysis"])
        for phase in phases:
            label = "Healthy side" if phase in ("baseline", "healthy") else phase.capitalize()
            block = kin.get(phase) if isinstance(kin.get(phase), dict) else {}
            if any(_plain(block.get(key)) for key, *_rest in KINEMATIC_VARS):
                lines.append(f"{label}: data recorded")

    lines.extend(["", "Stroke Rehab Platform  |  Confidential"])
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
            "—": "-",
            "–": "-",
            "−": "-",
            "‐": "-",
            "‑": "-",
            "‘": "'",
            "’": "'",
            "“": '"',
            "”": '"',
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
        while len(word) > width:
            lines.append(word[:width])
            word = word[width:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _pdf_color(rgb: Tuple[int, int, int]) -> str:
    return f"{rgb[0] / 255:.3f} {rgb[1] / 255:.3f} {rgb[2] / 255:.3f}"


class _Canvas:
    def __init__(self) -> None:
        self.pages: List[List[str]] = [[]]
        self.y = PAGE_H - 36

    def _ops(self) -> List[str]:
        return self.pages[-1]

    def new_page(self) -> None:
        self.pages.append([])
        self.y = PAGE_H - 36

    def ensure(self, needed: float) -> None:
        if self.y - needed < 52:
            self.new_page()

    def fill_rect(self, x: float, y: float, w: float, h: float, rgb: Tuple[int, int, int]) -> None:
        self._ops().append(f"{_pdf_color(rgb)} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def stroke_rect(self, x: float, y: float, w: float, h: float, rgb: Tuple[int, int, int], width: float = 0.6) -> None:
        self._ops().append(
            f"{_pdf_color(rgb)} RG {width:.2f} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S"
        )

    def text(self, s: str, x: float, y: float, size: float = 10, *, bold: bool = False, rgb: Tuple[int, int, int] = COLOR_HEADER, align: str = "left") -> None:
        font = "F2" if bold else "F1"
        escaped = _escape_pdf(s)
        if align == "center":
            # Helvetica average width ~0.5 em
            x = x - 0.5 * size * 0.5 * len(_latin1(s))
        elif align == "right":
            x = x - 0.5 * size * len(_latin1(s))
        self._ops().append(
            f"BT /{font} {size:.1f} Tf {_pdf_color(rgb)} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET"
        )

    def hline(self, y: float) -> None:
        self._ops().append(f"{_pdf_color(COLOR_LINE)} RG 0.5 w {MARGIN:.2f} {y:.2f} m {PAGE_W - MARGIN:.2f} {y:.2f} l S")


def _draw_table(
    cv: _Canvas,
    title: str,
    color: Tuple[int, int, int],
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    note: str = "",
    improving: Optional[Sequence[Optional[bool]]] = None,
) -> None:
    metric_width_chars = 46
    prepared: List[Tuple[List[str], Sequence[str]]] = []
    for row in rows:
        metric_lines = _wrap_line(str(row[0]), metric_width_chars)
        prepared.append((metric_lines, row))
    header_h = 18
    note_h = 16 if note else 0
    cv.ensure(36 + header_h + 16 + note_h)
    cv.y -= 8
    # section badge
    badge_w = min(CONTENT_W, 8 + 5.2 * len(title))
    cv.fill_rect(MARGIN, cv.y - 12, badge_w, 16, color)
    cv.text(title, MARGIN + 8, cv.y - 8, 8, bold=True, rgb=(255, 255, 255))
    cv.y -= 22

    def draw_header() -> None:
        cv.fill_rect(MARGIN, cv.y - 12, CONTENT_W, header_h, color)
        xs = [MARGIN + 8, MARGIN + COL_METRIC, MARGIN + COL_METRIC + COL_PRE, MARGIN + COL_METRIC + COL_PRE + COL_POST]
        labels = list(headers)[:4] or ["Metric / Task", "Pre", "Post", "Change"]
        cv.text(labels[0], xs[0], cv.y - 7, 8, bold=True, rgb=(255, 255, 255))
        for label, x in zip(labels[1:], xs[1:]):
            cv.text(label, x + 24, cv.y - 7, 8, bold=True, rgb=(255, 255, 255), align="center")
        cv.y -= header_h

    draw_header()
    for index, (metric_lines, row) in enumerate(prepared):
        row_h = max(16.0, 11.0 * len(metric_lines) + 6.0)
        if cv.y - row_h < 56:
            cv.new_page()
            draw_header()
        if index % 2 == 1:
            cv.fill_rect(MARGIN, cv.y - row_h + 4, CONTENT_W, row_h, COLOR_ROW)
        baseline = cv.y - 10
        cv.text(metric_lines[0], MARGIN + 8, baseline, 8)
        for extra_i, extra in enumerate(metric_lines[1:], start=1):
            cv.text(extra, MARGIN + 8, baseline - 11 * extra_i, 8)
        nums = [str(row[i]) if i < len(row) else MISSING for i in range(1, 4)]
        xs = [
            MARGIN + COL_METRIC + COL_PRE / 2,
            MARGIN + COL_METRIC + COL_PRE + COL_POST / 2,
            MARGIN + COL_METRIC + COL_PRE + COL_POST + COL_CHANGE / 2,
        ]
        imp = None
        if improving is not None and index < len(improving):
            imp = improving[index]
        change_color = COLOR_HEADER
        if nums[2] == MISSING:
            change_color = COLOR_MUTED
        elif imp is True:
            change_color = COLOR_GREEN
        elif imp is False:
            change_color = COLOR_RED
        for value, x, rgb in zip(nums, xs, (COLOR_HEADER, COLOR_HEADER, change_color)):
            cv.text(value, x, baseline, 8, bold=(rgb != COLOR_MUTED and value != MISSING), rgb=rgb, align="center")
        cv.y -= row_h
    if note:
        cv.ensure(18)
        cv.text(note, MARGIN + 8, cv.y - 10, 8, rgb=COLOR_MUTED)
        cv.y -= 16
    cv.y -= 10


def render_clinical_pdf(patient: Dict[str, Any], *, title: str = "Clinical Assessment Report") -> bytes:
    rec = program_patient_record(patient)
    demo = rec.get("demographics") if isinstance(rec.get("demographics"), dict) else {}
    name = _plain(demo.get("name") or demo.get("fullName") or "Participant") or "Participant"
    pid = _plain(demo.get("participantId") or rec.get("_id") or "")
    group = _demo_value("group", demo.get("group"))
    group_title = "AOMI Group" if group == "AOMI" else ("Control Group" if group == "Control" else "Stroke Rehabilitation Research Platform")
    stamped = datetime.now(timezone.utc).strftime("%d %b %Y")

    cv = _Canvas()
    # Header card
    header_h = 52
    cv.fill_rect(MARGIN, cv.y - header_h, CONTENT_W, header_h, (240, 253, 250) if group == "AOMI" else (253, 242, 248))
    cv.stroke_rect(MARGIN, cv.y - header_h, CONTENT_W, header_h, COLOR_LINE)
    cv.fill_rect(MARGIN, cv.y - header_h, 6, header_h, COLOR_TEAL)
    cv.text(group_title, MARGIN + 16, cv.y - 20, 13, bold=True)
    cv.text("Clinical Assessment Report", MARGIN + 16, cv.y - 36, 9, rgb=COLOR_MUTED)
    cv.text(stamped, PAGE_W - MARGIN - 12, cv.y - 20, 8, rgb=COLOR_MUTED, align="right")
    cv.text(name, PAGE_W - MARGIN - 12, cv.y - 36, 8, rgb=COLOR_MUTED, align="right")
    cv.y -= header_h + 14

    # Patient card
    demo_items = [
        ("Age", _demo_value("age", demo.get("age"))),
        ("Sex", _demo_value("sex", demo.get("sex"))),
        ("Stroke Type", _demo_value("strokeType", demo.get("strokeType"))),
        ("Affected Side", _demo_value("side", demo.get("side"))),
        ("Time Since Stroke", _demo_value("timeSinceStroke", demo.get("timeSinceStroke"))),
        ("MAS", _cell(demo.get("mas"))),
        ("MRC", _cell(demo.get("mrc"))),
        ("Group", group),
    ]
    patient_h = 102
    cv.ensure(patient_h + 8)
    cv.fill_rect(MARGIN, cv.y - patient_h, CONTENT_W, patient_h, (255, 255, 255))
    cv.stroke_rect(MARGIN, cv.y - patient_h, CONTENT_W, patient_h, COLOR_LINE)
    cv.fill_rect(MARGIN, cv.y - patient_h, 6, patient_h, COLOR_TEAL)
    cv.text(name, MARGIN + 16, cv.y - 18, 14, bold=True)
    cv.text(f"ID: {pid}" if pid else f"ID: {MISSING}", MARGIN + 16, cv.y - 32, 8, rgb=COLOR_MUTED)
    col_w = CONTENT_W / 4
    for i, (label, value) in enumerate(demo_items):
        cx = MARGIN + 16 + (i % 4) * col_w
        cy = cv.y - (50 if i < 4 else 78)
        cv.text(label, cx, cy, 6.5, rgb=COLOR_MUTED)
        cv.text(value, cx, cy - 12, 9, bold=True)
    cv.y -= patient_h + 16

    ipaq_rows = _ipaq_rows(patient)
    if ipaq_rows:
        _draw_table(
            cv,
            "Physical Activity (IPAQ)",
            COLOR_IPAQ,
            ["Activity", "Days/wk", "Min/day", "MET-min"],
            [(r[0], r[1], r[2], r[5]) for r in ipaq_rows],
        )

    tool_meta = {
        "VAS": ("Pain Scale (VAS)", COLOR_VAS),
        "VAMS": ("Mood Scale (VAMS-4)", COLOR_VAMS),
        "Muscle Control": ("Muscle Control Scale", COLOR_MOTOR),
        "KVIQ": ("Motor Imagery (KVIQ)", COLOR_KVIQ),
        "WMFT": ("Wolf Motor Function (WMFT)", COLOR_WMFT),
        "Kinematics": ("Kinematic Analysis", COLOR_KIN),
    }
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in build_summary_rows(patient):
        grouped.setdefault(row["tool"], []).append(row)

    for tool in ("VAS", "VAMS", "Muscle Control", "KVIQ", "WMFT", "Kinematics"):
        trows = grouped.get(tool) or []
        if not any(_has_value(r["pre"], r["post"]) for r in trows):
            continue
        display = trows
        if tool == "Muscle Control":
            pre_val = next((r["pre"] for r in trows if r["pre"] != MISSING), MISSING)
            post_val = next((r["post"] for r in trows if r["post"] != MISSING), MISSING)
            display = [
                {
                    "metric": "Felt Difference",
                    "pre": pre_val,
                    "post": post_val,
                    "delta": _delta(pre_val, post_val),
                    "improving": _improving(pre_val, post_val, "Muscle Control", lower=False),
                }
            ]
        title_s, color = tool_meta[tool]
        _draw_table(
            cv,
            title_s,
            color,
            ["Metric / Task", "Pre", "Post", "Change"],
            [(r["metric"], r["pre"], r["post"], r["delta"]) for r in display],
            note=_tool_interp(tool, trows),
            improving=[r.get("improving") for r in display],
        )

    kin = rec.get("kinematics") if isinstance(rec.get("kinematics"), dict) else {}
    phase_map = [("pre", "Pre"), ("post", "Post"), ("baseline", "Healthy side"), ("healthy", "Healthy side")]
    present = []
    seen_healthy = False
    for key, label in phase_map:
        block = kin.get(key)
        if not isinstance(block, dict) or not block:
            continue
        if key in ("baseline", "healthy"):
            if seen_healthy:
                continue
            seen_healthy = True
        present.append((label, block))
    if present:
        headers = ["Variable"] + [label for label, _block in present]
        body = []
        for key, label, unit, _direction in KINEMATIC_VARS:
            if "shoulder width" in label.lower():
                continue
            row = [f"{label} ({unit})" if unit and unit != "count" else label]
            for _plabel, block in present:
                row.append(_cell(block.get(key)))
            if any(cell != MISSING for cell in row[1:]):
                # pad to 4 columns for the table helper
                while len(row) < 4:
                    row.append("")
                body.append(row[:4])
        if body:
            _draw_table(cv, "Video Kinematic Analysis", COLOR_TEAL, headers[:4], body)

    # footers
    total = len(cv.pages)
    for index, ops in enumerate(cv.pages, start=1):
        footer = (
            f"{_pdf_color(COLOR_LINE)} RG 0.4 w {MARGIN:.2f} 40.00 m {PAGE_W - MARGIN:.2f} 40.00 l S "
            f"BT /F1 7.0 Tf {_pdf_color(COLOR_MUTED)} rg 1 0 0 1 {PAGE_W / 2:.2f} 28.00 Tm "
            f"(Stroke Rehab Platform  |  Confidential  |  Page {index} of {total}) Tj ET"
        )
        # center-ish: the Tm x is mid-page; shift left by half string
        label = f"Stroke Rehab Platform  |  Confidential  |  Page {index} of {total}"
        x = PAGE_W / 2 - 0.5 * 7.0 * 0.5 * len(label)
        ops.append(
            f"{_pdf_color(COLOR_LINE)} RG 0.4 w {MARGIN:.2f} 40.00 m {PAGE_W - MARGIN:.2f} 40.00 l S"
        )
        ops.append(
            f"BT /F1 7.0 Tf {_pdf_color(COLOR_MUTED)} rg 1 0 0 1 {x:.2f} 28.00 Tm ({_escape_pdf(label)}) Tj ET"
        )
        _ = footer

    objects: List[Optional[bytes]] = [None]

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects) - 1

    font_reg = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids: List[int] = []
    for ops in cv.pages:
        stream = "\n".join(ops).encode("latin-1", "replace")
        content_id = add(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )
        page_ids.append(
            add(
                (
                    f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {PAGE_W:.0f} {PAGE_H:.0f}] "
                    f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_reg} 0 R /F2 {font_bold} 0 R >> >> >>"
                ).encode("latin-1")
            )
        )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1"))
    for pid in page_ids:
        objects[pid] = objects[pid].replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("latin-1"))
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))
    add(f"<< /Title ({_escape_pdf(title)[:120]}) /Producer (NeuroLab Clinical Report) >>".encode("latin-1"))

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


def render_text_pdf(lines: List[str], *, title: str = "Clinical Assessment Report") -> bytes:
    """Fallback plain-text PDF (kept for tests / debugging)."""
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
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
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
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1"))
    for pid in page_ids:
        objects[pid] = objects[pid].replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("latin-1"))
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))
    add(f"<< /Title ({_escape_pdf(title)[:120]}) /Producer (NeuroLab Clinical Report) >>".encode("latin-1"))

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
    try:
        from glass_report import build_glass_pdf

        blob = build_glass_pdf(patient)
        if blob:
            return blob
    except Exception as exc:
        print(f"glass Export Report PDF fallback: {exc}", flush=True)
    return render_clinical_pdf(
        patient,
        title=f"Clinical Assessment Report - {name or patient_drive_key(patient)}",
    )
