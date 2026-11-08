"""Compare Drive folder metadata exports against a curriculum transfer ledger.

No PDF content is read. Unregistered PDFs are quarantined from indexing until
source, cover, grade, semester, completeness and fingerprint are verified.
"""
import argparse
import json
from pathlib import Path


def audit(ledger, inventory, min_review_bytes=100_000):
    registered = {}
    for record in ledger.get('records', []):
        if record.get('status') == 'uploaded_verified':
            drive = record.get('drive_file') or {}
            if drive.get('id'):
                registered[drive['id']] = record
    errors, review, matched = [], [], []
    seen = set()
    for item in inventory:
        file_id = item.get('id')
        if not isinstance(file_id, str) or not file_id:
            errors.append('inventory item missing Drive ID')
            continue
        if file_id in seen:
            errors.append(f'duplicate inventory ID {file_id}')
            continue
        seen.add(file_id)
        name = item.get('name', item.get('title', ''))
        if item.get('mime_type', item.get('mimeType')) != 'application/pdf':
            continue
        try:
            size = int(item.get('size', ''))
            if size < 1 or str(size) != str(item.get('size')):
                raise ValueError()
        except (ValueError, TypeError):
            errors.append(f'{file_id}: invalid PDF size')
            continue
        if file_id in registered:
            expected = (registered[file_id].get('drive_file') or {}).get('size')
            if expected is not None and str(expected) != str(size):
                errors.append(f'{file_id}: ledger/Drive size mismatch')
            matched.append(file_id)
        else:
            review.append({'id': file_id, 'name': name, 'size': size,
                           'reason': 'unregistered; verify source and PDF before indexing' +
                           ('; suspiciously small PDF' if size < min_review_bytes else '')})
    return errors, review, matched


def self_test():
    ledger = {'records': [{'status': 'uploaded_verified', 'drive_file': {'id': 'A', 'size': 200000}}]}
    pdf = lambda i, s: {'id': i, 'name': i+'.pdf', 'mime_type': 'application/pdf', 'size': str(s)}
    assert audit(ledger, [pdf('A', 200000)]) == ([], [], ['A'])
    assert len(audit(ledger, [pdf('B', 15106)])[1]) == 1
    assert 'suspiciously small' in audit(ledger, [pdf('B', 15106)])[1][0]['reason']
    assert len(audit(ledger, [pdf('A', 12)])[0]) == 1
    assert len(audit(ledger, [pdf('A', 200000), pdf('A', 200000)])[0]) == 1
    assert len(audit(ledger, [pdf('B', 0)])[0]) == 1
    assert audit(ledger, [{'id': 'X', 'mime_type': 'text/plain', 'size': '12'}]) == ([], [], [])
    print('6 inventory audit tests passed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('ledger', nargs='?', type=Path)
    p.add_argument('inventory', nargs='?', type=Path,
                   help='JSON array of Drive file metadata from folder listings')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        if not args.ledger or not args.inventory:
            p.error('ledger and inventory required')
        errors, review, matched = audit(json.loads(args.ledger.read_text()),
                                        json.loads(args.inventory.read_text()))
        print(json.dumps({'errors': errors, 'requires_review': review,
                          'matched_registered_count': len(matched)}, ensure_ascii=False, indent=2))
        raise SystemExit(bool(errors))
