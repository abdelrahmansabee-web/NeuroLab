#!/usr/bin/env python3
"""Save validation videos on VPS disk and send patientKey from the clinic UI."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

JS_OLD = 'o.append("phase",t),o.append("stroke_side",h)'
JS_NEW = 'o.append("phase",t),Ce&&o.append("patientKey",String(Ce)),o.append("stroke_side",h)'

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
            library_name=base_name,
        )
        print(f"Saved clinic validation files for patientKey={patient_key or 'anon'} phase={phase}", flush=True)
    except Exception as exc:
        print(f"Clinic video persist warning: {exc}", flush=True)

    _prog(95, "Finalizing results…")
'''


def _patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
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

    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if js.is_file():
        _patch(js, JS_OLD, JS_NEW, "frontend patientKey on /analyze")
    else:
        print("WARN: frontend bundle missing")

    main_py = root / "main.py"
    runner = root / "analyze_job_runner.py"
    if not main_py.is_file() or not runner.is_file():
        print("error: main.py or analyze_job_runner.py missing", file=sys.stderr)
        return 1

    _patch(main_py, MAIN_FORM_OLD, MAIN_FORM_NEW, "analyze patientKey form")
    _patch(main_py, KWARGS_OLD, KWARGS_NEW, "analyze kwargs patient_key")
    _patch(runner, EXECUTE_OLD, EXECUTE_NEW, "worker patient_key")
    _patch(runner, PIPELINE_SIG_OLD, PIPELINE_SIG_NEW, "pipeline signature")
    _patch(runner, PLAYBACK_OLD, PLAYBACK_NEW, "keep playback video")
    _patch(runner, PERSIST_OLD, PERSIST_NEW, "persist after overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
