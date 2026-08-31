#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from drive_persist import (
    _assemble_patient_record,
    _is_legacy_root,
    _patient_key_from_parts,
    _sanitize,
    clinic_drive_filename,
    drive_configured,
    reorganize_clinic_folder,
    trash_clinic_folder_contents,
    upload_named_files,
    upload_root_bytes,
    write_drive_connected_marker,
)


class DrivePersistTests(unittest.TestCase):
    def test_skips_when_unset(self) -> None:
        out = upload_named_files("101", [("pre_validation_original.mp4", Path("/nope"), "videos")])
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "drive_unset")

    def test_upserts_validation_video_in_patient_folder(self) -> None:
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "existing"}]}
        service.files.return_value.update.return_value.execute.return_value = {"id": "existing"}
        with self._tmp_mp4() as path:
            out = upload_named_files(
                "105_Ahmet_sever",
                [
                    ("pre_validation_original.mp4", path, "videos"),
                    ("pre_validation_unified.mp4", path, "videos"),
                    ("pre_validation_overlay.json", path, "data"),
                    ("01_demographics.json", path, "data"),
                ],
                service=service,
                folder_id="root",
            )
        self.assertTrue(out["ok"])
        self.assertIn("pre_validation.mp4", out["files"])
        self.assertNotIn("pre_validation_original.mp4", out["files"])
        self.assertNotIn("01_demographics.json", out["files"])
        self.assertEqual(out["patientKey"], "105_Ahmet_sever")
        self.assertEqual(len(out["locations"]), 1)
        service.files.return_value.update.assert_called()
        service.files.return_value.delete.assert_not_called()

    def test_sanitize(self) -> None:
        self.assertEqual(_sanitize("pre/../x"), "pre_.._x")

    def test_drive_keeps_pdf_and_validation_videos_only(self) -> None:
        self.assertEqual(clinic_drive_filename("pre_validation_unified.mp4"), "pre_validation.mp4")
        self.assertEqual(clinic_drive_filename("clip_unified_validation.mp4"), "clip_validation.mp4")
        self.assertIsNone(clinic_drive_filename("pre_validation_original.mp4"))
        self.assertIsNone(clinic_drive_filename("pre_original.mp4"))
        self.assertIsNone(clinic_drive_filename("pre_validation_overlay.json"))
        self.assertIsNone(clinic_drive_filename("01_demographics.json"))
        self.assertIsNone(clinic_drive_filename("patient.json"))
        self.assertIsNone(clinic_drive_filename("session.json"))
        self.assertEqual(clinic_drive_filename("baseline_validation.mp4"), "baseline_validation.mp4")
        self.assertEqual(clinic_drive_filename("105_Ahmet_sever.pdf"), "105_Ahmet_sever.pdf")

    def test_recovered_video_names(self) -> None:
        from drive_persist import recovered_drive_video_name

        self.assertEqual(recovered_drive_video_name("baseline_original.mp4"), "baseline_validation.mp4")
        self.assertEqual(recovered_drive_video_name("baseline_validation_original.mp4"), "baseline_validation.mp4")
        self.assertEqual(recovered_drive_video_name("pre_validation_unified.mp4"), "pre_validation.mp4")
        self.assertEqual(recovered_drive_video_name("baseline_validation.mp4"), "baseline_validation.mp4")
        self.assertIsNone(recovered_drive_video_name("patient.json"))

    def test_collects_videos_inside_trashed_nested_folders(self) -> None:
        from drive_persist import _collect_videos_from_trashed_trees

        service = _FakeTrashDrive()
        with patch("drive_persist._sa_service_or_none", return_value=None):
            videos = _collect_videos_from_trashed_trees(service)
        names = [item.get("name") for item in videos]
        self.assertIn("baseline_original.mp4", names)
        rec = next(item for item in videos if item.get("name") == "baseline_original.mp4")
        self.assertIn("111_Douan_ertan", rec.get("parts") or ())

    def test_restore_puts_validation_mp4_in_patient_folder(self) -> None:
        from drive_persist import restore_trashed_videos_to_patients

        service = _FakeDriveService()
        found = [
            {
                "id": "mp4",
                "name": "baseline_original.mp4",
                "mimeType": "video/mp4",
                "parents": ["videos"],
                "parts": ("team_patients", "111_Douan_ertan", "videos"),
            }
        ]
        with patch("drive_persist.drive_configured", return_value=True):
            with patch("drive_persist._build_service", return_value=(service, "root")):
                with patch("drive_persist._sa_service_or_none", return_value=None):
                    with patch(
                        "drive_persist._collect_videos_from_trashed_trees",
                        return_value=found,
                    ):
                        out = restore_trashed_videos_to_patients()
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["restored"][0]["patientKey"], "111_Douan_ertan")
        self.assertEqual(out["restored"][0]["name"], "baseline_validation.mp4")
        names = [item.get("name") for rows in service.tree.values() for item in rows]
        self.assertIn("baseline_validation.mp4", names)

    def test_legacy_root_names(self) -> None:
        self.assertTrue(_is_legacy_root("team_patients"))
        self.assertTrue(_is_legacy_root("u1"))
        self.assertTrue(_is_legacy_root("_NEUROLAB_DRIVE_OK.json"))
        self.assertFalse(_is_legacy_root("105_Ahmet_sever"))

    def test_patient_key_from_nested_paths(self) -> None:
        self.assertEqual(
            _patient_key_from_parts(("team_patients", "105_Ahmet_sever", "data")),
            "105_Ahmet_sever",
        )
        self.assertEqual(_patient_key_from_parts(("u1", "105_Ahmet_sever", "videos")), "105_Ahmet_sever")
        self.assertEqual(_patient_key_from_parts(("105_Ahmet_sever",)), "105_Ahmet_sever")
        self.assertEqual(_patient_key_from_parts(()), "")

    def test_assembles_patient_from_section_json(self) -> None:
        rec = _assemble_patient_record(
            {
                "01_demographics.json": b'{"participantId": "105", "name": "Ahmet"}',
                "07_wmft.json": b'{"score": 4}',
            }
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec["demographics"]["participantId"], "105")
        self.assertEqual(rec["wmft"]["score"], 4)

    def test_oauth_pending_does_not_use_service_account(self) -> None:
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "cid",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}",
            "GOOGLE_DRIVE_FOLDER_ID": "folder",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as raw:
                with patch("drive_oauth._data_dir", return_value=Path(raw)):
                    self.assertFalse(drive_configured())

    def test_root_upload_skips_without_oauth(self) -> None:
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "cid",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as raw:
                with patch("drive_oauth._data_dir", return_value=Path(raw)):
                    out = upload_root_bytes("_NEUROLAB_DRIVE_OK.json", b'{"ok":true}')
                    self.assertTrue(out.get("skipped"))

    def test_connected_marker_does_not_write_json(self) -> None:
        out = write_drive_connected_marker(email="a@b.c", folder_name=" NeuroLab_Backups")
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "patient_folders_only")

    def test_trashes_root_children(self) -> None:
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {
            "files": [
                {"id": "team", "name": "team_patients", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "u1", "name": "u1", "mimeType": "application/vnd.google-apps.folder"},
            ]
        }
        service.files.return_value.update.return_value.execute.return_value = {"id": "team"}
        with patch("drive_persist.drive_configured", return_value=True):
            with patch("drive_persist._build_service", return_value=(service, "root")):
                out = trash_clinic_folder_contents()
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(len(out["trashed"]), 2)
        service.files.return_value.delete.assert_not_called()

    def test_reorganize_builds_pdf_moves_video_and_trashes_json(self) -> None:
        service = _FakeDriveService()
        out = reorganize_clinic_folder(service=service, folder_id="root")
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["pdfs"], 1)
        self.assertGreaterEqual(out["videos"], 1)
        self.assertIn("baseline_validation.mp4", out["moved"])
        self.assertIn("team", out["trashed"])
        self.assertIn("marker", out["trashed"])

    def test_renames_validation_original_on_drive(self) -> None:
        from drive_persist import promote_original_videos_on_drive

        service = MagicMock()
        listed = [
            {
                "files": [
                    {"id": "vid1", "name": "baseline_validation_original.mp4", "mimeType": "video/mp4"},
                    {"id": "uni1", "name": "baseline_validation_unified.mp4", "mimeType": "video/mp4"},
                ]
            },
            {"files": []},
        ]
        service.files.return_value.list.return_value.execute.side_effect = listed
        service.files.return_value.update.return_value.execute.return_value = {"id": "vid1"}
        with patch("drive_persist.drive_configured", return_value=True):
            with patch("drive_persist._build_service", return_value=(service, "root")):
                out = promote_original_videos_on_drive()
        self.assertTrue(out["ok"])
        self.assertEqual(out["renamed"][0]["to"], "baseline_original.mp4")
        service.files.return_value.update.assert_called()

    def _tmp_mp4(self):
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            with tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / "clip.mp4"
                path.write_bytes(b"mp4-bytes-xx")
                yield path

        return ctx()


class _FakeTrashDrive:
    """Nested mp4s in trash are invisible unless the query includes trashed=true."""

    FOLDER = "application/vnd.google-apps.folder"

    def __init__(self) -> None:
        self.trash_roots = [
            {
                "id": "team",
                "name": "team_patients",
                "mimeType": self.FOLDER,
                "parents": ["gone"],
            }
        ]
        self.trash_children = {
            "team": [
                {
                    "id": "p111",
                    "name": "111_Douan_ertan",
                    "mimeType": self.FOLDER,
                    "parents": ["team"],
                }
            ],
            "p111": [
                {
                    "id": "videos",
                    "name": "videos",
                    "mimeType": self.FOLDER,
                    "parents": ["p111"],
                }
            ],
            "videos": [
                {
                    "id": "mp4",
                    "name": "baseline_original.mp4",
                    "mimeType": "video/mp4",
                    "parents": ["videos"],
                }
            ],
        }
        self.meta = {
            "team": {"id": "team", "name": "team_patients", "parents": ["gone"]},
            "p111": {"id": "p111", "name": "111_Douan_ertan", "parents": ["team"]},
            "videos": {"id": "videos", "name": "videos", "parents": ["p111"]},
            "mp4": {"id": "mp4", "name": "baseline_original.mp4", "parents": ["videos"]},
            "gone": {"id": "gone", "name": " NeuroLab_Backups", "parents": []},
        }

    def files(self):
        return self

    def list(self, q="", **_kwargs):
        items = []
        if " in parents" in q:
            parent = q.split("'", 2)[1]
            kids = list(self.trash_children.get(parent) or [])
            items = kids if "trashed=true" in q else []
        elif "trashed=true" in q and "mimeType='application/vnd.google-apps.folder'" in q:
            items = list(self.trash_roots)
        return _Exec({"files": items, "nextPageToken": None})

    def get(self, fileId="", **_kwargs):
        return _Exec(self.meta.get(fileId) or {"id": fileId, "name": "", "parents": []})


class _FakeDriveService:
    """Minimal Drive mock for rebuild: nested team_patients tree."""

    def __init__(self) -> None:
        self.tree = {
            "root": [
                {"id": "team", "name": "team_patients", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "marker", "name": "_NEUROLAB_DRIVE_OK.json", "mimeType": "application/json"},
            ],
            "team": [
                {"id": "p105", "name": "105_Ahmet_sever", "mimeType": "application/vnd.google-apps.folder"},
            ],
            "p105": [
                {"id": "data", "name": "data", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "videos", "name": "videos", "mimeType": "application/vnd.google-apps.folder"},
            ],
            "data": [
                {"id": "json1", "name": "01_demographics.json", "mimeType": "application/json"},
                {"id": "jsonp", "name": "patient.json", "mimeType": "application/json"},
            ],
            "videos": [
                {"id": "vid1", "name": "baseline_validation.mp4", "mimeType": "video/mp4"},
                {"id": "ov1", "name": "baseline_validation_overlay.json", "mimeType": "application/json"},
            ],
        }
        self.trashed: list[str] = []
        self.created: list[dict] = []
        self.moved: list[dict] = []
        self._next = 100

    def files(self):
        return self

    def list(self, q="", **_kwargs):
        parent = "root"
        if "'root' in parents" in q:
            parent = "root"
        else:
            for key in self.tree:
                if f"'{key}' in parents" in q:
                    parent = key
                    break
        items = list(self.tree.get(parent) or [])
        if "mimeType='application/vnd.google-apps.folder'" in q:
            items = [item for item in items if item.get("mimeType") == "application/vnd.google-apps.folder"]
        if "name=" in q:
            wanted = q.split("name='", 1)[-1].split("'", 1)[0]
            items = [item for item in items if item.get("name") == wanted]
        return _Exec({"files": items, "nextPageToken": None})

    def get_media(self, fileId=""):
        if fileId in ("json1", "jsonp"):
            payload = b'{"demographics":{"participantId":"105","name":"Ahmet Sever"},"wmft":{"score":3}}'
            if fileId == "json1":
                payload = b'{"participantId":"105","name":"Ahmet Sever"}'
            return _Exec(payload)
        return _Exec(b"")

    def create(self, body=None, media_body=None, **_kwargs):
        self._next += 1
        file_id = f"new{self._next}"
        name = (body or {}).get("name") or "file"
        parent = ((body or {}).get("parents") or ["root"])[0]
        item = {
            "id": file_id,
            "name": name,
            "mimeType": (body or {}).get("mimeType") or "application/octet-stream",
        }
        self.tree.setdefault(parent, []).append(item)
        if item["mimeType"] == "application/vnd.google-apps.folder":
            self.tree.setdefault(file_id, [])
        self.created.append({"id": file_id, "name": name, "parent": parent})
        return _Exec({"id": file_id})

    def update(self, fileId="", body=None, addParents=None, removeParents=None, media_body=None, **_kwargs):
        body = body or {}
        if body.get("trashed"):
            self.trashed.append(fileId)
            for parent, items in list(self.tree.items()):
                self.tree[parent] = [item for item in items if item.get("id") != fileId]
            return _Exec({"id": fileId})
        if addParents:
            item = None
            for parent, items in list(self.tree.items()):
                for candidate in items:
                    if candidate.get("id") == fileId:
                        item = candidate
                        self.tree[parent] = [row for row in items if row.get("id") != fileId]
                        break
            if item is None:
                item = {"id": fileId, "name": body.get("name") or "file"}
            if body.get("name"):
                item["name"] = body["name"]
            self.tree.setdefault(addParents, []).append(item)
            self.moved.append({"id": fileId, "to": addParents, "name": item["name"]})
        return _Exec({"id": fileId})


class _Exec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


if __name__ == "__main__":
    unittest.main()
