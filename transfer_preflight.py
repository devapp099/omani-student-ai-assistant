"""Read-only preflight for an official curriculum transfer ledger.

Never approves retrieval, downloads PDFs, or changes Drive. Emits actionable
source IDs requiring manual review before any upload or metadata update.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def preflight(ledger):
    records = ledger.get('records', [])
    seen_ids = set()
    drive_ids = defaultdict(list)
    hashes = defaultdict(list)
    issues = []
    for record in records:
        source_id = str(record.get('id', ''))
        if not source_id or source_id in seen_ids:
            issues.append({'source_id': source_id, 'reason': 'missing_or_duplicate_source_id'})
        seen_ids.add(source_id)
        if record.get('status') != 'uploaded_verified':
            continue
        drive = record.get('drive_file') or {}
        check = record.get('pdf_check') or {}
        drive_id = drive.get('id')
        if not drive_id:
            issues.append({'source_id': source_id, 'reason': 'missing_drive_id'})
        else:
            drive_ids[drive_id].append(source_id)
        size = check.get('bytes')
        pages = check.get('pages')
        try:
            valid_size = int(size) > 0 and int(size) == int(drive.get('size'))
        except (ValueError, TypeError):
            valid_size = False
        if not valid_size:
            issues.append({'source_id': source_id, 'reason': 'size_missing_or_mismatch'})
        if not isinstance(pages, int) or pages <= 0:
            issues.append({'source_id': source_id, 'reason': 'missing_page_count'})
        digest = check.get('sha256')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdefABCDEF' for c in digest):
            issues.append({'source_id': source_id, 'reason': 'missing_or_invalid_sha256'})
        else:
            hashes[digest.lower()].append(source_id)
    for sources in drive_ids.values():
        if len(sources) > 1:
            for source_id in sources:
                issues.append({'source_id': source_id, 'reason': 'duplicate_drive_id'})
    for sources in hashes.values():
        if len(sources) > 1:
            for source_id in sources:
                issues.append({'source_id': source_id, 'reason': 'duplicate_sha256'})
    return {'records': len(records), 'statuses': dict(Counter(r.get('status', 'missing') for r in records)),
            'issues': sorted(issues, key=lambda x: (x['reason'], x['source_id'])),
            'safe_to_auto_approve': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    args = parser.parse_args()
    print(json.dumps(preflight(json.loads(args.ledger.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
