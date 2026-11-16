import unittest
from curriculum_batch_preflight import preflight, safe_pdf


class PreflightTests(unittest.TestCase):
    def sample(self):
        return {'folder_map': {'6:1': 'private-folder'}, 'records': [
            {'id': '1', 'status': 'uploaded_verified',
             'pdf': 'https://home.moe.gov.om/images/manaheg/file/A.pdf'},
            {'id': '2', 'status': 'pending', 'page': 'https://home.moe.gov.om/ar/manaheg/1/show/2',
             'pdf': 'https://home.moe.gov.om/images/manaheg/file/B.pdf',
             'crumbs': ['الصف السادس', 'العلوم', 'الفصل الأول']}]}

    def test_safe_url(self):
        self.assertTrue(safe_pdf('https://home.moe.gov.om/images/manaheg/file/B.pdf'))
        for url in ('https://evil.test/images/manaheg/file/B.pdf',
                    'https://home.moe.gov.om/images/manaheg/file/B.pdf?x=1',
                    'https://home.moe.gov.om/images/manaheg/file/%2e%2e/B.pdf'):
            self.assertFalse(safe_pdf(url))

    def test_candidate_is_only_metadata(self):
        d = preflight(self.sample())
        self.assertEqual(d['pending_count'], 1)
        self.assertEqual(d['candidates'][0]['folder_key'], '6:1')
        self.assertNotIn('text', d['candidates'][0])

    def test_duplicate_uploaded_url_blocked(self):
        d = self.sample()
        d['records'][1]['pdf'] = d['records'][0]['pdf']
        self.assertEqual(preflight(d)['blocked']['duplicate_pdf_url'], 1)

    def test_missing_classification_blocked(self):
        d = self.sample()
        d['records'][1]['crumbs'] = ['الصف السادس', 'العلوم', 'غير محدد']
        self.assertEqual(preflight(d)['blocked']['unverified_grade_or_semester'], 1)

    def test_duplicate_pending_url_blocked(self):
        d = self.sample()
        r = dict(d['records'][1]); r['id'] = '3'; d['records'].append(r)
        self.assertEqual(preflight(d)['blocked']['duplicate_pdf_url'], 1)

    def test_duplicate_source_id_rejected(self):
        d = self.sample(); d['records'][1]['id'] = '1'
        with self.assertRaises(ValueError): preflight(d)


if __name__ == '__main__':
    unittest.main()
