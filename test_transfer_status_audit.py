import copy
import unittest
from transfer_status_audit import audit


def sample():
    return {"records": [
        {"id": "25", "status": "uploaded_verified",
         "drive_file": {"id": "abc", "size": "100"},
         "pdf_check": {"bytes": 100, "pages": 2}},
        {"id": "58", "status": "source_error"}],
        "summary": {"catalog_pages": 2, "uploaded_verified": 1,
                    "bytes_uploaded": 100,
                    "status_counts": {"uploaded_verified": 1, "source_error": 1}}}


class TestAudit(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(audit(sample()), [])

    def test_duplicate_source(self):
        d = sample()
        d["records"][1]["id"] = "25"
        self.assertTrue(any("duplicate source" in x for x in audit(d)))

    def test_missing_pdf_verification(self):
        d = sample()
        del d["records"][0]["pdf_check"]
        self.assertTrue(any("missing upload PDF verification" in x for x in audit(d)))

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


if __name__ == "__main__":
    unittest.main()
