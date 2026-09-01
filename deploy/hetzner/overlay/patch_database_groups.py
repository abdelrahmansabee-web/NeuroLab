#!/usr/bin/env python3
"""Split Database into Intervention/Control + Archive, and reorder Study IDs.

Archived sessions stay on the device/server but are left out of the analysis
dashboard, SPSS/Excel exports, and Drive patient database PDFs.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZS_FILE = HERE / "database_section_live.js"

MK_OLD = (
    'function mk(){try{return JSON.parse(localStorage.getItem(fk)||"[]")}catch(e){return[]}}'
    "function gk(e){localStorage.setItem(fk,JSON.stringify(e))}"
)
MK_NEW = MK_OLD + (
    "function nlA(e){return!(!e||!e._archived)}"
    "function nlB(e){return(null!=e?e:mk()).filter(function(e){return!nlA(e)})}"
    "function nlC(e){const t=[],n=[];(e||[]).forEach(function(e){e&&\"object\"==typeof e&&(nlA(e)?n:t).push(e)});"
    "t.sort(function(e,n){const r=parseInt(null===e.demographics||void 0===e.demographics?void 0:e.demographics.participantId,10),"
    "i=parseInt(null===n.demographics||void 0===n.demographics?void 0:n.demographics.participantId,10),"
    "a=isNaN(r)?1e9:r,s=isNaN(i)?1e9:i;return a!==s?a-s:String(e._savedAt||\"\").localeCompare(String(n._savedAt||\"\"))});"
    "return t.map(function(e,n){const r=Object.assign({},e),i=Object.assign({},e.demographics||{});"
    "return i.participantId=String(n+1),r.demographics=i,r}).concat(n)}"
)

GX_OLD = "const o=e.map(e=>mx(e,t,n,r)).filter(Boolean);"
GX_NEW = "const o=(e||[]).filter(e=>e&&!e._archived).map(e=>mx(e,t,n,r)).filter(Boolean);"

MS_OLD = "function mS(){const e=mk();"
MS_NEW = "function mS(){const e=nlB();"

DASH_OLD = "F=mk(),N=F.length"
DASH_NEW = "F=nlB(),N=F.length"

EXPORT_OLD = 'onClick:()=>{const e=mk();if(0===e.length)return void o("No patients to export"'
EXPORT_NEW = 'onClick:()=>{const e=nlB();if(0===e.length)return void o("No patients to export"'

JSON_OLD = "onClick:()=>{const e=mk();if(0===e.length)return;const t=e.map"
JSON_NEW = "onClick:()=>{const e=nlB();if(0===e.length)return;const t=e.map"

SPS_OLD = "const e=gx(mk(),ak,rk,tk)"
SPS_NEW = "const e=gx(nlB(),ak,rk,tk)"

BACKUP_OLD = (
    'onClick:()=>{const e=mk();fS(new Blob([JSON.stringify(e,null,2)],'
    '{type:"application/json"}),"neuro_backup_'
)
BACKUP_NEW = (
    'onClick:()=>{const e=nlB();fS(new Blob([JSON.stringify(e,null,2)],'
    '{type:"application/json"}),"neuro_backup_'
)

ID_OLD = "i.participantId=String(101+n)"
ID_NEW = "i.participantId=String(n+1)"
MS_ZERO_OLD = "function mS(){const e=nlB();let t=100;"
MS_ZERO_NEW = "function mS(){const e=nlB();let t=0;"
MIN_OLD = 'min:"101"'
MIN_NEW = 'min:"1"'

ZS_START = "zS=t=>{let r=t.fd,i=t.setFd,s=t.onLoadSession"
ZS_END = "const US=e=>{"

WORKER_OLD = """        for p in patients:
            if not isinstance(p, dict):
                continue
            key = _patient_drive_key_from_record(p)
"""
WORKER_NEW = """        for p in patients:
            if not isinstance(p, dict):
                continue
            if p.get("_archived"):
                continue
            key = _patient_drive_key_from_record(p)
"""

PATCHES = (
    ("loadPatients helpers for archive/active", MK_OLD, MK_NEW),
    ("exclude archived from master dataset", GX_OLD, GX_NEW),
    ("next Study ID skips archive", MS_OLD, MS_NEW),
    ("analysis dashboard skips archive", DASH_OLD, DASH_NEW),
    ("SPSS export skips archive", EXPORT_OLD, EXPORT_NEW),
    ("JSON study export skips archive", JSON_OLD, JSON_NEW),
    ("SPSS syntax rows skip archive", SPS_OLD, SPS_NEW),
    ("dashboard JSON backup skips archive", BACKUP_OLD, BACKUP_NEW),
    ("reorder Study IDs from 1", ID_OLD, ID_NEW),
    ("next Study ID from 1", MS_ZERO_OLD, MS_ZERO_NEW),
    ("Study ID input min 1", MIN_OLD, MIN_NEW),
)


def zs_new() -> str:
    text = ZS_FILE.read_text(encoding="utf-8").strip()
    if not text.startswith("zS=t=>{") or not text.endswith(";"):
        raise SystemExit("database_section_live.js must be zS=t=>{...};")
    return text


def patch_js_text(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in PATCHES:
        if old in text:
            text = text.replace(old, new, 1)
            applied.append(label)
            continue
        if new in text:
            applied.append(f"already {label}")
            continue
        if label == "loadPatients helpers for archive/active" and "function nlA(e)" in text:
            applied.append(f"already {label}")
            continue
        raise SystemExit(f"pattern not found: {label}")

    start = text.find(ZS_START)
    if start < 0:
        if "Intervention / AOMI" in text and "Reorder Study IDs" in text:
            applied.append("already database groups UI")
            return text, applied
        raise SystemExit("pattern not found: database section")
    end = text.find(ZS_END, start)
    if end < 0:
        raise SystemExit("pattern not found: database section end")
    replacement = zs_new()
    if not replacement.endswith("const US=e=>{") and replacement.endswith(";"):
        text = text[:start] + replacement + text[end:]
        applied.append("database groups UI")
    return text, applied


def patch_auth(root: Path) -> list[str]:
    notes: list[str] = []
    auth = root / "auth.py"
    if not auth.is_file():
        return notes
    text = auth.read_text(encoding="utf-8")
    if WORKER_NEW in text:
        notes.append("already skip archived Drive snapshots")
        return notes
    if WORKER_OLD in text:
        auth.write_text(text.replace(WORKER_OLD, WORKER_NEW, 1), encoding="utf-8")
        notes.append("skip archived Drive snapshots")
        return notes
    notes.append("WARN: Drive snapshot worker pattern missing")
    return notes


def patch_pwa_reload(root: Path) -> list[str]:
    notes: list[str] = []
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        updated = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            "main.0626212c.js?kin=10",
            html,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r"\g<1>31.82",
            updated,
            count=1,
        )
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append("index kin=10 nl-version 31.82")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != "./?v=29.64-pwa":
            data["start_url"] = "./?v=29.64-pwa"
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append("manifest start_url 29.64-pwa")
    return notes


def patch_database_groups(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; database groups not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("database-groups:", ", ".join(applied))
    notes = patch_pwa_reload(root)
    notes.extend(patch_auth(root))
    if notes:
        print("database-groups extra:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_database_groups.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_database_groups(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
