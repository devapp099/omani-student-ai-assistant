import unittest
from catalog_manifest_audit import audit

class ManifestAuditTests(unittest.TestCase):
    def test_pending_is_not_approved(self):
        result = audit({'records': [{'id': '1', 'status': 'pending', 'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book1.pdf'}], 'summary': {'catalog_pages': 1}})
        self.assertFalse(result['retrieval_approved'])
        self.assertEqual(result['issues'], [])

    def test_duplicate_and_untrusted_url(self):
        url = 'https://example.org/a.pdf'
        result = audit({'records': [{'id': '1', 'status': 'pending', 'pdf': url}, {'id': '2', 'status': 'pending', 'pdf': url}], 'summary': {'catalog_pages': 2}})
        self.assertTrue(any('duplicate_pdf_url' in x for x in result['issues']))
        self.assertEqual(sum('untrusted_pdf_url' in x for x in result['issues']), 2)

    def test_uploaded_without_evidence(self):
        result = audit({'records': [{'id': '3', 'status': 'uploaded_verified', 'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book1.pdf', 'drive_file': {'id': 'abc', 'size': '10'}, 'pdf_check': {'bytes': 11, 'pages': 2}}], 'summary': {'catalog_pages': 1}})
        self.assertTrue(any('missing_or_invalid_sha256' in x for x in result['issues']))
        self.assertTrue(any('file_size_mismatch' in x for x in result['issues']))

    def test_reject_url_tricks(self):
        for url in [
            'https://home.moe.gov.om.evil.test/images/manaheg/file/a.pdf',
            'https://home.moe.gov.om@evil.test/images/manaheg/file/a.pdf',
            'https://home.moe.gov.om:444/images/manaheg/file/a.pdf',
            'https://home.moe.gov.om/images/manaheg/file/a.pdf?redirect=1',
            'https://home.moe.gov.om/images/manaheg/file/a.pdf#fragment',
            'https://home.moe.gov.om/other/a.pdf',
            'https://home.moe.gov.om/images/manaheg/file/a.pdf;param',
            'https://home.moe.gov.om/images/manaheg/file/../private.pdf',
            'https://home.moe.gov.om/images/manaheg/file/%2e%2e%2fprivate.pdf',
            'https://home.moe.gov.om/images/manaheg/file/subdir/Book1.pdf',
            'https://home.moe.gov.om/images/manaheg/file/Book%2ePDF',
        ]:
            with self.subTest(url=url):
                result = audit({'records': [{'id': '1', 'status': 'pending', 'pdf': url}],
                                'summary': {'catalog_pages': 1}})
                self.assertTrue(any('untrusted_pdf_url' in x for x in result['issues']))

    def test_summary_reconciliation(self):
        record = {'id': '1', 'status': 'uploaded_verified',
                  'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book1.pdf',
                  'drive_file': {'id': 'file1', 'size': '12'},
                  'pdf_check': {'bytes': 12, 'pages': 1, 'sha256': 'a' * 64}}
        manifest = {'records': [record],
                    'summary': {'catalog_pages': 1, 'status_counts': {'uploaded_verified': 1},
                                'uploaded_verified': 1, 'bytes_uploaded': 12}}
        self.assertEqual(audit(manifest)['issues'], [])
        for field, bad_value, expected in [
            ('uploaded_verified', 2, 'uploaded_count_mismatch'),
            ('bytes_uploaded', 13, 'uploaded_bytes_mismatch'),
            ('status_counts', {'pending': 1}, 'status_counts_mismatch'),
        ]:
            with self.subTest(field=field):
                bad = {'records': [record], 'summary': dict(manifest['summary'], **{field: bad_value})}
                self.assertIn(expected, audit(bad)['issues'])

if __name__ == '__main__':
    unittest.main()
