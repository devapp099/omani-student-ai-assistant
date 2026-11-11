"""Regression tests for the read-only Drive transfer manifest audit."""
import copy
import unittest
from audit_curriculum_manifest import audit


class ManifestAuditTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            'folder_map': {'6:1': 'folder-six-one'},
            'records': [
                {'id': '92', 'status': 'uploaded_verified',
                 'drive_file': {'id': 'drive-92', 'size': '120',
                                'folder_key': '6:1', 'parent_id': 'folder-six-one'},
                 'pdf_check': {'bytes': 120, 'pages': 3}},
                {'id': '93', 'status': 'pending'},
            ],
            'summary': {'catalog_pages': 2, 'uploaded_verified': 1,
                        'bytes_uploaded': 120,
                        'status_counts': {'uploaded_verified': 1, 'pending': 1}},
        }

    def test_valid_manifest(self):
        result = audit(self.manifest)
        self.assertEqual(result['errors'], [])
        self.assertTrue(any('SHA256 missing' in w for w in result['warnings']))
        self.assertEqual((result['uploaded'], result['pending']), (1, 1))

    def test_valid_sha256_has_no_hash_warning(self):
        data = copy.deepcopy(self.manifest)
        data['records'][0]['pdf_check']['sha256'] = 'a' * 64
        self.assertEqual(audit(data)['warnings'], [])

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
            'id': '93', 'status': 'uploaded_verified',
            'drive_file': {'id': 'drive-93', 'size': '120',
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
