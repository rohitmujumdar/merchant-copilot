# Merchant Copilot — RL Shopping Agent
**Internet of Agents Hackathon · May 2026**

> A personal shopping agent that learns to find and buy sneakers better over 10 runs using reinforcement learning — and gets measurably smarter each time.

---

## The Demo (60 seconds)

1. Judge sees **context graph** — user prefs (Nike/Adidas, size 10, budget $120, 2-day delivery)
2. Agent runs **10 shopping episodes** back to back
3. Each run: agent picks a strategy → shops across simulated stores → gets a reward score
4. **Live reward curve climbs** on screen from Run 1 (~20pts) to Run 10 (~85pts)
5. On success: **simulated x402 payment fires** autonomously
6. Judge sees **agent reasoning trace** — Thought → Action → Observe in plain English
7. **4 strategy charts** shift as agent learns which site/query/filter works best

---

## The 5 Agents

| Agent | What it does | Owner |
|---|---|---|
| **Memory Agent** | Reads context graph before each run, writes lessons after | Rohit |
| **Shopper Agent** | Claude navigates simulated stores step by step (ReAct loop) | Rohit |
| **RL Reward Agent** | Scores each run, updates Thompson Sampling bandit | Rohit ✅ |
| **Auth Agent** | Issues scoped credential before payment fires | **Swati** |
| **Payment Agent** | Simulates x402 autonomous purchase after auth clears | **Swati** |

---

## The RL System

- **Algorithm:** Thompson Sampling (Bayesian bandit)
- **4 independent bandits**, each learning one dimension:
  - Which site → Zappos / Nike / Amazon
  - Query style → broad / moderate / specific
  - Filter strategy → price / brand / rating / size first
  - Abandon threshold → after 1 / 2 / 3 failures
- **10 runs** — reward curve goes from random exploration to converged strategy
- **Reward function:**

| Event | Points |
|---|---|
| Purchase completed | +25 |
| Item found (full match) | +20 |
| Checkout reached | +15 |
| Brand match | +15 |
| Under budget | +10 |
| Fast delivery | +5 |
| CAPTCHA / blocked | -10 |
| Out of stock dead end | -15 |
| Per wasted step | -5 |

---

## The Environment

3 **simulated** stores (not real websites) with fake product catalogs:

| Store | Strength | CAPTCHA Risk |
|---|---|---|
| Zappos | Best Nike/Adidas selection, good size availability | Low (5%) |
| Nike.com | Cheapest Nike prices, Nike-only | Medium (10%) |
| Amazon | Fastest shipping, widest selection | High (20%) |

---

## The Context Graph (`context_graph.json`)

The agent's persistent memory. Three layers:

| Layer | Contents | Who sets it |
|---|---|---|
| **Rules (hard)** | Budget ceiling, size, approved sites | User at onboarding — never overridden |
| **Preferences** | Brands, delivery max | User + refined by RL |
| **RL weights** | Learned strategy preferences | Agent discovers from runs |

---

## The Dashboard — Swati Builds This (`app.py`)

4 Streamlit components:

1. **Onboarding form** — 5 questions seed the context graph
2. **Live reward curve** — line chart, Run 1 to Run 10 (hero visual)
3. **Agent reasoning trace** — real-time Thought/Action/Observe stream
4. **Context graph viewer** — preferences + RL weights updating after each run

### How to build the dashboard

The run loop (Rohit's code) will expose a `run_episode()` function that returns:
```python
{
    "run": 5,
    "strategy": {"site": "zappos", "query_style": "specific", ...},
    "reward": 72,
    "reward_breakdown": {"purchase_completed": 25, "under_budget": 10, ...},
    "steps": 4,
    "reasoning_trace": [
        {"type": "thought", "text": "User prefers Nike, budget $120..."},
        {"type": "action", "text": "Navigate to Zappos, search specific query"},
        {"type": "observe", "text": "Found 3 results, 2 within budget"},
        {"type": "action", "text": "Select Nike Air Zoom $109, initiate checkout"},
        {"type": "complete", "text": "Purchase confirmed. Reward: +72pts"},
    ],
    "bandit_weights": {
        "site": {"zappos": 0.55, "nike": 0.30, "amazon": 0.15},
        "query_style": {"broad": 0.15, "moderate": 0.25, "specific": 0.60},
        ...
    },
    "payment": {"success": True, "amount": 109, "confirmation_id": "x402-abc123"}
}
```

Use `st.session_state` to store results across runs. Use `st.empty()` for real-time trace streaming.

---

## File Ownership

```
rl_bandit.py        ✅ Rohit — Thompson Sampling, 4 bandits
reward.py           ✅ Rohit — reward function
environment.py      ✅ Rohit — simulated Zappos/Nike/Amazon
context_graph.json  ✅ Rohit — user preferences schema
memory_agent.py     ← Rohit building now
shopping_agent.py   ← Rohit building now
run_loop.py         ← Rohit — wires all agents together

auth_agent.py       ← SWATI — stub ready, TODOs marked
payment_agent.py    ← SWATI — stub ready, TODOs marked
app.py              ← SWATI — Streamlit dashboard
```

---

## Git Rules for Today

```bash
# Before starting work
git pull

# After finishing a file
git add <filename>
git commit -m "done: auth_agent"
git push

# Never edit each other's files
# If unsure — ask before touching
```

---

## In Scope ✅

- Simulated shopping environment (fake stores, fake products)
- Thompson Sampling RL across 4 dimensions
- Claude as the inner reasoning agent (ReAct loop)
- Simulated x402 payment (mock — not real money)
- Simulated auth credential (JSON check)
- Context graph as a JSON file
- Reflexion: agent writes a plain-English lesson after each run
- Streamlit dashboard with reward curve + reasoning trace
- 10 runs, sneakers only, 3 hardcoded sites

## Out of Scope ❌

- Real browser automation (no live websites)
- Real x402 SDK
- Real Mem0 integration
- Guardrails AI library
- Multiple verticals
- More than 3 sites
- Real money or real purchases

---

## Run the App

```bash
# Install deps
uv add anthropic python-dotenv streamlit

# Run dashboard
uv run streamlit run app.py

# Test RL bandit
uv run python rl_bandit.py

# Test environment
uv run python environment.py
```

---

## Stack

| Layer | Tech |
|---|---|
| LLM | Claude Sonnet (Anthropic SDK) |
| RL | Thompson Sampling (pure Python) |
| Dashboard | Streamlit |
| Memory | JSON file (context_graph.json) |
| Payment | Simulated x402 |
| Environment | Simulated stores (Python) |
