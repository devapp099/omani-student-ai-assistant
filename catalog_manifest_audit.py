"""Read-only metadata audit for curriculum transfer; never approves retrieval."""
import collections
import json
import sys
import re
from urllib.parse import urlparse

ALLOWED = {'pending', 'uploaded_verified', 'source_error', 'excluded_wrong_source'}

def trusted_pdf_url(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        prefix = '/images/manaheg/file/'
        basename = parsed.path.removeprefix(prefix)
        return (parsed.scheme == 'https' and parsed.netloc == 'home.moe.gov.om'
                and parsed.path.startswith(prefix)
                and bool(basename) and '/' not in basename and '\\' not in basename
                and '%' not in parsed.path and basename.lower().endswith('.pdf')
                and not parsed.params and not parsed.query and not parsed.fragment)
    except ValueError:
        return False

def audit(manifest):
    records = manifest['records']
    counts = collections.Counter(r.get('status') for r in records)
    problems = []
    ids, pdf_urls, drive_ids, verified_hashes = set(), {}, set(), {}
    for r in records:
        rid = str(r.get('id', ''))
        if not rid or rid in ids:
            problems.append(f'duplicate_or_missing_source_id:{rid}')
        ids.add(rid)
        page = r.get('page')
        if page is not None:
            expected_page = rf'https://home\.moe\.gov\.om/ar/manaheg/[0-9]+/show/{re.escape(rid)}'
            if not isinstance(page, str) or not re.fullmatch(expected_page, page):
                problems.append(f'source_page_id_or_host_mismatch:{rid}')
        status = r.get('status')
        if status not in ALLOWED:
            problems.append(f'unknown_status:{rid}')
        pdf = r.get('pdf')
        if status in {'pending', 'uploaded_verified'} and not pdf:
            problems.append(f'missing_pdf_url:{rid}')
        if pdf:
            if not trusted_pdf_url(pdf):
                problems.append(f'untrusted_pdf_url:{rid}')
            if pdf in pdf_urls:
                problems.append(f'duplicate_pdf_url:{pdf_urls[pdf]}:{rid}')
            pdf_urls[pdf] = rid
        if status == 'uploaded_verified':
            drive = r.get('drive_file') or {}
            folder_key = drive.get('folder_key')
            parent_id = drive.get('parent_id')
            expected_parent = (manifest.get('folder_map') or {}).get(folder_key)
            if folder_key is not None and (not expected_parent or parent_id != expected_parent):
                problems.append(f'verified_folder_mismatch:{rid}')
            fid = drive.get('id')
            if not fid or fid in drive_ids:
                problems.append(f'duplicate_or_missing_drive_id:{rid}')
            if fid:
                drive_ids.add(fid)
            check = r.get('pdf_check') or {}
            if not isinstance(check.get('pages'), int) or check['pages'] <= 0:
                problems.append(f'missing_page_count:{rid}')
            sha = check.get('sha256')
            if isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdefABCDEF' for c in sha):
                normalized = sha.lower()
                if normalized in verified_hashes:
                    problems.append(f'duplicate_verified_pdf_hash:{verified_hashes[normalized]}:{rid}')
                else:
                    verified_hashes[normalized] = rid
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdefABCDEF' for c in sha):
                problems.append(f'missing_or_invalid_sha256:{rid}')
            try:
                if int(drive.get('size')) != int(check.get('bytes')):
                    problems.append(f'file_size_mismatch:{rid}')
            except (ValueError, TypeError):
                problems.append(f'missing_file_size:{rid}')
    summary = manifest.get('summary', {})
    if summary.get('status_counts') is not None:
        if not isinstance(summary['status_counts'], dict) or summary['status_counts'] != dict(counts):
            problems.append('status_counts_mismatch')
    if summary.get('uploaded_verified') is not None:
        if summary['uploaded_verified'] != counts.get('uploaded_verified', 0):
            problems.append('uploaded_count_mismatch')
    if summary.get('bytes_uploaded') is not None:
        try:
            total = sum(int((r.get('drive_file') or {}).get('size'))
                        for r in records if r.get('status') == 'uploaded_verified')
            if total != summary['bytes_uploaded']:
                problems.append('uploaded_bytes_mismatch')
        except (TypeError, ValueError):
            problems.append('uploaded_bytes_unverifiable')
    if len(records) != manifest.get('summary', {}).get('catalog_pages'):
        problems.append('catalog_count_mismatch')
    return {'records': len(records), 'statuses': dict(counts), 'issues': sorted(problems), 'retrieval_approved': False}

if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        print(json.dumps(audit(json.load(f)), ensure_ascii=False, indent=2))
