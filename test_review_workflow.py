import tempfile
import unittest
from pathlib import Path
from curriculum import init, add_book, connect
from review_workflow import apply_decision, review_report

class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'test.db')
        init(self.db)
        add_book(self.db, {'grade':7,'subject':'تقنية المعلومات','title':'بيانات تجريبية'})
    def tearDown(self): self.tmp.cleanup()
    def review(self, decision, **kwargs):
        values = {'reviewer':'Reviewer A','evidence_url':'https://ict.moe.gov.om/book/',
                  'note':'Reviewed metadata and supporting document'}
        values.update(kwargs)
        return apply_decision(self.db, 1, decision, **values)
    def test_default_pending(self):
        self.assertEqual(review_report(self.db)['permitted_content'],0)
        self.assertEqual(review_report(self.db)['pending_metadata'],1)
    def test_metadata_approval_does_not_permit_content(self):
        self.review('verify_metadata')
        self.assertEqual(review_report(self.db)['approved_metadata'],1)
        self.assertEqual(review_report(self.db)['permitted_content'],0)
    def test_content_permission_requires_prior_metadata(self):
        with self.assertRaisesRegex(ValueError,'Metadata must'):
            self.review('permit_content', note='Written permission provided')
    def test_permission_requires_evidence_and_audit(self):
        self.review('verify_metadata')
        with self.assertRaisesRegex(ValueError,'explicit permission'):
            self.review('permit_content')
        self.review('permit_content',note='Written permission approved from rights owner')
        self.assertEqual(review_report(self.db)['permitted_content'],1)
        self.assertEqual(review_report(self.db)['review_events'],2)
    def test_reject_revokes_pending_permission(self):
        self.review('verify_metadata')
        self.review('permit_content',note='Written permission approved')
        self.review('reject_metadata',note='Incorrect bibliographic reference')
        self.assertEqual(review_report(self.db)['permitted_content'],0)
    def test_no_unsourced_approval(self):
        with self.assertRaisesRegex(ValueError,'HTTPS'):
            self.review('verify_metadata',evidence_url='http://example.com')
        with self.assertRaisesRegex(ValueError,'mandatory'):
            self.review('verify_metadata',reviewer=' ')
    def test_nonexistent_book_rejected(self):
        with self.assertRaisesRegex(ValueError,'does not exist'):
            apply_decision(self.db,999,'verify_metadata','Reviewer A','https://ict.moe.gov.om/','Reviewed')
if __name__ == '__main__':
    unittest.main()
