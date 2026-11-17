"""Read-only manifest privacy checks; no book bytes or network requests."""
import argparse
import json
import unittest
from pathlib import Path


def audit(manifest):
    findings = []
    for record in manifest.get('records', []):
        if record.get('status') != 'uploaded_verified':
            continue
        drive = record.get('drive_file')
        issues = []
        if not isinstance(drive, dict):
            issues.append('invalid_drive_metadata')
        else:
            if drive.get('shared') is True:
                issues.append('shared_file_requires_permission_review')
            visibility = drive.get('source_visibility_status')
            if visibility not in ('not_shared', 'permission_metadata_available'):
                issues.append('visibility_not_verified')
            permissions = drive.get('permissions')
            if permissions is not None and not isinstance(permissions, list):
                issues.append('invalid_permission_metadata')
            elif isinstance(permissions, list):
                if any(not isinstance(p, dict) or not isinstance(p.get('type'), str) or not p['type']
                       for p in permissions):
                    issues.append('invalid_permission_metadata')
                if any(isinstance(p, dict) and p.get('type') in ('anyone', 'domain')
                       for p in permissions):
                    issues.append('broad_permission_detected')
            if visibility == 'permission_metadata_available' and permissions is None:
                issues.append('permission_list_missing')
        if issues:
            findings.append({'source_id': str(record.get('id', '')), 'issues': issues})
    return {'findings': findings, 'requires_live_drive_permission_check': True}


class PrivacyTests(unittest.TestCase):
    def record(self, drive):
        return {'records': [{'id': '92', 'status': 'uploaded_verified', 'drive_file': drive}]}

    def test_private(self):
        self.assertEqual(audit(self.record({'shared': False, 'source_visibility_status': 'not_shared'}))['findings'], [])

    def test_shared(self):
        self.assertIn('shared_file_requires_permission_review', audit(self.record({'shared': True}))['findings'][0]['issues'])

    def test_public_permission(self):
        self.assertIn('broad_permission_detected', audit(self.record({'permissions': [{'type': 'anyone'}]}))['findings'][0]['issues'])

    def test_unverified(self):
        self.assertIn('visibility_not_verified', audit(self.record({'source_visibility_status': 'access_not_verified'}))['findings'][0]['issues'])

    def test_missing_visibility_fails_closed(self):
        self.assertIn('visibility_not_verified', audit(self.record({}))['findings'][0]['issues'])

    def test_invalid_permission_shape(self):
        self.assertIn('invalid_permission_metadata', audit(self.record({'source_visibility_status': 'not_shared', 'permissions': 'anyone'}))['findings'][0]['issues'])

    def test_missing_permission_list_when_claimed_available(self):
        self.assertIn('permission_list_missing', audit(self.record({'source_visibility_status': 'permission_metadata_available'}))['findings'][0]['issues'])


    def test_malformed_permission_entry_fails_closed(self):
        result = audit(self.record({'source_visibility_status': 'permission_metadata_available', 'permissions': [None, {'role': 'reader'}]}))
        self.assertIn('invalid_permission_metadata', result['findings'][0]['issues'])

    def test_broad_permission_detected_alongside_malformed_entry(self):
        result = audit(self.record({'source_visibility_status': 'permission_metadata_available', 'permissions': ['broken', {'type': 'anyone'}]}))
        self.assertIn('invalid_permission_metadata', result['findings'][0]['issues'])
        self.assertIn('broad_permission_detected', result['findings'][0]['issues'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', nargs='?', type=Path)
    args = parser.parse_args()
    if args.manifest:
        print(json.dumps(audit(json.loads(args.manifest.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))
    else:
        unittest.main(argv=['audit_transfer_privacy.py'])
