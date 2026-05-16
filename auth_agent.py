"""
Auth Agent — Hour 4 (PM owns this file)

Issues a scoped credential at session start.
Defines exactly what the Shopper and Payment agents are authorized to do.
No agent can escalate permissions mid-session.

Credential is checked by Payment Agent before any purchase fires.
"""

import json
from datetime import datetime, timedelta


def issue_credential(context_graph: dict, session_id: str) -> dict:
    """
    Issue a scoped credential at session start.
    Called once per run, before any shopping happens.

    Returns a credential dict that Payment Agent checks before firing.
    """
    prefs = context_graph["user"]["preferences"]
    trust = context_graph["user"]["trust_rules"]

    # TODO (PM): Build out credential with full scope from context graph
    credential = {
        "agent_id": f"shopper-{session_id}",
        "user_id": context_graph.get("user_id", "user-001"),
        "authorized_sites": trust.get("approved_sites", ["zappos.com", "nike.com", "amazon.com"]),
        "max_autonomous_spend": trust.get("max_autonomous_spend", 120),
        "approved_categories": ["footwear"],
        "brand_whitelist": prefs.get("brands", []),
        "requires_human_approval_above": trust.get("requires_human_approval_above", 80),
        "session_expires": (datetime.utcnow() + timedelta(hours=8)).isoformat() + "Z",
        "issued_at": datetime.utcnow().isoformat() + "Z",
    }

    return {"valid": True, "credential": credential}


def verify_credential(credential: dict, site: str, amount: float) -> dict:
    """
    Verify a credential before payment fires.
    Called by Payment Agent.

    Returns {"cleared": True/False, "reason": str}
    """
    # TODO (PM): Add session expiry check
    # TODO (PM): Add site whitelist check
    # TODO (PM): Add spend cap enforcement

    if amount > credential["max_autonomous_spend"]:
        return {"cleared": False, "reason": f"Amount ${amount} exceeds cap ${credential['max_autonomous_spend']}"}

    if site not in credential["authorized_sites"]:
        return {"cleared": False, "reason": f"Site {site} not in approved list"}

    return {"cleared": True, "reason": "All checks passed"}


# --- Test ---
if __name__ == "__main__":
    with open("context_graph.json") as f:
        cg = json.load(f)

    cred = issue_credential(cg, session_id="run-001")
    print("Credential issued:", json.dumps(cred, indent=2))

    check = verify_credential(cred["credential"], site="zappos.com", amount=109)
    print("Verification:", check)
