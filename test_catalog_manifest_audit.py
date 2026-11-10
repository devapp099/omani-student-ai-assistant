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


    def test_duplicate_verified_pdf_hash_is_flagged(self):
        url = 'https://home.moe.gov.om/images/manaheg/file/'
        records = [
            {'id': str(i), 'status': 'uploaded_verified', 'pdf': url + f'Book{i}.pdf',
             'drive_file': {'id': f'file{i}', 'size': '12'},
             'pdf_check': {'bytes': 12, 'pages': 1, 'sha256': 'A' * 64 if i == 1 else 'a' * 64}}
            for i in (1, 2)
        ]
        manifest = {'records': records, 'summary': {'catalog_pages': 2}}
        self.assertIn('duplicate_verified_pdf_hash:1:2', audit(manifest)['issues'])
        records[1]['pdf_check']['sha256'] = 'b' * 64
        self.assertNotIn('duplicate_verified_pdf_hash:1:2', audit(manifest)['issues'])


    def test_source_page_must_match_record_id_and_official_host(self):
        base = {'id': '58', 'status': 'pending',
                'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book58.pdf'}
        for page in ('https://home.moe.gov.om/ar/manaheg/53/show/59',
                     'https://evil.example/ar/manaheg/53/show/58',
                     'https://home.moe.gov.om/ar/manaheg/53/show/58?x=1'):
            with self.subTest(page=page):
                result = audit({'records': [dict(base, page=page)],
                                'summary': {'catalog_pages': 1}})
                self.assertIn('source_page_id_or_host_mismatch:58', result['issues'])
        good = audit({'records': [dict(base, page='https://home.moe.gov.om/ar/manaheg/53/show/58')],
                      'summary': {'catalog_pages': 1}})
        self.assertNotIn('source_page_id_or_host_mismatch:58', good['issues'])

    def test_verified_drive_parent_must_match_folder_map(self):
        record = {'id': '92', 'status': 'uploaded_verified',
                  'pdf': 'https://home.moe.gov.om/images/manaheg/file/Book92.pdf',
                  'drive_file': {'id': 'file92', 'size': '12', 'folder_key': '6:1',
                                 'parent_id': 'wrong'},
                  'pdf_check': {'bytes': 12, 'pages': 1, 'sha256': 'a' * 64}}
        manifest = {'records': [record], 'folder_map': {'6:1': 'correct'},
                    'summary': {'catalog_pages': 1}}
        self.assertIn('verified_folder_mismatch:92', audit(manifest)['issues'])
        record['drive_file']['parent_id'] = 'correct'
        self.assertNotIn('verified_folder_mismatch:92', audit(manifest)['issues'])

if __name__ == '__main__':
    unittest.main()
