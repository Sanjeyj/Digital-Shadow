"""
analyzer/risk_scoring.py
Deterministic, explainable risk-scoring engine.

DISCLAIMER: The scores produced here are heuristic estimates based on
weighted severity contributions from deterministic, rule-based detection.
They are NOT a probability of identity theft, a formal security audit result,
or an insurance assessment. They should not be used for legal or regulatory
compliance purposes without independent expert review.
"""

from __future__ import annotations

from config import get_config


_cfg = get_config()
_WEIGHTS = _cfg.SEVERITY_WEIGHTS
_MAX_SCORE = _cfg.SCORE_CRITICAL_MAX


def compute_score(findings: list[dict]) -> dict:
    """
    Compute the aggregate heuristic risk score from a list of finding dicts.

    Each finding must contain:
        - rule_id      (str)   – unique rule identifier
        - severity     (str)   – one of: low | medium | high | critical
        - score_contribution (int) – already computed per-finding contribution

    Returns a result dict with:
        total_score, risk_category, score_breakdown, disclaimer, capped
    """
    seen_rules: set[str] = set()
    breakdown: list[dict] = []
    running_total = 0

    for f in findings:
        rule_id = f.get("rule_id", "UNKNOWN")
        severity = f.get("severity", "low").lower()
        contribution = f.get("score_contribution", _WEIGHTS.get(severity, 5))

        # Deduplicate: the same rule may not be counted twice.
        if rule_id in seen_rules:
            continue
        seen_rules.add(rule_id)

        running_total += contribution
        breakdown.append(
            {
                "rule_id": rule_id,
                "title": f.get("title", rule_id),
                "severity": severity,
                "contribution": contribution,
                "running_total": min(running_total, _MAX_SCORE),
            }
        )

    capped = running_total > _MAX_SCORE
    total_score = min(running_total, _MAX_SCORE)
    risk_category = _categorize(total_score)

    return {
        "total_score": total_score,
        "raw_score": running_total,
        "capped": capped,
        "risk_category": risk_category,
        "score_breakdown": breakdown,
        "disclaimer": (
            "This score is a heuristic risk indicator computed from weighted, "
            "rule-based analysis of the information you supplied. It is NOT a "
            "probability of identity theft, a formal security audit, or a legal "
            "assessment. Use it alongside professional security advice."
        ),
    }


def _categorize(score: int) -> str:
    cfg = get_config()
    if score <= cfg.SCORE_LOW_MAX:
        return "Low"
    if score <= cfg.SCORE_MODERATE_MAX:
        return "Moderate"
    if score <= cfg.SCORE_HIGH_MAX:
        return "High"
    return "Critical"


def severity_contribution(severity: str) -> int:
    """Return the score contribution for a given severity label."""
    return _WEIGHTS.get(severity.lower(), 5)


def build_finding(
    *,
    rule_id: str,
    title: str,
    category: str,
    severity: str,
    evidence: str,
    explanation: str,
    consequence: str,
    recommendation_action: str,
    recommendation_detail: str,
) -> dict:
    """
    Construct a standardised finding dict.
    All callers must use keyword arguments to prevent parameter mismatches.
    """
    contribution = severity_contribution(severity)
    return {
        "rule_id": rule_id,
        "title": title,
        "category": category,
        "severity": severity,
        "evidence": evidence,
        "explanation": explanation,
        "consequence": consequence,
        "recommendation_action": recommendation_action,
        "recommendation_detail": recommendation_detail,
        "score_contribution": contribution,
    }
