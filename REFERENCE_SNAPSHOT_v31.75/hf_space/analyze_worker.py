#!/usr/bin/env python3
"""Isolated analyze worker — never imports main.py / FastAPI."""
import json
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: analyze_worker.py <job_id> <kwargs.json>", flush=True)
        sys.exit(2)
    job_id = sys.argv[1]
    kw_path = Path(sys.argv[2])
    try:
        from analyze_job_runner import execute_analyze_job

        raw = json.loads(kw_path.read_text(encoding="utf-8"))
        execute_analyze_job(job_id, raw)
    except Exception as exc:
        traceback.print_exc()
        try:
            from analyze_job_runner import set_job_progress

            set_job_progress(job_id, 0, "Worker crash", done=True, error=str(exc))
        except Exception:
            pass
        sys.exit(1)
    finally:
        try:
            kw_path.unlink(missing_ok=True)
        except Exception:
            pass
