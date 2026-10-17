"""
analyzer/url_analyzer.py
Safe, local URL analysis. No outbound network requests are made here.

SECURITY NOTE: This module MUST NOT fetch, resolve, or connect to any URL
submitted by the user. All analysis is structural (parsing only).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs, unquote

from analyzer.patterns import (
    IP_PATTERN,
    PUNYCODE_PATTERN,
    NON_STANDARD_PORTS,
    TRACKING_PARAMS,
)
from analyzer.recommendations import get_recommendation
from analyzer.risk_scoring import build_finding


# Ports that are standard for HTTP/HTTPS
_STANDARD_PORTS = {80, 443}

# Absolute maximum URL length we will process
_MAX_URL_LENGTH = 2_000


def analyze_urls(urls: list[str]) -> list[dict]:
    """
    Analyze a list of user-provided URL strings locally.
    Returns a list of finding dicts (may be empty if no issues found).
    """
    findings: list[dict] = []
    seen: set[str] = set()

    for raw_url in urls:
        raw_url = raw_url.strip()
        if not raw_url or raw_url in seen:
            continue
        seen.add(raw_url)

        # Length guard
        if len(raw_url) > _MAX_URL_LENGTH:
            continue

        parsed = _safe_parse(raw_url)
        if parsed is None:
            continue

        findings.extend(_check_scheme(raw_url, parsed))
        findings.extend(_check_credentials(raw_url, parsed))
        findings.extend(_check_hostname(raw_url, parsed))
        findings.extend(_check_port(raw_url, parsed))
        findings.extend(_check_tracking_params(raw_url, parsed))

    return findings


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_parse(raw_url: str):
    """
    Parse a URL using urllib.parse. Return None if parsing fails or the
    scheme is not http/https.
    """
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None

    if parsed.scheme.lower() not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None

    return parsed


def _check_scheme(raw_url: str, parsed) -> list[dict]:
    findings = []
    if parsed.scheme.lower() == "http":
        rec = get_recommendation("URL_NON_HTTPS")
        findings.append(
            build_finding(
                rule_id="URL_NON_HTTPS",
                title="Non-HTTPS URL (unencrypted transport)",
                category="URL Risk Indicators",
                severity="medium",
                evidence=f"Scheme: http — full URL starts with: {_safe_display(raw_url)}",
                explanation=(
                    "This URL uses plain HTTP rather than HTTPS. Data exchanged "
                    "over HTTP is transmitted without encryption and can be "
                    "intercepted or modified by anyone on the same network path."
                ),
                consequence=(
                    "Sensitive information may be exposed to eavesdroppers "
                    "or modified by a man-in-the-middle attacker."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_credentials(raw_url: str, parsed) -> list[dict]:
    findings = []
    if parsed.username or parsed.password:
        rec = get_recommendation("URL_CREDENTIALS_EMBEDDED")
        safe_display = _safe_display(raw_url)
        findings.append(
            build_finding(
                rule_id="URL_CREDENTIALS_EMBEDDED",
                title="Credentials embedded in URL",
                category="URL Risk Indicators",
                severity="critical",
                evidence=f"URL contains a username/password component: {safe_display}",
                explanation=(
                    "The URL contains embedded authentication credentials "
                    "(username and/or password) in the authority section. "
                    "These credentials are logged by web servers, browser history, "
                    "and HTTP proxy logs in plaintext."
                ),
                consequence=(
                    "Credentials may be exposed in server logs, browser history, "
                    "and HTTP referrer headers sent to third-party services."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_hostname(raw_url: str, parsed) -> list[dict]:
    findings = []
    host = parsed.hostname or ""

    if IP_PATTERN.match(host):
        rec = get_recommendation("URL_SUSPICIOUS_HOST")
        findings.append(
            build_finding(
                rule_id="URL_SUSPICIOUS_HOST",
                title="URL uses a raw IP address as hostname",
                category="URL Risk Indicators",
                severity="medium",
                evidence=f"Hostname is an IP address: {host}",
                explanation=(
                    "The URL points to a raw IP address rather than a domain name. "
                    "Legitimate services almost always use named domains. "
                    "IP-based URLs are commonly associated with phishing and malware hosting."
                ),
                consequence=(
                    "This URL may point to a malicious or poorly secured server. "
                    "Visiting it could expose you to phishing or drive-by attacks."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    elif PUNYCODE_PATTERN.search(host):
        rec = get_recommendation("URL_SUSPICIOUS_HOST")
        findings.append(
            build_finding(
                rule_id="URL_SUSPICIOUS_HOST",
                title="Punycode / IDN hostname detected",
                category="URL Risk Indicators",
                severity="medium",
                evidence=f"Hostname contains punycode encoding: {host}",
                explanation=(
                    "Punycode-encoded hostnames can be used in homograph attacks, "
                    "where a domain appears visually identical to a legitimate domain "
                    "but maps to a different server."
                ),
                consequence=(
                    "You may be directed to a spoofed website that appears legitimate "
                    "but is operated by a malicious actor."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_port(raw_url: str, parsed) -> list[dict]:
    findings = []
    port = parsed.port
    if port is not None and port not in _STANDARD_PORTS:
        if port in NON_STANDARD_PORTS:
            severity = "low"
            explanation = (
                "This URL specifies a non-standard port that is commonly used "
                "for development or internal services. It is unusual for "
                "production websites to be served on this port."
            )
        else:
            severity = "medium"
            explanation = (
                "This URL uses an unusual port number. Ports outside the standard "
                "range may indicate a non-production service, a misconfigured server, "
                "or an attempt to hide a service from basic network scanning."
            )
        rec = get_recommendation("URL_NON_STANDARD_PORT")
        findings.append(
            build_finding(
                rule_id="URL_NON_STANDARD_PORT",
                title=f"Non-standard port in URL ({port})",
                category="URL Risk Indicators",
                severity=severity,
                evidence=f"Port {port} detected in: {_safe_display(raw_url)}",
                explanation=explanation,
                consequence=(
                    "The service may lack production hardening, security monitoring, "
                    "or TLS certificates appropriate for sensitive communication."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_tracking_params(raw_url: str, parsed) -> list[dict]:
    findings = []
    try:
        query_params = set(parse_qs(parsed.query).keys())
    except Exception:
        return findings

    found_trackers = query_params & TRACKING_PARAMS
    if found_trackers:
        rec = get_recommendation("URL_TRACKING_PARAMS")
        findings.append(
            build_finding(
                rule_id="URL_TRACKING_PARAMS",
                title="Marketing / tracking parameters in URL",
                category="URL Risk Indicators",
                severity="low",
                evidence=f"Tracking parameters detected: {', '.join(sorted(found_trackers))}",
                explanation=(
                    "This URL contains marketing or analytics tracking parameters. "
                    "If this URL is shared publicly or stored in a document, "
                    "it can reveal information about the context in which it was generated "
                    "(e.g., which email campaign, ad, or referral source)."
                ),
                consequence=(
                    "Third parties receiving the URL may determine your referral source, "
                    "campaign context, or browsing behaviour."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _safe_display(raw_url: str, max_len: int = 80) -> str:
    """
    Return a display-safe version of a URL:
    - credentials are redacted
    - the string is truncated
    """
    try:
        p = urlparse(raw_url)
        if p.username or p.password:
            netloc = p.hostname or ""
            if p.port:
                netloc += f":{p.port}"
            safe = p._replace(netloc=netloc).geturl()
        else:
            safe = raw_url
    except Exception:
        safe = raw_url

    if len(safe) > max_len:
        safe = safe[:max_len] + "…"
    return safe
