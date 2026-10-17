"""
analyzer/patterns.py — Deterministic regex patterns used across the engine.
All patterns are compiled once at import time for efficiency.
Patterns are intentionally conservative: they must match only what they claim.
"""

import re

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,253}\.[a-zA-Z]{2,}\b"
)

# ── Phone – international and local formats (intentionally broad) ─────────────
PHONE_PATTERN = re.compile(
    r"""
    (?<!\w)                         # no letter/digit before
    (?:
        \+?[1-9]\d{0,2}             # optional country code
        [\s\-.]?
    )?
    (?:
        \(?\d{2,4}\)?               # area/STD code
        [\s\-.]?
    )?
    \d{3,5}                         # first group
    [\s\-.]?
    \d{3,5}                         # second group
    (?!\w)                          # no letter/digit after
    """,
    re.VERBOSE,
)

# Stricter phone: must have ≥ 10 digits when combined
PHONE_MIN_DIGITS = 9

# ── Birth-date-like patterns ──────────────────────────────────────────────────
DATE_OF_BIRTH_PATTERNS = [
    # DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD with / - .
    re.compile(
        r"\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}\b"
    ),
    # YYYY-MM-DD
    re.compile(
        r"\b(19|20)\d{2}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}\b"
    ),
    # Textual: "born on 12 March 1995", "DOB: 1990-05-22"
    re.compile(
        r"(?i)\b(?:dob|date\s+of\s+birth|born\s+(?:on)?)\s*[:\-]?\s*"
        r"(?:\d{1,2}[\s\-\/\.]\w{3,9}[\s\-\/\.]\d{2,4}|\d{1,2}[\-\/\.]\d{1,2}[\-\/\.]\d{2,4})"
    ),
]

# ── Postal-address indicators ────────────────────────────────────────────────
# Heuristic: a line/phrase that looks like a street or postcode
ADDRESS_PATTERNS = [
    # US ZIP:  12345 or 12345-6789
    re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    # UK postcode: SW1A 2AA
    re.compile(
        r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE
    ),
    # IN pincode: 6-digit number prefixed by "pin" or standalone
    re.compile(r"(?i)\bpin(?:code)?[\s:\-]*\d{6}\b|\b[1-9]\d{5}\b"),
    # Generic street: number + road/street/avenue/lane/drive
    re.compile(
        r"(?i)\b\d+\s+\w+(?:\s+\w+)?\s+"
        r"(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|"
        r"boulevard|blvd|court|ct|place|pl|way|close|crescent)\b"
    ),
]

# ── Username / handle ─────────────────────────────────────────────────────────
# Matches a handle-like token starting with @
AT_HANDLE_PATTERN = re.compile(r"@([A-Za-z0-9_\.]{2,64})")

# ── URL – simple detector (full parsing done via urllib.parse) ────────────────
URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]{4,500}", re.IGNORECASE
)

# ── Sensitive filenames ───────────────────────────────────────────────────────
SENSITIVE_FILENAME_KEYWORDS = re.compile(
    r"(?i)(?:^|[\W_]|[_\-])"
    r"("
    r"password|passwd|secret|credential|private.?key|"
    r"ssn|national.?id|passport|tax.?return|bank.?statement|"
    r"medical|health.?record|confidential|salary|payslip"
    r")"
    r"(?:[\W_]|[_\-]|$|\.\w+$)"
)

# ── Tracking parameters ───────────────────────────────────────────────────────
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ttclid", "dclid", "mc_cid", "mc_eid",
    "_ga", "ref", "source", "affiliate", "partner",
}

# ── Suspicious hostname indicators ───────────────────────────────────────────
IP_PATTERN = re.compile(
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
)

PUNYCODE_PATTERN = re.compile(r"xn--", re.IGNORECASE)

NON_STANDARD_PORTS = {8080, 8443, 8888, 9000, 9090, 4000, 3000, 5000, 5173}
