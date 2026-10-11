"""
WARDEN Demo Agent — Scripted Mode (no external API key needed)
=================================================================
Demonstrates all 4 governance outcomes in sequence:

  Scenario 1: issue_refund Rs 200        → ALLOW        (low risk, allowed action)
  Scenario 2: issue_refund Rs 80,000     → PENDING_APPROVAL (high amount, human required)
  Scenario 3: export_customer_data       → BLOCKED      (out-of-scope action, agent paused)
  Scenario 4: delete_database            → HUMAN_ONLY   (catastrophic, never auto-approved)

Run:
  python demo_agent/run_demo.py

The backend must be running at http://127.0.0.1:8000
(cd backend && python -m uvicorn app.main:app --port 8000 --reload)
"""

import sys
import os
import time
import json
import httpx

WARDEN_URL  = os.getenv("WARDEN_URL", "http://127.0.0.1:8000")
AGENT_ID    = "support_agent_01"
API_KEY     = "wrd_demo_support_key_123"          # seeded in DB
POLL_SECS   = 2                                    # poll interval for PENDING
MAX_POLLS   = 30                                   # 60s max wait per pending action

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
DIM    = "\033[2m"

def banner(text, color=CYAN):
    width = 70
    print(f"\n{color}{BOLD}{'═' * width}")
    print(f"  {text}")
    print(f"{'═' * width}{RESET}")

def section(title, color=BOLD):
    print(f"\n{color}▶  {title}{RESET}")

def ok(msg):    print(f"  {GREEN}✔  {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠  {msg}{RESET}")
def err(msg):   print(f"  {RED}✖  {msg}{RESET}")
def info(msg):  print(f"  {DIM}{msg}{RESET}")


def check_backend():
    """Ensure backend is reachable before running demo."""
    try:
        res = httpx.get(f"{WARDEN_URL}/health", timeout=4)
        res.raise_for_status()
        ok(f"Backend reachable at {WARDEN_URL}")
    except Exception as e:
        err(f"Backend not reachable: {e}")
        print(f"\n  Start it with:")
        print(f"  {CYAN}cd backend && python -m uvicorn app.main:app --port 8000 --reload{RESET}\n")
        sys.exit(1)


def request_action(action: str, params: dict, amount: float = 0.0,
                   records: int = 0, data_class: str = "internal",
                   reversibility: str = "partially") -> dict:
    """Send pre-execution request to WARDEN control layer."""
    payload = {
        "agent_id": AGENT_ID,
        "action":   action,
        "params":   params,
        "amount":   amount,
        "records_affected": records,
        "data_class": data_class,
        "reversibility": reversibility,
    }
    headers = {
        "Content-Type":      "application/json",
        "X-Warden-Api-Key":  API_KEY,
    }
    res = httpx.post(
        f"{WARDEN_URL}/v1/actions/request",
        json=payload,
        headers=headers,
        timeout=10,
    )
    res.raise_for_status()
    return res.json()


def poll_decision(decision_id: str) -> dict:
    """Poll for human approval resolution."""
    print(f"  {YELLOW}⏳ Polling for human approval (decision_id={decision_id})...{RESET}")
    for i in range(MAX_POLLS):
        time.sleep(POLL_SECS)
        try:
            res = httpx.get(f"{WARDEN_URL}/v1/actions/decision/{decision_id}", timeout=5)
            data = res.json()
            decision = data.get("decision")
            if decision in ("ALLOW", "BLOCKED", "HUMAN_ONLY"):
                return data
            print(f"  {DIM}  [{i+1}/{MAX_POLLS}] Still PENDING_APPROVAL...{RESET}", end="\r")
        except Exception as e:
            warn(f"Poll error: {e}")
    return {"decision": "BLOCKED", "explanation": "SLA timed out after demo wait period"}


def print_decision(result: dict):
    """Pretty-print the governance decision."""
    decision = result.get("decision", "UNKNOWN")
    risk     = result.get("risk_score", 0)
    level    = result.get("risk_level", "—")
    explain  = result.get("explanation", "")
    d_id     = result.get("decision_id", "—")

    color = {
        "ALLOW":            GREEN,
        "PENDING_APPROVAL": YELLOW,
        "BLOCKED":          RED,
        "HUMAN_ONLY":       MAGENTA,
    }.get(decision, DIM)

    print(f"\n  {color}{BOLD}Decision: {decision}{RESET}")
    print(f"  {DIM}Risk Score : {risk:.2f}  |  Risk Level : {level}{RESET}")
    print(f"  {DIM}Decision ID: {d_id}{RESET}")
    print(f"  {DIM}Explanation: {explain}{RESET}")


def run_scenario(num: int, title: str, action: str, params: dict,
                 amount: float, records: int, data_class: str,
                 reversibility: str, expected: str):
    banner(f"Scenario {num}: {title}")
    info(f"Action      : {action}")
    info(f"Params      : {json.dumps(params)}")
    info(f"Amount      : Rs {amount:,.0f}")
    info(f"Data Class  : {data_class} | Reversibility: {reversibility}")
    info(f"Expected    : {expected}")
    print()

    try:
        result = request_action(
            action=action, params=params, amount=amount, records=records,
            data_class=data_class, reversibility=reversibility,
        )
        decision = result.get("decision")
        print_decision(result)

        if decision == "PENDING_APPROVAL":
            decision_id = result.get("decision_id")
            warn("Action requires human approval — opening WARDEN Console to approve/reject")
            warn(f"Visit: http://localhost:5173 → Approvals Queue")
            warn(f"Approve or reject decision {decision_id} there, then this demo will continue.")
            final = poll_decision(decision_id)
            print(f"\n  {CYAN}↳ Final resolution:{RESET}")
            print_decision(final)

    except httpx.HTTPStatusError as e:
        err(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        err(f"Error: {e}")

    time.sleep(1.2)


def main():
    banner("WARDEN Demo Agent — Scripted Governance Showcase", CYAN)
    print(f"  Agent ID : {AGENT_ID}")
    print(f"  API Key  : {API_KEY}")
    print(f"  Backend  : {WARDEN_URL}")

    check_backend()

    # ── Scenario 1: Small refund → ALLOW ──────────────────────────────────────
    run_scenario(
        num=1,
        title="Small Refund — Low Risk",
        action="issue_refund",
        params={"order_id": "ORD-10042", "customer_id": "CUST-882"},
        amount=200.0,
        records=1,
        data_class="internal",
        reversibility="partially",
        expected="ALLOW — amount < Rs 10,000 and action is in passport"
    )

    # ── Scenario 2: Large refund → PENDING_APPROVAL ───────────────────────────
    run_scenario(
        num=2,
        title="Large Refund Rs 80,000 — Requires Human Approval",
        action="issue_refund",
        params={"order_id": "ORD-55901", "customer_id": "CUST-7731", "note": "VIP escalation"},
        amount=80000.0,
        records=1,
        data_class="confidential",
        reversibility="partially",
        expected="PENDING_APPROVAL — blast radius high, escalate to human"
    )

    # ── Scenario 3: Out-of-scope export → BLOCKED + agent paused ─────────────
    run_scenario(
        num=3,
        title="Export Customer Data — Out-of-Scope Action",
        action="export_customer_data",
        params={"target": "s3://external-bucket", "rows": 50000},
        amount=0.0,
        records=50000,
        data_class="restricted",
        reversibility="irreversible",
        expected="BLOCKED — action not in agent passport, agent paused automatically"
    )

    # ── Scenario 4: Delete database → HUMAN_ONLY ─────────────────────────────
    run_scenario(
        num=4,
        title="Delete Database — Catastrophic, Human-Only",
        action="delete_database",
        params={"schema": "production", "backup_confirmed": False},
        amount=0.0,
        records=999999,
        data_class="restricted",
        reversibility="irreversible",
        expected="HUMAN_ONLY / BLOCKED — catastrophic, never auto-approved"
    )

    banner("Demo Complete — Check WARDEN Console for full audit trail", GREEN)
    print(f"  Frontend : {CYAN}http://localhost:5173{RESET}")
    print(f"  API Docs : {CYAN}{WARDEN_URL}/docs{RESET}")
    print(f"  Ledger   : {CYAN}{WARDEN_URL}/ledger{RESET}\n")


if __name__ == "__main__":
    main()
