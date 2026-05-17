# STRIDE — System Specification

## What is STRIDE?

STRIDE (Strategic Thompson-sampling Reinforcement for Internet Deal Exploration) is a 6-agent shopping system that learns how to find the best product for a user by exploring real shopping websites. It uses reinforcement learning to get better with each attempt, then asks the human for approval before purchasing.

The key insight: instead of one search on one site, STRIDE runs multiple exploration episodes across different sites and strategies, learns which approach works best, and presents the best candidate for human approval.

## The 6 Agents

1. **Memory Agent** — Stores user preferences, run history, and learned insights. Provides context to all other agents.
2. **RL Bandit Agent** — Uses Thompson Sampling with Beta distributions to pick strategies. Has 4 independent bandits (site, query style, filter, patience) with 16 total arms.
3. **Auth Agent** — Issues cryptographic credentials before each episode. Sets spend caps and approved sites. Defense in depth — can't be jailbroken mid-run.
4. **Shopping Agent** — Claude Sonnet with a ReAct reasoning loop. Navigates real websites via Jina.ai reader, searches, evaluates products, and decides whether to "purchase" (mark as candidate).
5. **Reward Agent** — Scores each episode: +40 purchase, +25 full match, +15 under budget, +10 fast delivery, -4 per step, -12 wrong color/size, -15 CAPTCHA blocked.
6. **Reflexion Agent** — After each episode, writes a one-sentence lesson in plain English (e.g., "Zappos has better selection for HOKA than StockX").

## How One Query Works (End to End)

User types: "Find me black Nike running shoes size 10 under $200"

### Phase 1: Preference Extraction
- Streamlit UI extracts structured preferences: brands, size, budget, color, style, delivery, spend cap
- Stores in `context_graph.json` as the user section
- Also stores the raw original query text for the shopping agent to use verbatim

### Phase 2: Exploration Loop (3-10 episodes, configurable via slider)
For EACH episode:
1. Memory Agent loads context (preferences + any history from prior episodes)
2. RL Bandit samples from Beta distributions to pick a strategy (e.g., {site: zappos, query: specific, filter: price_first, patience: after_2_fails})
3. Auth Agent issues a credential with spend cap
4. Shopping Agent runs a ReAct loop: NAVIGATE → SEARCH → EVALUATE → PURCHASE (or ABANDON)
5. Reward Agent scores the outcome
6. Bandit updates its Beta distributions (good outcome → higher alpha, bad → higher beta)
7. Reflexion Agent writes a lesson
8. Memory Agent stores the result

ALL episodes are exploration — no real payment happens during the loop.

### Phase 3: Human Approval
- After all episodes complete, the system identifies the best candidate (highest reward among products found)
- Presents it to the user: product name, price, brand, site, link
- User clicks "Buy This" → executes x402 payment on Base Sepolia
- User clicks "Not what I wanted" → enters feedback → system applies -30 penalty to that strategy → re-runs with feedback in prompt

## Thompson Sampling (The RL Core)

### Why Thompson Sampling?
- Converges in 3-5 samples (vs thousands for deep RL)
- Natural explore/exploit tradeoff via posterior sampling
- Each arm has a Beta(alpha, beta) distribution
- Sample from each arm's distribution → pick the highest sample → that arm is chosen
- Early episodes: all Beta(1,1) = uniform → pure exploration (random)
- Later episodes: winning arms peak → exploitation (use what works)

### The 4 Bandits
1. **Site** (6 arms): zappos, 6pm, stockx, goat, nike, amazon
2. **Query Style** (3 arms): broad ("running shoes"), moderate ("Nike running men"), specific ("Nike Pegasus size 10 under $120")
3. **Filter Strategy** (4 arms): price_first, brand_first, rating_first, size_first
4. **Abandon Threshold** (3 arms): after_1_fail, after_2_fails, after_3_fails

### What Persists vs. Resets
- **Persists across queries:** Beta distributions in `bandit_state.json`. If Zappos worked well for HOKA, it'll try Zappos early for Nike too. Learning compounds across sessions.
- **Resets each new query:** User preferences, original query, feedback, trust rules in `context_graph.json`. No stale "blue size 10" leaking into a "red size 9" search.

## The Shopping Agent (ReAct Loop)

Claude Sonnet operates in a constrained ReAct loop:
- Format: Thought → Action → Observation (from environment) → repeat
- Stop sequences prevent hallucination (Claude can't write its own Observation)
- Max 8 steps per episode (safety limit)

### Available Actions
- `NAVIGATE [site]` — Go to a real shopping site
- `SEARCH [query]` — Search for products (returns live inventory via Jina.ai)
- `EVALUATE [index]` — Check if product matches preferences (brand, price, size, color, delivery)
- `PURCHASE [index]` — Mark product as candidate
- `ASK_MEMORY [question]` — Query Memory Agent about past runs (Agent-to-Agent protocol)
- `NEED_APPROVAL [index, reason]` — Flag product that doesn't match exactly
- `ABANDON` — Give up on current site
- `DONE` — End run

### Guardrails in System Prompt
- Original user request quoted verbatim ("use these exact terms when searching")
- Required color enforced ("only buy this color, skip products that don't match")
- Specific product prioritized
- Excluded brands blocked
- Previous rejection feedback included
- Hard rules: never wrong size, never exceed budget, never buy wrong brand

## Live Scraping (How the Agent Navigates the Web)

4 sites have live scraping via Jina.ai reader: Zappos, 6pm, StockX, GOAT.
2 sites are simulated (JS-heavy/bot-blocked): Nike, Amazon.

### How it works
1. Build search URL with brands + color + style (e.g., `zappos.com/search?term=nike+black+running+sneakers+men`)
2. Fetch via Jina.ai reader (`r.jina.ai/{url}`) — returns markdown
3. Parse with regex (Zappos: brand, name, color, price, rating, URL) or Claude fallback
4. Normalize to standard product format with color field
5. Cache per site per episode (no re-fetching)

### Color/Size Evaluation
- Search URL includes color and style terms → more relevant results
- Zappos parser extracts "Color Black" from page markdown
- `evaluate_product()` checks color match — products without matching color get `wrong_color` event (-12 penalty)
- Products are shown to Claude with color info so it can make informed decisions

## Reward Function

| Event | Points |
|-------|--------|
| purchase_completed | +40 |
| item_found_full_match | +25 |
| under_budget | +15 |
| fast_delivery | +10 |
| checkout_reached | +10 |
| efficiency_bonus (≤4 steps) | +15 |
| efficiency_bonus (≤6 steps) | +8 |
| per_step_penalty | -4/step |
| captcha_blocked | -15 |
| out_of_stock | -20 |
| wrong_size | -12 |
| wrong_color | -12 |
| over_budget | -10 |

Perfect run: ~90-100 pts. Failed run: ~0-20 pts. The spread makes learning visible in few episodes.

## Human-in-the-Loop

### Why no auto-purchase?
Real products cost real money. The agent explores freely (no financial risk), but a human must approve the final purchase. This is the "merchant copilot" — it does the research, you make the decision.

### Approval Flow
1. Agent presents best candidate with product details + link
2. User approves → x402 payment executes on Base Sepolia (USDC)
3. User rejects → enters feedback ("I said Jordan not Pegasus") → -30 penalty applied to that strategy → re-run with feedback in shopping agent's prompt

### x402 Payment Protocol
- HTTP 402 Payment Required flow
- USDC on Base Sepolia testnet
- Facilitator verifies payment on-chain before endpoint returns
- Transaction visible on BaseScan

## Agent-to-Agent Protocol (A2A)

The Shopping Agent can query the Memory Agent MID-RUN using `ASK_MEMORY`. This isn't sequential handoff — it's a synchronous request/response between two running agents.

Example: Shopping Agent thinks "I wonder if StockX had better prices last time" → outputs `ASK_MEMORY what was the best price on StockX?` → Memory Agent responds with history → Shopping Agent uses that to decide whether to ABANDON or continue.

## Agent UX Endpoints (Internet of Agents)

The x402 server exposes endpoints that let ANY external agent discover and interact with STRIDE:

- `GET /agent-profile` — User preferences, trust rules, learned weights, past insights
- `GET /agent-capabilities` — API contract for all endpoints (sitemap for agents)
- `GET /agent-history` — Past shopping runs, strategies, rewards, products found
- `POST /purchase` — x402-protected checkout (requires USDC payment)

This is "UX for agents" — structured, discoverable, machine-readable. The equivalent of a well-designed website, but for AI agents.

## Key Design Decisions

| Choice | Alternative | Why |
|--------|-------------|-----|
| Thompson Sampling | UCB, epsilon-greedy | Bayesian, converges in 3-5 samples, natural explore/exploit |
| All explore, human approves | Auto-buy on last episode | No autonomous spending. Human always decides. |
| Persistent Beta state | Reset every session | Learning compounds. 3 sessions = 9+ episodes of experience. |
| Clean user context per query | Merge with previous | No stale preferences leak between different searches. |
| Jina.ai reader | Playwright/Selenium | Free, no browser needed. Episodes run in ~20s each. |
| ReAct with stop_sequences | Let Claude free-form | Prevents hallucination at source. API-level guarantee. |
| 4 independent bandits | One bandit over all combos | 16 arms vs 216 combinations. Converges with tiny sample sizes. |
| Step penalty -4/step | Flat reward | Creates visible learning curve. Efficient runs clearly win. |
| Reflexion lessons | Pure numeric signal | Interpretable. "Avoid GOAT for budget shoppers" is readable. |

## File Map

| File | Purpose |
|------|---------|
| `run_loop.py` | Orchestrator. All episodes explore, human approves after. Persists bandit. |
| `shopping_agent.py` | Claude ReAct loop. Navigates, searches, evaluates, purchases. |
| `environment.py` | Shopping environment. Live scraping + simulation fallback. |
| `live_scraper.py` | Jina.ai fetcher + regex/Claude parsers for 4 real sites. |
| `rl_bandit.py` | Thompson Sampling. 4 bandits, 16 arms, Beta distributions. |
| `reward.py` | Scoring function. Events → points. |
| `memory_agent.py` | Context persistence, history summaries. |
| `auth_agent.py` | Credential issuance, spend caps, site authorization. |
| `payment_agent.py` | x402 USDC payment execution. |
| `x402_server.py` | FastAPI server with Agent UX endpoints + x402 checkout. |
| `app.py` | Streamlit UI: onboarding, live run with logs, results dashboard. |
| `context_graph.json` | User preferences, trust rules, history. Resets per query. |
| `bandit_state.json` | Persisted Beta(α,β) for all 16 arms. Survives across sessions. |
| `architecture.html` | Visual explainer page with SVG diagrams. |

## What Makes This Different

1. **RL that works in 3-5 samples** — Thompson Sampling, not deep RL. Visible learning in a demo.
2. **Agent navigating the real web** — Not a toy. Jina.ai reader fetches live inventory from Zappos, StockX, GOAT, 6pm.
3. **Human-in-the-loop by design** — Never auto-purchases. Exploration is free, buying requires approval.
4. **Agent-to-Agent protocol** — Shopping Agent queries Memory Agent mid-reasoning-loop. Not just sequential handoff.
5. **x402 payment on-chain** — Real USDC transaction on Base Sepolia. Verifiable on BaseScan.
6. **Internet of Agents** — API endpoints let any external agent discover the user's preferences and shop on their behalf.
7. **Learning persists** — The more you use it, the better it gets. Beta distributions compound across sessions.
