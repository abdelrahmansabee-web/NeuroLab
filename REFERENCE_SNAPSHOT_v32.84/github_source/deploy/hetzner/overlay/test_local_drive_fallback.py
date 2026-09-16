#!/usr/bin/env python3
"""Unit tests for the VPS-local Drive fallback store."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from local_drive_fallback import (
    find_artifact,
    list_validation_sessions,
    load_patients_backup,
    merge_validation_sessions,
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

    def test_probe_backup_does_not_wipe_real_session(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            save_patients_backup(data_dir, 1, "neurolab_patients_1.json", [{"_id": "101"}])
            write_artifact(
                data_dir, 1, "101", "pre_validation_original.mp4",
                b"video", "videos", "team", _sanitize,
            )
            save_patients_backup(
                data_dir, 1, "neurolab_patients_1.json",
                [{"_id": "probe", "demographics": {"participantId": "probe"}}],
            )
            patients = load_patients_backup(data_dir, 1, "neurolab_patients_1.json")
            ids = {p.get("_id") for p in patients}
            self.assertIn("101", ids)
            self.assertNotIn("probe", ids)

    def test_empty_write_does_not_delete_existing_video(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            path = write_artifact(
                data_dir, 1, "101", "pre_validation_original.mp4",
                b"keep-me", "videos", "team", _sanitize,
            )
            write_artifact(
                data_dir, 1, "101", "pre_validation_original.mp4",
                b"", "videos", "team", _sanitize,
            )
            self.assertEqual(path.read_bytes(), b"keep-me")

    def test_restore_merges_disk_validation_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            write_artifact(
                data_dir, 1, "101", "pre_validation_overlay.json",
                b'{"frames":[1]}', "data", "team", _sanitize,
            )
            merged = merge_validation_sessions(data_dir, [])
            self.assertEqual(merged[0]["_id"], "101")
            self.assertTrue(merged[0]["never_delete"])
            self.assertEqual(len(list_validation_sessions(data_dir)), 1)


if __name__ == "__main__":
    unittest.main()
