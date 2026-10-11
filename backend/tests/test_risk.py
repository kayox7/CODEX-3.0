"""Tests for Deterministic Blast Radius Risk Scorer.
Verifies exact boundary conditions at 0.25 and 0.60 and explainability.
"""
from app.services.risk_service import calculate_blast_radius

def test_risk_score_low_boundary():
    """Score strictly below 0.25 maps to LOW risk."""
    # amount=200 -> money_factor = 0.002, 0.4*0.002 = 0.0008
    # records=1 -> records_factor = 0.0001, 0.3*0.0001 = 0.00003
    # reversibility='reversible' -> irrev_factor = 0.0
    # raw_score ~ 0.00083
    res = calculate_blast_radius(
        amount=200.0,
        records_affected=1,
        reversibility="reversible",
        data_class="internal",
        action="issue_refund"
    )
    assert res["score"] < 0.25
    assert res["risk_level"] == "LOW"
    assert "LOW risk" in res["explanation"]

def test_risk_score_exact_boundary_0_25():
    """
    Score exactly 0.25 is on the threshold:
    money_factor = 25000 / 100000 = 0.25 -> 0.4 * 0.25 = 0.10
    records_factor = 0
    irrev_factor (partially) = 0.5 -> 0.3 * 0.5 = 0.15
    Total score = 0.10 + 0 + 0.15 = 0.25 -> Must be MEDIUM.
    """
    res = calculate_blast_radius(
        amount=25000.0,
        records_affected=0,
        reversibility="partially",
        data_class="internal",
        action="issue_refund"
    )
    assert res["score"] == 0.25
    assert res["risk_level"] == "MEDIUM"

def test_risk_score_just_below_0_25():
    """Score just below 0.25 (e.g. 0.249) maps to LOW."""
    # amount = 24750 -> 0.4 * 0.2475 = 0.099 + 0.15 = 0.249
    res = calculate_blast_radius(
        amount=24750.0,
        records_affected=0,
        reversibility="partially",
        data_class="internal",
        action="issue_refund"
    )
    assert res["score"] == 0.249
    assert res["risk_level"] == "LOW"

def test_risk_score_exact_boundary_0_60():
    """
    Score exactly 0.60 is the upper threshold for MEDIUM:
    amount = 37500 -> 0.4 * 0.375 = 0.15
    records = 10000 -> 0.3 * 1.0 = 0.30
    irrev (partially) -> 0.3 * 0.5 = 0.15
    Total = 0.15 + 0.30 + 0.15 = 0.60 -> Must be MEDIUM.
    """
    res = calculate_blast_radius(
        amount=37500.0,
        records_affected=10000,
        reversibility="partially",
        data_class="internal",
        action="issue_refund"
    )
    assert res["score"] == 0.60
    assert res["risk_level"] == "MEDIUM"

def test_risk_score_above_0_60_high():
    """Score above 0.60 maps to HIGH risk."""
    # amount = 80000 -> 0.4 * 0.8 = 0.32
    # records = 5000 -> 0.3 * 0.5 = 0.15
    # irrev (irreversible) -> 0.3 * 1.0 = 0.30
    # Total = 0.32 + 0.15 + 0.30 = 0.77 (> 0.60)
    res = calculate_blast_radius(
        amount=80000.0,
        records_affected=5000,
        reversibility="irreversible",
        data_class="internal",
        action="issue_refund"
    )
    assert res["score"] > 0.60
    assert res["risk_level"] == "HIGH"
    assert "HIGH risk" in res["explanation"]

def test_restricted_data_class_overrides_to_restricted():
    """Any action involving 'restricted' data class is designated RESTRICTED."""
    res = calculate_blast_radius(
        amount=10.0,
        records_affected=1,
        reversibility="reversible",
        data_class="restricted",
        action="issue_refund"
    )
    assert res["risk_level"] == "RESTRICTED"
    assert "RESTRICTED" in res["explanation"]

def test_novel_action_overrides_to_restricted():
    """Unknown or unregistered action types are flagged as RESTRICTED (Human-Only)."""
    res = calculate_blast_radius(
        amount=0.0,
        records_affected=0,
        reversibility="reversible",
        data_class="public",
        action="unregistered_experimental_action"
    )
    assert res["risk_level"] == "RESTRICTED"
    assert "Novel/unregistered" in res["explanation"]
