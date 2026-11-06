import unittest
from manifest_cell_safety import is_formula_like, suspicious_cells


class SpreadsheetSafetyTests(unittest.TestCase):
    def test_formula_prefixes(self):
        for prefix in ('=', '+', '-', '@'):
            with self.subTest(prefix=prefix):
                self.assertTrue(is_formula_like(prefix + 'SUM(1,2)'))

    def test_leading_whitespace_and_bom(self):
        self.assertTrue(is_formula_like('\ufeff \t=1+1'))

    def test_normal_arabic_text_and_https_url(self):
        self.assertFalse(is_formula_like('رياضيات'))
        self.assertFalse(is_formula_like('https://ict.moe.gov.om/book/'))

    def test_field_names_only(self):
        self.assertEqual(suspicious_cells({'title': '=1+1', 'subject': 'علوم'}), ['title'])

    def test_non_string_is_not_formula(self):
        self.assertFalse(is_formula_like(None))
