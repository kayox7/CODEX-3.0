"""Tests for Audit Report Generation (CSV, JSON, HTML)."""

def test_audit_report_csv_generation(client, admin_headers):
    """CSV audit report returns 200, proper attachment headers, and CSV content."""
    res = client.get("/reports/audit?format=csv", headers=admin_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    text = res.text
    assert "ID,Timestamp (UTC),Event Type,Actor" in text
    assert "GENESIS" in text

def test_audit_report_json_generation(client, admin_headers):
    """JSON audit report returns structured list of ledger records."""
    res = client.get("/reports/audit?format=json", headers=admin_headers)
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    first_record = data[0]
    assert "prev_hash" in first_record
    assert "hash" in first_record
    assert first_record["event_type"] == "GENESIS"

def test_audit_report_html_generation(client, admin_headers):
    """HTML audit report returns printable document with styled tables and badges."""
    res = client.get("/reports/audit?format=html", headers=admin_headers)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text
    assert "WARDEN: AI Agent Governance Audit Report" in html
    assert "GENESIS" in html
    assert "<table" in html
