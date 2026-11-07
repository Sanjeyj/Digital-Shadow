"""
tests/test_auth.py
Unit and integration tests for Login, Session Authentication, Logout,
and Theme Colors compliance.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


@pytest.fixture
def client():
    app = create_app("testing")
    with app.test_client() as c:
        yield c


class TestLoginRoutes:
    def test_login_page_renders_ok(self, client):
        """GET /login must return HTTP 200 and include Sign In elements."""
        res = client.get("/login")
        assert res.status_code == 200
        html = res.data.decode("utf-8")
        assert "Sign In" in html
        assert "Digital Shadow" in html
        assert 'id="username"' in html
        assert 'id="password"' in html
        assert 'id="btn-demo-analyst"' in html

    def test_login_success_form_redirects(self, client):
        """POST /login with valid form data should set session and redirect to /."""
        res = client.post(
            "/login",
            data={
                "username": "sec_analyst",
                "password": "valid_secret_key",
                "remember": "1",
            },
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["Location"].endswith("/")

        # Following redirect, user is authenticated
        with client.session_transaction() as sess:
            assert "user" in sess
            assert sess["user"]["username"] == "sec_analyst"

        follow = client.get("/")
        html = follow.data.decode("utf-8")
        assert "sec_analyst" in html
        assert "Sign Out" in html

    def test_login_success_json_returns_user(self, client):
        """POST /login with JSON should return JSON status and user info."""
        res = client.post(
            "/login",
            json={
                "username": "analyst@example.com",
                "password": "validpassword",
            },
        )
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["success"] is True
        assert data["user"]["username"] == "analyst"
        assert data["user"]["email"] == "analyst@example.com"
        assert data["redirect"] == "/"

    def test_login_empty_username_fails(self, client):
        """POST /login without username should return 400 error."""
        res = client.post(
            "/login",
            json={"username": "", "password": "password123"},
        )
        assert res.status_code == 400
        data = json.loads(res.data)
        assert data["success"] is False
        assert "username or email" in data["error"].lower()

    def test_login_empty_password_fails(self, client):
        """POST /login without password should return 400 error."""
        res = client.post(
            "/login",
            json={"username": "analyst", "password": ""},
        )
        assert res.status_code == 400
        data = json.loads(res.data)
        assert data["success"] is False
        assert "password" in data["error"].lower()

    def test_login_short_password_fails(self, client):
        """POST /login with short password (< 4 chars) should return 400 error."""
        res = client.post(
            "/login",
            json={"username": "analyst", "password": "12"},
        )
        assert res.status_code == 400
        data = json.loads(res.data)
        assert data["success"] is False
        assert "at least 4 characters" in data["error"].lower()

    def test_logged_in_user_visiting_login_redirects(self, client):
        """If user is already signed in, visiting /login should redirect to homepage."""
        with client.session_transaction() as sess:
            sess["user"] = {"username": "existing_user", "email": "test@test.local"}

        res = client.get("/login", follow_redirects=False)
        assert res.status_code == 302
        assert res.headers["Location"].endswith("/")

    def test_logout_clears_session(self, client):
        """GET /logout should clear the user session and redirect to /."""
        with client.session_transaction() as sess:
            sess["user"] = {"username": "temp_user"}

        res = client.get("/logout", follow_redirects=False)
        assert res.status_code == 302

        with client.session_transaction() as sess:
            assert "user" not in sess

    def test_sitemap_includes_login(self, client):
        """sitemap.xml must include the /login page."""
        res = client.get("/sitemap.xml")
        assert res.status_code == 200
        body = res.data.decode("utf-8")
        assert "/login" in body


class TestThemeColors:
    def test_style_css_has_requested_theme_colors(self, client):
        """CSS must define the exact hex colors specified by user."""
        res = client.get("/static/css/style.css")
        assert res.status_code == 200
        css = res.data.decode("utf-8").lower()

        # JET BLACK #050505
        assert "#050505" in css

        # ROYAL AMETHYST #3b0a6b
        assert "#3b0a6b" in css

        # ELECTRIC CYAN #00e5ff
        assert "#00e5ff" in css

    def test_style_css_has_no_deep_navy_or_legacy_blue_backgrounds(self, client):
        """Website should have removed the previous deep navy #060b17 background and blue palette."""
        res = client.get("/static/css/style.css")
        assert res.status_code == 200
        css = res.data.decode("utf-8").lower()

        # Previous navy background must not be defined
        assert "#060b17" not in css
        # Previous primary blue #3b82f6 must not be active
        assert "#3b82f6" not in css

