#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from persist_validation import persist_phase_artifacts


class PersistValidationTests(unittest.TestCase):
    def test_copies_named_files_for_restore(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            src = data_dir / "src"
            src.mkdir()
            video = src / "clip.mp4"
            overlay = src / "ov.json"
            video.write_bytes(b"mp4-bytes")
            overlay.write_text("{}", encoding="utf-8")
            saved = persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=video,
                overlay_json=overlay,
                library_name="pre_test",
            )
            self.assertEqual(saved["files"]["pre_validation_original.mp4"], 9)
            dest_v = data_dir / "local_artifacts" / "team" / "101" / "videos" / "pre_validation_original.mp4"
            dest_o = data_dir / "local_artifacts" / "team" / "101" / "data" / "pre_validation_overlay.json"
            self.assertTrue(dest_v.is_file())
            self.assertTrue(dest_o.is_file())
            lib = data_dir / "local_artifacts" / "library" / "pre_test" / "pre_validation_original.mp4"
            self.assertTrue(lib.is_file())
            session = data_dir / "local_artifacts" / "team" / "101" / "session.json"
            self.assertTrue(session.is_file())
            rec = json.loads(session.read_text(encoding="utf-8"))
            self.assertTrue(rec["never_delete"])
            self.assertIn("pre", rec["phases"])


if __name__ == "__main__":
    unittest.main()
