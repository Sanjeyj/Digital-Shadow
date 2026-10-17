"""
analyzer/recommendations.py
Maps rule IDs to mitigation advice for each exposure finding.
"""

from __future__ import annotations

# ── Per-rule recommendations ──────────────────────────────────────────────────

RECOMMENDATIONS: dict[str, dict] = {
    # Contact exposure
    "CONTACT_EMAIL_IN_TEXT": {
        "action": "Remove or obfuscate your email address from public text.",
        "detail": (
            "Use a contact form instead of publishing your address directly. "
            "If you must share it, consider using a purpose-specific address "
            "(e.g., yourname+public@example.com) that you can disable if it receives spam."
        ),
    },
    "CONTACT_PHONE_IN_TEXT": {
        "action": "Remove your phone number from public-facing text.",
        "detail": (
            "Phone numbers can be used for social engineering, SIM-swapping attacks, "
            "and robocall campaigns. Use a VoIP number or a messaging handle instead."
        ),
    },
    "CONTACT_COMBINATION": {
        "action": "Avoid publishing multiple contact details in the same location.",
        "detail": (
            "A name, email, and phone number in the same profile gives attackers "
            "enough to craft highly targeted phishing messages."
        ),
    },
    # Personal information
    "PERSONAL_DOB_PATTERN": {
        "action": "Remove or obscure dates that could reveal your date of birth.",
        "detail": (
            "Date of birth is frequently used as a knowledge-based authentication "
            "factor. Publishing it publicly weakens account-recovery security."
        ),
    },
    "PERSONAL_ADDRESS_PATTERN": {
        "action": "Remove street addresses or postcodes from public profiles.",
        "detail": (
            "Even partial addresses can be combined with other data sources "
            "to determine your location. Use a P.O. box or omit the field entirely."
        ),
    },
    "PERSONAL_MULTI_ATTRIBUTE": {
        "action": "Reduce the number of personal attributes published together.",
        "detail": (
            "The combination of name, location, and contact details forms a "
            "highly identifying profile. Remove or generalize at least one attribute."
        ),
    },
    # Profile exposure
    "PROFILE_URL_PROVIDED": {
        "action": "Review the privacy settings on each linked public profile.",
        "detail": (
            "Check that each profile only reveals information you are comfortable "
            "with anyone seeing. Consider using platform privacy controls to restrict "
            "profile visibility to connections or authenticated users."
        ),
    },
    "PROFILE_MULTIPLE_URLS": {
        "action": "Limit the number of platforms you link to from a single source.",
        "detail": (
            "Linking to many platforms from one location allows an observer to "
            "build a comprehensive profile by cross-referencing each account."
        ),
    },
    "PROFILE_USERNAME_REUSE": {
        "action": "Use different usernames across platforms where possible.",
        "detail": (
            "A consistent username makes it trivial to correlate accounts across "
            "services. Even minor variations (e.g., adding a number) reduce linkability."
        ),
    },
    # Document metadata
    "DOC_SENSITIVE_FILENAME": {
        "action": "Rename files before sharing so the filename reveals no sensitive context.",
        "detail": (
            "Filenames like 'salary_2024.pdf' or 'medical_report.docx' disclose "
            "the nature of the document before anyone opens it."
        ),
    },
    "DOC_AUTHOR_METADATA": {
        "action": "Strip document metadata before sharing.",
        "detail": (
            "PDF and DOCX files often store the author's name, organization, "
            "and software version. Use 'File → Properties → Remove Personal Information' "
            "or a dedicated metadata-removal tool before distributing documents."
        ),
    },
    "DOC_SOFTWARE_METADATA": {
        "action": "Remove or sanitize document creator/producer metadata before sharing.",
        "detail": (
            "The software version used to create a document can reveal information "
            "about your system that attackers may exploit for targeted attacks."
        ),
    },
    # URL indicators
    "URL_NON_HTTPS": {
        "action": "Use HTTPS URLs wherever possible.",
        "detail": (
            "Plain HTTP transmits data in cleartext, making it susceptible to "
            "eavesdropping. If the site offers HTTPS, update your links. "
            "If it does not, consider whether the site is trustworthy."
        ),
    },
    "URL_CREDENTIALS_EMBEDDED": {
        "action": "Remove credentials from URLs immediately.",
        "detail": (
            "Credentials embedded in a URL (e.g., https://user:pass@example.com) "
            "are logged by servers, proxies, and browser history. Rotate the "
            "affected credentials as soon as possible."
        ),
    },
    "URL_SUSPICIOUS_HOST": {
        "action": "Verify whether this hostname is legitimate before using the URL.",
        "detail": (
            "IP-address hostnames, punycode domains, and unusual port numbers "
            "are commonly used in phishing and malware distribution. "
            "Compare the domain with the legitimate service's known address."
        ),
    },
    "URL_TRACKING_PARAMS": {
        "action": "Remove marketing tracking parameters before sharing URLs.",
        "detail": (
            "Parameters like utm_source or fbclid reveal information about "
            "your browsing context. Use a URL cleaner or remove them manually."
        ),
    },
    "URL_NON_STANDARD_PORT": {
        "action": "Verify the purpose of the non-standard port in this URL.",
        "detail": (
            "Non-standard ports can indicate developer services or misconfigured "
            "servers that may lack proper security hardening."
        ),
    },
    # Combination risk
    "COMBINATION_NAME_CONTACT": {
        "action": "Reduce the co-location of your name and contact information.",
        "detail": (
            "Your name combined with contact details is sufficient for spear-phishing. "
            "Use a pseudonym or alias where the platform permits it."
        ),
    },
    "COMBINATION_USERNAME_PROFILES": {
        "action": "Avoid linking the same username across multiple profile pages.",
        "detail": (
            "Cross-platform username correlation is the first step many OSINT "
            "researchers take. Distinct usernames significantly increase your privacy."
        ),
    },
}

GENERIC_RECOMMENDATION = {
    "action": "Review this finding and consider reducing your digital footprint.",
    "detail": (
        "Evaluate whether the identified information is necessary to publish "
        "and whether privacy settings on the relevant platform can be tightened."
    ),
}


def get_recommendation(rule_id: str) -> dict:
    """Return the recommendation dict for a rule ID, falling back to a generic one."""
    return RECOMMENDATIONS.get(rule_id, GENERIC_RECOMMENDATION)
