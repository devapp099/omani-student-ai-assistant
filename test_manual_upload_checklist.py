"""Regression tests for metadata-only manual upload checklist."""
import csv
import tempfile
import unittest
from pathlib import Path
from manual_manifest import FIELDS
from manual_upload_checklist import upload_checklist


class UploadChecklistTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "books.csv"

    def write(self, rows):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def row(self, **changes):
        row = dict.fromkeys(FIELDS, "")
        row.update(grade="4", semester="1", subject="Sample subject",
                   title="Sample title", official_url="https://ict.moe.gov.om/book/",
                   download_status="not_downloaded", upload_status="not_uploaded",
                   metadata_review="pending", rights_status="unknown")
        row.update(changes)
        return row

    def test_empty_manifest_does_not_invent_books(self):
        self.write([])
        result = upload_checklist(self.path)
        self.assertEqual(result["counts"]["recorded"], 0)
        self.assertTrue(result["official_coverage_unknown"])

    def test_downloaded_but_not_uploaded_appears_in_queue(self):
        self.write([self.row(download_status="downloaded", local_filename="sample.pdf")])
        result = upload_checklist(self.path)
        self.assertEqual(result["counts"]["awaiting_manual_upload"], 1)
        self.assertEqual(result["awaiting_manual_upload"][0]["csv_line"], 2)

    def test_uploaded_is_not_in_pending_queue(self):
        self.write([self.row(download_status="downloaded", upload_status="uploaded",
                             local_filename="sample.pdf", metadata_review="approved",
                             rights_status="permitted")])
        result = upload_checklist(self.path)
        self.assertEqual(result["counts"]["uploaded"], 1)
        self.assertEqual(result["counts"]["rights_review_needed"], 0)
        self.assertEqual(result["awaiting_manual_upload"], [])

    def test_invalid_manifest_is_rejected(self):
        self.write([self.row(grade="13")])
        with self.assertRaises(ValueError):
            upload_checklist(self.path)

    def test_formula_like_metadata_is_rejected(self):
        self.write([self.row(title="=HYPERLINK(1)")])
        with self.assertRaises(ValueError):
            upload_checklist(self.path)


if __name__ == "__main__":
    unittest.main()
