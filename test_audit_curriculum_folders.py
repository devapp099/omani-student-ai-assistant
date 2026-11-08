import unittest
from audit_curriculum_folders import check, expected_folder

class FolderAuditTests(unittest.TestCase):
    def test_arabic_hamza_variants(self):
        for spelling in ('الفصل الأول', 'الفصل الاول'):
            self.assertEqual(expected_folder(['الصف السابع', 'العلوم', spelling]), '7:1')

    def test_reject_mismatch(self):
        data = {'records': [{'id': '9', 'status': 'uploaded_verified', 'crumbs': ['الصف السادس', 'العلوم', 'الفصل الثاني'], 'drive_file': {'folder_key': '6:1'}}]}
        self.assertEqual(len(check(data)), 1)

    def test_unknown_semester_fails_closed(self):
        data = {'records': [{'id': '9', 'status': 'uploaded_verified', 'crumbs': ['الصف السادس', 'العلوم', 'غير محدد'], 'drive_file': {'folder_key': '6:1'}}]}
        self.assertEqual(len(check(data)), 1)

    def test_skip_pending(self):
        self.assertEqual(check({'records': [{'status': 'pending'}]}), [])

if __name__ == '__main__':
    unittest.main()
