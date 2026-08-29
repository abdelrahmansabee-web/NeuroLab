#!/usr/bin/env python3
"""Unit tests for the VPS-local Drive fallback store."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from local_drive_fallback import (
    find_artifact,
    load_patients_backup,
    save_patients_backup,
    write_artifact,
)


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


class LocalDriveFallbackTests(unittest.TestCase):
    def test_patients_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            save_patients_backup(data_dir, 1, "neurolab_patients_1.json", [{"_id": "p1"}])
            patients = load_patients_backup(data_dir, 1, "neurolab_patients_1.json")
            self.assertEqual(patients, [{"_id": "p1"}])
            self.assertEqual(load_patients_backup(data_dir, 2, "neurolab_patients_2.json"), [])

    def test_artifact_team_then_user(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            write_artifact(
                data_dir, 1, "101", "pre_validation_overlay.json",
                b'{"frames":[1]}', "data", "team", _sanitize,
            )
            found = find_artifact(
                data_dir, 1, "101", "pre_validation_overlay.json",
                "data", ("team", "user"), _sanitize,
            )
            self.assertIsNotNone(found)
            self.assertEqual(found.read_bytes(), b'{"frames":[1]}')
            self.assertIsNone(
                find_artifact(
                    data_dir, 1, "101", "missing.json",
                    "data", ("team", "user"), _sanitize,
                )
            )


if __name__ == "__main__":
    unittest.main()
