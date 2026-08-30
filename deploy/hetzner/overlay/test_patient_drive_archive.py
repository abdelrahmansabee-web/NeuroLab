#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from patient_drive_archive import (
    PROGRAM_SECTIONS,
    files_for_patient,
    parse_patients_payload,
    program_patient_record,
)


class PatientDriveArchiveTests(unittest.TestCase):
    def test_program_order_matches_clinic_sidebar(self) -> None:
        self.assertEqual(
            PROGRAM_SECTIONS,
            (
                "demographics",
                "ipaq",
                "vas",
                "vams",
                "motorchange",
                "kgia",
                "wmft",
                "kinematics",
            ),
        )
        rec = program_patient_record(
            {
                "_id": "pt_1",
                "demographics": {"participantId": "128", "name": "Betul"},
                "wmft": {"score": 4},
                "extra": "ignore",
            }
        )
        keys = [k for k in rec.keys() if k in PROGRAM_SECTIONS]
        self.assertEqual(keys, list(PROGRAM_SECTIONS))
        self.assertEqual(rec["wmft"], {"score": 4})
        self.assertEqual(rec["ipaq"], {})
        self.assertNotIn("extra", rec)

    def test_section_files_are_numbered_like_the_app(self) -> None:
        files = files_for_patient({"demographics": {"participantId": "101", "name": "Ahmet"}})
        names = [name for name, _content, sub in files]
        self.assertIn("patient.json", names)
        self.assertIn("01_demographics.json", names)
        self.assertIn("08_kinematics.json", names)
        self.assertEqual(names[-1], "08_kinematics.json")
        self.assertTrue(all(sub == "data" for _n, _c, sub in files))

    def test_parses_localstorage_dump(self) -> None:
        blob = {
            "stroke_rehab_patients_v6": json.dumps(
                [{"demographics": {"participantId": "109", "name": "Essmet"}, "kgia": {"a": 1}}]
            )
        }
        patients = parse_patients_payload(blob)
        self.assertEqual(len(patients), 1)
        self.assertEqual(patients[0]["demographics"]["participantId"], "109")


if __name__ == "__main__":
    unittest.main()
