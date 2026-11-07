import copy
import unittest
from transfer_status_audit import audit


def sample():
    return {"records": [
        {"id": "25", "status": "uploaded_verified",
         "page": "https://home.moe.gov.om/ar/manaheg/1/show/25",
         "pdf": "https://home.moe.gov.om/images/manaheg/file/Book25.pdf",
         "drive_file": {"id": "abc", "size": "100"},
         "pdf_check": {"bytes": 100, "pages": 2}},
        {"id": "58", "status": "source_error"}],
        "summary": {"catalog_pages": 2, "uploaded_verified": 1,
                    "bytes_uploaded": 100,
                    "status_counts": {"uploaded_verified": 1, "source_error": 1}}}


class TestAudit(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(audit(sample()), [])

    def test_reject_external_pdf_host(self):
        d = sample()
        d["records"][0]["pdf"] = "https://example.org/images/manaheg/file/Book25.pdf"
        self.assertTrue(any("invalid official PDF URL" in x for x in audit(d)))

    def test_reject_deceptive_pdf_host(self):
        d = sample()
        d["records"][0]["pdf"] = "https://home.moe.gov.om.evil.example/images/manaheg/file/Book25.pdf"
        self.assertTrue(any("invalid official PDF URL" in x for x in audit(d)))

    def test_reject_source_page_query(self):
        d = sample()
        d["records"][0]["page"] = "https://home.moe.gov.om/ar/manaheg/1/show/25?redirect=1"
        self.assertTrue(any("invalid official source page URL" in x for x in audit(d)))

    def test_duplicate_source(self):
        d = sample()
        d["records"][1]["id"] = "25"
        self.assertTrue(any("duplicate source" in x for x in audit(d)))

    def test_missing_pdf_verification(self):
        d = sample()
        del d["records"][0]["pdf_check"]
        self.assertTrue(any("missing upload PDF verification" in x for x in audit(d)))

    def test_missing_pdf_check_keeps_drive_bytes_in_total(self):
        d = sample()
        del d["records"][0]["pdf_check"]
        issues = audit(d)
        self.assertTrue(any("missing upload PDF verification" in x for x in issues))
        self.assertFalse(any("bytes_uploaded mismatch" in x for x in issues))

    def test_reject_wrong_destination_parent(self):
        d = sample()
        d["folder_map"] = {"2:2": "correct-folder"}
        d["records"][0]["drive_file"].update(
            {"folder_key": "2:2", "parent_id": "wrong-folder"})
        self.assertTrue(any("destination parent folder mismatch" in x for x in audit(d)))

    def test_reject_unknown_destination_folder(self):
        d = sample()
        d["folder_map"] = {"2:2": "correct-folder"}
        d["records"][0]["drive_file"].update(
            {"folder_key": "2:1", "parent_id": "wrong-folder"})
        self.assertTrue(any("unknown destination folder" in x for x in audit(d)))

    def test_accept_matching_destination_folder(self):
        d = sample()
        d["folder_map"] = {"2:2": "correct-folder"}
        d["records"][0]["drive_file"].update(
            {"folder_key": "2:2", "parent_id": "correct-folder"})
        self.assertEqual(audit(d), [])

    def test_wrong_size(self):
        d = sample()
        d["records"][0]["pdf_check"]["bytes"] = 99
        self.assertTrue(any("size mismatch" in x for x in audit(d)))

    def test_wrong_pages(self):
        d = sample()
        d["records"][0]["pdf_check"]["pages"] = 0
        self.assertTrue(any("page count" in x for x in audit(d)))

    def test_summary_mismatch(self):
        d = sample()
        d["summary"]["bytes_uploaded"] = 1
        self.assertTrue(any("bytes_uploaded mismatch" in x for x in audit(d)))

    def test_duplicate_drive(self):
        d = sample()
        d["records"].append(copy.deepcopy(d["records"][0]))
        self.assertTrue(any("duplicate Drive file ID" in x for x in audit(d)))


    def test_source_page_id_mismatch(self):
        d = sample()
        d["records"][0]["page"] = "https://home.moe.gov.om/ar/manaheg/1/show/26"
        self.assertTrue(any("source page ID mismatch" in x for x in audit(d)))

    def test_duplicate_uploaded_sha256(self):
        d = sample()
        duplicate = copy.deepcopy(d["records"][0])
        duplicate["id"] = "26"
        duplicate["page"] = "https://home.moe.gov.om/ar/manaheg/1/show/26"
        duplicate["drive_file"]["id"] = "different-file"
        duplicate["pdf_check"]["sha256"] = "a" * 64
        d["records"][0]["pdf_check"]["sha256"] = "a" * 64
        d["records"].append(duplicate)
        d["summary"]["catalog_pages"] = 3
        d["summary"]["uploaded_verified"] = 2
        d["summary"]["bytes_uploaded"] = 200
        d["summary"]["status_counts"]["uploaded_verified"] = 2
        self.assertTrue(any("duplicate uploaded PDF SHA256" in x for x in audit(d)))

if __name__ == "__main__":
    unittest.main()
