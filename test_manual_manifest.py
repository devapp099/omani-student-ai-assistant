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

    def test_rejects_whitespace_and_control_in_official_url(self):
        for url in ("https://example.org/book pdf", "https://example.org/\\tbook",
                    "https://example.org/book\\n", "https://example.org/book\\r"):
            with self.subTest(url=repr(url)):
                self.row(official_url=url)
                self.assertTrue(any("official URL" in e for e in validate_manifest(self.path)))

    def test_rejects_credentials_in_official_url(self):
        self.row(official_url="https://user:secret@example.org/book.pdf")
        self.assertTrue(any("official URL" in e for e in validate_manifest(self.path)))

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
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writerow(dict(grade="7", semester="1", subject="تقنية المعلومات",
                                 title="Verified example", official_url="https://ict.moe.gov.om/book/",
                                 download_status="not_downloaded", upload_status="not_uploaded",
                                 metadata_review="pending", rights_status="unknown"))
        self.assertTrue(any("duplicate" in e for e in validate_manifest(self.path)))

    def test_rejects_unicode_equivalent_duplicate_book_entries(self):
        for first, second in (("Café", "Cafe\u0301"), ("Book", "Ｂｏｏｋ")):
            with self.subTest(first=first, second=second):
                self.row(title=first)
                with self.path.open("a", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=FIELDS)
                    row = dict.fromkeys(FIELDS, "")
                    row.update(grade="7", semester="1", subject="تقنية المعلومات",
                               title=second, official_url="https://ict.moe.gov.om/book/",
                               download_status="not_downloaded", upload_status="not_uploaded",
                               metadata_review="pending", rights_status="unknown")
                    writer.writerow(row)
                self.assertTrue(any("duplicate book entry" in e
                                    for e in validate_manifest(self.path)))

    def test_rejects_upload_without_filename(self):
        self.row(download_status="downloaded", upload_status="uploaded")
        self.assertTrue(any("filename" in e for e in validate_manifest(self.path)))

    def test_rejects_filename_path_traversal(self):
        self.row(local_filename="../book.pdf")
        self.assertTrue(any("paths" in e for e in validate_manifest(self.path)))

    def test_rejects_unsafe_filename_characters(self):
        for filename in ("book\\n.pdf", "book\\u202e.pdf", "book.", "book "):
            with self.subTest(filename=repr(filename)):
                self.row(local_filename=filename)
                self.assertTrue(any("unsafe local filename" in e
                                    for e in validate_manifest(self.path)))

    def test_rejects_trailing_space_without_silently_normalizing_filename(self):
        self.row(local_filename="book.pdf ")
        errors = validate_manifest(self.path)
        self.assertTrue(any("unsafe local filename" in e for e in errors))

    def test_rejects_leading_whitespace_in_filename(self):
        for filename in (" book.pdf", "\tbook.pdf", "   "):
            with self.subTest(filename=repr(filename)):
                self.row(local_filename=filename)
                self.assertTrue(any("unsafe local filename" in e
                                    for e in validate_manifest(self.path)))

    def test_rejects_duplicate_uploaded_filenames_case_insensitively(self):
        self.row(download_status="downloaded", upload_status="uploaded", local_filename="Book.pdf")
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            row = dict.fromkeys(FIELDS, "")
            row.update(grade="8", semester="2", subject="Another subject",
                       title="Another verified example", official_url="https://ict.moe.gov.om/book/",
                       download_status="downloaded", upload_status="uploaded",
                       metadata_review="pending", rights_status="unknown",
                       local_filename="book.PDF")
            writer.writerow(row)
        self.assertTrue(any("duplicate uploaded filename" in e
                            for e in validate_manifest(self.path)))

    def test_rejects_unicode_equivalent_uploaded_filenames(self):
        for first, second in (("café.pdf", "cafe\u0301.pdf"),
                              ("Book.pdf", "Ｂｏｏｋ.pdf")):
            with self.subTest(first=first, second=second):
                self.row(download_status="downloaded", upload_status="uploaded",
                         local_filename=first)
                with self.path.open("a", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=FIELDS)
                    row = dict.fromkeys(FIELDS, "")
                    row.update(grade="8", semester="2", subject="Another subject",
                               title="Another verified example",
                               official_url="https://ict.moe.gov.om/book/",
                               download_status="downloaded", upload_status="uploaded",
                               metadata_review="pending", rights_status="unknown",
                               local_filename=second)
                    writer.writerow(row)
                self.assertTrue(any("duplicate uploaded filename" in e
                                    for e in validate_manifest(self.path)))

    def test_rejects_nonportable_filename(self):
        for filename in ("CON.pdf", "nul.txt", "LPT1.pdf", "COM9.pdf",
                         "book:part.pdf", "book?.pdf", "book|part.pdf"):
            with self.subTest(filename=filename):
                self.row(local_filename=filename)
                self.assertTrue(any("non-portable local filename" in e
                                    for e in validate_manifest(self.path)))

    def test_rejects_unicode_compatibility_device_names(self):
        # NFKC equivalents of Windows device names are unsafe on shared storage.
        for filename in ("ＣＯＮ.pdf", "ｎｕｌ.txt", "ＬＰＴ１.pdf"):
            with self.subTest(filename=filename):
                self.row(local_filename=filename)
                self.assertTrue(any("non-portable local filename" in e
                                    for e in validate_manifest(self.path)))

    def test_allows_valid_uploaded_filename(self):
        self.row(download_status="downloaded", upload_status="uploaded", local_filename="book.pdf")
        self.assertEqual(validate_manifest(self.path), [])

if __name__ == "__main__":
    unittest.main()
