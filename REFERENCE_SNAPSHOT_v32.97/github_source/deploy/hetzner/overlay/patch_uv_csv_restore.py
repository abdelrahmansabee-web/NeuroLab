#!/usr/bin/env python3
"""Keep pose CSV around for UV after Hugging Face restarts, and restore it from the iPad."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RUNNER_OLD = """        persist_phase_artifacts(
            DATA_DIR,
            patient_key,
            phase,
            original_video=playback_video if playback_video.exists() else video_path,
            overlay_json=overlay_file if overlay_file.exists() else None,
            library_name=base_name,
        )
"""
RUNNER_NEW = """        persist_phase_artifacts(
            DATA_DIR,
            patient_key,
            phase,
            original_video=playback_video if playback_video.exists() else video_path,
            overlay_json=overlay_file if overlay_file.exists() else None,
            pose_csv=Path(analysis_csv_path) if Path(analysis_csv_path).exists() else None,
            library_name=base_name,
        )
"""

UV_FORM_OLD = '''async def unified_validation(
    csv_filename: str = Form(...),
    video_filename: str = Form(...),
    rotation: str = Form("auto"),
    patientKey: str = Form(""),
    phase: str = Form(""),
):
'''
UV_FORM_NEW = '''async def unified_validation(
    csv_filename: str = Form(...),
    video_filename: str = Form(...),
    rotation: str = Form("auto"),
    patientKey: str = Form(""),
    phase: str = Form(""),
    csv: UploadFile = File(None),
    video: UploadFile = File(None),
):
'''

UV_MISSING_OLD = '''        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        search_dirs = [UPLOAD_DIR, OUTPUT_DIR]
'''
UV_MISSING_NEW = '''        if csv is not None:
            payload = await csv.read()
            if payload:
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                csv_path.write_bytes(payload)
        if video is not None:
            payload = await video.read()
            if payload:
                UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                (UPLOAD_DIR / Path(video_filename).name).write_bytes(payload)
        if not csv_path.exists():
            try:
                from persist_validation import hydrate_output_file

                restored = hydrate_output_file(DATA_DIR, OUTPUT_DIR, csv_filename)
                if restored:
                    csv_path = restored
            except Exception as hydrate_exc:
                print(f"CSV hydrate: {hydrate_exc}", flush=True)
        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        search_dirs = [UPLOAD_DIR, OUTPUT_DIR]
'''

OVERLAY_MISSING_OLD = '''        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        cache_path = _overlay_cache_path_for_csv(csv_path)
'''
OVERLAY_MISSING_NEW = '''        if not csv_path.exists():
            try:
                from persist_validation import hydrate_output_file

                restored = hydrate_output_file(DATA_DIR, OUTPUT_DIR, csv_filename)
                if restored:
                    csv_path = restored
            except Exception as hydrate_exc:
                print(f"overlay CSV hydrate: {hydrate_exc}", flush=True)
        if not csv_path.exists():
            return JSONResponse(status_code=404, content={"error": f"CSV not found: {csv_filename}"})

        cache_path = _overlay_cache_path_for_csv(csv_path)
'''

ME_VARS_OLD = "if(Ce)try{var n,r,i,a,s,o,l,c,d,u;const h=await H_(Ce,e)"
ME_VARS_NEW = "if(Ce)try{var n,r,i,a,s,o,l,c,d,u,v;const h=await H_(Ce,e)"

ME_BLOB_OLD = (
    "unifiedVideoBlob:null!==(u=t.unifiedVideoBlob)&&void 0!==u?u:null===h||void 0===h?void 0:h.unifiedVideoBlob,"
    "kinematicsSnapshot:"
)
ME_BLOB_NEW = (
    "unifiedVideoBlob:null!==(u=t.unifiedVideoBlob)&&void 0!==u?u:null===h||void 0===h?void 0:h.unifiedVideoBlob,"
    "csvBlob:null!==(v=t.csvBlob)&&void 0!==v?v:null===h||void 0===h?void 0:h.csvBlob,"
    "kinematicsSnapshot:"
)

CACHE_CSV_OLD = (
    '!i&&_.csv_filename&&(G(e=>a(a({},e),{},{[t]:{pct:100,step:"Loading validation overlay\\u2026"}})),'
    "Ue(t,_.csv_filename,{syncResults:!0},8).catch(()=>{}))"
)
CACHE_CSV_NEW = (
    '!i&&_.csv_filename&&(G(e=>a(a({},e),{},{[t]:{pct:100,step:"Loading validation overlay\\u2026"}})),'
    'fetch("".concat(pS,"/download/").concat(encodeURIComponent(_.csv_filename))).then(e=>e.ok?e.blob():null)'
    ".then(e=>{e&&Me(t,{csvFilename:_.csv_filename,csvBlob:e,kinematicsSnapshot:P})}).catch(()=>{}),"
    "Ue(t,_.csv_filename,{syncResults:!0},8).catch(()=>{}))"
)

UV_POST_OLD = (
    'const t=new FormData;t.append("csv_filename",r.csv_filename),t.append("video_filename",r.video_filename),'
    'Ce&&t.append("patientKey",String(Ce)),t.append("phase",e),console.log("[UV] queueing for "'
)
UV_POST_NEW = (
    'const t=new FormData;t.append("csv_filename",r.csv_filename),t.append("video_filename",r.video_filename),'
    'Ce&&t.append("patientKey",String(Ce)),t.append("phase",e);try{const rec=Ce?await H_(Ce,e):null;'
    "if(rec&&rec.csvBlob instanceof Blob&&rec.csvBlob.size>0)t.append(\"csv\",rec.csvBlob,r.csv_filename);"
    "const vid=rec&&rec.originalVideoBlob instanceof Blob&&rec.originalVideoBlob.size>0?rec.originalVideoBlob:null;"
    'vid&&t.append("video",vid,r.video_filename)}catch(z){}console.log("[UV] queueing for "'
)

UV_ERR_OLD = (
    '}catch(i){console.error(i);const t=i.message||"Failed to generate unified validation video";'
    '$e(n=>a(a({},n),{},{[e]:t})),u(t,"error"),B(t=>a(a({},t),{},{[e]:"idle"}))}}else u("Analyze the video first","error")}'
)
UV_ERR_NEW = (
    '}catch(i){console.error(i);const raw=String(i.message||"");'
    'const t=raw.indexOf("CSV not found")>=0||raw.indexOf("Video not found")>=0?'
    '"ملف التحليل اتمسح من السيرفر. اضغطي ▶ مرة واحدة واستني Analysis complete وبعدين UV.":'
    '(raw||"Failed to generate unified validation video");'
    '$e(n=>a(a({},n),{},{[e]:t})),u(t,"error"),B(t=>a(a({},t),{},{[e]:"idle"}))}}else u("Analyze the video first","error")}'
)

PY_PATCHES = (
    ("persist pose csv from runner", RUNNER_OLD, RUNNER_NEW),
    ("UV form accepts csv/video files", UV_FORM_OLD, UV_FORM_NEW),
    ("UV hydrates or accepts uploaded csv", UV_MISSING_OLD, UV_MISSING_NEW),
    ("overlay-data hydrates csv", OVERLAY_MISSING_OLD, OVERLAY_MISSING_NEW),
)

JS_PATCHES = (
    ("Me csvBlob var", ME_VARS_OLD, ME_VARS_NEW),
    ("Me csvBlob field", ME_BLOB_OLD, ME_BLOB_NEW),
    ("cache pose csv in IndexedDB", CACHE_CSV_OLD, CACHE_CSV_NEW),
    ("UV posts cached csv/video", UV_POST_OLD, UV_POST_NEW),
    ("Arabic CSV missing toast", UV_ERR_OLD, UV_ERR_NEW),
)


def _apply(text: str, patches: tuple, already_ok: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in patches:
        if new in text:
            applied.append(f"already {label}")
            continue
        if old not in text:
            raise SystemExit(f"pattern not found: {label}")
        text = text.replace(old, new, 1)
        applied.append(label)
    return text, applied


def patch_uv_csv_restore(root: Path) -> int:
    runner = root / "analyze_job_runner.py"
    main_py = root / "main.py"
    if runner.is_file():
        text = runner.read_text(encoding="utf-8")
        if RUNNER_NEW in text:
            print("already patched: persist pose csv from runner")
        elif RUNNER_OLD in text:
            runner.write_text(text.replace(RUNNER_OLD, RUNNER_NEW, 1), encoding="utf-8")
            print("patched persist pose csv from runner")
        else:
            raise SystemExit("pattern not found: persist pose csv from runner")
    if main_py.is_file():
        text = main_py.read_text(encoding="utf-8")
        updated, applied = _apply(text, PY_PATCHES[1:], "main")
        if updated != text:
            main_py.write_text(updated, encoding="utf-8")
        print("uv-csv-restore main:", ", ".join(applied))

    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if js.is_file():
        original = js.read_text(encoding="utf-8", errors="replace")
        updated, applied = _apply(original, JS_PATCHES, "js")
        if updated != original:
            js.write_text(updated, encoding="utf-8")
        print("uv-csv-restore js:", ", ".join(applied))
        idx = root / "frontend" / "build" / "index.html"
        if idx.is_file():
            html = idx.read_text(encoding="utf-8")
            busted = re.sub(
                r"main\.0626212c\.js(?:\?[^\"']*)?",
                "main.0626212c.js?kin=2",
                html,
            )
            if busted != html:
                idx.write_text(busted, encoding="utf-8")
                print("cache-bust index.html main JS ?kin=2")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_uv_csv_restore.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_uv_csv_restore(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
