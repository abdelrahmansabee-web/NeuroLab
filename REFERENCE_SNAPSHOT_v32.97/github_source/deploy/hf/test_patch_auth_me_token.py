#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_auth_me_token import NEW, OLD, patch_auth_me_token


class AuthMeTokenTests(unittest.TestCase):
    def test_injects_cookie_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "auth.py").write_text(OLD + "\n        }\n", encoding="utf-8")
            self.assertEqual(patch_auth_me_token(root), 0)
            text = (root / "auth.py").read_text(encoding="utf-8")
            self.assertIn("async def auth_me(request: Request", text)
            self.assertIn('"token": token', text)
            self.assertIn("neurolab_token", text)
            self.assertEqual(patch_auth_me_token(root), 0)

    def test_old_snippet_has_no_token_field(self) -> None:
        self.assertNotIn('"token": token', OLD)
        self.assertIn("token", NEW)


if __name__ == "__main__":
    unittest.main()
