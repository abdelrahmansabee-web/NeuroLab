#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backfill_drive import backfill_data_dir, collect_local_sessions
from persist_validation import persist_phase_artifacts


class BackfillDriveTests(unittest.TestCase):
    def test_collects_team_and_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=self._write(data_dir / "a.mp4", b"video-bytes"),
                overlay_json=self._write(data_dir / "a.json", b"{}"),
            )
            cache = data_dir / "validation_cache" / "128_betul_yusel" / "pre"
            cache.mkdir(parents=True)
            (cache / "original.mp4").write_bytes(b"betul-video")
            sessions = collect_local_sessions(data_dir)
            keys = {(key, phase) for key, phase, _files in sessions}
            self.assertIn(("101", "pre"), keys)
            self.assertIn(("128_betul_yusel", "pre"), keys)

    def test_backfill_skips_drive_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=self._write(data_dir / "a.mp4", b"video-bytes"),
            )
            out = backfill_data_dir(data_dir)
            self.assertEqual(out["count"], 1)
            self.assertTrue(out["sessions"][0]["drive"].get("skipped"))

    def _write(self, path: Path, content: bytes) -> Path:
        path.write_bytes(content)
        return path


if __name__ == "__main__":
    unittest.main()
