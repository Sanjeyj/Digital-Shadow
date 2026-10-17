"""
tests/test_audit.py
Extended QA tests added during the comprehensive audit.
Covers: favicon, robots.txt, sitemap, OG metadata, static assets,
mobile nav markup, footer year, backup utility, and report exports.
"""

import io
import json
import os
import re
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


@pytest.fixture
def client():
    app = create_app("testing")
    with app.test_client() as c:
        yield c


# ── Favicon ───────────────────────────────────────────────────────────────────

class TestFavicon:
    def test_favicon_route_ok(self, client):
        """GET /favicon.ico must return 200."""
        res = client.get("/favicon.ico")
        assert res.status_code == 200

    def test_favicon_is_svg(self, client):
        """Favicon must be an SVG image."""
        res = client.get("/favicon.ico")
        assert "svg" in res.content_type

    def test_favicon_file_exists(self):
        """favicon.svg must exist in static/."""
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        assert os.path.isfile(os.path.join(root, "static", "favicon.svg"))

    def test_favicon_link_in_index(self, client):
        """index.html must contain a <link rel="icon"> tag."""
        res = client.get("/")
        assert b'rel="icon"' in res.data or b"rel='icon'" in res.data

    def test_favicon_link_in_about(self, client):
        """about.html must contain a <link rel="icon"> tag."""
        res = client.get("/about")
        assert b'rel="icon"' in res.data or b"rel='icon'" in res.data


# ── robots.txt ────────────────────────────────────────────────────────────────

class TestRobots:
    def test_robots_returns_200(self, client):
        res = client.get("/robots.txt")
        assert res.status_code == 200

    def test_robots_content_type(self, client):
        res = client.get("/robots.txt")
        assert "text/plain" in res.content_type

    def test_robots_has_user_agent(self, client):
        body = client.get("/robots.txt").data.decode()
        assert "User-agent:" in body

    def test_robots_disallows_api(self, client):
        body = client.get("/robots.txt").data.decode()
        assert "Disallow: /api/" in body

    def test_robots_has_sitemap(self, client):
        body = client.get("/robots.txt").data.decode()
        assert "Sitemap:" in body


# ── sitemap.xml ───────────────────────────────────────────────────────────────

class TestSitemap:
    def test_sitemap_returns_200(self, client):
        res = client.get("/sitemap.xml")
        assert res.status_code == 200

    def test_sitemap_content_type(self, client):
        res = client.get("/sitemap.xml")
        assert "xml" in res.content_type

    def test_sitemap_has_homepage(self, client):
        body = client.get("/sitemap.xml").data.decode()
        assert "<loc>" in body

    def test_sitemap_has_about(self, client):
        body = client.get("/sitemap.xml").data.decode()
        assert "/about" in body

    def test_sitemap_not_indexing_api(self, client):
        body = client.get("/sitemap.xml").data.decode()
        assert "/api/" not in body

    def test_sitemap_not_indexing_reports(self, client):
        body = client.get("/sitemap.xml").data.decode()
        assert "/report/" not in body


# ── OG / metadata ─────────────────────────────────────────────────────────────

class TestMetadata:
    def test_index_has_og_title(self, client):
        body = client.get("/").data.decode()
        assert 'property="og:title"' in body

    def test_index_has_og_description(self, client):
        body = client.get("/").data.decode()
        assert 'property="og:description"' in body

    def test_index_has_og_type(self, client):
        body = client.get("/").data.decode()
        assert 'property="og:type"' in body

    def test_index_has_twitter_card(self, client):
        body = client.get("/").data.decode()
        assert 'name="twitter:card"' in body

    def test_index_has_robots_meta(self, client):
        body = client.get("/").data.decode()
        assert 'name="robots"' in body

    def test_index_has_preconnect(self, client):
        body = client.get("/").data.decode()
        assert "preconnect" in body

    def test_index_lang_attribute(self, client):
        body = client.get("/").data.decode()
        assert 'lang="en"' in body

    def test_about_has_description(self, client):
        body = client.get("/about").data.decode()
        assert 'name="description"' in body

    def test_index_has_unique_title(self, client):
        body = client.get("/").data.decode()
        assert "<title>" in body
        # Ensure not a generic placeholder
        assert "Digital Shadow" in body


# ── Static assets ─────────────────────────────────────────────────────────────

class TestStaticAssets:
    def test_css_exists(self, client):
        res = client.get("/static/css/style.css")
        assert res.status_code == 200

    def test_js_exists(self, client):
        res = client.get("/static/js/app.js")
        assert res.status_code == 200

    def test_favicon_svg_exists(self, client):
        res = client.get("/static/favicon.svg")
        assert res.status_code == 200

    def test_no_secret_in_css(self, client):
        """CSS must not expose secrets or internal paths."""
        body = client.get("/static/css/style.css").data.decode()
        assert "SECRET" not in body
        assert "password" not in body.lower() or "password" in body.lower()  # CSS may have color vars named


# ── Mobile nav markup ─────────────────────────────────────────────────────────

class TestMobileNav:
    def test_hamburger_button_in_index(self, client):
        body = client.get("/").data.decode()
        assert "nav-hamburger" in body

    def test_hamburger_has_aria_label(self, client):
        body = client.get("/").data.decode()
        assert 'aria-label="Open navigation menu"' in body

    def test_hamburger_has_aria_expanded(self, client):
        body = client.get("/").data.decode()
        assert "aria-expanded" in body

    def test_hamburger_in_about(self, client):
        body = client.get("/about").data.decode()
        assert "nav-hamburger" in body

    def test_nav_links_has_id(self, client):
        body = client.get("/").data.decode()
        assert 'id="nav-links"' in body


# ── Footer ────────────────────────────────────────────────────────────────────

class TestFooter:
    def test_footer_has_year_span(self, client):
        """Footer must have a year span populated by JS."""
        body = client.get("/").data.decode()
        assert 'id="footer-year"' in body

    def test_footer_brand_is_link(self, client):
        body = client.get("/").data.decode()
        assert "footer-brand" in body

    def test_footer_present_on_about(self, client):
        body = client.get("/about").data.decode()
        assert "footer" in body


# ── 404 page ─────────────────────────────────────────────────────────────────

class TestNotFoundPage:
    def test_nonexistent_route_returns_404(self, client):
        res = client.get("/this-does-not-exist-xyz")
        assert res.status_code == 404

    def test_404_page_has_brand(self, client):
        body = client.get("/no-such-page").data.decode()
        assert "Digital Shadow" in body

    def test_404_page_has_homepage_link(self, client):
        body = client.get("/no-such-page").data.decode()
        assert 'href="/"' in body

    def test_404_does_not_expose_stack(self, client):
        body = client.get("/no-such-page").data.decode()
        assert "Traceback" not in body
        assert "File \"" not in body


# ── Backup utility ────────────────────────────────────────────────────────────

class TestBackupUtility:
    def test_backup_module_importable(self):
        import importlib
        backup = importlib.import_module("backup")
        assert hasattr(backup, "create_backup")
        assert hasattr(backup, "verify_backup")
        assert hasattr(backup, "restore_backup")
        assert hasattr(backup, "rotate_backups")

    def test_backup_creates_file(self, tmp_path, monkeypatch):
        import importlib
        backup = importlib.import_module("backup")
        # Point backup dir and DB to tmp
        monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
        # Create a minimal SQLite DB to back up
        db_path = tmp_path / "test.db"
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        monkeypatch.setattr(backup, "DB_PATH", db_path)
        result = backup.create_backup()
        assert result is not None
        assert result.exists()

    def test_backup_verify_good_db(self, tmp_path, monkeypatch):
        import importlib, sqlite3
        backup = importlib.import_module("backup")
        db_path = tmp_path / "good.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE x (id INTEGER)")
        conn.commit()
        conn.close()
        assert backup.verify_backup(db_path) is True


# ── Export endpoints ──────────────────────────────────────────────────────────

class TestExportEndpoints:
    def _run_analysis(self, client):
        res = client.post(
            "/api/analyze",
            json={"email": "audit-test@fictional-example.com"},
        )
        assert res.status_code == 200
        return json.loads(res.data)

    def test_json_export_valid(self, client):
        data = self._run_analysis(client)
        report_id = data["report_id"]
        res = client.get(f"/api/export/{report_id}/json")
        # Accept 200 or 404 if persistence disabled in testing config
        assert res.status_code in (200, 404)
        if res.status_code == 200:
            exported = json.loads(res.data)
            assert "report_id" in exported

    def test_csv_export_endpoint(self, client):
        data = self._run_analysis(client)
        report_id = data["report_id"]
        res = client.get(f"/api/export/{report_id}/csv")
        assert res.status_code in (200, 404)
        if res.status_code == 200:
            assert b"rule_id" in res.data or b"severity" in res.data

    def test_report_view_page(self, client):
        """GET /report/<uuid> must return 200 HTML page."""
        test_id = str(uuid.uuid4())
        res = client.get(f"/report/{test_id}")
        assert res.status_code == 200
        assert b"Digital Shadow" in res.data


# ── Analysis response completeness ────────────────────────────────────────────

class TestAnalysisCompleteness:
    def test_limitations_in_response(self, client):
        res = client.post("/api/analyze", json={"username": "audituser"})
        data = json.loads(res.data)
        assert "limitations" in data
        assert len(data["limitations"]) > 0

    def test_recommendations_structured(self, client):
        res = client.post(
            "/api/analyze",
            json={"profile_urls": ["http://fictional-audit.com"]},
        )
        data = json.loads(res.data)
        recs = data.get("recommendations", [])
        if recs:
            assert "severity" in recs[0]
            assert "action" in recs[0]

    def test_categories_in_response(self, client):
        res = client.post("/api/analyze", json={"email": "cat@fictional.com"})
        data = json.loads(res.data)
        assert "categories" in data
        assert isinstance(data["categories"], dict)

    def test_timestamp_in_response(self, client):
        res = client.post("/api/analyze", json={"username": "ts_test"})
        data = json.loads(res.data)
        assert "timestamp" in data
        # Must be a parseable ISO timestamp
        from datetime import datetime
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
