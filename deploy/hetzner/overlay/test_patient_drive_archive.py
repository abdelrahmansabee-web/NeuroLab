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

    def test_decrypts_enc_patients_on_disk(self) -> None:
        import base64
        import os
        import tempfile
        from unittest.mock import patch

        from cryptography.fernet import Fernet
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        from patient_drive_archive import archive_from_data_dir

        secret = "unit-test-jwt-secret"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"neurolab_static_salt_v1",
            iterations=200000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        patients = [{"demographics": {"participantId": "128", "name": "Betul"}, "wmft": {"score": 3}}]
        blob = "enc:" + Fernet(key).encrypt(json.dumps(patients).encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            dest = data_dir / "patients" / "1.json"
            dest.parent.mkdir(parents=True)
            dest.write_text(blob, encoding="utf-8")
            with patch.dict(os.environ, {"JWT_SECRET": secret}, clear=False):
                with patch("patient_drive_archive.archive_patients", return_value={"ok": True, "uploaded": 1}) as mocked:
                    archive_from_data_dir(data_dir)
            saved = mocked.call_args[0][0]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["demographics"]["participantId"], "128")

    def test_clinic_folder_id_is_pinned(self) -> None:
        import os
        from unittest.mock import patch

        import drive_oauth

        with patch.dict(os.environ, {"GOOGLE_DRIVE_FOLDER_ID": ""}, clear=False):
            with patch.object(drive_oauth, "load_token", return_value={}):
                self.assertEqual(drive_oauth.clinic_backup_folder_id(), "1o30Gi0XlWtpHoI5rsUoc8217IWoJUInK")


if __name__ == "__main__":
    unittest.main()
