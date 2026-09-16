#!/usr/bin/env python3
from __future__ import annotations

import unittest

from drive_doc_identity import (
    canonicalize_upload_name,
    document_kind,
    is_foreign_person_pdf,
    should_trash_as_alias,
)


class DriveDocIdentityTests(unittest.TestCase):
    def test_dated_pdf_collapses_to_patient_slot(self) -> None:
        self.assertEqual(document_kind("report_115_Ahmet_2026-09-14.pdf"), "clinic_report")
        self.assertEqual(
            canonicalize_upload_name(
                "report_115_Ahmet_2026-09-14.pdf",
                patient_key="115_Ahmet_sever",
            ),
            "115_Ahmet_sever.pdf",
        )
        self.assertEqual(
            canonicalize_upload_name("clinic_report.pdf", patient_key="115_Ahmet_sever"),
            "115_Ahmet_sever.pdf",
        )
        self.assertEqual(
            canonicalize_upload_name("115_Ahmet_sever.pdf"),
            "115_Ahmet_sever.pdf",
        )

    def test_validation_aliases_share_one_mp4_slot(self) -> None:
        self.assertEqual(document_kind("pre_validation_unified.webm"), "pre_validation")
        self.assertEqual(canonicalize_upload_name("pre_validation_unified.webm"), "pre_validation.mp4")
        self.assertEqual(canonicalize_upload_name("baseline_validation.mp4"), "healthy_validation.mp4")
        self.assertEqual(
            canonicalize_upload_name("post_validation_unified.mp4"),
            "post_validation.mp4",
        )

    def test_original_clip_is_not_the_baked_video(self) -> None:
        self.assertEqual(document_kind("pre_validation_original.mp4"), "pre_validation_original")
        self.assertEqual(canonicalize_upload_name("pre_original.mp4"), "pre_validation_original.mp4")
        self.assertNotEqual(
            canonicalize_upload_name("pre_validation.mp4"),
            canonicalize_upload_name("pre_validation_original.mp4"),
        )

    def test_overlay_and_kinematics_slots(self) -> None:
        self.assertEqual(
            canonicalize_upload_name("post_validation_overlay.json"),
            "post_validation_overlay.json",
        )
        self.assertEqual(canonicalize_upload_name("baseline_kinematics.json"), "healthy_kinematics.json")

    def test_trash_dated_pdf_and_unified_alias_not_foreign_pdf(self) -> None:
        folder = "115_Ahmet_sever"
        keep = "115_Ahmet_sever.pdf"
        self.assertTrue(
            should_trash_as_alias("report_115_Ahmet_2026-09-10.pdf", keep, folder_key=folder)
        )
        self.assertTrue(should_trash_as_alias("clinic_report.pdf", keep, folder_key=folder))
        self.assertFalse(
            should_trash_as_alias("104_Other_person.pdf", keep, folder_key=folder)
        )
        self.assertTrue(is_foreign_person_pdf("104_Other_person.pdf", folder))
        self.assertTrue(
            should_trash_as_alias(
                "pre_validation_unified.mp4",
                "pre_validation.mp4",
            )
        )
        self.assertTrue(should_trash_as_alias("pre_validation.webm", "pre_validation.mp4"))
        self.assertFalse(
            should_trash_as_alias("pre_validation_original.mp4", "pre_validation.mp4")
        )
        self.assertTrue(
            should_trash_as_alias(
                "115_Ahmet_sever.pdf",
                "115_Ahmet_sever.pdf",
                keep_id="keep",
                child_id="extra",
            )
        )
        self.assertFalse(
            should_trash_as_alias(
                "115_Ahmet_sever.pdf",
                "115_Ahmet_sever.pdf",
                keep_id="keep",
                child_id="keep",
            )
        )


if __name__ == "__main__":
    unittest.main()
