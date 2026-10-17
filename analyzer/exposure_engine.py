"""
analyzer/exposure_engine.py
Main analysis engine. Applies deterministic rules to user-supplied data
and returns a structured list of findings.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from analyzer.patterns import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    PHONE_MIN_DIGITS,
    DATE_OF_BIRTH_PATTERNS,
    ADDRESS_PATTERNS,
    AT_HANDLE_PATTERN,
    URL_PATTERN,
)
from analyzer.recommendations import get_recommendation
from analyzer.risk_scoring import build_finding


def run_exposure_analysis(data: dict) -> list[dict]:
    """
    Run all exposure rules against the supplied user data dict.

    Expected keys (all optional):
        username        str
        email           str
        profile_urls    list[str]
        website_urls    list[str]
        profile_text    str
        document_findings list[dict]  – pre-computed by metadata_analyzer

    Returns a deduplicated list of finding dicts.
    """
    findings: list[dict] = []
    seen_rule_ids: set[str] = set()

    username: str = (data.get("username") or "").strip()
    email: str = (data.get("email") or "").strip()
    profile_urls: list[str] = data.get("profile_urls") or []
    website_urls: list[str] = data.get("website_urls") or []
    profile_text: str = (data.get("profile_text") or "").strip()
    doc_findings: list[dict] = data.get("document_findings") or []

    # Combine all text for pattern matching
    all_text_parts = [username, email, profile_text]
    all_text = " ".join(p for p in all_text_parts if p)

    # ── A. Contact information exposure ───────────────────────────────────────
    _add_unique(findings, seen_rule_ids, _check_email_exposure(email, profile_text))
    _add_unique(findings, seen_rule_ids, _check_phone_exposure(all_text))

    # ── B. Personal information disclosure ────────────────────────────────────
    _add_unique(findings, seen_rule_ids, _check_dob_patterns(all_text))
    _add_unique(findings, seen_rule_ids, _check_address_patterns(all_text))

    # ── C. Public profile exposure ────────────────────────────────────────────
    all_urls = profile_urls + website_urls
    _add_unique(findings, seen_rule_ids, _check_profile_urls(profile_urls))
    _add_unique(findings, seen_rule_ids, _check_multiple_urls(all_urls))
    _add_unique(findings, seen_rule_ids, _check_username_reuse(username, all_urls))

    # ── D. Document findings (passed in pre-computed) ─────────────────────────
    for df in doc_findings:
        _add_unique(findings, seen_rule_ids, [df])

    # ── E. (URL analysis findings are merged by the caller) ───────────────────

    # ── F. Information combination risk ───────────────────────────────────────
    _add_unique(findings, seen_rule_ids, _check_name_contact_combination(
        username, email, all_text))
    _add_unique(findings, seen_rule_ids, _check_username_profiles_combination(
        username, all_urls))
    _add_unique(findings, seen_rule_ids, _check_multi_attribute_combination(
        username, email, profile_text))

    return findings


# ── A. Contact information ────────────────────────────────────────────────────

def _check_email_exposure(email: str, text: str) -> list[dict]:
    findings = []
    detected_emails = set()

    if email:
        detected_emails.add(email)

    for match in EMAIL_PATTERN.finditer(text):
        detected_emails.add(match.group())

    if detected_emails:
        rec = get_recommendation("CONTACT_EMAIL_IN_TEXT")
        sample = ", ".join(sorted(detected_emails)[:3])
        findings.append(
            build_finding(
                rule_id="CONTACT_EMAIL_IN_TEXT",
                title="Email address present in supplied data",
                category="Contact Information Exposure",
                severity="medium",
                evidence=f"Email address(es) detected: {sample}",
                explanation=(
                    "Your email address appears in the supplied information. "
                    "Email addresses published in public profiles or documents "
                    "are harvested by spam bots and used as phishing entry points."
                ),
                consequence=(
                    "Your address may receive spam, phishing attempts, and "
                    "be used in credential-stuffing attacks if associated with "
                    "reused passwords."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_phone_exposure(text: str) -> list[dict]:
    findings = []
    candidates = PHONE_PATTERN.findall(text)
    valid_phones = []
    for c in candidates:
        digits = re.sub(r"\D", "", c)
        if len(digits) >= PHONE_MIN_DIGITS:
            valid_phones.append(c.strip())

    # Deduplicate
    valid_phones = list(dict.fromkeys(valid_phones))

    if valid_phones:
        rec = get_recommendation("CONTACT_PHONE_IN_TEXT")
        sample = ", ".join(valid_phones[:3])
        findings.append(
            build_finding(
                rule_id="CONTACT_PHONE_IN_TEXT",
                title="Phone-number-like pattern in supplied text",
                category="Contact Information Exposure",
                severity="medium",
                evidence=f"Phone-like pattern(s): {sample}",
                explanation=(
                    "A phone number pattern was detected in the supplied text. "
                    "Note: this is a heuristic match and may include numbers that "
                    "are not phone numbers. If a phone number is genuinely present, "
                    "it can be used for spam calls, SIM-swapping, and social engineering."
                ),
                consequence=(
                    "Phone numbers can be used to bypass SMS-based two-factor "
                    "authentication via SIM-swapping attacks."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── B. Personal information ───────────────────────────────────────────────────

def _check_dob_patterns(text: str) -> list[dict]:
    findings = []
    for pattern in DATE_OF_BIRTH_PATTERNS:
        if pattern.search(text):
            rec = get_recommendation("PERSONAL_DOB_PATTERN")
            findings.append(
                build_finding(
                    rule_id="PERSONAL_DOB_PATTERN",
                    title="Date-of-birth-like pattern in supplied data",
                    category="Personal Information Disclosure",
                    severity="high",
                    evidence="A date-of-birth-like pattern was matched in the submitted text.",
                    explanation=(
                        "The supplied data contains a pattern that resembles a date of birth. "
                        "Dates of birth are used as knowledge-based authentication factors "
                        "by banks, government services, and customer-support lines."
                    ),
                    consequence=(
                        "An attacker may use your date of birth to reset passwords, "
                        "impersonate you in support calls, or pass identity verification checks."
                    ),
                    recommendation_action=rec["action"],
                    recommendation_detail=rec["detail"],
                )
            )
            break  # one finding per category is sufficient
    return findings


def _check_address_patterns(text: str) -> list[dict]:
    findings = []
    for pattern in ADDRESS_PATTERNS:
        if pattern.search(text):
            rec = get_recommendation("PERSONAL_ADDRESS_PATTERN")
            findings.append(
                build_finding(
                    rule_id="PERSONAL_ADDRESS_PATTERN",
                    title="Postal-address-like pattern detected",
                    category="Personal Information Disclosure",
                    severity="high",
                    evidence="An address-like pattern (street, postcode, or PIN) was matched.",
                    explanation=(
                        "The supplied text contains a pattern resembling a street address "
                        "or postcode. Physical location data has high re-identification value "
                        "when combined with other personal attributes. "
                        "Note: this is a heuristic match and may produce false positives."
                    ),
                    consequence=(
                        "Your location may be inferred by anyone who reads the text, "
                        "enabling physical surveillance or targeted attacks."
                    ),
                    recommendation_action=rec["action"],
                    recommendation_detail=rec["detail"],
                )
            )
            break
    return findings


# ── C. Public profile exposure ────────────────────────────────────────────────

def _check_profile_urls(profile_urls: list[str]) -> list[dict]:
    findings = []
    valid_urls = [u for u in profile_urls if u.strip().startswith(("http://", "https://"))]
    if valid_urls:
        rec = get_recommendation("PROFILE_URL_PROVIDED")
        sample = valid_urls[:3]
        findings.append(
            build_finding(
                rule_id="PROFILE_URL_PROVIDED",
                title="Public profile URL(s) supplied",
                category="Public Profile Exposure",
                severity="low",
                evidence=f"{len(valid_urls)} profile URL(s) provided. Examples: "
                         + "; ".join(sample),
                explanation=(
                    "You have provided links to public profiles. Each profile may "
                    "expose additional personal information depending on the platform's "
                    "privacy settings and what you have shared there. "
                    "This application does not fetch or inspect these URLs."
                ),
                consequence=(
                    "Each linked profile may individually expose limited information, "
                    "but multiple profiles together can significantly increase "
                    "your identifiability."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_multiple_urls(all_urls: list[str]) -> list[dict]:
    findings = []
    valid = [u for u in all_urls if u.strip().startswith(("http://", "https://"))]
    if len(valid) >= 3:
        rec = get_recommendation("PROFILE_MULTIPLE_URLS")
        findings.append(
            build_finding(
                rule_id="PROFILE_MULTIPLE_URLS",
                title=f"Multiple public URLs provided ({len(valid)} links)",
                category="Public Profile Exposure",
                severity="medium",
                evidence=f"{len(valid)} URLs supplied across profile and website fields.",
                explanation=(
                    "You have supplied three or more URLs. An observer who collects "
                    "all of these can cross-reference the accounts to build a richer "
                    "picture of your online identity than any single account reveals."
                ),
                consequence=(
                    "Cross-platform correlation allows an observer to deduce interests, "
                    "routines, relationships, and contact details not visible in any "
                    "single profile."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_username_reuse(username: str, urls: list[str]) -> list[dict]:
    findings = []
    if not username or len(username) < 3:
        return findings

    u_lower = username.lower()
    reused_in = []
    for url in urls:
        try:
            parsed = urlparse(url)
            path_lower = (parsed.path or "").lower()
            netloc_lower = (parsed.netloc or "").lower()
            if u_lower in path_lower or u_lower in netloc_lower:
                reused_in.append(url[:80])
        except Exception:
            continue

    if len(reused_in) >= 2:
        rec = get_recommendation("PROFILE_USERNAME_REUSE")
        findings.append(
            build_finding(
                rule_id="PROFILE_USERNAME_REUSE",
                title="Username appears in multiple supplied URLs",
                category="Public Profile Exposure",
                severity="medium",
                evidence=f"Username '{username}' found in: " + "; ".join(reused_in[:3]),
                explanation=(
                    f"The username '{username}' appears in multiple of the URLs you supplied. "
                    "Using the same username across platforms makes it straightforward to "
                    "link all of your accounts together."
                ),
                consequence=(
                    "An adversary can quickly find all of your linked accounts by "
                    "searching for your username on each platform, revealing a "
                    "comprehensive picture of your online activity."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── F. Combination risk ───────────────────────────────────────────────────────

def _check_name_contact_combination(
    username: str, email: str, text: str
) -> list[dict]:
    findings = []
    has_name = bool(username)
    has_email = bool(email) or bool(EMAIL_PATTERN.search(text))
    has_phone = bool(
        m for m in PHONE_PATTERN.finditer(text)
        if len(re.sub(r"\D", "", m.group())) >= PHONE_MIN_DIGITS
    )

    if has_name and (has_email or has_phone):
        rec = get_recommendation("COMBINATION_NAME_CONTACT")
        contact_types = []
        if has_email:
            contact_types.append("email")
        if has_phone:
            contact_types.append("phone")

        findings.append(
            build_finding(
                rule_id="COMBINATION_NAME_CONTACT",
                title="Name combined with contact information",
                category="Information Combination Risk",
                severity="high",
                evidence=(
                    f"Name/username ('{username}') co-located with "
                    f"{' and '.join(contact_types)} in supplied data."
                ),
                explanation=(
                    "Your name and contact information appear together in the supplied data. "
                    "Individually, a name or an email address may seem harmless. "
                    "Combined, they provide everything needed to impersonate you "
                    "in a targeted phishing message."
                ),
                consequence=(
                    "Spear-phishing attackers can craft convincing messages that "
                    "reference your name and contact you through your stated channel, "
                    "dramatically increasing the likelihood that you or your contacts "
                    "will be deceived."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_username_profiles_combination(
    username: str, urls: list[str]
) -> list[dict]:
    findings = []
    valid_urls = [u for u in urls if u.strip().startswith(("http://", "https://"))]
    if username and len(valid_urls) >= 2:
        rec = get_recommendation("COMBINATION_USERNAME_PROFILES")
        findings.append(
            build_finding(
                rule_id="COMBINATION_USERNAME_PROFILES",
                title="Username linked to multiple public profiles",
                category="Information Combination Risk",
                severity="medium",
                evidence=(
                    f"Username '{username}' supplied alongside "
                    f"{len(valid_urls)} profile/website URL(s)."
                ),
                explanation=(
                    "A named identity linked to multiple public profiles greatly "
                    "increases the amount of information an observer can aggregate. "
                    "Each additional link adds another data source that can reveal "
                    "location, relationships, activities, and opinions."
                ),
                consequence=(
                    "Aggregated profiles can reveal sensitive patterns — such as "
                    "daily routines, employer, political views, or social connections — "
                    "none of which are apparent from any single account."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


def _check_multi_attribute_combination(
    username: str, email: str, text: str
) -> list[dict]:
    findings = []
    attribute_count = sum([
        bool(username),
        bool(email),
        bool(EMAIL_PATTERN.search(text)),
        any(p.search(text) for p in DATE_OF_BIRTH_PATTERNS),
        any(p.search(text) for p in ADDRESS_PATTERNS),
    ])

    if attribute_count >= 3:
        rec = get_recommendation("PERSONAL_MULTI_ATTRIBUTE")
        findings.append(
            build_finding(
                rule_id="PERSONAL_MULTI_ATTRIBUTE",
                title="Multiple identifying attributes detected together",
                category="Information Combination Risk",
                severity="high",
                evidence=(
                    f"At least {attribute_count} identifying attributes were found "
                    "in the supplied data (name, email, dates, address indicators, etc.)."
                ),
                explanation=(
                    "The more identifying attributes that appear together, the easier "
                    "it is to uniquely identify an individual. Research in data privacy "
                    "has shown that as few as three attributes (zip code, birth date, "
                    "and sex) can uniquely identify 87 % of the US population."
                ),
                consequence=(
                    "Your combined profile may be sufficient to uniquely identify you, "
                    "enabling re-identification even from data that has been partially "
                    "anonymized."
                ),
                recommendation_action=rec["action"],
                recommendation_detail=rec["detail"],
            )
        )
    return findings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_unique(
    findings: list[dict],
    seen: set[str],
    new_findings: list[dict],
) -> None:
    """Add findings whose rule_id has not been seen yet."""
    for f in new_findings:
        rid = f.get("rule_id", "")
        if rid not in seen:
            seen.add(rid)
            findings.append(f)
