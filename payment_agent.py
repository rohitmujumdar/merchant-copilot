"""
Payment Agent — Closes the purchase via x402 protocol on Base Sepolia.

ONLY fires after Auth Agent has cleared.
Hard budget cap enforced from credential.

Modes:
  - Real x402: set EVM_PRIVATE_KEY env var + X402_SERVER_URL
  - Simulation: runs without any env vars (for teammate testing)
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# x402 real payment (Base Sepolia testnet)
# ---------------------------------------------------------------------------

def _x402_available() -> bool:
    """Check if x402 SDK and wallet key are configured."""
    if not os.getenv("EVM_PRIVATE_KEY"):
        return False
    try:
        import x402  # noqa: F401
        return True
    except ImportError:
        return False


async def _execute_x402_payment(product: dict, credential: dict) -> dict:
    """
    Make a real x402 payment on Base Sepolia testnet.
    The x402 SDK intercepts HTTP 402 responses, signs a USDC transfer,
    and retries with a payment header — all automatically.
    """
    from eth_account import Account
    from x402 import x402Client
    from x402.http import x402HTTPClient
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    # Setup client and signer
    client = x402Client()
    account = Account.from_key(os.environ["EVM_PRIVATE_KEY"])
    register_exact_evm_client(client, EthAccountSigner(account))

    server_url = os.getenv("X402_SERVER_URL", "http://localhost:4021")
    purchase_url = f"{server_url}/purchase"

    payload = {
        "product": product["name"],
        "brand": product.get("brand", ""),
        "price": product["price"],
        "agent_id": credential.get("agent_id", "unknown"),
        "credential_id": credential.get("credential_id", "unknown"),
    }

    async with x402HttpxClient(client) as http:
        response = await http.post(purchase_url, json=payload)
        await response.aread()

        if response.is_success:
            # Extract settlement info from response headers
            http_client = x402HTTPClient(client)
            settle = http_client.get_payment_settle_response(
                lambda name: response.headers.get(name)
            )
            tx_hash = settle.transaction if settle else None

            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

            return {
                "success": True,
                "protocol": "x402-base-sepolia",
                "transaction_hash": tx_hash,
                "confirmation_id": body.get("confirmation_id", f"x402-{uuid.uuid4().hex[:8]}"),
                "amount_charged": product["price"],
                "currency": "USDC",
                "network": "eip155:84532",
                "product": product["name"],
                "brand": product.get("brand", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "success": False,
                "protocol": "x402-base-sepolia",
                "reason": f"x402 payment failed: HTTP {response.status_code} — {response.text}",
            }


# ---------------------------------------------------------------------------
# Simulated payment (fallback when x402 is not configured)
# ---------------------------------------------------------------------------

def _simulate_payment(product: dict, credential: dict) -> dict:
    """Simulated x402 payment for local testing without wallet setup."""
    return {
        "success": True,
        "protocol": "x402-simulated",
        "confirmation_id": f"x402-sim-{uuid.uuid4().hex[:8]}",
        "amount_charged": product["price"],
        "currency": "USD",
        "product": product["name"],
        "brand": product.get("brand", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public API — called by run_loop.py
# ---------------------------------------------------------------------------

def execute_payment(product: dict, credential: dict, auth_check: dict) -> dict:
    """
    Execute a payment for a product.

    Args:
        product: the product to buy (from environment.py), must have "name", "price"
        credential: issued by auth_agent.issue_credential()
        auth_check: result of auth_agent.verify_credential()

    Returns:
        Payment result dict with "success", "confirmation_id", "amount_charged", etc.
    """
    # Safety: never fire without auth clearance
    if not auth_check.get("cleared"):
        return {
            "success": False,
            "reason": f"Auth not cleared: {auth_check.get('reason')}",
        }

    price = product["price"]
    cap = credential.get("max_autonomous_spend", 120)

    # Hard cap — final safety net
    if price > cap:
        return {
            "success": False,
            "reason": f"Price ${price} exceeds hard cap ${cap}",
        }

    # Human approval gate (flagged by auth_agent)
    if auth_check.get("human_approval_required"):
        # In demo, we auto-approve but log it
        print(f"[payment_agent] Human approval simulated for ${price} purchase")

    # Dispatch to real x402 or simulation
    if _x402_available():
        print("[payment_agent] Using real x402 on Base Sepolia")
        return asyncio.run(_execute_x402_payment(product, credential))
    else:
        print("[payment_agent] Using simulated x402 (set EVM_PRIVATE_KEY for real payments)")
        return _simulate_payment(product, credential)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from auth_agent import issue_credential, verify_credential

    with open("context_graph.json") as f:
        cg = json.load(f)

    # Issue credential
    cred_result = issue_credential(cg, session_id="pay-test-001", run_number=1)
    credential = cred_result["credential"]
    print("Credential:", json.dumps(credential, indent=2))

    # Product from environment
    product = {
        "name": "Nike Air Zoom Pegasus 41",
        "brand": "Nike",
        "price": 109,
        "site": "zappos.com",
    }

    # Verify auth
    auth_check = verify_credential(credential, site="zappos.com", amount=product["price"])
    print("\nAuth check:", auth_check)

    # Execute payment
    result = execute_payment(product, credential, auth_check)
    print("\nPayment result:", json.dumps(result, indent=2))

    # Test: blocked payment (no auth)
    bad_auth = {"cleared": False, "reason": "Site not approved"}
    result2 = execute_payment(product, credential, bad_auth)
    print("\nBlocked payment:", json.dumps(result2, indent=2))

    # Test: over cap
    expensive = {"name": "Expensive Shoe", "brand": "Gucci", "price": 999}
    auth_ok = {"cleared": True, "reason": "All checks passed"}
    result3 = execute_payment(expensive, credential, auth_ok)
    print("\nOver cap:", json.dumps(result3, indent=2))
