#!/usr/bin/env python3
"""Save validation videos on VPS disk and send patientKey from the clinic UI."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

JS_OLD = 'o.append("phase",t),o.append("stroke_side",h)'
JS_NEW = 'o.append("phase",t),Ce&&o.append("patientKey",String(Ce)),o.append("stroke_side",h)'
JS_RESTORE_OLD = (
    "p=!1!==c.overlay&&!(null!==h&&void 0!==h&&null!==(t=h.overlay)&&void 0!==t"
    "&&null!==(n=t.frames)&&void 0!==n&&n.length),f=!1!==c.original&&!((null===h||void 0===h||"
    "null===(r=h.originalVideoBlob)||void 0===r?void 0:r.size)>0),g=!1!==c.unified&&!((null===h"
    "||void 0===h||null===(i=h.unifiedVideoBlob)||void 0===i?void 0:i.size)>0);"
    "if(!p&&!f&&!g)return h&&Ee(e,h),h;"
)
JS_RESTORE_NEW = "p=!1!==c.overlay,f=!1!==c.original,g=!1!==c.unified;"
JS_KEEP_DRIVE_OLD = "return Y_(b,d)?(await K_(b),Ee(e,b),b):h"
JS_KEEP_DRIVE_NEW = "return v||Y_(b,d)?(await K_(b),Ee(e,b),b):h"
JS_UV_OLD = 't.append("csv_filename",r.csv_filename),t.append("video_filename",r.video_filename)'
JS_UV_NEW = 't.append("csv_filename",r.csv_filename),t.append("video_filename",r.video_filename),Ce&&t.append("patientKey",String(Ce)),t.append("phase",e)'

MAIN_FORM_OLD = '''    patient_height_cm: str = Form("auto"),

    cutoff_frequency: str = Form("4.0"),
'''
MAIN_FORM_NEW = '''    patient_height_cm: str = Form("auto"),
    patientKey: str = Form(""),

    cutoff_frequency: str = Form("4.0"),
'''

KWARGS_OLD = '''            "patient_height_cm": patient_height_cm,
            "original_filename": video.filename or "video",
'''
KWARGS_NEW = '''            "patient_height_cm": patient_height_cm,
            "original_filename": video.filename or "video",
            "patient_key": (patientKey or "").strip(),
'''

EXECUTE_OLD = '''        "patient_height_cm": raw.get("patient_height_cm", "auto"),
        "original_filename": raw.get("original_filename", "video"),
    }
'''
EXECUTE_NEW = '''        "patient_height_cm": raw.get("patient_height_cm", "auto"),
        "original_filename": raw.get("original_filename", "video"),
        "patient_key": raw.get("patient_key") or "",
    }
'''

SAVE_PATIENTS_OLD = '''        _write_patients_file(_patients_file_for_user(user), patients)
        return {"success": True, "count": len(patients)}
'''
SAVE_PATIENTS_NEW = '''        _write_patients_file(_patients_file_for_user(user), patients)
        try:
            import threading
            from patient_drive_archive import archive_patients

            uid = int((user or {}).get("id") or 1)
            threading.Thread(
                target=archive_patients,
                args=(patients,),
                kwargs={"user_id": uid},
                daemon=True,
            ).start()
        except Exception as exc:
            print(f"Drive patient archive: {exc}", flush=True)
        return {"success": True, "count": len(patients)}
'''

PIPELINE_SIG_OLD = '''    original_filename: str,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
'''
PIPELINE_SIG_NEW = '''    original_filename: str,
    job_id: Optional[str] = None,
    patient_key: str = "",
) -> Dict[str, Any]:
'''

PLAYBACK_OLD = '''    video_path = _downscale_video_for_analysis(video_path)
'''
PLAYBACK_NEW = '''    playback_video = video_path
    video_path = _downscale_video_for_analysis(video_path)
'''

PERSIST_OLD = '''    _prog(95, "Finalizing results…")
'''
PERSIST_NEW = '''    try:
        from persist_validation import persist_phase_artifacts

        overlay_file = _overlay_cache_path_for_csv(Path(analysis_csv_path))
        persist_phase_artifacts(
            DATA_DIR,
            patient_key,
            phase,
            original_video=playback_video if playback_video.exists() else video_path,
            overlay_json=overlay_file if overlay_file.exists() else None,
            pose_csv=Path(analysis_csv_path) if Path(analysis_csv_path).exists() else None,
            library_name=base_name,
        )
        print(f"Saved clinic validation files for patientKey={patient_key or 'anon'} phase={phase}", flush=True)
    except Exception as exc:
        print(f"Clinic video persist warning: {exc}", flush=True)

    _prog(95, "Finalizing results…")
'''


PERSIST_TRY = PERSIST_NEW.split('    _prog(95', 1)[0]
PERSIST_ALREADY = "persist_phase_artifacts("
PLAYBACK_STACK_RE = re.compile(r"(?:    playback_video = video_path\n){2,}")

UV_SIG_OLD = '''def _run_uv_generation(job_id: str, csv_path: Path, video_path: Path, rotation: str):
'''
UV_SIG_NEW = '''def _run_uv_generation(job_id: str, csv_path: Path, video_path: Path, rotation: str, patient_key: str = "", phase: str = ""):
'''
UV_FORM_OLD = '''async def unified_validation(
    csv_filename: str = Form(...),
    video_filename: str = Form(...),
    rotation: str = Form("auto"),
):
'''
UV_FORM_NEW = '''async def unified_validation(
    csv_filename: str = Form(...),
    video_filename: str = Form(...),
    rotation: str = Form("auto"),
    patientKey: str = Form(""),
    phase: str = Form(""),
):
'''
UV_JOB_OLD = '''        loop.run_in_executor(None, _run_uv_generation, job_id, csv_path, video_path, rotation)
'''
UV_JOB_NEW = '''        loop.run_in_executor(
            None,
            _run_uv_generation,
            job_id,
            csv_path,
            video_path,
            rotation,
            (patientKey or "").strip(),
            (phase or "").strip(),
        )
'''
UV_SAVE_OLD = '''        if uv_path and Path(uv_path).exists() and Path(uv_path).stat().st_size > 1000:
            uv_jobs[job_id].update({
                "status": "done",
'''
UV_SAVE_NEW = '''        if uv_path and Path(uv_path).exists() and Path(uv_path).stat().st_size > 1000:
            try:
                from persist_validation import persist_phase_artifacts

                persist_phase_artifacts(
                    DATA_DIR,
                    patient_key or "",
                    phase or "baseline",
                    unified_video=Path(uv_path),
                    library_name=Path(uv_path).stem,
                )
            except Exception as persist_exc:
                print(f"Drive validation video persist: {persist_exc}", flush=True)
            uv_jobs[job_id].update({
                "status": "done",
'''


def collapse_stacked_runner_patches(text: str) -> str:
    """Undo restacked persist/playback replacements if the patch ran twice."""
    text = PLAYBACK_STACK_RE.sub("    playback_video = video_path\n", text)
    doubled = PERSIST_TRY + PERSIST_TRY
    while doubled in text:
        text = text.replace(doubled, PERSIST_TRY)
    return text


def _patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {label}")
        return
    if old not in text:
        raise SystemExit(f"pattern not found: {label} in {path}")
    count = text.count(old)
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched {label} ({count}x)")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_persist_videos.py /opt/neurolab", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    overlay = Path(__file__).resolve().parent
    shutil.copy2(overlay / "persist_validation.py", root / "persist_validation.py")
    print("copied persist_validation.py")
    drive_src = overlay / "drive_persist.py"
    if drive_src.is_file():
        shutil.copy2(drive_src, root / "drive_persist.py")
        print("copied drive_persist.py")
    fallback_src = overlay / "local_drive_fallback.py"
    if fallback_src.is_file():
        shutil.copy2(fallback_src, root / "local_drive_fallback.py")
        print("copied local_drive_fallback.py")
    for extra in (
        "backfill_drive.py",
        "validation_cache.py",
        "sync_ipad_cache.html",
        "drive_oauth.py",
        "drive_oauth_routes.py",
        "connect_drive.html",
        "patient_drive_archive.py",
        "patient_pdf.py",
        "glass_report.py",
    ):
        src = overlay / extra
        if src.is_file():
            shutil.copy2(src, root / extra)
            print(f"copied {extra}")

    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if js.is_file():
        _patch(js, JS_OLD, JS_NEW, "frontend patientKey on /analyze")
        _patch(js, JS_RESTORE_OLD, JS_RESTORE_NEW, "restore validation from server disk first")
        _patch(js, JS_KEEP_DRIVE_OLD, JS_KEEP_DRIVE_NEW, "keep Drive videos even if kinematics csv missing")
        _patch(js, JS_UV_OLD, JS_UV_NEW, "frontend patientKey on /unified-validation")
        idx = root / "frontend" / "build" / "index.html"
        if idx.is_file():
            html = idx.read_text(encoding="utf-8")
            updated = re.sub(
                r"main\.0626212c\.js(?:\?[^\"']*)?",
                "main.0626212c.js?srv=2",
                html,
            )
            if updated != html:
                idx.write_text(updated, encoding="utf-8")
                print("cache-bust index.html main JS ?srv=2")
    else:
        print("WARN: frontend bundle missing")

    main_py = root / "main.py"
    runner = root / "analyze_job_runner.py"
    if not main_py.is_file() or not runner.is_file():
        print("error: main.py or analyze_job_runner.py missing", file=sys.stderr)
        return 1

    _patch(main_py, MAIN_FORM_OLD, MAIN_FORM_NEW, "analyze patientKey form")
    _patch(main_py, KWARGS_OLD, KWARGS_NEW, "analyze kwargs patient_key")
    _patch(main_py, SAVE_PATIENTS_OLD, SAVE_PATIENTS_NEW, "archive patients to Drive")
    _patch(runner, EXECUTE_OLD, EXECUTE_NEW, "worker patient_key")
    _patch(runner, PIPELINE_SIG_OLD, PIPELINE_SIG_NEW, "pipeline signature")
    _patch(runner, PLAYBACK_OLD, PLAYBACK_NEW, "keep playback video")
    runner_text = runner.read_text(encoding="utf-8")
    if PERSIST_ALREADY in runner_text:
        print("already patched: persist after overlay")
    else:
        _patch(runner, PERSIST_OLD, PERSIST_NEW, "persist after overlay")
    _patch(main_py, UV_SIG_OLD, UV_SIG_NEW, "uv worker patient key")
    main_now = main_py.read_text(encoding="utf-8")
    if 'patientKey: str = Form("")' in main_now:
        print("already patched: uv form patientKey")
    else:
        _patch(main_py, UV_FORM_OLD, UV_FORM_NEW, "uv form patientKey")
    _patch(main_py, UV_JOB_OLD, UV_JOB_NEW, "uv job patient key")
    _patch(main_py, UV_SAVE_OLD, UV_SAVE_NEW, "persist unified validation to Drive")
    stacked = runner.read_text(encoding="utf-8")
    collapsed = collapse_stacked_runner_patches(stacked)
    if collapsed != stacked:
        runner.write_text(collapsed, encoding="utf-8")
        print("collapsed restacked persist/playback blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
