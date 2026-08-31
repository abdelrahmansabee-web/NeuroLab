#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from glass_report import build_glass_html
from patient_pdf import (
    MISSING,
    build_patient_pdf,
    build_summary_rows,
    patient_pdf_filename,
    patient_pdf_lines,
)


DOUAN = {
    "demographics": {
        "participantId": "111",
        "name": "Douan ertan",
        "age": "50",
        "sex": "1",
        "strokeType": "1",
        "side": "1",
        "group": "1",
        "mas": "1+",
        "mrc": "4",
    },
    "ipaq": {
        "light": {"gun": "7", "sure": "60"},
        "sitting": {"gun": "7", "sure": "400"},
        "extra": {"gun": "6", "sure": "20"},
    },
    "vas": {"rest": {"pre": 0}},
    "vams": {
        "happy": {"pre": 10, "post": 10},
        "sad": {"pre": 0, "post": 0},
        "calm": {"pre": 6, "post": 8},
        "tense": {"pre": 2, "post": 0},
    },
    "motorchange": {"control": 5, "difference": 10},
    "kgia": {
        "0_gorsel": {"once": 3, "sonra": 5},
        "0_kinestetik": {"once": 3, "sonra": 5},
    },
    "wmft": {
        "1": {"pre": {"time": 4.2, "rating": 3}, "post": {"time": 3.1, "rating": 4}},
    },
    "kinematics": {
        "pre": {"nvp": 4, "movement_time_sec": 2.4},
        "post": {"nvp": 3, "movement_time_sec": 1.9},
        "baseline": {"nvp": 1},
    },
}

NECK = "Visual: Neck forward–backward flexion"


def _pdf_text(blob: bytes) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return blob.decode("latin-1", "replace")
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "r.pdf"
        path.write_bytes(blob)
        out = subprocess.run(
            [pdftotext, "-layout", str(path), "-"],
            capture_output=True,
            check=False,
        )
        return (out.stdout or b"").decode("utf-8", "replace")


class PatientPdfTests(unittest.TestCase):
    def test_filename_uses_id_and_name(self) -> None:
        name = patient_pdf_filename({"demographics": {"participantId": "105", "name": "Ahmet Sever"}})
        self.assertEqual(name, "105_Ahmet_Sever.pdf")

    def test_pdf_contains_clinical_fields(self) -> None:
        patient = {
            "demographics": {
                "participantId": "105",
                "name": "Ahmet Sever",
                "age": "62",
                "sex": "1",
                "strokeType": "1",
            },
            "wmft": {"score": 4},
        }
        lines = patient_pdf_lines(patient)
        blob = "\n".join(lines)
        self.assertIn("Clinical Assessment Report", blob)
        self.assertIn("Ahmet Sever", blob)
        self.assertIn("ID: 105", blob)
        self.assertIn("Male", blob)
        self.assertIn("Ischemic", blob)
        pdf = build_patient_pdf(patient)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf)

    def test_glass_html_matches_program_export(self) -> None:
        html = build_glass_html(DOUAN)
        self.assertIn("AOMI Group / AOMI Grubu", html)
        self.assertIn("Clinical Assessment Report / Klinik Değerlendirme Raporu", html)
        self.assertIn("Pain Scale (VAS) / Ağrı Skalası", html)
        self.assertIn("Mood Scale (VAMS-4) / Ruh Hali", html)
        self.assertIn("Muscle Control Scale / Kas Kontrolü", html)
        self.assertIn("Motor Imagery (KVIQ) / Motor İmgeleme", html)
        self.assertIn("Physical Activity (IPAQ) / Fiziksel Aktivite", html)
        self.assertIn("Age / Yaş", html)
        self.assertIn("Felt Difference", html)
        self.assertIn(NECK, html)
        self.assertIn("Summary / Özet", html)
        self.assertIn("Clinical Narrative / Klinik Anlatım", html)
        self.assertNotIn("0_gorsel", html)
        self.assertIn("#f5f0eb", html)
        self.assertIn("#800020", html)

    def test_matches_program_labels_not_raw_keys(self) -> None:
        lines = "\n".join(patient_pdf_lines(DOUAN))
        self.assertIn(NECK, lines)
        self.assertNotIn("0_gorsel", lines)
        self.assertIn("Felt Difference", lines)
        self.assertIn("Hand to Table (front) — Time (sec)", lines)
        self.assertIn("Pain at Rest", lines)
        self.assertIn(MISSING, lines)

    def test_export_pdf_has_glass_titles(self) -> None:
        pdf = build_patient_pdf(DOUAN)
        text = _pdf_text(pdf)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn("AOMI Group", text)
        self.assertIn("Clinical Assessment Report", text)
        self.assertIn("Felt Difference", text)
        self.assertIn("Pain Scale (VAS)", text)
        self.assertNotIn("0_gorsel", text)
        self.assertIn("Douan ertan", text)

    def test_summary_rows_follow_program_order(self) -> None:
        rows = build_summary_rows(DOUAN)
        tools = [r["tool"] for r in rows]
        self.assertEqual(tools[:3], ["VAS", "VAS", "VAS"])
        kviq = [r for r in rows if r["tool"] == "KVIQ"]
        self.assertEqual(len(kviq), 20)
        self.assertEqual(kviq[0]["metric"], NECK)
        self.assertEqual(kviq[0]["pre"], "3")
        self.assertEqual(kviq[0]["post"], "5")
        self.assertEqual(kviq[0]["delta"], "+2.00")
        wmft = [r for r in rows if r["tool"] == "WMFT"]
        self.assertEqual(len(wmft), 8)
        self.assertEqual(wmft[0]["metric"], "Hand to Table (front) — Time (sec)")
        self.assertEqual(wmft[0]["pre"], "4.2")
        self.assertEqual(wmft[0]["post"], "3.1")


if __name__ == "__main__":
    unittest.main()
