import sqlite3
import tempfile
import unittest
from pathlib import Path
from retrieval_gate import eligible_chunks

class RetrievalGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "gate.db")
        with sqlite3.connect(self.db) as db:
            db.executescript("""
            CREATE TABLE books(id INTEGER PRIMARY KEY,review_status TEXT,rights_status TEXT,extraction_status TEXT,url TEXT);
            CREATE TABLE units(id INTEGER PRIMARY KEY,book_id INTEGER,sequence INTEGER);
            CREATE TABLE lessons(id INTEGER PRIMARY KEY,unit_id INTEGER,sequence INTEGER);
            CREATE TABLE chunks(id INTEGER PRIMARY KEY,lesson_id INTEGER,review_status TEXT,page_start INTEGER,page_end INTEGER,text TEXT);
            CREATE TABLE book_review_events(id INTEGER PRIMARY KEY,book_id INTEGER,decision TEXT,evidence_url TEXT);
            INSERT INTO books VALUES(1,'approved','permitted','completed','https://example.org/book');
            INSERT INTO units VALUES(1,1,1);
            INSERT INTO lessons VALUES(1,1,1);
            INSERT INTO chunks VALUES(1,1,'approved',1,2,'PRIVATE TEXT');
            INSERT INTO chunks VALUES(2,1,'pending',3,4,'PRIVATE TEXT');
            INSERT INTO book_review_events VALUES(1,1,'permit_content','https://example.org/permission');
            """)
    def tearDown(self):
        self.tmp.cleanup()
    def change(self, sql):
        with sqlite3.connect(self.db) as db:
            db.execute(sql)
    def test_only_approved_chunk_metadata(self):
        self.assertEqual(eligible_chunks(self.db,1), [{"chunk_id":1,"page_start":1,"page_end":2}])
        self.assertNotIn("PRIVATE",str(eligible_chunks(self.db,1)))
    def test_unknown_book(self):
        self.assertEqual(eligible_chunks(self.db,999),[])
    def test_pending_review_denied(self):
        self.change("UPDATE books SET review_status='pending'")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_restricted_denied(self):
        self.change("UPDATE books SET rights_status='restricted'")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_unfinished_extraction_denied(self):
        self.change("UPDATE books SET extraction_status='not_started'")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_missing_evidence_denied(self):
        self.change("DELETE FROM book_review_events")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_revocation_denied(self):
        self.change("INSERT INTO book_review_events VALUES(2,1,'restrict_content','https://example.org/revoke')")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_unsafe_url_denied(self):
        self.change("UPDATE books SET url='http://example.org/book'")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_missing_audit_table_denied(self):
        self.change("DROP TABLE book_review_events")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_revocation_then_new_permission(self):
        self.change("INSERT INTO book_review_events VALUES(2,1,'restrict_content','https://example.org/revoke')")
        self.assertEqual(eligible_chunks(self.db,1),[])
        self.change("INSERT INTO book_review_events VALUES(3,1,'permit_content','https://example.org/new-permission')")
        self.assertEqual(len(eligible_chunks(self.db,1)),1)
    def test_latest_permission_requires_https_evidence(self):
        self.change("INSERT INTO book_review_events VALUES(2,1,'permit_content','http://example.org/unsafe')")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_credential_bearing_evidence_denied(self):
        self.change("UPDATE book_review_events SET evidence_url='https://user:pass@example.org/permission'")
        self.assertEqual(eligible_chunks(self.db,1),[])
    def test_unknown_audit_decision_fails_closed(self):
        self.change("INSERT INTO book_review_events VALUES(2,1,'unexpected_decision','https://example.org/evidence')")
        self.assertEqual(eligible_chunks(self.db,1),[])

    def test_unknown_decision_not_overridden_by_later_permission(self):
        self.change("INSERT INTO book_review_events VALUES(2,1,'unexpected_decision','https://example.org/evidence')")
        self.change("INSERT INTO book_review_events VALUES(3,1,'permit_content','https://example.org/new-permission')")
        self.assertEqual(eligible_chunks(self.db,1),[])

    def test_book_url_with_whitespace_or_controls_denied(self):
        for url in ("https://example.org/a b", "https://example.org/\\nbook", "https://example.org/\\tbook"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE books SET url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_evidence_url_with_whitespace_or_controls_denied(self):
        for url in ("https://example.org/a b", "https://example.org/\\npermission", "https://example.org/\\tpermission"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE book_review_events SET evidence_url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_unicode_whitespace_and_backslash_book_urls_denied(self):
        for url in ("https://example.org/a\u00a0b", "https://example.org/a\u2003b",
                    "https://example.org\\@evil.example/book"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE books SET url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_unicode_whitespace_and_backslash_evidence_urls_denied(self):
        for url in ("https://example.org/a\u00a0b", "https://example.org/a\u2003b",
                    "https://example.org\\@evil.example/permission"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE book_review_events SET evidence_url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_malformed_book_url_ports_denied(self):
        for url in ("https://example.org:abc/book", "https://example.org:99999/book",
                    "https://example.org:0/book"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE books SET url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_malformed_evidence_url_ports_denied(self):
        for url in ("https://example.org:abc/evidence", "https://example.org:99999/evidence",
                    "https://example.org:0/evidence"):
            with self.subTest(url=url):
                with sqlite3.connect(self.db) as db:
                    db.execute("UPDATE book_review_events SET evidence_url=?", (url,))
                self.assertEqual(eligible_chunks(self.db, 1), [])

    def test_invalid_page_ranges_excluded(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO chunks VALUES(3,1,'approved',0,1,'PRIVATE TEXT')")
            db.execute("INSERT INTO chunks VALUES(4,1,'approved',5,3,'PRIVATE TEXT')")
            db.execute("INSERT INTO chunks VALUES(5,1,'approved',NULL,7,'PRIVATE TEXT')")
            db.execute("INSERT INTO chunks VALUES(6,1,'approved',8,NULL,'PRIVATE TEXT')")
        self.assertEqual(eligible_chunks(self.db, 1),
                         [{"chunk_id":1,"page_start":1,"page_end":2}])

    def test_non_integer_page_metadata_excluded(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO chunks VALUES(3,1,'approved','1','2','PRIVATE TEXT')")
            db.execute("INSERT INTO chunks VALUES(4,1,'approved',1.5,2.5,'PRIVATE TEXT')")
            db.execute("INSERT INTO chunks VALUES(5,1,'approved',3,'4','PRIVATE TEXT')")
        self.assertEqual(eligible_chunks(self.db, 1),
                         [{"chunk_id":1,"page_start":1,"page_end":2}])

    def test_non_integer_page_metadata_does_not_consume_limit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE chunks SET page_start='1',page_end='2' WHERE id=1")
            db.execute("INSERT INTO chunks VALUES(3,1,'approved',5,6,'PRIVATE TEXT')")
        self.assertEqual(eligible_chunks(self.db, 1, limit=1),
                         [{"chunk_id":3,"page_start":5,"page_end":6}])

    def test_invalid_page_ranges_do_not_consume_limit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO chunks VALUES(0,1,'approved',0,0,'PRIVATE TEXT')")
        self.assertEqual(eligible_chunks(self.db, 1, limit=1),
                         [{"chunk_id":1,"page_start":1,"page_end":2}])

    def test_invalid_limit_types_and_bounds(self):
        for value in (0,-1,True,1.5,"10",101):
            with self.subTest(limit=value), self.assertRaises(ValueError):
                eligible_chunks(self.db,1,value)
    def test_invalid_parameters(self):
        for value in (0,True,"1"):
            with self.assertRaises(ValueError):
                eligible_chunks(self.db,value)
        with self.assertRaises(ValueError):
            eligible_chunks(self.db,1,101)

if __name__ == "__main__":
    unittest.main()
