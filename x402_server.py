"""
x402 Checkout Server — Real on-chain payment endpoint + Agent UX endpoints.

Two responsibilities:
  1. x402 checkout: POST /purchase (HTTP 402 payment flow)
  2. Agent UX: endpoints that let ANY agent discover who the user is,
     what they're allowed to do, and what the system has learned.

This is "UX for agents" — the equivalent of a well-designed website,
but for AI agents instead of humans.

Setup:
  1. pip install "x402[fastapi,evm]" uvicorn
  2. Set EVM_ADDRESS in .env (your wallet that receives payment)
  3. Fund client wallet with test USDC from Circle faucet
  4. python x402_server.py  (runs on port 4021)

The transaction is visible on https://sepolia.basescan.org
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

load_dotenv()

# ── Configuration ───────────────────────────────────────────────────────────
RECIPIENT_ADDRESS = os.getenv("EVM_ADDRESS")
NETWORK: Network = "eip155:84532"  # Base Sepolia
USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"  # USDC on Base Sepolia
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
PORT = int(os.getenv("X402_SERVER_PORT", "4021"))

if not RECIPIENT_ADDRESS:
    raise ValueError(
        "Set EVM_ADDRESS in your .env file to the wallet address that should receive payments.\n"
        "Example: EVM_ADDRESS=0xYourBaseSepoliaWalletAddress"
    )

# ── Paths ──────────────────────────────────────────────────────────────────
CONTEXT_GRAPH_PATH = Path(__file__).parent / "context_graph.json"
RUN_RESULTS_PATH = Path(__file__).parent / "run_results.json"

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(title="STRIDE x402 Checkout", version="1.0.0")

# ── x402 setup ──────────────────────────────────────────────────────────────
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(NETWORK, ExactEvmServerScheme())

# ── Protected routes ────────────────────────────────────────────────────────
# POST /purchase is the checkout endpoint. Price is dynamic per request,
# but x402 middleware needs a base price. We set $0.01 as the minimum
# and the actual product price is handled in the response.
routes: dict[str, RouteConfig] = {
    "POST /purchase": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=RECIPIENT_ADDRESS,
                price="$0.01",  # Base price in USDC (testnet)
                network=NETWORK,
            ),
        ],
        mime_type="application/json",
        description="Purchase a product via x402 payment",
    ),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Unprotected health check."""
    return {
        "status": "ok",
        "network": NETWORK,
        "recipient": RECIPIENT_ADDRESS,
        "facilitator": FACILITATOR_URL,
    }


@app.post("/purchase")
async def purchase(request: Request):
    """
    x402-protected purchase endpoint.

    If the client hasn't paid, the x402 middleware returns HTTP 402 before
    this function runs. If we get here, payment has been verified and
    settled on-chain by the facilitator.
    """
    body = await request.json()

    confirmation = {
        "confirmation_id": f"x402-{uuid.uuid4().hex[:8]}",
        "status": "confirmed",
        "product": body.get("product", "unknown"),
        "brand": body.get("brand", ""),
        "price": body.get("price", 0),
        "currency": "USDC",
        "network": NETWORK,
        "recipient": RECIPIENT_ADDRESS,
        "agent_id": body.get("agent_id", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=confirmation)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT UX ENDPOINTS
# These let any agent on the internet understand this user and system.
# This is "UX for agents" — structured, discoverable, machine-readable.
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/agent-profile")
async def agent_profile():
    """
    Returns everything an external agent needs to shop for this user.

    An agent hitting this endpoint learns:
      - Who the user is (preferences, brands, size, budget)
      - What it's allowed to do (spend cap, approved sites, approval rules)
      - What the system has learned (RL weights, insights from past runs)

    This is the "front door" for the Internet of Agents — any agent
    can read this and know how to act on behalf of this user.
    """
    cg = json.loads(CONTEXT_GRAPH_PATH.read_text())

    return {
        "schema_version": "1.0",
        "user_preferences": cg["user"]["preferences"],
        "trust_rules": cg["user"]["trust_rules"],
        "learned_weights": cg.get("rl_weights", {}),
        "learned_insights": cg.get("learned_insights", [])[-5:],  # last 5 lessons
        "total_sessions": len(cg.get("history", [])) // 10,  # approx sessions completed
        "total_runs": len(cg.get("history", [])),
        "payment": {
            "protocol": "x402",
            "network": NETWORK,
            "currency": "USDC",
            "checkout_endpoint": "/purchase",
        },
    }


@app.get("/agent-capabilities")
async def agent_capabilities():
    """
    Describes what actions are available and how to use them.

    This is like a sitemap for agents — instead of HTML links for humans,
    it's a list of endpoints with input/output contracts for agents.
    """
    return {
        "name": "STRIDE Shopping System",
        "description": "RL-powered shopping agent with x402 payment on Base Sepolia",
        "endpoints": {
            "GET /agent-profile": {
                "description": "Learn about the user: preferences, trust rules, what the system has learned",
                "auth_required": False,
            },
            "GET /agent-capabilities": {
                "description": "This endpoint — discover what actions are available",
                "auth_required": False,
            },
            "GET /agent-history": {
                "description": "Past shopping runs: what was bought, rewards, strategies used",
                "auth_required": False,
            },
            "POST /purchase": {
                "description": "Buy a product. Requires x402 USDC payment.",
                "auth_required": True,
                "payment": "x402 (USDC on Base Sepolia)",
                "input": {"product": "str", "brand": "str", "price": "float", "agent_id": "str"},
                "output": {"confirmation_id": "str", "status": "str", "network": "str"},
            },
            "GET /health": {
                "description": "Check if the system is online",
                "auth_required": False,
            },
        },
        "supported_protocols": ["x402", "HTTP/JSON"],
        "network": NETWORK,
    }


@app.get("/agent-history")
async def agent_history():
    """
    Returns past shopping runs so an agent can learn from history.

    An external agent can use this to understand:
      - Which sites worked best
      - What strategies got high rewards
      - What products were purchased
    """
    if not RUN_RESULTS_PATH.exists():
        return {"runs": [], "summary": "No runs yet"}

    results = json.loads(RUN_RESULTS_PATH.read_text())

    summary = {
        "total_runs": len(results),
        "avg_reward": round(sum(r["reward"] for r in results) / len(results), 1) if results else 0,
        "best_site": _most_common([r["strategy"]["site"] for r in results if r["reward"] >= 60]),
        "best_strategy": _most_common([r["strategy"]["query_style"] for r in results if r["reward"] >= 60]),
        "success_rate": f"{sum(1 for r in results if r['outcome'] == 'purchased') / len(results) * 100:.0f}%",
    }

    runs = []
    for r in results:
        runs.append({
            "run": r["run"],
            "reward": r["reward"],
            "outcome": r["outcome"],
            "strategy": r["strategy"],
            "product": r.get("product", {}).get("name") if r.get("product") else None,
            "price": r.get("product", {}).get("price") if r.get("product") else None,
            "lesson": r.get("lesson", ""),
        })

    return {"summary": summary, "runs": runs}


def _most_common(items: list) -> str:
    """Return the most frequent item in a list."""
    if not items:
        return "none"
    return max(set(items), key=items.count)


# ── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print(f"\n{'='*60}")
    print("STRIDE — x402 CHECKOUT SERVER")
    print(f"  Network:     Base Sepolia ({NETWORK})")
    print(f"  USDC:        {USDC_ADDRESS}")
    print(f"  Recipient:   {RECIPIENT_ADDRESS}")
    print(f"  Facilitator: {FACILITATOR_URL}")
    print(f"  Port:        {PORT}")
    print(f"{'='*60}\n")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
