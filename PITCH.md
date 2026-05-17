# STRIDE — Internet of Agents Hackathon Submission

## Project Name
STRIDE

## Tagline
An AI shopping agent that learns your style, scrapes real websites, and pays autonomously via x402.

## Description
STRIDE is a multi-agent shopping system where 6 specialized AI agents collaborate to find, evaluate, and purchase sneakers on behalf of a user. The agent gets measurably smarter over 10 runs using Thompson Sampling reinforcement learning — learning which site, search strategy, and filter works best for each user.

What makes STRIDE different:
- **Real product data** — scrapes live inventory from Zappos, 6pm, StockX, and GOAT via Jina.ai
- **Real payments** — x402 protocol settles USDC on Base Sepolia (verifiable on BaseScan)
- **Real learning** — reward curve climbs from ~20 pts (random exploration) to ~99 pts (optimized strategy)
- **Agentic guardrails** — user says "only buy blue Jordans, ask before anything else" and the agent respects it. Color preferences, specific product requests, custom instructions, and NEED_APPROVAL flow prevent unwanted purchases
- **UX for agents** — `/agent-profile`, `/agent-capabilities`, `/agent-history` endpoints let any external agent discover the user's preferences, trust rules, and learned insights via standard HTTP/JSON

The 6-agent pipeline:
1. **Memory Agent** — reads user context and past run history
2. **RL Bandit** — Thompson Sampling picks strategy across 4 dimensions (site, query style, filter, abandon threshold)
3. **Auth Agent** — issues scoped credentials with spend caps, site whitelists, and human approval gates
4. **Shopping Agent** — Claude Sonnet 4.6 ReAct loop reasons step-by-step: think, search, evaluate, buy
5. **Payment Agent** — real x402 USDC payment on Base Sepolia, verified by on-chain facilitator
6. **Reflexion** — agent writes a plain-English lesson after each run that changes next run's behavior

## Tech Stack
Claude Sonnet 4.6 (Anthropic SDK), Thompson Sampling (Python), x402 Protocol (Base Sepolia/USDC), Streamlit, Jina.ai (web scraping), FastAPI, Python

## Repository URL
https://github.com/rohitmujumdar/merchant-copilot

## Demo URL
http://localhost:8501 (local Streamlit — requires x402 server for live payments)

## Track
General Track

## Team Members
- Swati Chauhan — Auth Agent, Payment Agent, x402 Server, Streamlit Dashboard, Agentic Guardrails
- Rohit Mujumdar — RL Bandit, Reward Function, Shopping Agent, Environment, Live Scraper, Memory Agent

## Key Demo Moments

1. **Onboarding**: User chats with STRIDE — "I want Tiffany Nike Air Force 1s, size 10, under $400, ask before buying anything else"
2. **Agent runs**: Watch Claude reason step-by-step across real websites, learning which site has the best inventory
3. **Guardrails in action**: Agent finds Nike Pegasus but outputs NEED_APPROVAL instead of buying — respects user's custom instructions
4. **Reward curve**: Chart shows improvement from random exploration (-55 pts) to optimized strategy (99 pts)
5. **Real payment**: Click the BaseScan link to see the x402 USDC transaction on-chain
6. **Agent UX endpoints**: Hit `/agent-profile` — any agent on the internet can now shop for this user

## Internet of Agents Alignment

- **6 agents collaborating** via structured protocols (not just a pipeline — Memory Agent is queried mid-run by Shopping Agent)
- **x402 machine-to-machine payments** — open protocol, any agent can pay
- **Agent UX endpoints** — any external agent can discover user preferences and interact with the system
- **Agentic guardrails** — user-defined rules that constrain what autonomous agents can do
- **Learning compounds** — bandit state persists across sessions, so the agent network gets smarter over time
