#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from drive_persist import _sanitize, upload_named_files


class DrivePersistTests(unittest.TestCase):
    def test_skips_when_unset(self) -> None:
        out = upload_named_files("101", [("pre_validation_original.mp4", Path("/nope"), "videos")])
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "drive_unset")
        self.assertTrue(out.get("never_delete"))

    def test_upserts_existing_and_never_calls_delete(self) -> None:
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "existing"}]}
        service.files.return_value.update.return_value.execute.return_value = {"id": "existing"}
        with self._tmp_mp4() as path:
            out = upload_named_files(
                "p 101",
                [("pre_validation_original.mp4", path, "videos")],
                service=service,
                folder_id="root",
            )
        self.assertTrue(out["ok"])
        self.assertEqual(out["patientKey"], "p_101")
        service.files.return_value.update.assert_called()
        service.files.return_value.delete.assert_not_called()
        service.files.return_value.create.assert_not_called()

    def test_sanitize(self) -> None:
        self.assertEqual(_sanitize("pre/../x"), "pre_.._x")

    def _tmp_mp4(self):
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            with tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / "clip.mp4"
                path.write_bytes(b"mp4-bytes-xx")
                yield path

        return ctx()


if __name__ == "__main__":
    unittest.main()
