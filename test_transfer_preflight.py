import unittest
from transfer_preflight import preflight


class PreflightTests(unittest.TestCase):
    def test_missing_hash_never_approves(self):
        ledger = {'records': [{'id': '25', 'status': 'uploaded_verified', 'drive_file': {'id': 'x', 'size': '100'}, 'pdf_check': {'bytes': 100, 'pages': 2}}]}
        result = preflight(ledger)
        self.assertFalse(result['safe_to_auto_approve'])
        self.assertIn({'source_id': '25', 'reason': 'missing_or_invalid_sha256'}, result['issues'])

    def test_duplicate_digest(self):
        records = [{'id': str(i), 'status': 'uploaded_verified', 'drive_file': {'id': str(i), 'size': '10'}, 'pdf_check': {'bytes': 10, 'pages': 1, 'sha256': 'a'*64}} for i in (1, 2)]
        result = preflight({'records': records})
        self.assertEqual(sum(i['reason'] == 'duplicate_sha256' for i in result['issues']), 2)

    def test_mismatched_size(self):
        record = {'id': '1', 'status': 'uploaded_verified', 'drive_file': {'id': 'f', 'size': '20'}, 'pdf_check': {'bytes': 10, 'pages': 1, 'sha256': 'b'*64}}
        self.assertIn({'source_id': '1', 'reason': 'size_missing_or_mismatch'}, preflight({'records': [record]})['issues'])

    def test_pending_not_approved(self):
        self.assertEqual(preflight({'records': [{'id': '1', 'status': 'pending'}]})['issues'], [])
        self.assertFalse(preflight({'records': []})['safe_to_auto_approve'])


if __name__ == '__main__':
    unittest.main()
