"""Regression tests for the read-only Drive transfer manifest audit."""
import copy
import unittest
from audit_curriculum_manifest import audit


class ManifestAuditTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            'folder_map': {'6:1': 'folder-six-one'},
            'records': [
                {'id': '92', 'page': 'https://home.moe.gov.om/ar/manaheg/103/show/92', 'status': 'uploaded_verified',
                 'crumbs': ['الصف السادس', 'العلوم', 'الفصل الأول'],
                 'pdf': 'https://home.moe.gov.om/images/manaheg/file/science-92.pdf',
                 'drive_file': {'id': 'drive-92', 'title': 'science-92.pdf', 'size': '120', 'mime_type': 'application/pdf',
                                'folder_key': '6:1', 'parent_id': 'folder-six-one'},
                 'pdf_check': {'bytes': 120, 'pages': 3}},
                {'id': '93', 'page': 'https://home.moe.gov.om/ar/manaheg/104/show/93', 'status': 'pending'},
            ],
            'summary': {'catalog_pages': 2, 'uploaded_verified': 1,
                        'bytes_uploaded': 120,
                        'status_counts': {'uploaded_verified': 1, 'pending': 1}},
        }

    def test_verified_missing_pdf_source_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        del data['records'][0]['pdf']
        self.assertTrue(any('verified source lacks a PDF URL' in e for e in audit(data)['errors']))

    def test_verified_non_pdf_mime_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['drive_file']['mime_type'] = 'text/html'
        self.assertTrue(any('not PDF MIME type' in e for e in audit(data)['errors']))

    def test_verified_non_pdf_filename_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['drive_file']['title'] = 'science-92.html'
        self.assertTrue(any('lacks .pdf extension' in e for e in audit(data)['errors']))

    def test_valid_manifest(self):
        result = audit(self.manifest)
        self.assertEqual(result['errors'], [])
        self.assertTrue(any('SHA256 missing' in w for w in result['warnings']))
        self.assertEqual((result['uploaded'], result['pending']), (1, 1))

    def test_valid_sha256_has_no_hash_warning(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['sha256'] = 'a' * 64
        self.assertFalse(any('SHA256 missing' in w for w in audit(data)['warnings']))

    def test_invalid_sha256_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['sha256'] = 'not-a-digest'
        self.assertTrue(any('invalid SHA256' in e for e in audit(data)['errors']))

    def test_non_string_sha256_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['sha256'] = 123
        self.assertTrue(any('invalid SHA256' in e for e in audit(data)['errors']))

    def test_duplicate_verified_pdf_digest_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['sha256'] = 'A' * 64
        data['records'][1] = {
            'id': '93', 'page': 'https://home.moe.gov.om/ar/manaheg/104/show/93', 'status': 'uploaded_verified',
            'drive_file': {'id': 'drive-93', 'title': 'science-93.pdf', 'size': '120',
                           'folder_key': '6:1', 'parent_id': 'folder-six-one'},
            'pdf_check': {'bytes': 120, 'pages': 3, 'sha256': 'a' * 64},
        }
        data['summary']['uploaded_verified'] = 2
        data['summary']['bytes_uploaded'] = 240
        data['summary']['status_counts'] = {'uploaded_verified': 2}
        result = audit(data)
        self.assertTrue(any('duplicate PDF content' in e for e in result['errors']))

    def test_pending_source_with_drive_file_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['drive_file'] = {'id': 'unverified-file'}
        self.assertTrue(any('non-uploaded source has Drive file metadata' in e
                            for e in audit(data)['errors']))

    def test_excluded_source_with_drive_file_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['status'] = 'excluded_wrong_source'
        data['records'][1]['drive_file'] = {'id': 'wrong-book'}
        data['summary']['status_counts'] = {
            'uploaded_verified': 1, 'excluded_wrong_source': 1}
        self.assertTrue(any('non-uploaded source has Drive file metadata' in e
                            for e in audit(data)['errors']))

    def test_off_domain_pdf_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf'] = 'https://attacker.example/book.pdf'
        self.assertTrue(any('untrusted pdf URL' in e for e in audit(data)['errors']))

    def test_insecure_page_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['page'] = 'http://home.moe.gov.om/ar/manaheg/104/show/93'
        self.assertTrue(any('untrusted page URL' in e for e in audit(data)['errors']))

    def test_missing_page_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        del data['records'][1]['page']
        self.assertTrue(any('invalid page URL' in e for e in audit(data)['errors']))

    def test_valid_official_pdf_is_accepted(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf'] = 'https://home.moe.gov.om/images/manaheg/file/book.pdf'
        self.assertEqual(audit(data)['errors'], [])

    def test_same_host_unrelated_pdf_path_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf'] = 'https://home.moe.gov.om/admin/export.pdf'
        self.assertTrue(any('untrusted pdf URL' in e for e in audit(data)['errors']))

    def test_query_string_on_pdf_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf'] = 'https://home.moe.gov.om/images/manaheg/file/book.pdf?next=external'
        self.assertTrue(any('untrusted pdf URL' in e for e in audit(data)['errors']))

    def test_page_path_must_match_official_route(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['page'] = 'https://home.moe.gov.om/ar/manaheg/104/other/93'
        self.assertTrue(any('untrusted page URL' in e for e in audit(data)['errors']))

    def test_page_source_id_mismatch_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['page'] = 'https://home.moe.gov.om/ar/manaheg/104/show/999'
        self.assertTrue(any('page URL source ID mismatch' in e for e in audit(data)['errors']))

    def test_duplicate_pdf_url_across_sources_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        shared_url = 'https://home.moe.gov.om/images/manaheg/file/shared.pdf'
        data['records'][0]['pdf'] = shared_url
        data['records'][1]['pdf'] = shared_url
        self.assertTrue(any('duplicate PDF URL' in e for e in audit(data)['errors']))

    def test_distinct_pdf_urls_are_accepted(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf'] = 'https://home.moe.gov.om/images/manaheg/file/a.pdf'
        data['records'][1]['pdf'] = 'https://home.moe.gov.om/images/manaheg/file/b.pdf'
        self.assertEqual(audit(data)['errors'], [])

    def test_duplicate_drive_filename_in_same_folder_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['drive_file']['title'] = 'Science.PDF'
        data['records'][1] = {
            'id': '93', 'page': 'https://home.moe.gov.om/ar/manaheg/104/show/93',
            'status': 'uploaded_verified',
            'drive_file': {'id': 'drive-93', 'title': 'science.pdf',
                           'size': '100', 'folder_key': '6:1',
                           'parent_id': 'folder-six-one'},
            'pdf_check': {'bytes': 100, 'pages': 2},
        }
        data['summary']['uploaded_verified'] = 2
        data['summary']['bytes_uploaded'] = 220
        data['summary']['status_counts'] = {'uploaded_verified': 2}
        self.assertTrue(any('duplicate Drive filename' in e for e in audit(data)['errors']))

    def test_missing_drive_filename_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        del data['records'][0]['drive_file']['title']
        self.assertTrue(any('missing Drive filename' in e for e in audit(data)['errors']))

    def test_duplicate_source_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][1]['id'] = '92'
        self.assertIn('duplicate source IDs', audit(data)['errors'])

    def test_missing_pdf_check_warns_without_claiming_verification(self):
        data = copy.deepcopy(self.manifest)
        del data['records'][0]['pdf_check']
        result = audit(data)
        self.assertEqual(result['errors'], [])
        self.assertTrue(any('PDF check metadata missing' in x for x in result['warnings']))

    def test_inconsistent_bytes_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['bytes'] = 119
        self.assertTrue(any('inconsistent PDF byte count' in x for x in audit(data)['errors']))

    def test_wrong_folder_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['drive_file']['parent_id'] = 'other-folder'
        self.assertTrue(any('folder mapping mismatch' in x for x in audit(data)['errors']))

    def test_invalid_page_count_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['pages'] = 0
        self.assertTrue(any('invalid page count' in x for x in audit(data)['errors']))

    def test_summary_mismatch_is_rejected(self):
        data = copy.deepcopy(self.manifest)
        data['summary']['bytes_uploaded'] += 1
        self.assertIn('uploaded summary mismatch', audit(data)['errors'])


if __name__ == '__main__':
    unittest.main()
