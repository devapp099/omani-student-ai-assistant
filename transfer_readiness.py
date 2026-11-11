"""Read-only transfer queue report. Never downloads, opens, or publishes books."""
import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(ledger):
    records = ledger.get('records')
    if not isinstance(records, list):
        raise ValueError('records must be a list')
    ids = set()
    counts = Counter()
    missing_hash = []
    ready_for_review = []
    ambiguous_semester = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError('record must be an object')
        source_id = str(row.get('id', ''))
        if not source_id.isascii() or not source_id.isdecimal() or int(source_id) < 1 or source_id in ids:
            raise ValueError('invalid or duplicate source id')
        ids.add(source_id)
        status = row.get('status')
        if status not in {'pending', 'uploaded_verified', 'source_error', 'excluded_wrong_source'}:
            raise ValueError('invalid status')
        counts[status] += 1
        if status == 'uploaded_verified':
            digest = (row.get('pdf_check') or {}).get('sha256')
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                missing_hash.append(source_id)
        if status == 'pending' and isinstance(row.get('pdf'), str) and row['pdf'].startswith('https://home.moe.gov.om/images/manaheg/file/') and row['pdf'].endswith('.pdf'):
            crumbs = row.get('crumbs')
            semester = crumbs[-1] if isinstance(crumbs, list) and crumbs else None
            if semester not in {'الفصل الأول', 'الفصل الثاني'}:
                ambiguous_semester.append(source_id)
            else:
                ready_for_review.append(source_id)
    summary = ledger.get('summary', {})
    if summary.get('catalog_pages') != len(records) or summary.get('status_counts') != dict(counts):
        raise ValueError('ledger summary does not match records')
    return {'catalog_pages': len(records), 'status_counts': dict(counts), 'missing_uploaded_sha256': sorted(missing_hash, key=int), 'pending_with_verified_semester_label': len(ready_for_review), 'pending_with_ambiguous_semester': sorted(ambiguous_semester, key=int), 'next_source_ids_for_manual_verification': sorted(ready_for_review, key=int)[:10], 'note': 'Candidate URLs are not proof of PDF integrity, edition, rights, or upload eligibility.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.ledger.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
