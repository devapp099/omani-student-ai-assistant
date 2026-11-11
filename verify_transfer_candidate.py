"""Offline fail-closed PDF candidate gate; does not upload or approve covers.

Usage: python verify_transfer_candidate.py STATUS.json SOURCE_ID BOOK.pdf
Requires: pip install pypdf
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

GRADES = ('الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس',
          'السابع', 'الثامن', 'التاسع', 'العاشر', 'الحادي عشر', 'الثاني عشر')
SEMESTERS = {'الفصل الأول': 1, 'الفصل الثاني': 2}


def preflight(manifest, source_id, filename):
    records = [r for r in manifest['records'] if str(r.get('id')) == str(source_id)]
    if len(records) != 1:
        raise ValueError('Source ID is missing or duplicated')
    record = records[0]
    if record.get('status') != 'pending':
        raise ValueError('Source is not pending')
    crumbs = record.get('crumbs') or []
    grades = [i for i, name in enumerate(GRADES, 1) if 'الصف ' + name in crumbs]
    semesters = [SEMESTERS[s] for s in crumbs if s in SEMESTERS]
    if len(grades) != 1 or len(semesters) != 1:
        raise ValueError('Ambiguous grade or semester; inspect official source')
    key = f'{grades[0]}:{semesters[0]}'
    folder = manifest.get('folder_map', {}).get(key)
    if not folder:
        raise ValueError('Destination folder is not registered')
    url = urlsplit(record.get('pdf') or '')
    if (url.scheme != 'https' or url.hostname != 'home.moe.gov.om'
            or not url.path.startswith('/images/manaheg/file/')
            or not url.path.lower().endswith('.pdf')
            or url.username or url.password or url.query or url.fragment):
        raise ValueError('Missing or untrusted ministry PDF URL')
    path = Path(filename)
    if not path.is_file() or path.stat().st_size < 100:
        raise ValueError('Missing or implausibly small PDF')
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise ValueError('Invalid PDF header')
        stream.seek(0)
        for block in iter(lambda: stream.read(1048576), b''):
            sha.update(block)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('Install pypdf for structural validation') from exc
    reader = PdfReader(str(path), strict=True)
    pages = len(reader.pages)
    if pages < 1:
        raise ValueError('PDF has no pages')
    for page in reader.pages:
        _ = page.mediabox
    digest = sha.hexdigest()
    for other in manifest['records']:
        if str(other.get('id')) != str(source_id):
            existing = (other.get('pdf_check') or {}).get('sha256')
            if existing and existing.lower() == digest:
                raise ValueError(f'Duplicate SHA256: source {other.get("id")}')
    return {'source_id': str(source_id), 'grade': grades[0],
            'semester': semesters[0], 'folder_id': folder,
            'bytes': path.stat().st_size, 'pages': pages,
            'sha256': digest, 'requires_manual_cover_review': True,
            'approved_for_upload': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('source_id')
    parser.add_argument('pdf')
    args = parser.parse_args()
    try:
        result = preflight(json.loads(Path(args.manifest).read_text(encoding='utf-8')),
                           args.source_id, args.pdf)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.exit(2, f'BLOCKED: {exc}\n')


if __name__ == '__main__':
    main()
