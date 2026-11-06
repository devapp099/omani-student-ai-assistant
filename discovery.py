"""Book metadata only; never fetch or copy textbook contents."""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REQUIRED = ('discovery_id','grade','subject','title','semester','source_url','verification_status','rights_status')
ALLOWED_STATUS = {'source_page_observed','needs_manual_review','rejected'}

def check_catalog(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as file:
        reader = csv.DictReader(file)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
        rows = list(reader)
    ids = set()
    for line,row in enumerate(rows,2):
        def fail(message):
            raise ValueError(f'Line {line}: {message}')
        key = row['discovery_id'].strip()
        if not key or key in ids: fail('duplicate or missing discovery ID')
        ids.add(key)
        try: grade = int(row['grade'])
        except (ValueError,TypeError): fail('invalid grade')
        if not 1 <= grade <= 12: fail('invalid grade')
        if row['semester'] not in ('1','2'): fail('invalid semester')
        if not row['subject'].strip() or not row['title'].strip(): fail('missing subject/title')
        u = urlsplit(row['source_url'])
        if u.scheme != 'https' or u.hostname != 'ict.moe.gov.om' or not u.path.startswith('/book/'):
            fail('untrusted book source URL')
        if row['verification_status'] not in ALLOWED_STATUS: fail('invalid verification status')
        if row['rights_status'] != 'unknown': fail('rights require a separate written authorization workflow')
    return rows

def register_metadata(db_path,catalog_path):
    """Idempotent metadata import, always leaving rights and review pending."""
    from curriculum import init,connect
    rows = check_catalog(catalog_path)
    init(db_path)
    inserted=0
    with connect(db_path) as db:
        for row in rows:
            if row['verification_status']=='rejected': continue
            subject=row['subject'].strip()
            db.execute('INSERT OR IGNORE INTO subjects(name_ar) VALUES(?)',(subject,))
            sid=db.execute('SELECT id FROM subjects WHERE name_ar=?',(subject,)).fetchone()[0]
            grade=int(row['grade']); semester=int(row['semester'])
            title=row['title'].strip(); url=row['source_url'].strip()
            exists=db.execute('SELECT 1 FROM books WHERE grade_id=? AND subject_id=? AND title=? AND semester=? AND url=?',(grade,sid,title,semester,url)).fetchone()
            if not exists:
                db.execute('INSERT INTO books(grade_id,subject_id,title,semester,url) VALUES(?,?,?,?,?)',(grade,sid,title,semester,url))
                inserted+=1
    return inserted

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['check','register'])
    parser.add_argument('--csv',default=str(ROOT/'discovered_books.csv'))
    parser.add_argument('--db',default=str(ROOT/'curriculum.sqlite3'))
    args=parser.parse_args()
    if args.command=='check':
        rows=check_catalog(args.csv)
        print(json.dumps({'catalog_rows':len(rows),'approved':0,'rights':'unknown'},ensure_ascii=False))
    else:
        print(json.dumps({'registered':register_metadata(args.db,args.csv)},ensure_ascii=False))
if __name__=='__main__': main()
