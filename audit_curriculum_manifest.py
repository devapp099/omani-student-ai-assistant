"""Read-only consistency audit for a curriculum transfer manifest."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

VALID = {'pending', 'uploaded_verified', 'source_error', 'excluded_wrong_source'}

def audit(manifest):
    errors, warnings = [], []
    records = manifest.get('records', [])
    counts = Counter(r.get('status') for r in records)
    ids = [str(r.get('id')) for r in records]
    if len(ids) != len(set(ids)):
        errors.append('duplicate source IDs')
    if set(counts) - VALID:
        errors.append('unknown status values')
    summary = manifest.get('summary', {})
    if summary.get('catalog_pages') != len(records):
        errors.append('catalog_pages mismatch')
    if summary.get('status_counts') != dict(counts):
        errors.append('status_counts mismatch')
    # A non-uploaded record must never claim a Drive file. Otherwise a retry
    # could treat an unverified or explicitly excluded source as transferred.
    for r in records:
        if r.get('status') != 'uploaded_verified' and r.get('drive_file'):
            errors.append(f"source {r.get('id')}: non-uploaded source has Drive file metadata")
    # Treat source links as untrusted input: reject off-domain or insecure links
    # before any future downloader can use the manifest for network requests.
    for r in records:
        for field in ('page', 'pdf'):
            url = r.get(field)
            if url is None and field == 'pdf':
                continue  # Some source pages do not provide a downloadable PDF.
            if not isinstance(url, str):
                errors.append(f"source {r.get('id')}: invalid {field} URL")
                continue
            try:
                parsed = urlsplit(url)
                # Restrict both the host and the exact official path shape.
                # A same-host URL to another endpoint is not a curriculum PDF.
                path = parsed.path
                valid_path = (re.fullmatch(r'/ar/manaheg/\d+/show/\d+', path)
                              if field == 'page' else
                              re.fullmatch(r'/images/manaheg/file/[A-Za-z0-9_.-]+\.pdf', path, re.I))
                if field == 'page' and valid_path and path.rsplit('/', 1)[-1] != str(r.get('id')):
                    errors.append(f"source {r.get('id')}: page URL source ID mismatch")
                if (parsed.scheme != 'https' or parsed.hostname != 'home.moe.gov.om'
                        or parsed.username is not None or parsed.password is not None
                        or parsed.port not in (None, 443) or parsed.query or parsed.fragment
                        or not valid_path):
                    errors.append(f"source {r.get('id')}: untrusted {field} URL")
            except ValueError:
                errors.append(f"source {r.get('id')}: malformed {field} URL")
    # The same official PDF URL across different source IDs must be reviewed
    # before transfer: titles or semester labels alone cannot prove uniqueness.
    pdf_sources = {}
    for r in records:
        pdf_url = r.get('pdf')
        if isinstance(pdf_url, str):
            if pdf_url in pdf_sources:
                errors.append(
                    f"source {r.get('id')}: duplicate PDF URL with source {pdf_sources[pdf_url]}"
                )
            else:
                pdf_sources[pdf_url] = r.get('id')
    uploaded = [r for r in records if r.get('status') == 'uploaded_verified']
    # A verified transfer must be an actual PDF on both ends. A valid-looking
    # filename or a non-empty Drive ID alone is not evidence of a PDF upload.
    for r in uploaded:
        f = r.get('drive_file') or {}
        pdf_url = r.get('pdf')
        if not isinstance(pdf_url, str) or not pdf_url.lower().endswith('.pdf'):
            errors.append(f"source {r.get('id')}: verified source lacks a PDF URL")
        if f.get('mime_type') != 'application/pdf':
            errors.append(f"source {r.get('id')}: verified Drive file is not PDF MIME type")
        if not isinstance(f.get('title'), str) or not f['title'].lower().endswith('.pdf'):
            errors.append(f"source {r.get('id')}: verified Drive filename lacks .pdf extension")
    file_ids = [r.get('drive_file', {}).get('id') for r in uploaded]
    if any(not x for x in file_ids) or len(file_ids) != len(set(file_ids)):
        errors.append('missing or duplicate Drive file IDs')
    # A filename collision in the same Drive folder can silently overwrite or
    # confuse retrieval even when Drive IDs differ. Compare case-insensitively.
    seen_names = {}
    for r in uploaded:
        f = r.get('drive_file') or {}
        name = f.get('title')
        parent = f.get('parent_id')
        if not isinstance(name, str) or not name.strip():
            errors.append(f"source {r.get('id')}: missing Drive filename")
            continue
        if not parent:
            continue  # Existing folder mapping validation handles this.
        key = (parent, name.casefold())
        if key in seen_names:
            errors.append(f"source {r.get('id')}: duplicate Drive filename with source {seen_names[key]}")
        else:
            seen_names[key] = r.get('id')
    # Verify destination grade and semester against the source breadcrumbs.
    # Normalize Arabic hamza variants in semester labels (الاول / الأول).
    grade_words = ('الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس',
                   'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر',
                   'الحادي عشر', 'الثاني عشر')
    for r in uploaded:
        crumbs = r.get('crumbs') or []
        grade_label = crumbs[0] if len(crumbs) > 0 else ''
        semester_label = crumbs[2] if len(crumbs) > 2 else ''
        grade = next((i for i, word in enumerate(grade_words, 1)
                      if grade_label == 'الصف ' + word), None)
        normalized = semester_label.replace('أ', 'ا').replace('إ', 'ا')
        semester = (1 if normalized == 'الفصل الاول' else
                    2 if normalized == 'الفصل الثاني' else None)
        expected = f'{grade}:{semester}' if grade and semester else None
        if not expected or (r.get('drive_file') or {}).get('folder_key') != expected:
            errors.append(f"source {r.get('id')}: destination grade/semester differs from source breadcrumbs")
    total = 0
    seen_digests = {}
    for r in uploaded:
        f = r.get('drive_file', {})
        try:
            size = int(f['size'])
            check = r.get('pdf_check')
            if not check:
                warnings.append(f"source {r['id']}: PDF check metadata missing")
            else:
                digest = check.get('sha256')
                if digest is None:
                    warnings.append(f"source {r['id']}: SHA256 missing; duplicate-content check unavailable")
                elif not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                    errors.append(f"source {r['id']}: invalid SHA256 digest")
                if isinstance(digest, str) and re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                    normalized = digest.lower()
                    if normalized in seen_digests:
                        errors.append(f"source {r['id']}: duplicate PDF content with source {seen_digests[normalized]}")
                    else:
                        seen_digests[normalized] = r['id']
                if size <= 0 or size != int(check['bytes']):
                    errors.append(f"source {r['id']}: inconsistent PDF byte count")
                if int(check['pages']) <= 0:
                    errors.append(f"source {r['id']}: invalid page count")
            if f.get('parent_id') != manifest.get('folder_map', {}).get(f.get('folder_key')):
                errors.append(f"source {r['id']}: folder mapping mismatch")
            # A tiny PDF may be a placeholder or an incomplete download. Flag it
            # for manual review without falsely declaring the file corrupt.
            if 0 < size < 100_000:
                warnings.append(f"source {r['id']}: unusually small PDF ({size} bytes); verify completeness")
            total += size
        except (KeyError, ValueError, TypeError):
            errors.append(f"source {r['id']}: incomplete PDF metadata")
    if summary.get('uploaded_verified') != len(uploaded) or summary.get('bytes_uploaded') != total:
        errors.append('uploaded summary mismatch')
    return {'records': len(records), 'uploaded': len(uploaded), 'pending': counts['pending'],
            'bytes_uploaded': total, 'warnings': warnings, 'errors': errors}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.manifest.read_text(encoding='utf-8')))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result['errors'] else 0)

if __name__ == '__main__':
    main()
