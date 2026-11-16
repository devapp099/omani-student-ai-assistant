"""Read-only transfer preflight. Never downloads, copies or indexes textbook content."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

GRADE_NAMES = ('الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس',
               'السابع', 'الثامن', 'التاسع', 'العاشر', 'الحادي عشر', 'الثاني عشر')
PDF_PATH = re.compile(r'/images/manaheg/file/[A-Za-z0-9_-]+\.pdf')


def official_key(crumbs):
    if not isinstance(crumbs, list) or len(crumbs) < 3:
        return None
    grade, term = crumbs[0], crumbs[-1]
    if grade not in ['الصف ' + g for g in GRADE_NAMES]:
        return None
    if term not in ('الفصل الأول', 'الفصل الاول', 'الفصل الثاني'):
        return None
    return f'{GRADE_NAMES.index(grade[len("الصف "):]) + 1}:{2 if term == "الفصل الثاني" else 1}'


def safe_pdf(url):
    if not isinstance(url, str):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == 'https' and u.netloc == 'home.moe.gov.om'
                and not (u.query or u.fragment or u.username or u.password)
                and PDF_PATH.fullmatch(u.path) is not None)
    except ValueError:
        return False


def safe_source_page(url, source_id):
    if not isinstance(url, str):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == 'https' and u.netloc == 'home.moe.gov.om'
                and not (u.query or u.fragment or u.username or u.password)
                and re.fullmatch(r'/ar/manaheg/[1-9]\\d*/show/' + re.escape(str(source_id)), u.path) is not None)
    except ValueError:
        return False


def preflight(manifest):
    """Return metadata-only review candidates; never marks a book verified."""
    records = manifest['records']
    used_ids = set()
    used_urls = set()
    used_hashes = set()
    for r in records:
        sid = str(r.get('id', ''))
        if not re.fullmatch(r'[1-9]\d*', sid) or sid in used_ids:
            raise ValueError('Duplicate or invalid source ID')
        used_ids.add(sid)
        if r.get('status') == 'uploaded_verified':
            if r.get('pdf'):
                used_urls.add(r['pdf'])
            digest = (r.get('pdf_check') or {}).get('sha256')
            if digest:
                used_hashes.add(digest)
    candidates, blocked = [], Counter()
    seen_pending_urls = set()
    for r in records:
        if r.get('status') != 'pending':
            continue
        url = r.get('pdf')
        key = official_key(r.get('crumbs'))
        if not safe_source_page(r.get('page'), r['id']):
            blocked['invalid_official_source_page'] += 1
        elif not safe_pdf(url):
            blocked['invalid_official_pdf_url'] += 1
        elif url in used_urls or url in seen_pending_urls:
            blocked['duplicate_pdf_url'] += 1
        elif not key or key not in manifest.get('folder_map', {}):
            blocked['unverified_grade_or_semester'] += 1
        elif (r.get('pdf_check') or {}).get('sha256') in used_hashes and (r.get('pdf_check') or {}).get('sha256'):
            blocked['duplicate_sha256'] += 1
        else:
            candidates.append({'source_id': str(r['id']), 'page': r['page'],
                               'pdf': url, 'folder_key': key})
        if safe_pdf(url):
            seen_pending_urls.add(url)
    return {'candidates': candidates, 'blocked': dict(blocked),
            'pending_count': sum(r.get('status') == 'pending' for r in records)}


def main():
    parser = argparse.ArgumentParser(description='Read-only official curriculum transfer preflight')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    data = preflight(json.loads(args.manifest.read_text(encoding='utf-8')))
    print(json.dumps({**data, 'candidates': data['candidates'][:max(0, args.limit)]},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
