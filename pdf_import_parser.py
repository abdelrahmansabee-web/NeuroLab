"""Server-side NeuroLab Clinical Assessment Report PDF parser.

Mirrors the frontend patientImport.js parser but uses pdfplumber for robust
text extraction. Used by /api/parse-pdf so the browser does not depend on the
pdf.js worker.
"""

import re
from typing import Any, Dict, Optional

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore


SECTION_KEYS = [
    "demographics",
    "ipaq",
    "vas",
    "vams",
    "motorchange",
    "kgia",
    "wmft",
    "kinematics",
]

KVIQ_LABELS = [
    "Neck forward-backward flexion",
    "Shoulder elevation (shrug)",
    "Forward arm raise",
    "Elbow flexion",
    "Thumb-to-finger opposition",
    "Forward trunk lean",
    "Knee extension",
    "Hip abduction",
    "Foot tapping",
    "Foot external rotation",
]

KIN_PDF_VARS = [
    (re.compile(r"SPARC", re.I), "sparc"),
    (re.compile(r"Trunk\s*Ratio|Trunk/Palm", re.I), "trunk_ratio"),
    (re.compile(r"Shoulder\s*Vert|Shoulder\s*elevation", re.I), "shoulder_vert_norm"),
    (re.compile(r"Elbow\s*angle", re.I), "elbow_angle_mean"),
    (re.compile(r"Movement\s*time|Duration", re.I), "movement_time_sec"),
    (re.compile(r"Peak\s*Velocity", re.I), "peak_velocity_px_s"),
]

WMFT_PDF = [
    (re.compile(r"Hand to Table \(front\).*Ability Rating", re.I), "1"),
    (re.compile(r"Hand to Box \(front\).*Ability Rating", re.I), "2"),
    (re.compile(r"Extend Elbow \(no weight\).*Ability Rating", re.I), "3"),
    (re.compile(r"Lift Can \(front\).*Ability Rating", re.I), "4"),
]


def _dash(v: Any) -> Optional[str]:
    if v is None or v == "" or v == "—" or v == "-":
        return None
    return str(v)


def _num(v: Any) -> Optional[float]:
    d = _dash(v)
    if d is None:
        return None
    try:
        n = float(str(d).replace(",", "."))
        return n if n == n else None  # NaN guard
    except ValueError:
        return None


def _str(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    return str(v)


def _find_kviq_index(label: str) -> int:
    norm = label.lower().replace("–", "-").replace("—", "-").strip()
    for i, k in enumerate(KVIQ_LABELS):
        k_norm = k.lower().replace("–", "-").replace("—", "-")
        if norm in k_norm or k_norm in norm:
            return i
    return -1


def _extract_key_value_pairs(text: str) -> Dict[str, str]:
    """Extract label:value pairs from plain text using colons or wide spaces."""
    pairs: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Colon separated: "Age: 45"
        if ":" in line:
            key, _, val = line.partition(":")
            pairs[key.strip().lower()] = val.strip()
            continue
        # Wide-space separated: "Age          45"
        parts = re.split(r"\s{2,}", line)
        if len(parts) >= 2:
            key = parts[0].strip().lower()
            val = parts[1].strip()
            if key and val:
                pairs[key] = val
    return pairs


_LABEL_MAP = {
    "name": ["name", "patient name", "full name", "pt name", "participant name"],
    "participantId": ["id", "participant id", "patient id", "record no", "code", "id no", "record number", "patient code"],
    "age": ["age", "patient age", "years", "yrs"],
    "sex": ["sex", "gender"],
    "strokeType": ["stroke type", "diagnosis", "stroke subtype", "pathology"],
    "side": ["affected side", "paretic side", "paretic arm", "involved side", "affected arm", "hemiplegic side", "side", "lesion side"],
    "mas": ["mas", "modified ashworth", "ashworth scale"],
    "mrc": ["mrc", "medical research council"],
    "height": ["height", "ht"],
    "weight": ["weight", "wt"],
    "timeSinceStroke": ["time since stroke", "onset", "duration", "time post stroke", "months since stroke"],
}


def _map_value(key: str, val: str) -> Any:
    val = val.strip()
    if key == "sex":
        if re.search(r"\bmale\b", val, re.I): return "1"
        if re.search(r"\bfemale\b", val, re.I): return "2"
        if val.lower() == "m": return "1"
        if val.lower() == "f": return "2"
        return None
    if key == "strokeType":
        if re.search(r"\bischemic\b|\binfarct\b", val, re.I): return "1"
        if re.search(r"\bhemorrhagic\b|\bhemorrhage\b|\bbleed\b", val, re.I): return "2"
        return None
    if key == "side":
        if re.search(r"\bleft\b", val, re.I): return "1"
        if re.search(r"\bright\b", val, re.I): return "2"
        return None
    if key in ("mas", "mrc"):
        m = re.search(r"([0-5]\+?)", val)
        return m.group(1) if m else None
    if key == "age":
        m = re.search(r"(\d+)", val)
        return m.group(1) if m else None
    if key == "participantId":
        m = re.search(r"(\d+)", val)
        return m.group(1) if m else None
    if key == "name":
        return val.split()[0] if val.split() else val
    return val


def _extract_first(patterns, text, group=1, flags=re.I):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(group)
    return None


def _extract_number_near_label(text, labels, unit=None):
    """Find a number near one of the given labels."""
    for label in labels:
        unit_pat = rf"(?:\s*(?:{unit}))?" if unit else ""
        m = re.search(rf"{label}\s*[\s:]{{0,3}}([\d.]{{1,5}}){unit_pat}", text, re.I)
        if m:
            return m.group(1)
    return None


def enhance_with_generic_extraction(text: str, patient: Dict[str, Any]) -> None:
    """Fill missing demographic/assessment fields using generic clinical-report patterns."""
    d = patient.setdefault("demographics", {})
    kvs = _extract_key_value_pairs(text)

    # Map label:value pairs to demographics
    for target, labels in _LABEL_MAP.items():
        if d.get(target):
            continue
        for label in labels:
            val = kvs.get(label)
            if val:
                mapped = _map_value(target, val)
                if mapped:
                    d[target] = mapped
                break

    if not d.get("name"):
        name = _extract_first(
            [
                r"Patient\s*Name\s*[\-\-]?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,40})",
                r"Full\s*Name\s*[\-\-]?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,40})",
                r"Name\s*[\-\-]?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,40})",
            ],
            text,
        )
        if name:
            d["name"] = name.strip().split()[0]


    if not d.get("participantId"):
        pid = _extract_first(
            [
                r"(?:Participant\s*ID|Patient\s*ID|Record\s*No|Code|ID\s*No)[:\s]+(\d+)",
                r"\bID\s*[:\-]?\s*(\d{3,})\b",
                r"\bID:\s*(\d+)\b",
            ],
            text,
        )
        if pid:
            d["participantId"] = pid

    if not d.get("age"):
        age = _extract_first(
            [
                r"Age\s*[:\-]?\s*(\d+)",
                r"\b(\d{1,3})\s*(?:years?|yrs?|y)\s*old\b",
                r"\b(\d{1,2})\s*(?:yrs?|years?)\b",
            ],
            text,
        )
        if age:
            d["age"] = age

    if not d.get("sex"):
        if re.search(r"\bMale\b", text, re.I):
            d["sex"] = "1"
        elif re.search(r"\bFemale\b", text, re.I):
            d["sex"] = "2"

    if not d.get("strokeType"):
        if re.search(r"\bIschemic\b", text, re.I):
            d["strokeType"] = "1"
        elif re.search(r"\bHemorrhagic\b", text, re.I):
            d["strokeType"] = "2"
        elif re.search(r"\bInfarct\b", text, re.I):
            d["strokeType"] = "1"
        elif re.search(r"\bHemorrhage\b", text, re.I):
            d["strokeType"] = "2"

    if not d.get("side"):
        side = _extract_first(
            [
                r"(?:Affected|Paralyzed|Paralytic|Paretic|Lesion|Hemiplegic|Involved)\s+(?:Side|Arm|Limb|Extremity)[:\s\S]{0,30}?\b(Left|Right)\b",
                r"(?:Affected|Paralyzed|Paralytic|Paretic|Lesion|Hemiplegic|Involved)\s+(?:Side|Arm|Limb)[:\s]*\b(Left|Right)\b",
                r"\bSide\s*[:\-]?\s*(Left|Right)\b",
            ],
            text,
        )
        if side:
            d["side"] = "1" if side.lower() == "left" else "2"

    if not d.get("mas"):
        mas = _extract_first(
            [
                r"(?:Modified\s+Ashworth|Ashworth|MAS)\s*[:\s]*([0-4]\+?)",
                r"\bMAS\s*[:\s]*([0-4]\+?)\b",
            ],
            text,
        )
        if mas:
            d["mas"] = mas

    if not d.get("mrc"):
        mrc = _extract_first(
            [
                r"\bMRC\s*[:\s]*([0-5])\b",
                r"\bMedical\s+Research\s+Council\s*[:\s]*([0-5])\b",
            ],
            text,
        )
        if mrc:
            d["mrc"] = mrc

    if not d.get("height"):
        ht = _extract_first(
            [
                r"(?:Height|Ht)[:\s]*([\d.]+)\s*(?:cm|m)",
                r"Height\s*[:\-]?\s*([\d.]+)",
            ],
            text,
        )
        if ht:
            d["height"] = ht

    if not d.get("weight"):
        wt = _extract_first(
            [
                r"(?:Weight|Wt)[:\s]*([\d.]+)\s*(?:kg|kg)",
                r"Weight\s*[:\-]?\s*([\d.]+)",
            ],
            text,
        )
        if wt:
            d["weight"] = wt

    if not d.get("timeSinceStroke"):
        tss = _extract_first(
            [
                r"(?:Time\s*since\s*stroke|Onset|Duration|Time\s*since)[\s:]*([\d.]+\s*(?:months?|years?|weeks?|days?))",
                r"(?:Onset)[\s:]*([\d.]+\s*(?:months?|years?|weeks?|days?))",
            ],
            text,
        )
        if tss:
            d["timeSinceStroke"] = tss

    # Generic VAS / pain scale extraction
    vas = patient.setdefault("vas", {})
    if not vas.get("rest"):
        m = re.search(r"(?:Pain|VAS)\s*(?:at\s*)?rest\s*[:\s]*([\d.]+|—)", text, re.I)
        if m and _dash(m.group(1)):
            vas["rest"] = {"pre": m.group(1)}
    if not vas.get("activity"):
        m = re.search(r"(?:Pain|VAS)\s*(?:during\s*)?activity\s*[:\s]*([\d.]+|—)", text, re.I)
        if m and _dash(m.group(1)):
            vas["activity"] = {"pre": m.group(1)}
    if not vas.get("night"):
        m = re.search(r"(?:Night\s*pain|VAS\s*night)\s*[:\s]*([\d.]+|—)", text, re.I)
        if m and _dash(m.group(1)):
            vas["night"] = {"pre": m.group(1)}


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract plain text from a PDF using pdfplumber."""
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed")
    parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:  # type: ignore
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                parts.append(txt)
    return "\n".join(parts)


def parse_clinical_report_pdf(text: str) -> Dict[str, Any]:
    """Parse NeuroLab Clinical Assessment Report PDF text into patient shape."""
    patient: Dict[str, Any] = {k: {} for k in SECTION_KEYS}

    if re.search(r"AOMI Group", text, re.I):
        patient["demographics"]["group"] = "1"
    elif re.search(r"Control Group", text, re.I):
        patient["demographics"]["group"] = "2"

    id_m = re.search(r"ID:\s*(\d+)", text, re.I)
    if id_m:
        patient["demographics"]["participantId"] = id_m.group(1)

    date_m = re.search(r"\d{1,2}\s+\w{3}\s+\d{4}", text)
    if date_m:
        start = date_m.end()
        after = text[start : start + 80]
        name_m = re.search(r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,40})", after)
        if name_m:
            patient["demographics"]["name"] = name_m.group(1).strip().split()[0]

    age_m = re.search(r"AGE[\s\S]{0,30}?(\d{2})\s*yrs", text, re.I) or re.search(
        r"\b(\d{2})\s*yrs\b", text, re.I
    )
    if age_m:
        patient["demographics"]["age"] = age_m.group(1)

    if re.search(r"\bFemale\b", text, re.I):
        patient["demographics"]["sex"] = "2"
    elif re.search(r"\bMale\b", text, re.I):
        patient["demographics"]["sex"] = "1"

    if re.search(r"\bIschemic\b", text, re.I):
        patient["demographics"]["strokeType"] = "1"
    elif re.search(r"\bHemorrhagic\b", text, re.I):
        patient["demographics"]["strokeType"] = "2"

    side_m = re.search(r"AFFECTED SIDE[\s\S]{0,20}?\bLeft\b", text, re.I)
    if side_m:
        patient["demographics"]["side"] = "1"
    else:
        side_m = re.search(r"AFFECTED SIDE[\s\S]{0,20}?\bRight\b", text, re.I)
        if side_m:
            patient["demographics"]["side"] = "2"

    mas_m = re.search(r"\bMAS\b[\s\n]+(0|1\+|1|2|3|4)\b", text)
    if mas_m:
        patient["demographics"]["mas"] = mas_m.group(1)

    mrc_m = re.search(r"\bMRC\b[\s\n]+(2|3|4|5)\b", text)
    if mrc_m:
        patient["demographics"]["mrc"] = mrc_m.group(1)

    ipaq_rows = [
        ("light", re.compile(r"Light activity[^\d]*(\d+)\s+(\d+)", re.I)),
        ("sitting", re.compile(r"Total daily sitting time[^\d]*(\d+)\s+(\d+)", re.I)),
        ("extra", re.compile(r"Additional \(cycling[^\d]*(\d+)\s+(\d+)", re.I)),
    ]
    for key, re_ in ipaq_rows:
        m = re_.search(text)
        if m:
            patient["ipaq"][key] = {"gun": m.group(1), "sure": m.group(2)}

    vas_rest = re.search(r"Pain at Rest\s+([\d.]+|—)\s+([\d.]+|—)", text, re.I)
    if vas_rest:
        patient["vas"]["rest"] = {}
        if _dash(vas_rest.group(1)):
            patient["vas"]["rest"]["pre"] = vas_rest.group(1)
        if _dash(vas_rest.group(2)):
            patient["vas"]["rest"]["post"] = vas_rest.group(2)

    vas_act = re.search(r"Pain During Activity\s+([\d.]+|—)\s+([\d.]+|—)", text, re.I)
    if vas_act:
        patient["vas"]["activity"] = {}
        if _dash(vas_act.group(1)):
            patient["vas"]["activity"]["pre"] = vas_act.group(1)
        if _dash(vas_act.group(2)):
            patient["vas"]["activity"]["post"] = vas_act.group(2)

    vas_night = re.search(r"Night Pain\s+([\d.]+|—)\s+([\d.]+|—)", text, re.I)
    if vas_night:
        patient["vas"]["night"] = {}
        if _dash(vas_night.group(1)):
            patient["vas"]["night"]["pre"] = vas_night.group(1)
        if _dash(vas_night.group(2)):
            patient["vas"]["night"]["post"] = vas_night.group(2)

    mc_narr = re.search(r"muscle control changed from (\d+) to (\d+)", text, re.I)
    if mc_narr:
        patient["motorchange"]["control"] = mc_narr.group(1)
        patient["motorchange"]["difference"] = mc_narr.group(2)
    else:
        mc_tbl = re.search(r"Felt Difference\s+(\d+)\s+(\d+)", text, re.I)
        if mc_tbl:
            patient["motorchange"]["control"] = mc_tbl.group(1)
            patient["motorchange"]["difference"] = mc_tbl.group(2)

    for km in re.finditer(
        r"(Visual|Kinesthetic):\s*([^\n]+?)\s+([\d.]+|—)\s+([\d.]+|—)", text, re.I
    ):
        type_key = "gorsel" if km.group(1).lower() == "visual" else "kinestetik"
        idx = _find_kviq_index(km.group(2))
        if idx < 0:
            continue
        cell_key = f"{idx}_{type_key}"
        patient["kgia"][cell_key] = patient["kgia"].get(cell_key, {})
        if _dash(km.group(3)):
            patient["kgia"][cell_key]["once"] = km.group(3)
        if _dash(km.group(4)):
            patient["kgia"][cell_key]["sonra"] = km.group(4)

    for re_, id_ in WMFT_PDF:
        m = re.search(
            re_.pattern + r"[\s\S]{0,40}?(\d+|—)\s+(\d+|—)", text, re.I
        )
        if not m:
            continue
        patient["wmft"][id_] = {"pre": {}, "post": {}}
        if _dash(m.group(1)):
            patient["wmft"][id_]["pre"]["rating"] = m.group(1)
        if _dash(m.group(2)):
            patient["wmft"][id_]["post"]["rating"] = m.group(2)

    kin: Dict[str, Any] = {}
    for re_, key in KIN_PDF_VARS:
        m = re.search(
            re_.pattern + r"[\s↓↑]*\s*\S*\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
            text,
            re.I,
        )
        if not m:
            continue
        kin.setdefault("result_pre", {})[key] = _num(m.group(1))
        kin.setdefault("result_post", {})[key] = _num(m.group(2))
        kin.setdefault("result_baseline", {})[key] = _num(m.group(3))
        kin["status_pre"] = "completed"
        kin["status_post"] = "completed"
        kin["status_baseline"] = "completed"
    patient["kinematics"] = kin

    enhance_with_generic_extraction(text, patient)
    return patient


import io  # noqa: E402
