import unittest
from transfer_readiness import summarize


def ledger(rows):
    from collections import Counter
    return {'records': rows, 'summary': {'catalog_pages': len(rows), 'status_counts': dict(Counter(row['status'] for row in rows))}}


class TransferReadinessTests(unittest.TestCase):
    def test_pending_candidate_not_verified(self):
        report = summarize(ledger([{'id': '2', 'status': 'pending', 'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book123.pdf'}]))
        self.assertEqual(report['pending_with_official_pdf_link'], 1)
        self.assertEqual(report['next_source_ids_for_manual_verification'], ['2'])

    def test_missing_hash_reported_without_changing_status(self):
        report = summarize(ledger([{'id': '3', 'status': 'uploaded_verified', 'pdf_check': {'bytes': 10}}]))
        self.assertEqual(report['missing_uploaded_sha256'], ['3'])
        self.assertEqual(report['status_counts']['uploaded_verified'], 1)

    def test_duplicate_source_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize(ledger([{'id': '1', 'status': 'pending'}, {'id': '1', 'status': 'pending'}]))

    def test_inconsistent_summary_fails_closed(self):
        value = ledger([{'id': '1', 'status': 'pending'}])
        value['summary']['catalog_pages'] = 9
        with self.assertRaises(ValueError):
            summarize(value)


if __name__ == '__main__':
    unittest.main()
