"""Check declared grade/semester against the Drive folder key; metadata only."""
import argparse
import json
import re
from pathlib import Path

GRADES = {
    'الأول': 1, 'الثاني': 2, 'الثالث': 3, 'الرابع': 4,
    'الخامس': 5, 'السادس': 6, 'السابع': 7, 'الثامن': 8,
    'التاسع': 9, 'العاشر': 10, 'الحادي عشر': 11, 'الثاني عشر': 12,
}


def expected_folder(crumbs):
    if not isinstance(crumbs, list) or len(crumbs) < 3:
        return None
    grade_text = re.sub(r'\s+', ' ', str(crumbs[0]).strip())
    grade = GRADES.get(grade_text.removeprefix('الصف ')) if grade_text.startswith('الصف ') else None
    semester_text = re.sub(r'\s+', ' ', str(crumbs[2]).strip()).replace('أ', 'ا').replace('إ', 'ا')
    semester = {'الفصل الاول': 1, 'الفصل الثاني': 2}.get(semester_text)
    return f'{grade}:{semester}' if grade and semester else None


def check(data):
    errors = []
    for record in data.get('records', []):
        if record.get('status') != 'uploaded_verified':
            continue
        expected = expected_folder(record.get('crumbs'))
        actual = (record.get('drive_file') or {}).get('folder_key')
        if expected is None:
            errors.append(f"source {record.get('id')}: unrecognized grade/semester")
        elif actual != expected:
            errors.append(f"source {record.get('id')}: folder {actual!r} != {expected!r}")
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    args = parser.parse_args()
    errors = check(json.loads(args.ledger.read_text(encoding='utf-8')))
    print('\n'.join(errors) if errors else 'Grade/semester folder metadata OK')
    raise SystemExit(bool(errors))
