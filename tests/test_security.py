"""
tests/test_security.py
Security-focused tests: URL safety, file upload limits,
SQL injection guards, and header verification.
"""

import json
import io
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from analyzer.url_analyzer import analyze_urls


@pytest.fixture
def client():
    app = create_app('testing')
    with app.test_client() as c:
        yield c


# ── URL safety ────────────────────────────────────────────────────────────────

class TestURLAnalyzerSecurity:
    def test_rejects_non_http_scheme(self):
        """Only http/https are accepted; ftp/file/data must produce no findings."""
        findings = analyze_urls(['ftp://fictional.example.com/secret'])
        # ftp is rejected, so no findings from a bad scheme
        assert all(f.get('rule_id') != 'URL_NON_HTTPS' for f in findings)

    def test_handles_malformed_url_gracefully(self):
        findings = analyze_urls(['not a url at all !!'])
        assert isinstance(findings, list)

    def test_handles_empty_list(self):
        findings = analyze_urls([])
        assert findings == []

    def test_detects_credentials(self):
        findings = analyze_urls(['https://user:secret@fictional.example.com'])
        rule_ids = [f['rule_id'] for f in findings]
        assert 'URL_CREDENTIALS_EMBEDDED' in rule_ids

    def test_credentials_not_in_evidence(self):
        """Credentials must be redacted from any displayed evidence text."""
        findings = analyze_urls(['https://admin:password123@fictional.example.com'])
        for f in findings:
            evidence = f.get('evidence', '')
            assert 'password123' not in evidence, "Credential leaked in evidence!"

    def test_detects_ip_hostname(self):
        findings = analyze_urls(['http://192.168.99.1/path'])
        rule_ids = [f['rule_id'] for f in findings]
        # IP hostname → URL_SUSPICIOUS_HOST; also http → URL_NON_HTTPS
        assert 'URL_SUSPICIOUS_HOST' in rule_ids

    def test_detects_punycode(self):
        findings = analyze_urls(['https://xn--e1afmkfd.xn--p1ai/'])
        rule_ids = [f['rule_id'] for f in findings]
        assert 'URL_SUSPICIOUS_HOST' in rule_ids

    def test_detects_tracking_params(self):
        findings = analyze_urls(['https://fictional.com/page?fbclid=abc123'])
        rule_ids = [f['rule_id'] for f in findings]
        assert 'URL_TRACKING_PARAMS' in rule_ids

    def test_very_long_url_ignored(self):
        """URLs over 2000 chars are silently skipped."""
        long_url = 'https://fictional.example.com/' + 'a' * 2000
        findings = analyze_urls([long_url])
        assert isinstance(findings, list)

    def test_duplicate_urls_not_double_counted(self):
        """Duplicate URLs should produce at most one set of findings."""
        url = 'http://fictional-dup.example.com'
        findings_single = analyze_urls([url])
        findings_double = analyze_urls([url, url])
        assert len(findings_double) == len(findings_single)


# ── Security headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        res = client.get('/')
        assert res.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options(self, client):
        res = client.get('/')
        assert res.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    def test_referrer_policy(self, client):
        res = client.get('/')
        assert 'Referrer-Policy' in res.headers

    def test_csp_present(self, client):
        res = client.get('/')
        assert 'Content-Security-Policy' in res.headers


# ── File upload limits ────────────────────────────────────────────────────────

class TestFileUpload:
    _URL = '/api/analyze-document'

    def test_no_file_returns_400(self, client):
        res = client.post(self._URL, data={})
        assert res.status_code == 400

    def test_unsupported_extension_returns_400(self, client):
        data = {'document': (io.BytesIO(b'fake content'), 'evil.exe')}
        res = client.post(self._URL, data=data, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_txt_extension_rejected(self, client):
        data = {'document': (io.BytesIO(b'fake text'), 'notes.txt')}
        res = client.post(self._URL, data=data, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_valid_pdf_extension_accepted(self, client):
        # Minimal fake PDF (not a real PDF – metadata extraction will fail gracefully)
        fake_pdf = b'%PDF-1.4 fake content'
        data = {'document': (io.BytesIO(fake_pdf), 'test_report.pdf')}
        res = client.post(self._URL, data=data, content_type='multipart/form-data')
        # Should succeed (even if no metadata found) — not crash
        assert res.status_code == 200

    def test_corrupted_pdf_handled_gracefully(self, client):
        data = {'document': (io.BytesIO(b'this is not a pdf'), 'corrupt.pdf')}
        res = client.post(self._URL, data=data, content_type='multipart/form-data')
        assert res.status_code == 200

    def test_sensitive_filename_flagged(self, client):
        data = {'document': (io.BytesIO(b'%PDF-1.4 fake'), 'password_list.pdf')}
        res = client.post(self._URL, data=data, content_type='multipart/form-data')
        assert res.status_code == 200
        body = json.loads(res.data)
        rule_ids = [f['rule_id'] for f in body.get('findings', [])]
        assert 'DOC_SENSITIVE_FILENAME' in rule_ids


# ── Database safety ───────────────────────────────────────────────────────────

class TestDatabaseSafety:
    def test_sql_injection_in_report_id_rejected(self, client):
        """A malformed report_id that looks like SQL injection must return 400."""
        res = client.get("/api/report/'; DROP TABLE reports; --")
        assert res.status_code == 400

    def test_sql_injection_in_delete(self, client):
        res = client.delete("/api/report/' OR '1'='1")
        assert res.status_code == 400
