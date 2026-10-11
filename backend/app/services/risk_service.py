"""Deterministic, explainable Blast Radius risk scorer for pre-execution actions.
Calculates blast radius from financial exposure, affected record count, and irreversibility.
"""
from typing import Any, Dict

IRREVERSIBILITY_WEIGHTS = {
    "reversible": 0.0,
    "partially": 0.5,
    "irreversible": 1.0
}

KNOWN_ACTIONS = {
    "issue_refund",
    "update_record",
    "view_order",
    "sync_records",
    "vendor_payout",
    "export_customers",
    "send_email",
    "create_ticket"
}

def calculate_blast_radius(
    amount: float,
    records_affected: int,
    reversibility: str,
    data_class: str,
    action: str
) -> Dict[str, Any]:
    """
    Compute deterministic Blast Radius score:
    score = 0.4 * money_factor + 0.3 * records_factor + 0.3 * irreversibility_factor
    Thresholds:
    - score < 0.25: LOW
    - 0.25 <= score <= 0.60: MEDIUM
    - score > 0.60: HIGH
    - data_class == 'restricted' or novel action: RESTRICTED
    """
    safe_amount = max(float(amount or 0.0), 0.0)
    safe_records = max(int(records_affected or 0), 0)
    rev_key = reversibility.lower().strip() if reversibility else "partially"
    irrev_factor = IRREVERSIBILITY_WEIGHTS.get(rev_key, 0.5)

    money_factor = min(safe_amount / 100000.0, 1.0)
    records_factor = min(safe_records / 10000.0, 1.0)

    raw_score = (0.4 * money_factor) + (0.3 * records_factor) + (0.3 * irrev_factor)
    score = round(raw_score, 4)

    is_novel = action not in KNOWN_ACTIONS
    is_restricted_data = (data_class or "").lower() == "restricted"

    if is_restricted_data or is_novel:
        risk_level = "RESTRICTED"
        if is_restricted_data and is_novel:
            explanation = f"RESTRICTED: Involves restricted data classification '{data_class}' and unknown/novel action '{action}'"
        elif is_restricted_data:
            explanation = f"RESTRICTED: Data classification '{data_class}' requires human-only execution"
        else:
            explanation = f"RESTRICTED: Novel/unregistered action type '{action}' detected"
    elif score < 0.25:
        risk_level = "LOW"
        explanation = f"LOW risk (score {score:.2f} < 0.25): Contained blast radius (Rs {safe_amount:,.2f}, {safe_records} records, {rev_key})"
    elif score <= 0.60:
        risk_level = "MEDIUM"
        explanation = f"MEDIUM risk (score {score:.2f} between 0.25 and 0.60): Requires human approval (Rs {safe_amount:,.2f}, {safe_records} records, {rev_key})"
    else:
        risk_level = "HIGH"
        explanation = f"HIGH risk (score {score:.2f} > 0.60): Critical blast radius requires expedited human approval (Rs {safe_amount:,.2f}, {safe_records} records, {rev_key})"

    return {
        "score": score,
        "risk_level": risk_level,
        "money_factor": round(money_factor, 4),
        "records_factor": round(records_factor, 4),
        "irreversibility_factor": round(irrev_factor, 4),
        "explanation": explanation
    }
