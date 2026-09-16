#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import unittest


class ValidationCacheReportTests(unittest.TestCase):
    def test_wires_sync_report_routes(self) -> None:
        src = Path(__file__).resolve().parent.joinpath("validation_cache.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile', src)
        self.assertIn('@app.post("/api/ipad-sync-report")', src)
        self.assertIn('@app.get("/api/ipad-sync-report")', src)
        self.assertIn("saved[\"skipped\"] = True", src)
        self.assertIn("drive.get(\"ok\")", src)


if __name__ == "__main__":
    unittest.main()
