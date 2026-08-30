#!/usr/bin/env python3
from __future__ import annotations

import unittest

from patient_pdf import build_patient_pdf, patient_pdf_filename, patient_pdf_lines


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
        self.assertIn("Ahmet Sever", blob)
        self.assertIn("Study ID: 105", blob)
        self.assertIn("Male", blob)
        self.assertIn("Ischemic", blob)
        pdf = build_patient_pdf(patient)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"%%EOF", pdf)


if __name__ == "__main__":
    unittest.main()
