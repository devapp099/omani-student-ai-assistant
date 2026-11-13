"""Regression tests: official catalog counts must not become invented book records."""
import unittest
from audit_catalog_drift import compare, source_id


class CatalogDriftSafetyTests(unittest.TestCase):
    def test_verified_source_url(self):
        self.assertEqual(source_id('https://home.moe.gov.om/ar/manaheg/53/show/58'), '58')

    def test_untrusted_or_modified_urls_rejected(self):
        for value in (
            'http://home.moe.gov.om/ar/manaheg/53/show/58',
            'https://home.moe.gov.om.evil.test/ar/manaheg/53/show/58',
            'https://home.moe.gov.om/ar/manaheg/53/show/58?download=1',
            'https://home.moe.gov.om/ar/manaheg/53/show/58#section',
            'https://user@home.moe.gov.om/ar/manaheg/53/show/58',
            'https://home.moe.gov.om/ar/manaheg/53/show/58/extra',
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_id(value)

    def test_invalid_ids_rejected(self):
        for value in (True, 0, -1, '0', '58.0', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_id(value)

    def test_mismatched_manifest_page_rejected(self):
        manifest = {'records': [{'id': '58', 'page': 'https://home.moe.gov.om/ar/manaheg/53/show/59'}]}
        with self.assertRaises(ValueError):
            compare(manifest, ['58'])

    def test_duplicate_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            compare({'records': []}, ['58', '58'])

    def test_count_is_not_source_list(self):
        with self.assertRaises((ValueError, TypeError)):
            compare({'records': []}, 354)

    def test_drift_does_not_assert_pdf_availability(self):
        manifest = {'records': [{'id': '58', 'page': 'https://home.moe.gov.om/ar/manaheg/53/show/58'}]}
        result = compare(manifest, ['59'])
        self.assertEqual(result['new_source_ids'], ['59'])
        self.assertEqual(result['missing_from_official_snapshot'], ['58'])
        self.assertIn('do not establish PDF availability', result['warning'])


if __name__ == '__main__':
    unittest.main()
