"""
app.py — Digital Shadow: Personal Data Exposure Mapping & Privacy Risk Analyzer
Flask application entry point.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
import os
import re
import secrets
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from analyzer.exposure_engine import run_exposure_analysis
from analyzer.url_analyzer import analyze_urls
from analyzer.metadata_analyzer import analyze_document_metadata
from analyzer.risk_scoring import compute_score
from config import get_config
from database.db import delete_report, get_report, init_db, list_reports, save_report


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("digital_shadow")


# ── Application factory ───────────────────────────────────────────────────────

def create_app(env: str | None = None) -> Flask:
    cfg = get_config(env)

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(cfg)

    # Flask-native upload limit
    app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_CONTENT_LENGTH

    # ── Database init ─────────────────────────────────────────────────────────
    if cfg.PERSIST_REPORTS and cfg.DATABASE_PATH != ":memory:":
        try:
            init_db(cfg.DATABASE_PATH)
            logger.info("Database initialized at %s", cfg.DATABASE_PATH)
        except Exception as exc:
            logger.error("Database init failed: %s", exc)

    # ── Security headers ──────────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        for header, value in cfg.SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    # ── Error handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(error="Upload too large. Maximum 5 MB."), 413

    @app.errorhandler(500)
    def internal_error(_e):
        logger.exception("Internal server error")
        if request.path.startswith("/api/"):
            return jsonify(error="An internal error occurred."), 500
        return render_template("404.html", code=500, message="Internal Server Error"), 500

    # ── Page routes ───────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/report/<report_id>")
    def view_report(report_id: str):
        return render_template("report.html", report_id=report_id)

    # ── Favicon ───────────────────────────────────────────────────────────────

    @app.route("/favicon.ico")
    def favicon():
        return send_file(
            os.path.join(app.static_folder, "favicon.svg"),
            mimetype="image/svg+xml",
        )

    # ── robots.txt ────────────────────────────────────────────────────────────

    @app.route("/robots.txt")
    def robots():
        from flask import Response
        content = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /api/\n"
            "Disallow: /report/\n"
            "Sitemap: /sitemap.xml\n"
        )
        return Response(content, mimetype="text/plain")

    # ── sitemap.xml ───────────────────────────────────────────────────────────

    @app.route("/sitemap.xml")
    def sitemap():
        from flask import Response
        base = request.host_url.rstrip("/")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'  <url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
            f'  <url><loc>{base}/about</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n'
            '</urlset>\n'
        )
        return Response(xml, mimetype="application/xml")

    # ── Health check ──────────────────────────────────────────────────────────

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "digital-shadow"}), 200


    # ── Main analysis endpoint ────────────────────────────────────────────────

    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        """
        Accepts JSON with optional fields:
            username, email, profile_urls (list), website_urls (list), profile_text
        Returns a structured analysis report.
        """
        try:
            payload = request.get_json(silent=True) or {}
        except Exception:
            return jsonify(error="Invalid JSON body."), 400

        # ── Input validation ──────────────────────────────────────────────────
        username = _sanitize_str(payload.get("username"), cfg.MAX_USERNAME_LENGTH)
        email = _sanitize_str(payload.get("email"), cfg.MAX_EMAIL_LENGTH)
        profile_text = _sanitize_str(payload.get("profile_text"), cfg.MAX_TEXT_LENGTH)

        profile_urls = _sanitize_urls(payload.get("profile_urls"), cfg.MAX_URLS)
        website_urls = _sanitize_urls(payload.get("website_urls"), cfg.MAX_URLS)

        if not any([username, email, profile_text, profile_urls, website_urls]):
            return jsonify(error="Please provide at least one input field."), 400

        # ── Run exposure analysis ─────────────────────────────────────────────
        analysis_data = {
            "username": username,
            "email": email,
            "profile_urls": profile_urls,
            "website_urls": website_urls,
            "profile_text": profile_text,
        }

        exposure_findings = run_exposure_analysis(analysis_data)

        # ── Run URL analysis (all supplied URLs) ──────────────────────────────
        all_urls = profile_urls + website_urls
        url_findings = analyze_urls(all_urls)

        # Merge, deduplicating by rule_id
        seen_rule_ids = {f["rule_id"] for f in exposure_findings}
        for uf in url_findings:
            if uf["rule_id"] not in seen_rule_ids:
                exposure_findings.append(uf)
                seen_rule_ids.add(uf["rule_id"])

        # ── Compute risk score ────────────────────────────────────────────────
        scoring = compute_score(exposure_findings)

        # ── Build report ──────────────────────────────────────────────────────
        report_id = str(uuid.uuid4())
        report = _build_report(
            report_id=report_id,
            findings=exposure_findings,
            scoring=scoring,
        )

        # ── Persist (optional) ────────────────────────────────────────────────
        if cfg.PERSIST_REPORTS:
            try:
                save_report(cfg.DATABASE_PATH, report)
            except Exception as exc:
                logger.warning("Could not save report: %s", exc)

        return jsonify(report), 200

    # ── Document metadata analysis ────────────────────────────────────────────

    @app.route("/api/analyze-document", methods=["POST"])
    def analyze_document():
        """
        Accepts a multipart/form-data upload with a single file field 'document'.
        Returns metadata findings only.
        SECURITY: file is processed locally and deleted immediately.
        """
        if "document" not in request.files:
            return jsonify(error="No file field 'document' in request."), 400

        file = request.files["document"]
        if not file or not file.filename:
            return jsonify(error="No file selected."), 400

        original_filename = file.filename
        ext = Path(original_filename).suffix.lower().lstrip(".")

        if ext not in cfg.ALLOWED_EXTENSIONS:
            return jsonify(
                error=f"Unsupported file type '{ext}'. Accepted: pdf, docx."
            ), 400

        # Read into memory, then check size
        file_bytes = file.read()
        if len(file_bytes) > cfg.MAX_UPLOAD_BYTES:
            return jsonify(
                error=f"File too large. Maximum {cfg.MAX_UPLOAD_BYTES // (1024*1024)} MB."
            ), 413

        # Write to a secure temp file
        tmp_path: Optional[str] = None
        try:
            suffix = f".{ext}"
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False, dir=tempfile.gettempdir()
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            findings = analyze_document_metadata(tmp_path, original_filename)
        except Exception as exc:
            logger.warning("Document analysis error: %s", exc)
            findings = []
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        scoring = compute_score(findings)
        report_id = str(uuid.uuid4())
        report = _build_report(
            report_id=report_id,
            findings=findings,
            scoring=scoring,
            note="Document metadata analysis only.",
        )

        if cfg.PERSIST_REPORTS:
            try:
                save_report(cfg.DATABASE_PATH, report)
            except Exception as exc:
                logger.warning("Could not save report: %s", exc)

        return jsonify(report), 200

    # ── Report retrieval / deletion ───────────────────────────────────────────

    @app.route("/api/report/<report_id>", methods=["GET"])
    def get_report_api(report_id: str):
        if not _is_valid_uuid(report_id):
            return jsonify(error="Invalid report ID."), 400
        if not cfg.PERSIST_REPORTS:
            return jsonify(error="Report persistence is disabled."), 404
        row = get_report(cfg.DATABASE_PATH, report_id)
        if row is None:
            return jsonify(error="Report not found."), 404
        return jsonify(row), 200

    @app.route("/api/report/<report_id>", methods=["DELETE"])
    def delete_report_api(report_id: str):
        if not _is_valid_uuid(report_id):
            return jsonify(error="Invalid report ID."), 400
        if not cfg.PERSIST_REPORTS:
            return jsonify(error="Report persistence is disabled."), 404
        deleted = delete_report(cfg.DATABASE_PATH, report_id)
        if not deleted:
            return jsonify(error="Report not found."), 404
        return jsonify({"deleted": True, "report_id": report_id}), 200

    # ── Report export ─────────────────────────────────────────────────────────

    @app.route("/api/export/<report_id>/json", methods=["GET"])
    def export_json(report_id: str):
        """Export a stored report as JSON. For in-session export, the frontend
        uses the data returned by /api/analyze directly."""
        if not _is_valid_uuid(report_id):
            return jsonify(error="Invalid report ID."), 400
        if not cfg.PERSIST_REPORTS:
            return jsonify(error="Report persistence is disabled."), 404
        row = get_report(cfg.DATABASE_PATH, report_id)
        if row is None:
            return jsonify(error="Report not found."), 404

        json_bytes = json.dumps(row, indent=2, ensure_ascii=False).encode("utf-8")
        buf = io.BytesIO(json_bytes)
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"digital_shadow_report_{report_id[:8]}.json",
        )

    return app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_report(
    *,
    report_id: str,
    findings: list[dict],
    scoring: dict,
    note: str = "",
) -> dict:
    """Assemble the final structured report dict."""
    severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    categories: dict[str, int] = {}

    for f in findings:
        sev = (f.get("severity") or "low").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1
        cat = f.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + 1

    recommendations = _deduplicate_recommendations(findings)

    return {
        "report_id": report_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "severity_counts": severity_counts,
        "categories": categories,
        "total_findings": len(findings),
        "scoring": scoring,
        "recommendations": recommendations,
        "note": note,
        "limitations": [
            "Analysis is limited to the information you voluntarily submitted.",
            "URL analysis is structural only — no outbound requests are made.",
            "Pattern matching may produce false positives for phone numbers and addresses.",
            "The risk score is a heuristic estimate, not a security audit.",
            "This application does not claim to find all exposures on the internet.",
        ],
    }


def _deduplicate_recommendations(findings: list[dict]) -> list[dict]:
    """Return a deduplicated list of recommendation objects ordered by severity."""
    seen: set[str] = set()
    result: list[dict] = []
    order = ["critical", "high", "medium", "low"]

    for sev in order:
        for f in findings:
            if f.get("severity", "low").lower() != sev:
                continue
            action = f.get("recommendation_action", "")
            if action and action not in seen:
                seen.add(action)
                result.append(
                    {
                        "severity": sev,
                        "action": action,
                        "detail": f.get("recommendation_detail", ""),
                        "rule_id": f.get("rule_id", ""),
                    }
                )
    return result


def _sanitize_str(value, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def _sanitize_urls(value, max_count: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(stripped)
        if len(result) >= max_count:
            break
    return result


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except Exception:
        return False


# ── Entry point ───────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
