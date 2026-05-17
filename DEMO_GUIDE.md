# STRIDE — Complete Architecture & Demo Guide

## The Problem

Online shopping is broken for AI agents. Today, if you want an AI to buy something for you:
- It can't browse real websites
- It can't learn from past mistakes
- It can't pay autonomously
- It has no guardrails — it'll buy whatever it finds
- Other agents can't collaborate with it

There's no "internet" for agents — just isolated scripts that do one thing.

## What STRIDE Solves

STRIDE is a **network of 6 specialized AI agents** that collaborate to shop for you. It scrapes real products from real websites, learns which strategy works best over time, respects your personal guardrails, and pays with real cryptocurrency via the x402 protocol.

The key insight: **an AI shopping agent needs the same infrastructure humans have** — identity (who am I shopping for?), trust (what am I allowed to do?), learning (what worked last time?), payment (how do I pay?), and guardrails (what should I never do?).

---

## Architecture — The 6 Agents

```
┌─────────────────────────────────────────────────────────────────┐
│                         STRIDE Pipeline                          │
│                                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │  Memory   │──▶│ RL Bandit│──▶│   Auth   │──▶│   Shopping   │ │
│  │  Agent    │   │ (Thompson│   │  Agent   │   │    Agent     │ │
│  │          │   │ Sampling)│   │          │   │ (Claude 4.6) │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────┬───────┘ │
│       ▲                                               │          │
│       │              ┌──────────┐              ┌──────▼───────┐ │
│       │              │Reflexion │◀─────────────│   Payment    │ │
│       │              │ (Lesson) │              │    Agent     │ │
│       │              └────┬─────┘              │   (x402)    │ │
│       │                   │                    └──────────────┘ │
│       └───────────────────┘                                      │
│                                                                   │
│  ═══════════════════ Agent UX Layer ═══════════════════════════  │
│  GET /agent-profile  │  GET /agent-capabilities  │  POST /purchase│
└─────────────────────────────────────────────────────────────────┘
```

### Agent 1: Memory Agent (Rohit)
**File:** `memory_agent.py`
**What it does:** Reads and writes the user's context graph — preferences, history, learned insights.
**Why it matters:** This is the agent's long-term memory. Without it, every session starts from zero.

### Agent 2: RL Bandit (Rohit)
**File:** `rl_bandit.py`
**What it does:** Thompson Sampling across 4 independent dimensions:
- **Site**: Which store to try (Zappos, 6pm, StockX, GOAT, Nike, Amazon)
- **Query style**: How specific the search query should be (broad, moderate, specific)
- **Filter strategy**: What to prioritize (price, brand, rating, size)
- **Abandon threshold**: When to give up on a site (after 1, 2, or 3 failures)

**Why it matters:** This is why the agent gets smarter. Each dimension has a Beta distribution that updates based on rewards. Over 10 runs, the bandit converges on the best strategy for this specific user.

**Learning persists:** Bandit state saves to `bandit_state.json` so the next session starts from where the last one ended.

### Agent 3: Auth Agent (Swati)
**File:** `auth_agent.py`
**What it does:** Issues a scoped credential before any shopping starts. Verifies the credential before any payment fires.

**The credential contains:**
- `agent_id`: Which agent is shopping
- `authorized_sites`: Only these 6 stores
- `max_autonomous_spend`: Hard spend cap from trust rules
- `budget`: User's actual budget
- `approved_categories`: Only footwear
- `requires_human_approval`: True for first 3 runs (trust building)
- `session_expires`: Dies after 1 hour

**Verification checks (5 layers):**
1. Session not expired
2. Site is in whitelist
3. Amount doesn't exceed spend cap
4. Amount doesn't exceed user budget
5. Human approval gate for early runs

**Why it matters:** No agent can escalate permissions mid-session. Even if Claude's reasoning goes wrong, the auth layer blocks unauthorized purchases.

### Agent 4: Shopping Agent (Rohit, guardrails by Swati)
**File:** `shopping_agent.py`
**What it does:** Claude Sonnet 4.6 in a ReAct loop — thinks step by step, takes actions, observes results.

**Available actions:**
- `NAVIGATE [url]` — go to a real website
- `SEARCH [query]` — search for products (triggers live scraping via Jina.ai)
- `EVALUATE [index]` — check a product against user preferences
- `PURCHASE [index]` — buy it (only if all guardrails pass)
- `NEED_APPROVAL [index, reason]` — flag a product that doesn't match exact request
- `ASK_MEMORY [question]` — query the Memory Agent mid-run (agent-to-agent communication)
- `ABANDON` — give up on current site, try another
- `DONE` — end the run

**Guardrails injected into Claude's system prompt:**
- Required color (e.g., "tiffany blue")
- Specific product (e.g., "Nike x Tiffany Air Force 1")
- Custom instructions (e.g., "ask before buying anything that isn't Jordan")
- Excluded brands (e.g., "no Reebok")
- Hard rules: "violating these = failed run"

**Why it matters:** Claude has full reasoning capability but operates within strict guardrails. It can think creatively about HOW to find what you want, but can't violate WHAT you want.

### Agent 5: Payment Agent (Swati)
**File:** `payment_agent.py`
**What it does:** Executes the purchase via x402 protocol on Base Sepolia.

**Flow:**
1. Checks auth credential (is this allowed?)
2. Checks hard spend cap (final safety net)
3. Flags human approval for early runs
4. Makes real x402 USDC payment on Base Sepolia

**Two modes:**
- **Real x402**: When `EVM_PRIVATE_KEY` is set — actual on-chain USDC transfer
- **Simulation**: When no wallet is configured — for teammate testing

**Why it matters:** This is the "Internet of Agents" moment. An AI agent autonomously moves real cryptocurrency. The transaction is verifiable on BaseScan.

### Agent 6: Reflexion (Rohit, in run_loop.py)
**What it does:** After each run, Claude writes a one-sentence lesson in plain English.
**Examples:**
- "Avoid GOAT — everything's over budget"
- "Price-first filtering on Zappos efficiently secures full-match items under budget"
- "StockX has the best selection for limited-edition Nikes"

**Why it matters:** The agent doesn't just learn numerically (RL weights) — it learns in words. These lessons are fed into the next run's prompt, so Claude's reasoning improves in a human-readable way.

---

## The Context Graph — User's Digital Identity

**File:** `context_graph.json`

```json
{
  "user": {
    "preferences": {
      "brands": ["Nike", "Adidas"],
      "size": 10,
      "budget": 120,
      "max_delivery_days": 2,
      "style": "running",
      "color": "blue",
      "specific_product": "Nike Air Force 1",
      "custom_instructions": "ask before buying anything over $100",
      "excluded_brands": ["Reebok"]
    },
    "trust_rules": {
      "max_autonomous_spend": 150,
      "approved_categories": ["footwear"],
      "require_approval_first_n_runs": 3
    }
  },
  "history": [...],
  "learned_insights": [...],
  "rl_weights": {...}
}
```

This is the single source of truth. Every agent reads from it. The onboarding chat writes to it. The `/agent-profile` endpoint exposes it. Any external agent can read it.

---

## Live Scraping — Real Products from Real Websites

**File:** `live_scraper.py`

| Site | Method | URL Format |
|------|--------|-----------|
| Zappos | Jina.ai reader + regex | Captures name, price, rating, URL |
| 6pm | Jina.ai reader + regex | Same parser as Zappos (both Zappos-owned) |
| StockX | Jina.ai reader + regex | Captures name, price, URL from markdown |
| GOAT | Jina.ai reader + regex | Captures name, price, URL from markdown |
| Nike | Simulated (JS-heavy) | Falls back to hardcoded catalog |
| Amazon | Simulated (bot-blocked) | Falls back to hardcoded catalog |

**Claude fallback:** If regex parsing fails, Claude Sonnet 4.6 extracts product data from raw page text.

**Search URLs are dynamic:** Built from user's brand preferences, not hardcoded.

---

## x402 Payment — Real On-Chain Transactions

### What is x402?
HTTP 402 ("Payment Required") is a status code that was reserved since 1999 but never used. x402 is a protocol by Coinbase that finally implements it — enabling machine-to-machine payments over HTTP.

### How our x402 works:

```
Payment Agent                    x402 Server                  Blockchain
     │                                │                            │
     │── POST /purchase ──────────▶   │                            │
     │                                │                            │
     │◀── HTTP 402 "Pay $0.01 USDC"──│                            │
     │                                │                            │
     │── Signs USDC transfer ─────▶   │                            │
     │   (EIP-3009 authorization)     │                            │
     │                                │── Sends to facilitator ──▶│
     │                                │                            │
     │                                │◀── Settlement confirmed ──│
     │                                │                            │
     │◀── 200 OK + confirmation ─────│                            │
     │                                │                            │
```

### What's real:
- Wallet: Real Ethereum wallet (private key in `.env`)
- USDC: Real tokens on Base Sepolia testnet (free from Circle faucet)
- Blockchain: Real Base Sepolia chain — transactions visible on sepolia.basescan.org
- x402 protocol: Real HTTP 402 flow with real signed transfers
- Facilitator: Real x402.org facilitator verifies and settles

### What's testnet:
- The money is test USDC — worth $0 in real life
- The store is our own server — not Zappos/StockX
- To go to production: change one config line (network from Sepolia to Base Mainnet)

### Files:
- `x402_server.py` — FastAPI server with x402 middleware (the "store checkout")
- `payment_agent.py` — x402 client that signs payments (the "wallet")

---

## Agent UX Endpoints — UX for the Internet of Agents

### GET /agent-profile
Returns everything an external agent needs to shop for this user:
- Preferences (brands, size, budget, color, custom instructions)
- Trust rules (spend cap, approved categories, approval requirements)
- Learned RL weights (which site/strategy is currently best)
- Last 5 reflexion lessons
- Payment info (protocol, network, checkout endpoint)

### GET /agent-capabilities
A sitemap for agents — describes every available endpoint with input/output contracts. An agent reads this and knows exactly how to interact.

### GET /agent-history
Past shopping runs with rewards, strategies, products, and lessons. An external agent can learn from history without running its own experiments.

### POST /purchase (x402-protected)
Buy a product. Requires USDC payment via x402 protocol.

**Why these matter:** If someone else's agent at this hackathon wants to shop for our user, it just calls `/agent-profile`, reads the preferences, and hits `/purchase`. No integration meeting, no API docs — the system describes itself.

---

## Agentic Guardrails — What the Agent Cannot Do

### Preference Guardrails (shopping_agent.py)
- **Color**: "REQUIRED COLOR: blue — only buy this color"
- **Specific product**: "ONLY buy Nike x Tiffany Air Force 1. Do not substitute."
- **Custom instructions**: Injected verbatim into Claude's system prompt
- **Excluded brands**: "Never buy from these brands"
- **NEED_APPROVAL action**: Agent flags non-matching products instead of buying

### Auth Guardrails (auth_agent.py)
- 5-layer verification before any payment
- Session expiry (1 hour max)
- Site whitelist (only 6 approved stores)
- Hard spend cap (cannot exceed trust_rules.max_autonomous_spend)
- Budget enforcement (cannot exceed user's stated budget)
- Human approval gate (first 3 runs require approval)

### Payment Guardrails (payment_agent.py)
- Never fires without auth clearance
- Double-checks spend cap
- Only pays on final episode (exploration runs don't spend money)

### Protocol Guardrails (x402_server.py)
- x402 middleware handles payment verification
- On-chain settlement — irreversible but transparent
- Transaction visible on BaseScan

---

## The Reward Function — How the Agent Learns

**File:** `reward.py`

| Event | Points |
|-------|--------|
| Purchase completed | +40 |
| Full preference match | +25 |
| Under budget | +15 |
| Fast delivery | +10 |
| Checkout reached | +10 |
| Efficiency bonus (≤4 steps) | +15 |
| Efficiency bonus (≤6 steps) | +8 |
| Partial match | +5 |
| Per step penalty | -4 each |
| Captcha blocked | -15 |
| Out of stock | -20 |
| Over budget | -10 |
| Wrong size | -12 |

**Range:** Perfect run ~99 pts. Failed run ~-55 pts. This wide spread is what makes the learning curve visible.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Claude Sonnet 4.6 (Anthropic SDK) |
| RL | Thompson Sampling (pure Python, Beta distributions) |
| Payment | x402 Protocol (USDC on Base Sepolia) |
| Scraping | Jina.ai reader + regex + Claude fallback |
| Dashboard | Streamlit (dark theme, custom CSS) |
| Server | FastAPI + x402 middleware |
| Memory | JSON files (context_graph.json, bandit_state.json) |
| Blockchain | Base Sepolia (Coinbase L2 testnet) |

---

## File Ownership

| File | Owner | Purpose |
|------|-------|---------|
| auth_agent.py | Swati | Credential issuing and verification |
| payment_agent.py | Swati | x402 payment execution |
| x402_server.py | Swati | Checkout server + Agent UX endpoints |
| app.py | Swati | Streamlit dashboard (3 screens) |
| shopping_agent.py | Rohit (guardrails by Swati) | Claude ReAct shopping loop |
| rl_bandit.py | Rohit | Thompson Sampling RL |
| reward.py | Rohit | Reward function |
| environment.py | Rohit | Store simulation + live scraping toggle |
| live_scraper.py | Rohit | Jina.ai scraping for 4 real sites |
| memory_agent.py | Rohit | Context graph read/write |
| run_loop.py | Rohit | Orchestrator wiring all 6 agents |

---

## Demo Script (2.5 minutes)

**[0:00] Onboarding (30s)**
Type: "I'm looking for Nike running shoes, size 10, budget $120, need them in 2 days"
→ Show Claude extracting preferences → "Profile saved!"

**[0:30] Show guardrails (15s)**
Point to sidebar: brands, size, budget, color, custom instructions all captured

**[0:45] Load results (5s)**
Click "Load from run_results.json" → instant

**[0:50] Reward curve (20s)**
"Run 1 scored -24 points — the agent was exploring randomly. By Run 8, it scored 99 — it learned which site and strategy works best. That's Thompson Sampling."

**[1:10] Reasoning trace (30s)**
Select Run 1: "8 steps, tried wrong site, abandoned, tried again"
Select Run 8: "4 steps, went straight to the best site, perfect match, bought it"
"The agent taught itself. No human told it which site was better."

**[1:40] Purchases (15s)**
"These are real products scraped from real websites. Click this link — it goes to the actual product page."

**[1:55] Payment (15s)**
"This is a real x402 USDC transaction on Base Sepolia." Click BaseScan link.
"The agent moved real crypto autonomously. Zero human in the loop."

**[2:10] Agent UX (20s)**
Click "Test /agent-profile"
"Any agent on the internet can call this endpoint and instantly know how to shop for this user. That's UX for the Internet of Agents."

**[2:30] Done.**

---

## One-liner for judges

"We built a network of 6 AI agents that scrape real websites, learn via reinforcement learning, respect user-defined guardrails, and pay with real cryptocurrency — all autonomously. This is what the internet looks like when agents are the users."
