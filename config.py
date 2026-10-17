"""
config.py — Application configuration for Digital Shadow.
All tunable parameters are kept here for easy modification and testing.
"""

import os
import secrets


class Config:
    # ── Flask core ──────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    DEBUG: bool = False
    TESTING: bool = False

    # ── Upload limits ────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 5 * 1024 * 1024  # 5 MB hard limit (Flask)
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024    # 5 MB soft limit in upload handler
    ALLOWED_EXTENSIONS: set = {"pdf", "docx"}

    # ── Input limits ─────────────────────────────────────────────────────────
    MAX_TEXT_LENGTH: int = 8_000     # characters for free-text fields
    MAX_URLS: int = 10               # maximum URLs accepted in one request
    MAX_USERNAME_LENGTH: int = 64
    MAX_EMAIL_LENGTH: int = 254

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_PATH: str = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(__file__), "digital_shadow.db"),
    )
    PERSIST_REPORTS: bool = True     # set False to disable DB writes

    # ── Risk scoring thresholds ───────────────────────────────────────────────
    SCORE_LOW_MAX: int = 19
    SCORE_MODERATE_MAX: int = 39
    SCORE_HIGH_MAX: int = 69
    SCORE_CRITICAL_MAX: int = 100

    # Severity → score contribution mapping
    SEVERITY_WEIGHTS: dict = {
        "low": 5,
        "medium": 10,
        "high": 20,
        "critical": 30,
    }

    # ── Security headers ──────────────────────────────────────────────────────
    SECURITY_HEADERS: dict = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm/chart.js; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        ),
    }


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_PATH = ":memory:"
    PERSIST_REPORTS = False
    SECRET_KEY = "test-secret-key-not-for-production"


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": Config,
    "default": DevelopmentConfig,
}


def get_config(env: str | None = None) -> Config:
    env = env or os.environ.get("FLASK_ENV", "default")
    return config_map.get(env, DevelopmentConfig)()
