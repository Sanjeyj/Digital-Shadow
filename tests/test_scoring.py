"""
tests/test_scoring.py
Tests for the risk-scoring engine.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analyzer.risk_scoring import compute_score, build_finding, severity_contribution


# ── Severity weight tests ─────────────────────────────────────────────────────

class TestSeverityWeights:
    def test_low_weight(self):
        assert severity_contribution('low') == 5

    def test_medium_weight(self):
        assert severity_contribution('medium') == 10

    def test_high_weight(self):
        assert severity_contribution('high') == 20

    def test_critical_weight(self):
        assert severity_contribution('critical') == 30

    def test_unknown_defaults_to_low(self):
        assert severity_contribution('unknown_sev') == 5

    def test_case_insensitive(self):
        assert severity_contribution('HIGH') == 20
        assert severity_contribution('Critical') == 30


# ── Score computation tests ───────────────────────────────────────────────────

def _make_finding(rule_id, severity):
    return build_finding(
        rule_id=rule_id,
        title=f'Test finding {rule_id}',
        category='Test',
        severity=severity,
        evidence='test evidence',
        explanation='test explanation',
        consequence='test consequence',
        recommendation_action='test action',
        recommendation_detail='test detail',
    )


class TestComputeScore:
    def test_empty_findings_score_zero(self):
        result = compute_score([])
        assert result['total_score'] == 0
        assert result['risk_category'] == 'Low'

    def test_single_low_finding(self):
        result = compute_score([_make_finding('TEST_LOW', 'low')])
        assert result['total_score'] == 5

    def test_single_medium_finding(self):
        result = compute_score([_make_finding('TEST_MED', 'medium')])
        assert result['total_score'] == 10

    def test_single_high_finding(self):
        result = compute_score([_make_finding('TEST_HIGH', 'high')])
        assert result['total_score'] == 20

    def test_single_critical_finding(self):
        result = compute_score([_make_finding('TEST_CRIT', 'critical')])
        assert result['total_score'] == 30

    def test_multiple_findings_sum(self):
        findings = [
            _make_finding('A', 'low'),      # 5
            _make_finding('B', 'medium'),   # 10
            _make_finding('C', 'high'),     # 20
        ]
        result = compute_score(findings)
        assert result['total_score'] == 35

    def test_score_capped_at_100(self):
        """Score must never exceed 100."""
        findings = [_make_finding(f'R{i}', 'critical') for i in range(10)]  # 10 × 30 = 300
        result = compute_score(findings)
        assert result['total_score'] == 100
        assert result['capped'] is True

    def test_deduplication_same_rule(self):
        """Duplicate rule_ids must not be counted twice."""
        findings = [
            _make_finding('SAME_RULE', 'high'),
            _make_finding('SAME_RULE', 'high'),
        ]
        result = compute_score(findings)
        assert result['total_score'] == 20  # counted only once

    def test_deduplication_different_rules(self):
        """Different rule_ids must each be counted."""
        findings = [
            _make_finding('RULE_A', 'medium'),
            _make_finding('RULE_B', 'medium'),
        ]
        result = compute_score(findings)
        assert result['total_score'] == 20


# ── Risk category boundary tests ──────────────────────────────────────────────

class TestRiskCategories:
    def _score_result(self, score):
        """Create a synthetic result at a specific score by building enough findings."""
        # Use one critical (30) + padding lows (5 each)
        findings = []
        remaining = score
        idx = 0
        while remaining >= 30:
            findings.append(_make_finding(f'CRIT_{idx}', 'critical'))
            remaining -= 30
            idx += 1
        while remaining >= 20:
            findings.append(_make_finding(f'HIGH_{idx}', 'high'))
            remaining -= 20
            idx += 1
        while remaining >= 10:
            findings.append(_make_finding(f'MED_{idx}', 'medium'))
            remaining -= 10
            idx += 1
        while remaining >= 5:
            findings.append(_make_finding(f'LOW_{idx}', 'low'))
            remaining -= 5
            idx += 1
        return compute_score(findings)

    def test_score_0_is_low(self):
        assert compute_score([])['risk_category'] == 'Low'

    def test_score_19_is_low(self):
        result = self._score_result(15)  # closest buildable below 19
        assert result['risk_category'] == 'Low'

    def test_score_20_is_moderate(self):
        result = self._score_result(20)
        assert result['risk_category'] == 'Moderate'

    def test_score_39_is_moderate(self):
        result = self._score_result(35)
        assert result['risk_category'] == 'Moderate'

    def test_score_40_is_high(self):
        result = self._score_result(40)
        assert result['risk_category'] == 'High'

    def test_score_69_is_high(self):
        result = self._score_result(65)
        assert result['risk_category'] == 'High'

    def test_score_70_is_critical(self):
        result = self._score_result(70)
        assert result['risk_category'] == 'Critical'

    def test_score_100_is_critical(self):
        findings = [_make_finding(f'C{i}', 'critical') for i in range(10)]
        result = compute_score(findings)
        assert result['risk_category'] == 'Critical'
        assert result['total_score'] == 100


# ── Score breakdown tests ─────────────────────────────────────────────────────

class TestScoreBreakdown:
    def test_breakdown_present(self):
        findings = [_make_finding('TEST', 'medium')]
        result = compute_score(findings)
        assert len(result['score_breakdown']) == 1

    def test_breakdown_has_correct_fields(self):
        findings = [_make_finding('RULE_X', 'high')]
        bd = compute_score(findings)['score_breakdown'][0]
        assert bd['rule_id'] == 'RULE_X'
        assert bd['contribution'] == 20
        assert bd['severity'] == 'high'

    def test_disclaimer_present(self):
        result = compute_score([])
        assert len(result.get('disclaimer', '')) > 20
