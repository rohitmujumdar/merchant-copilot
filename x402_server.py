"""
x402 Checkout Server — Real on-chain payment endpoint for the shopping agent.

This is a FastAPI server that acts as the "store checkout" using the x402 protocol.
When the payment agent hits POST /purchase, the server returns HTTP 402 demanding
USDC payment on Base Sepolia. The x402 SDK on the client side signs the transfer
automatically, and the facilitator settles it on-chain.

Setup:
  1. pip install "x402[fastapi,evm]" uvicorn
  2. Set EVM_ADDRESS in .env (your wallet that receives payment)
  3. Fund client wallet with test USDC from Circle faucet
  4. python x402_server.py  (runs on port 4021)

The transaction is visible on https://sepolia.basescan.org
"""

import os
import uuid
from datetime import datetime, timezone

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

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(title="Merchant Copilot x402 Checkout", version="1.0.0")

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


# ── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print(f"\n{'='*60}")
    print("MERCHANT COPILOT — x402 CHECKOUT SERVER")
    print(f"  Network:     Base Sepolia ({NETWORK})")
    print(f"  USDC:        {USDC_ADDRESS}")
    print(f"  Recipient:   {RECIPIENT_ADDRESS}")
    print(f"  Facilitator: {FACILITATOR_URL}")
    print(f"  Port:        {PORT}")
    print(f"{'='*60}\n")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
