"""Reject spreadsheet formulas in manually entered curriculum metadata.

CSV cells may be interpreted as formulas when opened in spreadsheet software.
This module never opens books or fetches URLs.
"""

FORMULA_PREFIXES = ('=', '+', '-', '@')


def is_formula_like(value):
    """Detect formula prefixes even after leading whitespace or BOM."""
    if not isinstance(value, str):
        return False
    cleaned = value.lstrip('\ufeff \t\r\n')
    return bool(cleaned) and cleaned[0] in FORMULA_PREFIXES


def suspicious_cells(row):
    """Return unsafe fields without echoing potentially sensitive cell values."""
    return [field for field, value in row.items() if is_formula_like(value)]
