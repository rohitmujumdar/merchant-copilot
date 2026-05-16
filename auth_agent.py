"""
Auth Agent — Issues scoped credentials before payment fires.

Defines exactly what the Shopper and Payment agents are authorized to do.
No agent can escalate permissions mid-session.
Credential is checked by Payment Agent before any purchase fires.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone


def issue_credential(context_graph: dict, session_id: str, run_number: int = 1) -> dict:
    """
    Issue a scoped credential at session start.
    Called once per run, before any shopping happens.

    Args:
        context_graph: The full context graph (with "user" key).
        session_id: Unique session identifier for this run.
        run_number: Which run this is (1-10). Used for first-N-runs approval gate.

    Returns:
        {"valid": True, "credential": {...}} on success.
    """
    prefs = context_graph["user"]["preferences"]
    trust = context_graph["user"]["trust_rules"]

    now = datetime.now(timezone.utc)

    credential = {
        "credential_id": f"cred-{uuid.uuid4().hex[:8]}",
        "agent_id": f"shopper-{session_id}",
        "user_id": context_graph.get("user_id", "user-001"),
        "run_number": run_number,
        "authorized_sites": ["zappos.com", "6pm.com", "stockx.com", "goat.com", "nike.com", "amazon.com"],
        "max_autonomous_spend": trust.get("max_autonomous_spend", 120),
        "approved_categories": trust.get("approved_categories", ["footwear"]),
        "brand_whitelist": prefs.get("brands", []),
        "budget": prefs.get("budget", 120),
        "requires_human_approval": run_number <= trust.get("require_approval_first_n_runs", 3),
        "issued_at": now.isoformat(),
        "session_expires": (now + timedelta(hours=1)).isoformat(),
    }

    return {"valid": True, "credential": credential}


def verify_credential(credential: dict, site: str, amount: float) -> dict:
    """
    Verify a credential before payment fires.
    Called by Payment Agent before x402 transaction.

    Checks:
        1. Session not expired
        2. Site is in authorized list
        3. Amount does not exceed spend cap
        4. Amount does not exceed user budget
        5. Human approval gate for early runs

    Returns:
        {"cleared": True/False, "reason": str}
    """
    now = datetime.now(timezone.utc)

    # 1. Session expiry
    expires = datetime.fromisoformat(credential["session_expires"])
    if now > expires:
        return {"cleared": False, "reason": "Session credential has expired"}

    # 2. Site whitelist
    if site not in credential["authorized_sites"]:
        return {
            "cleared": False,
            "reason": f"Site '{site}' not in approved list: {credential['authorized_sites']}",
        }

    # 3. Spend cap
    cap = credential["max_autonomous_spend"]
    if amount > cap:
        return {"cleared": False, "reason": f"Amount ${amount} exceeds spend cap ${cap}"}

    # 4. Budget check
    budget = credential.get("budget", cap)
    if amount > budget:
        return {"cleared": False, "reason": f"Amount ${amount} exceeds user budget ${budget}"}

    # 5. Human approval gate (first N runs — simulated as auto-approve for demo)
    if credential.get("requires_human_approval", False):
        return {
            "cleared": True,
            "reason": f"Approved (human approval simulated for run {credential['run_number']})",
            "human_approval_required": True,
        }

    return {"cleared": True, "reason": "All checks passed"}


# --- Test ---
if __name__ == "__main__":
    with open("context_graph.json") as f:
        cg = json.load(f)

    # Test: Issue credential for run 1 (should require human approval)
    cred = issue_credential(cg, session_id="run-001", run_number=1)
    print("Credential issued:", json.dumps(cred, indent=2))

    # Test: Verify — valid purchase
    check = verify_credential(cred["credential"], site="zappos.com", amount=109)
    print("\nVerify $109 on zappos:", check)

    # Test: Verify — over budget
    check = verify_credential(cred["credential"], site="nike.com", amount=200)
    print("Verify $200 on nike:", check)

    # Test: Verify — bad site
    check = verify_credential(cred["credential"], site="shady.com", amount=50)
    print("Verify $50 on shady.com:", check)

    # Test: Run 5 (no human approval needed)
    cred5 = issue_credential(cg, session_id="run-005", run_number=5)
    check5 = verify_credential(cred5["credential"], site="amazon.com", amount=99)
    print(f"\nRun 5, $99 on amazon:", check5)
