#!/usr/bin/env python3
from __future__ import annotations

import re
import unittest

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


def _pdf_strings(blob: bytes) -> str:
    parts = []
    for raw in re.findall(rb"\((?:\\.|[^\\)])*\)", blob):
        text = raw[1:-1].decode("latin-1")
        text = (
            text.replace("\\(", "(")
            .replace("\\)", ")")
            .replace("\\\\", "\\")
        )
        parts.append(text)
    return "\n".join(parts)


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
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf)
        self.assertIn(b"startxref", pdf)
        xref_at = pdf.rfind(b"startxref")
        self.assertGreater(xref_at, 0)
        obj1 = pdf.find(b"1 0 obj")
        self.assertGreater(obj1, 8)
        self.assertNotEqual(pdf[pdf.find(b"xref"):].split(b"\n")[2], b"0000000000 00000 n ")

    def test_matches_program_labels_not_raw_keys(self) -> None:
        lines = "\n".join(patient_pdf_lines(DOUAN))
        self.assertIn("Visual: Neck forward-backward flexion", lines)
        self.assertIn("Kinesthetic: Neck forward-backward flexion", lines)
        self.assertNotIn("0_gorsel", lines)
        self.assertNotIn("0_kinestetik", lines)
        self.assertIn("Felt Difference", lines)
        self.assertIn("How much do you feel you can control your muscles?", "\n".join(r["metric"] for r in build_summary_rows(DOUAN)))
        self.assertIn("Hand to Table (front) - Time (sec)", lines)
        self.assertIn("Hand to Box (front) - Ability Rating (0-5)", "\n".join(r["metric"] for r in build_summary_rows(DOUAN)))
        self.assertIn("Pain at Rest", lines)
        self.assertIn("VAMS Calm", lines)
        self.assertIn("Number of Velocity Peaks (NVP)", lines)
        self.assertNotIn("—", lines)
        self.assertIn(MISSING, lines)

    def test_empty_cells_are_ascii_dash_not_question_mark(self) -> None:
        pdf = build_patient_pdf(DOUAN)
        text = _pdf_strings(pdf)
        self.assertIn("Visual: Neck forward-backward flexion", text)
        self.assertIn("Felt Difference", text)
        self.assertIn("Hand to Table (front) - Time (sec)", text)
        self.assertIn("Time Since Stroke", text)
        self.assertIn("AOMI Group", text)
        self.assertNotIn("0_gorsel", text)
        self.assertNotIn("How much do you feel you can 5", text)
        # missing TSS / empty VAS cells must not become latin-1 '?'
        self.assertNotRegex(text, r"TSS:\s*\?")
        self.assertIn("Clinical Assessment Report", text)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertNotEqual(pdf[pdf.find(b"xref"):].split(b"\n")[2], b"0000000000 00000 n ")

    def test_summary_rows_follow_program_order(self) -> None:
        rows = build_summary_rows(DOUAN)
        tools = [r["tool"] for r in rows]
        self.assertEqual(tools[:3], ["VAS", "VAS", "VAS"])
        kviq = [r for r in rows if r["tool"] == "KVIQ"]
        self.assertEqual(len(kviq), 20)
        self.assertEqual(kviq[0]["metric"], "Visual: Neck forward-backward flexion")
        self.assertEqual(kviq[0]["pre"], "3")
        self.assertEqual(kviq[0]["post"], "5")
        self.assertEqual(kviq[0]["delta"], "+2.00")
        wmft = [r for r in rows if r["tool"] == "WMFT"]
        self.assertEqual(len(wmft), 8)
        self.assertEqual(wmft[0]["metric"], "Hand to Table (front) - Time (sec)")
        self.assertEqual(wmft[0]["pre"], "4.2")
        self.assertEqual(wmft[0]["post"], "3.1")


if __name__ == "__main__":
    unittest.main()
