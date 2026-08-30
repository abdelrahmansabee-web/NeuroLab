#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from patch_persist_videos import JS_KEEP_DRIVE_NEW, JS_KEEP_DRIVE_OLD, JS_RESTORE_NEW, JS_RESTORE_OLD


class RestoreServerFirstTests(unittest.TestCase):
    def test_forces_server_fetch_instead_of_indexeddb_only(self) -> None:
        sample = (
            "const u=await H_(Ce,e),h=Y_(u,d)?u:null,"
            + JS_RESTORE_OLD
            + "const v=await async function(e,t){"
        )
        out = sample.replace(JS_RESTORE_OLD, JS_RESTORE_NEW)
        self.assertIn(JS_RESTORE_NEW, out)
        self.assertNotIn("if(!p&&!f&&!g)return h&&Ee(e,h),h;", out)
        self.assertIn("await H_(Ce,e)", out)

    def test_keeps_drive_files_without_kinematics_csv(self) -> None:
        sample = "if(!v&&!h)return null;const b=merge;" + JS_KEEP_DRIVE_OLD + ",[Ce,m,Ee])"
        out = sample.replace(JS_KEEP_DRIVE_OLD, JS_KEEP_DRIVE_NEW)
        self.assertIn(JS_KEEP_DRIVE_NEW, out)
        self.assertNotIn("return Y_(b,d)?(await K_(b),Ee(e,b),b):h", out)

    def test_keep_drive_pattern_exists_in_clinic_bundle(self) -> None:
        root = Path(__file__).resolve().parents[3]
        bundle = (
            root
            / "REFERENCE_SNAPSHOT_v31.75"
            / "hf_space"
            / "frontend"
            / "build"
            / "static"
            / "js"
            / "main.0626212c.js"
        )
        if not bundle.is_file():
            self.skipTest("clinic bundle snapshot missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        self.assertIn(JS_KEEP_DRIVE_OLD, text)

    def test_pattern_exists_in_clinic_bundle(self) -> None:
        root = Path(__file__).resolve().parents[3]
        bundle = (
            root
            / "REFERENCE_SNAPSHOT_v31.75"
            / "hf_space"
            / "frontend"
            / "build"
            / "static"
            / "js"
            / "main.0626212c.js"
        )
        if not bundle.is_file():
            self.skipTest("clinic bundle snapshot missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        self.assertIn(JS_RESTORE_OLD, text)


if __name__ == "__main__":
    unittest.main()
