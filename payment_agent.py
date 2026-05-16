"""
Payment Agent — Hour 5 (PM owns this file)

Closes the purchase autonomously via simulated x402 protocol.
ONLY fires after Auth Agent has cleared.
Hard budget cap enforced from context graph trust_rules.
"""

import json
import uuid
from datetime import datetime


def execute_payment(product: dict, credential: dict, auth_check: dict) -> dict:
    """
    Execute a payment for a product.

    Args:
        product: the product to buy (from environment.py)
        credential: issued by auth_agent.py
        auth_check: result of auth_agent.verify_credential()

    Returns:
        payment result dict
    """

    # Safety: never fire without auth clearance
    if not auth_check.get("cleared"):
        return {
            "success": False,
            "reason": f"Auth not cleared: {auth_check.get('reason')}",
        }

    price = product["price"]
    cap = credential.get("max_autonomous_spend", 120)
    approval_threshold = credential.get("requires_human_approval_above", 80)

    # Needs human approval
    if price > approval_threshold:
        return {
            "success": False,
            "requires_human_approval": True,
            "amount": price,
            "product": product["name"],
            "reason": f"Purchase ${price} requires human approval (threshold: ${approval_threshold})",
        }

    # Hard cap check
    if price > cap:
        return {
            "success": False,
            "reason": f"Price ${price} exceeds hard cap ${cap}",
        }

    # TODO (PM): Replace this simulation with real x402 SDK call
    # Simulated x402 payment
    confirmation = _simulate_x402_payment(product, price, credential)

    return {
        "success": True,
        "confirmation_id": confirmation["id"],
        "amount_charged": price,
        "product": product["name"],
        "brand": product["brand"],
        "timestamp": datetime.utcnow().isoformat(),
        "protocol": "x402-simulated",
    }


def _simulate_x402_payment(product: dict, amount: float, credential: dict) -> dict:
    """
    Simulates an x402 autonomous payment.
    Replace with real x402 SDK when available.
    """
    return {
        "id": f"x402-{uuid.uuid4().hex[:8]}",
        "status": "confirmed",
        "amount": amount,
        "currency": "USD",
        "recipient": "zappos-merchant-001",
        "agent_id": credential.get("agent_id"),
    }


# --- Test ---
if __name__ == "__main__":
    product = {
        "name": "Nike Air Zoom Pegasus 41",
        "brand": "Nike",
        "price": 109,
    }

    credential = {
        "agent_id": "shopper-001",
        "max_autonomous_spend": 120,
        "requires_human_approval_above": 80,
        "authorized_sites": ["zappos.com"],
    }

    auth_check = {"cleared": True, "reason": "All checks passed"}

    result = execute_payment(product, credential, auth_check)
    print("Payment result:", json.dumps(result, indent=2))
