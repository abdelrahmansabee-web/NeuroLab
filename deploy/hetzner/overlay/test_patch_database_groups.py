#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patient_groups import active_patients, is_archived_patient, reorder_study_ids
from patch_database_groups import (
    DASH_NEW,
    MK_NEW,
    MS_NEW,
    ZS_START,
    patch_database_groups,
    patch_js_text,
    zs_new,
)


class PatientGroupTests(unittest.TestCase):
    def test_reorder_skips_archived_and_starts_at_1(self) -> None:
        patients = [
            {"_id": "b", "demographics": {"participantId": "220", "group": "2"}, "_savedAt": "2026-01-02"},
            {"_id": "a", "demographics": {"participantId": "109", "group": "1"}, "_savedAt": "2026-01-01"},
            {"_id": "z", "_archived": True, "demographics": {"participantId": "999"}},
        ]
        out = reorder_study_ids(patients)
        self.assertEqual([p["_id"] for p in out], ["a", "b", "z"])
        self.assertEqual(out[0]["demographics"]["participantId"], "1")
        self.assertEqual(out[1]["demographics"]["participantId"], "2")
        self.assertEqual(out[2]["demographics"]["participantId"], "999")
        self.assertTrue(is_archived_patient(out[2]))
        self.assertEqual(len(active_patients(out)), 2)

    def test_archive_patients_skips_archived(self) -> None:
        from patient_drive_archive import archive_patients

        with patch("drive_persist.upload_named_files") as upload:
            upload.return_value = {"ok": True}
            result = archive_patients(
                [
                    {"_archived": True, "demographics": {"participantId": "109", "name": "Skip"}},
                    {"demographics": {"participantId": "101", "name": "Keep"}},
                ],
                user_id=1,
            )
        self.assertEqual(result["uploaded"], 1)
        self.assertEqual(len(result["patients"]), 1)
        self.assertEqual(result["patients"][0]["patientKey"].startswith("101"), True)


class DatabaseGroupsPatchTests(unittest.TestCase):
    def test_zs_fragment_is_valid(self) -> None:
        text = zs_new()
        self.assertTrue(text.startswith("zS=t=>{"))
        self.assertIn("Intervention / AOMI", text)
        self.assertIn("Reorder Study IDs", text)
        self.assertIn("Moved to Archive", text)
        self.assertIn("grid-cols-2", text)
        self.assertIn("aria-label", text)
        self.assertIn("Confirm reorder 1", text)
        self.assertIn("Date.parse", text)
        self.assertNotIn('H("Archive"', text)

    def test_helpers_and_dashboard_on_sample(self) -> None:
        sample = (
            'function mk(){try{return JSON.parse(localStorage.getItem(fk)||"[]")}catch(e){return[]}}'
            "function gk(e){localStorage.setItem(fk,JSON.stringify(e))}"
            "function gx(e,t,n,r){const o=e.map(e=>mx(e,t,n,r)).filter(Boolean);return o}"
            "function mS(){const e=mk();let t=100;return t+1}"
            "F=mk(),N=F.length"
            'onClick:()=>{const e=mk();if(0===e.length)return void o("No patients to export","error");}'
            "onClick:()=>{const e=mk();if(0===e.length)return;const t=e.map(e=>e)}"
            "const e=gx(mk(),ak,rk,tk);"
            'onClick:()=>{const e=mk();fS(new Blob([JSON.stringify(e,null,2)],{type:"application/json"}),"neuro_backup_'
            'i.participantId=String(101+n)min:"101"'
            "zS=t=>{let r=t.fd,i=t.setFd,s=t.onLoadSession,o=t.showToast,l=t.isActive;return null};const US=e=>{"
        )
        out, applied = patch_js_text(sample)
        self.assertIn("database groups UI", applied)
        self.assertIn(MK_NEW, out)
        self.assertIn(MS_NEW, out)
        self.assertIn(DASH_NEW, out)
        self.assertIn("function nlB(", out)
        self.assertIn("e&&!e._archived", out)
        self.assertIn("Intervention / AOMI", out)
        self.assertIn("grid-cols-2", out)
        self.assertIn("String(n+1)", out)
        self.assertIn("let t=0;", out)

    def test_applies_to_live_clinic_bundle(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        original = bundle.read_text(encoding="utf-8", errors="replace")
        out, applied = patch_js_text(original)
        self.assertGreaterEqual(len(applied), 8)
        self.assertIn("function nlB(", out)
        self.assertIn("F=nlB(),N=F.length", out)
        self.assertIn("Intervention / AOMI", out)
        self.assertIn("Reorder Study IDs", out)
        self.assertIn("grid-cols-2", out)
        self.assertIn("const US=e=>{", out)
        self.assertIn("function mS(){const e=nlB();let t=0;", out)
        self.assertNotIn('H("Archive"', out)

    def test_writes_bundle_and_pwa_reload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            sample = (
                'function mk(){try{return JSON.parse(localStorage.getItem(fk)||"[]")}catch(e){return[]}}'
                "function gk(e){localStorage.setItem(fk,JSON.stringify(e))}"
                "function gx(e,t,n,r){const o=e.map(e=>mx(e,t,n,r)).filter(Boolean);return o}"
                "function mS(){const e=mk();let t=100;return t+1}"
                "F=mk(),N=F.length"
                'onClick:()=>{const e=mk();if(0===e.length)return void o("No patients to export","error");}'
                "onClick:()=>{const e=mk();if(0===e.length)return;const t=e.map(e=>e)}"
                "const e=gx(mk(),ak,rk,tk);"
                'onClick:()=>{const e=mk();fS(new Blob([JSON.stringify(e,null,2)],{type:"application/json"}),"neuro_backup_'
                'i.participantId=String(101+n)min:"101"'
                "zS=t=>{let r=t.fd,i=t.setFd,s=t.onLoadSession,o=t.showToast,l=t.isActive;return null};const US=e=>{"
            )
            (js_dir / "main.0626212c.js").write_text(sample, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<meta name="nl-version" content="31.80"/>'
                '<script src="/static/js/main.0626212c.js?kin=8"></script>',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.62-pwa"}),
                encoding="utf-8",
            )
            (root / "auth.py").write_text(
                "        for p in patients:\n"
                "            if not isinstance(p, dict):\n"
                "                continue\n"
                "            key = _patient_drive_key_from_record(p)\n",
                encoding="utf-8",
            )
            self.assertEqual(patch_database_groups(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn("Reorder Study IDs", js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=11", html)
            self.assertIn("31.83", html)
            auth = (root / "auth.py").read_text(encoding="utf-8")
            self.assertIn('p.get("_archived")', auth)


if __name__ == "__main__":
    unittest.main()
