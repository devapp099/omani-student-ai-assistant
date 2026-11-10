"""Read-only metadata audit for curriculum transfer; never approves retrieval."""
import collections
import json
import sys
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
    ids, pdf_urls, drive_ids = set(), {}, set()
    for r in records:
        rid = str(r.get('id', ''))
        if not rid or rid in ids:
            problems.append(f'duplicate_or_missing_source_id:{rid}')
        ids.add(rid)
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
            fid = drive.get('id')
            if not fid or fid in drive_ids:
                problems.append(f'duplicate_or_missing_drive_id:{rid}')
            if fid:
                drive_ids.add(fid)
            check = r.get('pdf_check') or {}
            if not isinstance(check.get('pages'), int) or check['pages'] <= 0:
                problems.append(f'missing_page_count:{rid}')
            sha = check.get('sha256')
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdefABCDEF' for c in sha):
                problems.append(f'missing_or_invalid_sha256:{rid}')
            try:
                if int(drive.get('size')) != int(check.get('bytes')):
                    problems.append(f'file_size_mismatch:{rid}')
            except (ValueError, TypeError):
                problems.append(f'missing_file_size:{rid}')
    if len(records) != manifest.get('summary', {}).get('catalog_pages'):
        problems.append('catalog_count_mismatch')
    return {'records': len(records), 'statuses': dict(counts), 'issues': sorted(problems), 'retrieval_approved': False}

if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        print(json.dumps(audit(json.load(f)), ensure_ascii=False, indent=2))
