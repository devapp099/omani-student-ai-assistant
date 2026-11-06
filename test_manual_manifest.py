"""Tests for blank, non-fabricated manual curriculum manifest."""
import csv
import tempfile
import unittest
from pathlib import Path
from manual_manifest import FIELDS, blank_manifest, validate_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "books.csv"

    def row(self, **updates):
        row = dict.fromkeys(FIELDS, "")
        row.update(grade="7", semester="1", subject="تقنية المعلومات",
                   title="Verified example", official_url="https://ict.moe.gov.om/book/",
                   download_status="not_downloaded", upload_status="not_uploaded",
                   metadata_review="pending", rights_status="unknown")
        row.update(updates)
        with self.path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)

    def test_blank_template_contains_no_books(self):
        blank_manifest(self.path)
        self.assertEqual(validate_manifest(self.path), [])
        with self.path.open(encoding="utf-8-sig") as f:
            self.assertEqual(len(f.readlines()), 1)

    def test_refuses_overwrite(self):
        blank_manifest(self.path)
        with self.assertRaises(FileExistsError):
            blank_manifest(self.path)

    def test_valid_example(self):
        self.row()
        self.assertEqual(validate_manifest(self.path), [])

    def test_rejects_invalid_grade(self):
        self.row(grade="13")
        self.assertTrue(validate_manifest(self.path))

    def test_rejects_insecure_link(self):
        self.row(official_url="http://example.org/book.pdf")
        self.assertTrue(validate_manifest(self.path))

    def test_rejects_upload_without_download(self):
        self.row(upload_status="uploaded")
        self.assertTrue(validate_manifest(self.path))

    def test_rejects_unverified_missing_title(self):
        self.row(title="")
        self.assertTrue(validate_manifest(self.path))

    def test_rejects_invalid_rights(self):
        self.row(rights_status="automatically_permitted")
        self.assertTrue(validate_manifest(self.path))


    def test_rejects_duplicate_book_entry(self):
        self.row()
        with self.path.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writerow(dict(grade="7", semester="1", subject="تقنية المعلومات",
                                 title="Verified example", official_url="https://ict.moe.gov.om/book/",
                                 download_status="not_downloaded", upload_status="not_uploaded",
                                 metadata_review="pending", rights_status="unknown"))
        self.assertTrue(any("duplicate" in e for e in validate_manifest(self.path)))

    def test_rejects_upload_without_filename(self):
        self.row(download_status="downloaded", upload_status="uploaded")
        self.assertTrue(any("filename" in e for e in validate_manifest(self.path)))

    def test_rejects_filename_path_traversal(self):
        self.row(local_filename="../book.pdf")
        self.assertTrue(any("paths" in e for e in validate_manifest(self.path)))

    def test_allows_valid_uploaded_filename(self):
        self.row(download_status="downloaded", upload_status="uploaded", local_filename="book.pdf")
        self.assertEqual(validate_manifest(self.path), [])

if __name__ == "__main__":
    unittest.main()
