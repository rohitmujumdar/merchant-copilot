"""Generate STRIDE Product & Tech Document as PDF."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch
import textwrap

BG = '#0f172a'
CARD = '#1a1f2e'
WHITE = '#e2e8f0'
GRAY = '#94a3b8'
BLUE = '#60a5fa'
PURPLE = '#a78bfa'
GREEN = '#10b981'
AMBER = '#fbbf24'
PINK = '#f472b6'

def new_page(title, subtitle=''):
    fig, ax = plt.subplots(1, 1, figsize=(11, 14))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 16)
    ax.axis('off')
    ax.text(5, 15.5, title, ha='center', fontsize=22, fontweight='bold', color=WHITE)
    if subtitle:
        ax.text(5, 15.0, subtitle, ha='center', fontsize=10, color=GRAY)
    ax.text(5, 0.2, 'STRIDE  |  Internet of Agents Hackathon  |  Swati Chauhan & Rohit Mujumdar',
            ha='center', fontsize=7, color='#475569')
    return fig, ax

def section(ax, y, title, color=BLUE):
    ax.plot([0.5, 9.5], [y, y], color=color, lw=1.5)
    ax.text(0.5, y + 0.15, title, fontsize=12, fontweight='bold', color=color)
    return y - 0.6

def body(ax, y, text, fontsize=8.5, color=WHITE):
    for line in text.split('\n'):
        for wl in (textwrap.wrap(line, width=100) or ['']):
            ax.text(0.5, y, wl, fontsize=fontsize, color=color)
            y -= 0.35
    return y - 0.1

def bullet(ax, y, items, fontsize=8.5, color=WHITE):
    for item in items:
        for i, wl in enumerate(textwrap.wrap(item, width=95)):
            prefix = '  \u2022 ' if i == 0 else '    '
            ax.text(0.5, y, prefix + wl, fontsize=fontsize, color=color)
            y -= 0.35
    return y - 0.1

def card(ax, x, y, w, h, title, lines, border=BLUE):
    box = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.15', facecolor=CARD, edgecolor=border, lw=1.2)
    ax.add_patch(box)
    ax.text(x+0.2, y+h-0.35, title, fontsize=9, fontweight='bold', color=border)
    ty = y+h-0.7
    for l in lines:
        ax.text(x+0.2, ty, l, fontsize=7, color=GRAY)
        ty -= 0.28


pages = []

# ═══ PAGE 1: COVER ═══
fig, ax = new_page('', '')
ax.text(5, 11.5, 'STRIDE', ha='center', fontsize=52, fontweight='bold', color=WHITE)
ax.text(5, 10.6, 'Smart Trading & Retail Intelligence for Digital Economies', ha='center', fontsize=12, color=GRAY)
ax.plot([3, 7], [10.2, 10.2], color=BLUE, lw=2)
ax.text(5, 9.3, 'Product & Technical Documentation', ha='center', fontsize=14, color=PURPLE)
ax.text(5, 8.5, 'Internet of Agents Hackathon 2026', ha='center', fontsize=11, color=GRAY)
ax.text(5, 6.8, 'A multi-agent AI system that learns your preferences,', ha='center', fontsize=10, color=WHITE)
ax.text(5, 6.4, 'scrapes real products, enforces agentic guardrails,', ha='center', fontsize=10, color=WHITE)
ax.text(5, 6.0, 'and pays autonomously via x402 protocol.', ha='center', fontsize=10, color=WHITE)
ax.text(5, 4.5, 'Team', ha='center', fontsize=12, fontweight='bold', color=AMBER)
ax.text(5, 4.0, 'Swati Chauhan \u2014 Auth, Payment, x402, Dashboard, Guardrails', ha='center', fontsize=9, color=WHITE)
ax.text(5, 3.6, 'Rohit Mujumdar \u2014 RL, Reward, Shopping Agent, Scraping, Memory', ha='center', fontsize=9, color=WHITE)
ax.text(5, 2.4, 'Tech Stack', ha='center', fontsize=12, fontweight='bold', color=GREEN)
ax.text(5, 1.9, 'Claude Sonnet 4.6  \u2022  Thompson Sampling  \u2022  x402/USDC  \u2022  Base Sepolia', ha='center', fontsize=8, color=GRAY)
ax.text(5, 1.5, 'Jina.ai  \u2022  Streamlit  \u2022  FastAPI  \u2022  Python 3.12', ha='center', fontsize=8, color=GRAY)
pages.append(fig)

# ═══ PAGE 2: PROBLEM & SOLUTION ═══
fig, ax = new_page('Problem & Solution', 'Why autonomous shopping agents don\'t exist yet')
y = section(ax, 14.2, 'THE PROBLEM')
y = body(ax, y, 'AI assistants can recommend products but cannot buy them. The gap between\n"here\'s what I found" and "I bought it for you" requires solving 5 hard problems:')
y = bullet(ax, y, [
    'Discovery: Agents can\'t browse real websites \u2014 limited to APIs or hardcoded catalogs',
    'Learning: Each session starts from scratch \u2014 no memory of what worked before',
    'Payment: No standard protocol for machines to pay machines autonomously',
    'Trust: If an agent can spend your money, who controls what it\'s allowed to do?',
    'Collaboration: Agents from different teams can\'t work together \u2014 no shared standards',
])
y = section(ax, y - 0.2, 'OUR SOLUTION: STRIDE')
y = bullet(ax, y, [
    'Discovery: Live scraping of Zappos, StockX, GOAT, 6pm via Jina.ai \u2014 real products, real prices',
    'Learning: Thompson Sampling RL across 4 dimensions \u2014 measurably smarter over runs',
    'Payment: x402 protocol \u2014 real USDC on Base Sepolia, verifiable on BaseScan',
    'Trust: 4-layer guardrail system \u2014 preferences, auth, payment checks, protocol verification',
    'Collaboration: Agent UX endpoints \u2014 any external agent can discover and interact via HTTP',
])
y = section(ax, y - 0.2, 'KEY INSIGHT')
y = body(ax, y, 'An AI shopping agent needs the same infrastructure humans have: identity\n(who am I shopping for?), trust (what am I allowed to do?), learning (what\nworked last time?), payment (how do I pay?), guardrails (what should I never do?).')
pages.append(fig)

# ═══ PAGE 3: 6-AGENT ARCHITECTURE ═══
fig, ax = new_page('System Architecture', '6 agents connected by structured protocols')
y = section(ax, 14.2, 'THE 6-AGENT PIPELINE')
y = body(ax, y, 'Each run: Memory \u2192 RL Bandit \u2192 Auth \u2192 Shopping Agent \u2192 Payment \u2192 Reflexion \u2192 Memory')
card(ax, 0.3, 10.5, 3, 1.8, 'Agent 1: Memory', ['memory_agent.py (Rohit)', 'Reads context_graph.json', 'User prefs, history, insights', 'Single source of truth'], BLUE)
card(ax, 3.5, 10.5, 3, 1.8, 'Agent 2: RL Bandit', ['rl_bandit.py (Rohit)', 'Thompson Sampling', '4 bandits: site, query, filter,', 'abandon. Persists across sessions.'], PURPLE)
card(ax, 6.7, 10.5, 3, 1.8, 'Agent 3: Auth', ['auth_agent.py (Swati)', 'Issues scoped credential', '5 verification checks', 'Human approval gate (runs 1-3)'], AMBER)
card(ax, 0.3, 8.2, 3, 1.8, 'Agent 4: Shopping', ['shopping_agent.py (Rohit+Swati)', 'Claude Sonnet 4.6 ReAct loop', '7 actions incl NEED_APPROVAL', 'Guardrails in system prompt'], GREEN)
card(ax, 3.5, 8.2, 3, 1.8, 'Agent 5: Payment', ['payment_agent.py (Swati)', 'Real x402 on Base Sepolia', 'USDC via EIP-3009', 'Simulation fallback mode'], PINK)
card(ax, 6.7, 8.2, 3, 1.8, 'Agent 6: Reflexion', ['run_loop.py (Rohit)', 'Claude writes 1-sentence lesson', 'Fed into next run\'s prompt', 'Human-readable learning'], BLUE)
y = section(ax, 7.8, 'AGENT-TO-AGENT COMMUNICATION')
y = body(ax, y, 'Not just sequential \u2014 Shopping Agent queries Memory Agent mid-run:\n  Shopping: ASK_MEMORY "which site had best Yeezy prices?"\n  Memory: "StockX had reward 99, GOAT had 51"\n  Shopping: "I\'ll try StockX first."')
y = section(ax, y - 0.2, 'ORCHESTRATION')
y = body(ax, y, 'run_loop.py is a simple Python for-loop calling each agent in sequence.\nNo LangGraph, no LangChain, no framework. Each agent is a pure function\nthat takes a dict and returns a dict \u2014 LangGraph-ready by design.\nComplexity is in the agents, not the wiring.')
pages.append(fig)

# ═══ PAGE 4: THOMPSON SAMPLING ═══
fig, ax = new_page('Reinforcement Learning', 'Thompson Sampling \u2014 how the agent learns')
y = section(ax, 14.2, 'THE EXPLORE-EXPLOIT PROBLEM')
y = body(ax, y, 'Should the agent try a new site (explore) or stick with what worked (exploit)?\nThompson Sampling solves this with Bayesian probability.')
y = section(ax, y - 0.2, 'HOW IT WORKS')
y = bullet(ax, y, [
    'Each arm (e.g., site=zappos) has a Beta(alpha, beta) distribution',
    'Alpha = accumulated successes + 1 (prior). Beta = accumulated failures + 1',
    'To select: sample from each arm\'s Beta distribution, pick the highest',
    'After reward: normalize to [0,1], add to alpha (success) and beta (failure)',
    'Over time: successful arms get higher alpha \u2192 sampled more \u2192 exploitation',
    'But Beta distributions always have variance \u2192 occasionally tries low arms \u2192 exploration',
])
y = section(ax, y - 0.2, '4 INDEPENDENT BANDITS')
y = bullet(ax, y, [
    'Site (6 arms): zappos, 6pm, stockx, goat, nike, amazon',
    'Query Style (3 arms): broad, moderate, specific',
    'Filter Strategy (4 arms): price_first, brand_first, rating_first, size_first',
    'Abandon Threshold (3 arms): after_1_fail, after_2_fails, after_3_fails',
])
y = section(ax, y - 0.2, 'REWARD FUNCTION (reward.py)')
y = bullet(ax, y, [
    'Purchase completed: +40  |  Full match: +25  |  Under budget: +15  |  Fast delivery: +10',
    'Efficiency bonus (4 steps or fewer): +15  |  Checkout reached: +10  |  Partial match: +5',
    'Per step penalty: -4 each  |  Captcha: -15  |  Out of stock: -20  |  Over budget: -10',
    'Range: perfect run ~99 pts, failed run ~-55 pts. Wide spread makes learning visible.',
    'MAX_REWARD = 115 for normalization. Bandit state persists to bandit_state.json.',
])
pages.append(fig)

# ═══ PAGE 5: x402 PROTOCOL ═══
fig, ax = new_page('x402 Protocol', 'Machine-to-machine payments over HTTP')
y = section(ax, 14.2, 'WHAT IS x402?')
y = body(ax, y, 'HTTP 402 ("Payment Required") was reserved in 1999 but never used.\nCoinbase created x402 to implement it \u2014 enabling AI agents to pay\nfor services using stablecoins (USDC) over standard HTTP.')
y = section(ax, y - 0.2, 'THE 7-STEP FLOW')
y = bullet(ax, y, [
    'Step 1: Payment Agent sends POST /purchase to x402 Server',
    'Step 2: Server returns HTTP 402 + X-PAYMENT-REQUIRED header (price, token, recipient)',
    'Step 3: x402 SDK selects the matching payment scheme (EVM/Base Sepolia)',
    'Step 4: EthAccountSigner signs USDC transferWithAuthorization (EIP-3009)',
    'Step 5: SDK retries request with X-PAYMENT header (signed proof)',
    'Step 6: Server sends to facilitator (x402.org) for on-chain settlement',
    'Step 7: Facilitator verifies, USDC settles on Base Sepolia, server returns 200 OK',
])
y = section(ax, y - 0.2, 'OUR IMPLEMENTATION')
y = bullet(ax, y, [
    'Client: payment_agent.py \u2014 x402 SDK + EthAccountSigner, private key from .env',
    'Server: x402_server.py \u2014 FastAPI + PaymentMiddlewareASGI on port 4021',
    'Network: Base Sepolia (eip155:84532) \u2014 Coinbase L2 testnet',
    'Token: USDC at 0x036CbD53842c5426634e7929541eC2318f3dCF7e',
    'Facilitator: x402.org/facilitator \u2014 verifies and settles on-chain',
    'Wallet: eth_account.Account.create() \u2014 funded with free test USDC from Circle faucet',
])
y = section(ax, y - 0.2, 'WHY x402 MATTERS')
y = body(ax, y, 'x402 is an open standard. Any agent that speaks HTTP can pay any\nx402-enabled server. No API keys, no OAuth \u2014 the wallet IS the credential.\nWhen stores adopt x402, our agent connects directly \u2014 zero code change.')
pages.append(fig)

# ═══ PAGE 6: GUARDRAILS ═══
fig, ax = new_page('Agentic Guardrails', '4 layers of protection before any purchase')
y = section(ax, 14.2, 'WHY GUARDRAILS MATTER')
y = body(ax, y, 'An autonomous agent that can spend money needs constraints. Without guardrails,\nit might buy the wrong product, overspend, or ignore user\'s instructions.\nSTRIDE uses defense-in-depth: 4 independent layers, each catching different failures.')
y = section(ax, y - 0.2, 'LAYER 1: PREFERENCE GUARDRAILS (shopping_agent.py)')
y = bullet(ax, y, [
    'color: "REQUIRED COLOR: blue \u2014 only buy this color"',
    'specific_product: "ONLY buy Nike x Tiffany AF1. Do not substitute."',
    'custom_instructions: User\'s exact words injected into Claude\'s system prompt',
    'excluded_brands: "Never buy from these brands"',
    'NEED_APPROVAL action: flags non-matching products instead of buying',
])
y = section(ax, y - 0.2, 'LAYER 2: AUTH GUARDRAILS (auth_agent.py)')
y = bullet(ax, y, [
    'Session expiry (1 hour) \u2022 Site whitelist (6 stores) \u2022 Hard spend cap',
    'Budget enforcement \u2022 Human approval gate (first 3 runs)',
])
y = section(ax, y - 0.2, 'LAYER 3: PAYMENT GUARDRAILS (payment_agent.py)')
y = bullet(ax, y, [
    'Auth clearance required \u2022 Double-checks spend cap \u2022 Exploration mode (no payment until final run)',
])
y = section(ax, y - 0.2, 'LAYER 4: PROTOCOL GUARDRAILS (x402 + blockchain)')
y = bullet(ax, y, [
    'x402 middleware verifies payment signature \u2022 Facilitator validates on-chain',
    'Transaction irreversible but transparent \u2022 Verifiable on BaseScan',
])
y = section(ax, y - 0.2, 'GUARDRAILS IN ACTION')
y = body(ax, y, 'User: "I want Tiffany Nike AF1, ask before buying anything else"\nAgent finds Nike Pegasus \u2192 Layer 1: NEED_APPROVAL (not the requested product)\nAgent finds Tiffany AF1 over budget \u2192 Layer 2: blocked (exceeds budget)\nAgent finds Tiffany AF1 on bad site \u2192 Layer 2: blocked (site not in whitelist)\nAgent finds Tiffany AF1 on StockX at right price \u2192 All 4 layers pass \u2192 x402 pays')
pages.append(fig)

# ═══ PAGE 7: SCRAPING + AGENT UX ═══
fig, ax = new_page('Live Scraping & Agent UX', 'Real products + endpoints for the Internet of Agents')
y = section(ax, 14.2, 'LIVE WEB SCRAPING (live_scraper.py)')
y = body(ax, y, 'Jina.ai Reader fetches pages as markdown. Custom regex parsers extract products.\nClaude fallback if regex fails. Search URLs built dynamically from user brands.')
y = bullet(ax, y, [
    'Zappos (LIVE): regex captures name, price, rating, URL from markdown links',
    '6pm (LIVE): same parser as Zappos \u2014 discount inventory',
    'StockX (LIVE): regex captures from "[Product Lowest Ask price](url)" format',
    'GOAT (LIVE): regex captures from nested markdown image+link format',
    'Nike (SIMULATED): JS-heavy, falls back to catalog  |  Amazon (SIMULATED): bot-blocked',
])
y = section(ax, y - 0.2, 'AGENT UX ENDPOINTS (x402_server.py)')
y = body(ax, y, 'Traditional UX = buttons for humans. Agent UX = structured endpoints for AI agents.')
y = bullet(ax, y, [
    'GET /agent-profile \u2014 user preferences, trust rules, RL weights, lessons, payment info',
    'GET /agent-capabilities \u2014 every endpoint with description and input/output schema',
    'GET /agent-history \u2014 past runs with rewards, strategies, products, summary stats',
    'POST /purchase \u2014 x402-protected, any agent with USDC wallet can pay',
])
y = section(ax, y - 0.2, 'CONTEXT GRAPH SCHEMA (context_graph.json)')
y = body(ax, y, 'The single source of truth. Every agent reads from it. Onboarding writes to it.', color=GRAY)
y = bullet(ax, y, [
    'preferences: brands, size, budget, max_delivery_days, style + guardrails (color, specific_product, custom_instructions, excluded_brands)',
    'trust_rules: max_autonomous_spend, approved_categories, require_approval_first_n_runs',
    'history: every past run (strategy, reward, outcome)',
    'learned_insights: reflexion lessons from Claude',
    'rl_weights: current Thompson Sampling bandit weights per dimension',
])
y = section(ax, y - 0.2, 'INTERNET OF AGENTS ALIGNMENT')
y = bullet(ax, y, [
    '6 agents collaborating via structured protocols',
    'x402 machine-to-machine payments \u2014 open standard',
    'Agent UX endpoints \u2014 any agent can discover and interact',
    'Agentic guardrails \u2014 user-defined rules that constrain agents',
    'Learning compounds \u2014 bandit state persists, reflexion lessons feed next run',
])
pages.append(fig)

# ═══ PAGE 8: DEMO SCRIPT ═══
fig, ax = new_page('Demo Script', '2.5 minutes \u2014 what to show and when')
y = section(ax, 14.2, 'THE DEMO FLOW')
y = bullet(ax, y, [
    '[0:00 - 0:30] ONBOARDING: Type "I want Nike running shoes, size 10, budget 120, need them in 2 days." Show Claude extracting preferences. "Profile saved!"',
    '[0:30 - 0:45] GUARDRAILS: Point to sidebar showing brands, size, budget, color, custom instructions all captured from natural language.',
    '[0:45 - 0:50] LOAD RESULTS: Click "Load from run_results.json" \u2014 instant, no API calls.',
    '[0:50 - 1:10] REWARD CURVE: "Run 1 scored -24. By Run 8, it scored 99. The agent taught itself which site and strategy works best. That\'s Thompson Sampling."',
    '[1:10 - 1:40] REASONING TRACE: Compare Run 1 (8 steps, wrong site, abandoned) vs Run 8 (4 steps, perfect match). "No human told it which site was better."',
    '[1:40 - 1:55] PURCHASES: "Real products scraped from real websites. Click this \u2014 it goes to the actual product page on StockX."',
    '[1:55 - 2:10] PAYMENT: "Real x402 USDC transaction on Base Sepolia." Click BaseScan link. "Zero human in the loop."',
    '[2:10 - 2:30] AGENT UX: Click "Test /agent-profile". "Any agent on the internet can call this and instantly know how to shop for this user."',
])
y = section(ax, y - 0.2, 'IF JUDGES ASK...')
y = bullet(ax, y, [
    '"Can you run it live?" \u2192 Wait 60s (rate limit), click Run Agent Live with slider at 3.',
    '"What if I want something specific?" \u2192 Go to onboarding, type "I want Jordan 4 in black under 300, ask before buying anything else." Show guardrails.',
    '"Is this LangGraph?" \u2192 "No \u2014 simpler. Pure functions, simple loop. Complexity is in agents, not wiring. LangGraph-ready by design."',
    '"Is the payment real?" \u2192 "Yes \u2014 real USDC on Base Sepolia testnet. Click the BaseScan link. To go mainnet: change one config line."',
])
y = section(ax, y - 0.2, 'ONE-LINER FOR JUDGES')
y = body(ax, y, '"We built a network of 6 AI agents that scrape real websites, learn via\nreinforcement learning, respect user-defined guardrails, and pay with real\ncryptocurrency \u2014 all autonomously. This is what the internet looks like\nwhen agents are the users."', fontsize=10, color=AMBER)
pages.append(fig)

# ═══ SAVE ═══
with PdfPages('stride_product_doc.pdf') as pdf:
    for p in pages:
        pdf.savefig(p, facecolor=p.get_facecolor(), bbox_inches='tight')
        plt.close(p)

print(f'Generated stride_product_doc.pdf \u2014 {len(pages)} pages')
