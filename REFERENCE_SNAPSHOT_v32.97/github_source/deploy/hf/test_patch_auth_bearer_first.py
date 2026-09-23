#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_auth_bearer_first import NEW, OLD, patch_auth_bearer_first


class AuthBearerFirstTests(unittest.TestCase):
    def test_prefers_bearer_over_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "auth.py").write_text(OLD, encoding="utf-8")
            self.assertEqual(patch_auth_bearer_first(root), 0)
            text = (root / "auth.py").read_text(encoding="utf-8")
            self.assertIn("for token in candidates:", text)
            self.assertIn("auth.lower().startswith(\"bearer \")", text)
            self.assertLess(text.index("bearer"), text.index("neurolab_token"))
            self.assertEqual(patch_auth_bearer_first(root), 0)

    def test_old_snippet_uses_cookie_first(self) -> None:
        self.assertIn("request.cookies.get(\"neurolab_token\")", OLD)
        cookie_at = OLD.index("cookies")
        bearer_at = OLD.index("Bearer")
        self.assertLess(cookie_at, bearer_at)
        self.assertIn("candidates", NEW)


if __name__ == "__main__":
    unittest.main()
