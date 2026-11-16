import unittest
from audit_transfer_evidence import evidence_report


class EvidenceTests(unittest.TestCase):
    def test_missing_evidence_does_not_change_status(self):
        record = {"id": 25, "status": "uploaded_verified", "drive_file": {"id": "a", "parent_id": "b", "size": "100"}, "pdf_check": {"bytes": 100}}
        report = evidence_report({"records": [record]})
        self.assertEqual(report["needs_review"], [{"source_id": "25", "issues": ["pdf_pages", "sha256"]}])
        self.assertEqual(record["status"], "uploaded_verified")
        self.assertFalse(report["automatic_reverification"])

    def test_complete_evidence(self):
        record = {"id": "92", "status": "uploaded_verified", "drive_file": {"id": "a", "parent_id": "b", "size": "100"}, "pdf_check": {"bytes": 100, "pages": 2, "sha256": "a" * 64}}
        report = evidence_report({"records": [record]})
        self.assertEqual(report["evidence_complete"], 1)
        self.assertEqual(report["needs_review"], [])

    def test_size_mismatch_and_excluded_ignored(self):
        records = [{"id": 1, "status": "uploaded_verified", "drive_file": {"id": "a", "parent_id": "b", "size": "99"}, "pdf_check": {"bytes": 100, "pages": 1, "sha256": "a" * 64}},
                   {"id": 129, "status": "excluded_wrong_source"}]
        report = evidence_report({"records": records})
        self.assertEqual(report["uploaded_records"], 1)
        self.assertEqual(report["needs_review"][0]["issues"], ["size_mismatch"])

    def test_invalid_evidence_is_not_accepted(self):
        record = {"id": 1, "status": "uploaded_verified", "drive_file": {"id": "a", "parent_id": "b", "size": "10"}, "pdf_check": {"bytes": True, "pages": 0, "sha256": "unknown"}}
        self.assertEqual(evidence_report({"records": [record]})["needs_review"][0]["issues"], ["pdf_bytes", "pdf_pages", "sha256"])


if __name__ == "__main__":
    unittest.main()
