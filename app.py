"""
Streamlit Dashboard — STRIDE Shopping Agent

3 screens:
  1. Onboarding: New user chats with Claude to set preferences
  2. Agent Run: Watch the agent shop in real-time
  3. Results: Reward curve, reasoning trace, bandit weights, payment log
"""

import json
import os
from pathlib import Path

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import anthropic

load_dotenv()

st.set_page_config(page_title="STRIDE", page_icon="🛒", layout="wide")

CONTEXT_GRAPH_PATH = Path("context_graph.json")
RUN_RESULTS_PATH = Path("run_results.json")

# Anthropic client — gracefully handle missing API key (e.g., on Streamlit Cloud)
_api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not _api_key:
    try:
        _api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        _api_key = ""
client = anthropic.Anthropic(api_key=_api_key) if _api_key else None

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0e1117; }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f2e 0%, #0e1117 100%);
        border-right: 1px solid #1e2a3a;
    }

    /* Card styling */
    .card {
        background: linear-gradient(135deg, #1a1f2e 0%, #151922 100%);
        border: 1px solid #1e2a3a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .card-highlight {
        background: linear-gradient(135deg, #1a2332 0%, #151d2a 100%);
        border: 1px solid #2563eb33;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #151922 100%);
        border: 1px solid #1e2a3a;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="stMetric"] label {
        color: #8b95a5 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #e2e8f0 !important;
        font-size: 1.5rem !important;
        font-weight: 600;
    }

    /* Hero header */
    .hero {
        text-align: center;
        padding: 40px 20px 30px;
        margin-bottom: 20px;
    }
    .hero h1 {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    .hero p {
        color: #8b95a5;
        font-size: 1.1rem;
    }

    /* Section headers */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 24px 0 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #1e2a3a;
    }
    .section-header h3 {
        color: #e2e8f0;
        font-size: 1.2rem;
        font-weight: 600;
        margin: 0;
    }

    /* Step cards in reasoning trace */
    .step-card {
        background: #151922;
        border-left: 3px solid #2563eb;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .step-card-action {
        background: #151922;
        border-left: 3px solid #10b981;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
    }

    /* Tag pills */
    .tag {
        display: inline-block;
        background: #1e2a3a;
        color: #60a5fa;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        margin: 2px 4px 2px 0;
    }
    .tag-green {
        background: #0d3320;
        color: #10b981;
    }
    .tag-purple {
        background: #2d1b4e;
        color: #a78bfa;
    }
    .tag-amber {
        background: #3d2e0a;
        color: #fbbf24;
    }

    /* Payment table */
    .dataframe { border-radius: 8px !important; }

    /* Chat messages */
    div[data-testid="stChatMessage"] {
        border-radius: 12px;
        border: 1px solid #1e2a3a;
        margin-bottom: 8px;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="secondary"] {
        border: 1px solid #1e2a3a !important;
        border-radius: 8px !important;
    }

    /* Expander */
    details {
        border: 1px solid #1e2a3a !important;
        border-radius: 8px !important;
        background: #151922 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background: #1a1f2e !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ──────────────────────────────────────────────────
if "screen" not in st.session_state:
    if CONTEXT_GRAPH_PATH.exists():
        cg = json.loads(CONTEXT_GRAPH_PATH.read_text())
        has_prefs = cg.get("user", {}).get("preferences", {}).get("brands")
        st.session_state.screen = "results" if has_prefs else "onboarding"
    else:
        st.session_state.screen = "onboarding"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "preferences_extracted" not in st.session_state:
    st.session_state.preferences_extracted = False
if "run_progress" not in st.session_state:
    st.session_state.run_progress = []

# Auto-load results on startup for demo
if "results" not in st.session_state and RUN_RESULTS_PATH.exists():
    try:
        raw = json.loads(RUN_RESULTS_PATH.read_text())
        if isinstance(raw, dict) and "runs" in raw:
            st.session_state.results = raw["runs"]
            if raw.get("best_candidate"):
                st.session_state.best_candidate = raw["best_candidate"]
        elif isinstance(raw, list):
            st.session_state.results = raw
    except Exception:
        pass
if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = False
if "best_candidate" not in st.session_state:
    st.session_state.best_candidate = None
if "show_feedback" not in st.session_state:
    st.session_state.show_feedback = False


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 16px 0;">
        <div style="font-size: 2.5rem;">🛒</div>
        <div style="font-size: 1.6rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">STRIDE</div>
        <div style="color: #8b95a5; font-size: 0.8rem; margin-top: 4px;">AI Shopping Agent</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    screen = st.radio(
        "Navigate",
        ["onboarding", "run", "results"],
        format_func=lambda x: {
            "onboarding": "👤  Setup Preferences",
            "run": "🚀  Run Agent",
            "results": "📊  Results Dashboard",
        }[x],
        index=["onboarding", "run", "results"].index(st.session_state.screen),
    )
    st.session_state.screen = screen

    st.divider()

    # Current profile card
    if CONTEXT_GRAPH_PATH.exists():
        cg = json.loads(CONTEXT_GRAPH_PATH.read_text())
        prefs = cg.get("user", {}).get("preferences", {})
        if prefs.get("brands"):
            st.markdown('<div style="color: #8b95a5; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px;">Current Profile</div>', unsafe_allow_html=True)

            brands_html = " ".join(f'<span class="tag">{b}</span>' for b in prefs.get("brands", []))
            st.markdown(f'{brands_html}', unsafe_allow_html=True)

            tags_html = f"""
            <div style="margin-top: 12px; line-height: 1.8;">
                <span class="tag-green tag">Size {prefs.get('size', '?')}</span>
                <span class="tag-purple tag">${prefs.get('budget', '?')} budget</span>
                <span class="tag-amber tag">{prefs.get('style', '?')}</span>
            """
            if prefs.get("color"):
                tags_html += f'<span class="tag" style="background:#1e1a3a; color:#818cf8;">{prefs["color"]}</span>'
            tags_html += "</div>"
            st.markdown(tags_html, unsafe_allow_html=True)

            if prefs.get("specific_product"):
                st.caption(f"Looking for: {prefs['specific_product']}")
            if prefs.get("custom_instructions"):
                st.caption(f"Rules: {prefs['custom_instructions']}")

            trust = cg.get("user", {}).get("trust_rules", {})
            st.caption(f"Spend cap: ${trust.get('max_autonomous_spend', '?')}")

    st.divider()
    st.markdown("""
    <div style="text-align: center;">
        <div style="color: #4b5563; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em;">Internet of Agents Hackathon</div>
        <div style="color: #374151; font-size: 0.65rem; margin-top: 4px;">Claude Sonnet 4.6 + Thompson Sampling + x402</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.screen == "onboarding":

    st.markdown("""
    <div class="hero">
        <h1>Welcome to STRIDE</h1>
        <p>Your AI shopping agent that learns your style, finds the best deals, and pays autonomously.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header"><h3>Chat with your agent to get started</h3></div>', unsafe_allow_html=True)
    st.caption("Tell STRIDE what you're looking for in natural language. It'll set up your profile automatically.")

    SYSTEM_PROMPT = """You are the onboarding assistant for STRIDE, a personal shopping agent.
Your job: have a friendly conversation to learn the user's shopping preferences.

You need to extract these REQUIRED fields:
- brands (list of preferred brands, e.g. Nike, Adidas, Jordan)
- size (shoe size, numeric)
- budget (max they want to spend, in dollars)
- max_delivery_days (how fast they need it)
- style (running, casual, basketball, etc.)
- max_autonomous_spend (max the agent can spend without asking — usually same or slightly above budget)

Also listen for these OPTIONAL fields (include them if the user mentions them):
- color (preferred color, e.g. "blue", "black/red")
- specific_product (exact product they want, e.g. "Jordan 4 Retro", "Yeezy Boost 350")
- custom_instructions (any special rules, e.g. "ask me before buying anything that isn't Jordan", "only buy on sale")
- excluded_brands (brands they do NOT want, e.g. "no Reebok")

Pay close attention to instructions like "ask me before...", "don't buy...", "only buy...". These go in custom_instructions.

Be conversational and friendly. Ask follow-up questions if needed. Once you have ALL required info,
respond with EXACTLY this format at the end of your message (the system will parse it):

PREFERENCES_JSON:
{"brands": ["Jordan"], "size": 10, "budget": 300, "max_delivery_days": 3, "style": "casual", "max_autonomous_spend": 350, "color": "blue", "specific_product": "Jordan 4 Retro", "custom_instructions": "ask me before buying anything that is not Jordan", "excluded_brands": []}

Only output the JSON block when you have ALL required fields. Until then, keep chatting.
Include optional fields only if the user mentioned them. Omit them if not mentioned."""

    # Chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar="🛒" if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    if not st.session_state.chat_history:
        greeting = "Hey! I'm **STRIDE**, your personal shopping agent. I'll learn what you like and hunt down the best deals across the internet.\n\nWhat kind of shoes are you looking for today?"
        st.session_state.chat_history.append({"role": "assistant", "content": greeting})
        st.rerun()

    if user_input := st.chat_input("Tell me what you're looking for..."):
        if not client:
            st.error("No API key configured. Add ANTHROPIC_API_KEY to Streamlit secrets or .env file.")
            st.stop()

        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar="🛒"):
            with st.spinner("Thinking..."):
                messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=500,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                )
                reply = response.content[0].text

            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})

            if "PREFERENCES_JSON:" in reply:
                try:
                    json_str = reply.split("PREFERENCES_JSON:")[1].strip()
                    if "\n\n" in json_str:
                        json_str = json_str.split("\n\n")[0]
                    prefs = json.loads(json_str)

                    cg = json.loads(CONTEXT_GRAPH_PATH.read_text()) if CONTEXT_GRAPH_PATH.exists() else {"user": {}, "history": [], "learned_insights": []}
                    user_prefs = {
                        "brands": prefs["brands"],
                        "size": prefs["size"],
                        "budget": prefs["budget"],
                        "max_delivery_days": prefs["max_delivery_days"],
                        "style": prefs["style"],
                    }
                    # Optional guardrail fields
                    if prefs.get("color"):
                        user_prefs["color"] = prefs["color"]
                    if prefs.get("specific_product"):
                        user_prefs["specific_product"] = prefs["specific_product"]
                    if prefs.get("custom_instructions"):
                        user_prefs["custom_instructions"] = prefs["custom_instructions"]
                    if prefs.get("excluded_brands"):
                        user_prefs["excluded_brands"] = prefs["excluded_brands"]

                    # Reset user section cleanly for new query (no stale feedback/query from previous runs)
                    cg["user"] = {
                        "preferences": user_prefs,
                        "trust_rules": {
                            "max_autonomous_spend": prefs.get("max_autonomous_spend", prefs["budget"] + 30),
                            "approved_categories": ["footwear"],
                            "require_approval_first_n_runs": 3,
                        },
                    }
                    # Store original query text so shopping agent can use exact terms
                    user_msgs = [m["content"] for m in st.session_state.chat_history if m["role"] == "user"]
                    cg["user"]["original_query"] = " | ".join(user_msgs)
                    CONTEXT_GRAPH_PATH.write_text(json.dumps(cg, indent=2))
                    st.session_state.preferences_extracted = True
                    st.success("Profile saved! Head to **Run Agent** to start shopping.")
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

    # Quick setup
    st.markdown("")
    with st.expander("Quick setup (skip chat)"):
        with st.form("quick_setup"):
            col1, col2 = st.columns(2)
            with col1:
                brands = st.multiselect("Brands", ["Nike", "Adidas", "Jordan", "New Balance", "HOKA", "Brooks", "Asics", "Reebok", "Yeezy"], default=["Nike", "Adidas"])
                size = st.number_input("Shoe size", min_value=5, max_value=16, value=10)
                style = st.selectbox("Style", ["running", "casual", "basketball", "trail", "walking"])
                color = st.text_input("Preferred color (optional)", placeholder="e.g. blue, black/red")
            with col2:
                budget = st.number_input("Budget ($)", min_value=30, max_value=500, value=120)
                max_days = st.number_input("Max delivery days", min_value=1, max_value=7, value=2)
                spend_cap = st.number_input("Agent spend cap ($)", min_value=30, max_value=500, value=150)
                specific_product = st.text_input("Specific product (optional)", placeholder="e.g. Jordan 4 Retro")
            custom_instructions = st.text_area("Custom instructions (optional)", placeholder="e.g. Ask me before buying anything that isn't Jordan")
            search_query = st.text_input("What are you looking for? (natural language)", placeholder="e.g. blue Nike Jordan 4 Retro basketball shoes")

            if st.form_submit_button("Save Profile", type="primary"):
                cg = json.loads(CONTEXT_GRAPH_PATH.read_text()) if CONTEXT_GRAPH_PATH.exists() else {"user": {}, "history": [], "learned_insights": []}
                user_prefs = {"brands": brands, "size": size, "budget": budget, "max_delivery_days": max_days, "style": style}
                if color:
                    user_prefs["color"] = color
                if specific_product:
                    user_prefs["specific_product"] = specific_product
                if custom_instructions:
                    user_prefs["custom_instructions"] = custom_instructions
                # Reset user section cleanly for new query (no stale feedback/query from previous runs)
                cg["user"] = {
                    "preferences": user_prefs,
                    "trust_rules": {"max_autonomous_spend": spend_cap, "approved_categories": ["footwear"], "require_approval_first_n_runs": 3},
                }
                # Store original query for shopping agent search terms
                if search_query:
                    cg["user"]["original_query"] = search_query
                else:
                    # Construct from fields
                    cg["user"]["original_query"] = f"{color} {' '.join(brands)} {specific_product} {style} shoes size {size}".strip()
                CONTEXT_GRAPH_PATH.write_text(json.dumps(cg, indent=2))
                st.success("Profile saved! Head to **Run Agent** to start shopping.")
                st.session_state.preferences_extracted = True


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: RUN AGENT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.screen == "run":

    st.markdown("""
    <div class="hero">
        <h1>Launch STRIDE</h1>
        <p>Your agent will search real websites, compare products, and pay via x402 on Base Sepolia.</p>
    </div>
    """, unsafe_allow_html=True)

    if not CONTEXT_GRAPH_PATH.exists():
        st.warning("Set up your preferences first in the **Setup Preferences** tab.")
        st.stop()

    cg = json.loads(CONTEXT_GRAPH_PATH.read_text())
    if not cg.get("user", {}).get("preferences", {}).get("brands"):
        st.warning("Set up your preferences first in the **Setup Preferences** tab.")
        st.stop()

    prefs = cg["user"]["preferences"]
    trust = cg["user"]["trust_rules"]

    # Agent knowledge cards
    st.markdown('<div class="section-header"><h3>Agent Knowledge</h3></div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Brands", ", ".join(prefs.get("brands", [])))
    col2.metric("Size", prefs.get("size", "?"))
    col3.metric("Budget", f"${prefs.get('budget', '?')}")
    col4.metric("Spend Cap", f"${trust.get('max_autonomous_spend', '?')}")

    st.markdown("")

    # Architecture visual
    st.markdown("""
    <div class="card" style="text-align: center; padding: 24px;">
        <div style="color: #8b95a5; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 16px;">Agent Pipeline</div>
        <div style="font-size: 1rem; color: #e2e8f0; line-height: 2;">
            <span class="tag">Memory Agent</span> &rarr;
            <span class="tag-purple tag">RL Bandit</span> &rarr;
            <span class="tag-amber tag">Auth Agent</span> &rarr;
            <span class="tag">Claude Sonnet 4.6</span> &rarr;
            <span class="tag-green tag">x402 Payment</span> &rarr;
            <span class="tag-purple tag">Reflexion</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_run, col_load = st.columns(2)

    with col_run:
        st.markdown('<div class="card-highlight">', unsafe_allow_html=True)
        num_runs = st.slider("Number of episodes", min_value=3, max_value=10, value=10)
        if st.button("🚀 Run Agent Live", type="primary", use_container_width=True):
            try:
                from run_loop import run_full_loop
                status_container = st.status(f"Running {num_runs} episodes...", expanded=True)
                log_area = status_container.empty()
                logs = []

                def on_status(msg):
                    logs.append(msg)
                    # Show last 12 lines to keep it readable
                    log_area.code("\n".join(logs[-12:]), language=None)

                output = run_full_loop(total_runs=num_runs, status_callback=on_status)
                status_container.update(label="✅ All episodes complete!", state="complete")
                st.session_state.results = output
                st.session_state.best_candidate = output.get("best_candidate")
                st.session_state.awaiting_approval = True
            except Exception as e:
                st.error(f"Run failed: {e}")
                st.session_state.awaiting_approval = False
        st.markdown('</div>', unsafe_allow_html=True)

    with col_load:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Load previous results**")
        st.caption("View results from the last run without re-running.")
        if st.button("📂 Load from run_results.json", use_container_width=True):
            if RUN_RESULTS_PATH.exists():
                st.session_state.results = json.loads(RUN_RESULTS_PATH.read_text())
                st.session_state.best_candidate = st.session_state.results.get("best_candidate")
                st.session_state.awaiting_approval = bool(st.session_state.best_candidate)
                st.success("Loaded previous results.")
            else:
                st.error("No run_results.json found.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── HUMAN APPROVAL GATE ─────────────────────────────────────────────
    if st.session_state.get("awaiting_approval") and st.session_state.get("best_candidate"):
        candidate = st.session_state.best_candidate
        product = candidate["product"]

        st.markdown("---")
        st.markdown('<div class="section-header"><h3>Best Product Found — Your Approval Needed</h3></div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card-highlight" style="padding: 24px;">
            <div style="font-size: 1.3rem; font-weight: 700; color: #e2e8f0;">{product['name']}</div>
            <div style="margin-top: 8px; color: #8b95a5;">
                Brand: <strong>{product.get('brand', '?')}</strong> &bull;
                Price: <strong style="color: #10b981;">${product['price']}</strong> &bull;
                Site: <strong>{candidate['strategy']['site']}</strong> &bull;
                Reward: <strong>{candidate['reward']} pts</strong>
            </div>
            {f'<div style="margin-top: 8px;"><a href="{product["url"]}" target="_blank" style="color: #60a5fa;">View on site</a></div>' if product.get('url') else ''}
        </div>
        """, unsafe_allow_html=True)

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("✅ Buy This", type="primary", use_container_width=True):
                from run_loop import execute_approved_purchase
                cg_current = json.loads(CONTEXT_GRAPH_PATH.read_text())
                pay_result = execute_approved_purchase(product, cg_current)
                if pay_result.get("success"):
                    st.success(f"Purchased! Confirmation: {pay_result.get('confirmation_id')}")
                else:
                    st.error(f"Payment failed: {pay_result.get('reason')}")
                st.session_state.awaiting_approval = False
                # Clear feedback from previous rejections
                cg_current.pop("feedback", None)
                if "user" in cg_current:
                    cg_current["user"].pop("feedback", None)
                CONTEXT_GRAPH_PATH.write_text(json.dumps(cg_current, indent=2))

        with col_reject:
            if st.button("❌ Not what I wanted", use_container_width=True):
                st.session_state.show_feedback = True

        if st.session_state.get("show_feedback"):
            feedback = st.text_input("What's wrong? What do you actually want?", placeholder="e.g. I said Jordan 4 not Pegasus")
            if st.button("Re-run with feedback", type="primary"):
                if feedback:
                    from run_loop import apply_rejection_feedback, run_full_loop
                    apply_rejection_feedback(feedback, candidate["strategy"])
                    st.session_state.show_feedback = False
                    st.session_state.awaiting_approval = False
                    status_container = st.status(f"Re-running {num_runs} episodes with feedback...", expanded=True)
                    log_area = status_container.empty()
                    logs = []

                    def on_status(msg):
                        logs.append(msg)
                        log_area.code("\n".join(logs[-12:]), language=None)

                    output = run_full_loop(total_runs=num_runs, status_callback=on_status)
                    status_container.update(label="✅ Re-run complete!", state="complete")
                    st.session_state.results = output
                    st.session_state.best_candidate = output.get("best_candidate")
                    st.session_state.awaiting_approval = True
                    st.rerun()
                else:
                    st.warning("Please enter feedback so the agent knows what to look for.")
    elif st.session_state.get("awaiting_approval") and not st.session_state.get("best_candidate"):
        st.warning("Agent explored but couldn't find a product matching your criteria. Try adjusting preferences.")
        st.session_state.awaiting_approval = False


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: RESULTS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.screen == "results":

    raw_results = st.session_state.get("results")
    if not raw_results and RUN_RESULTS_PATH.exists():
        raw_results = json.loads(RUN_RESULTS_PATH.read_text())
        st.session_state.results = raw_results

    # Handle both old format (list) and new format (dict with "runs" key)
    if isinstance(raw_results, dict):
        results = raw_results.get("runs", [])
    elif isinstance(raw_results, list):
        results = raw_results
    else:
        results = []

    if not results:
        st.info("No results yet. Run the agent first in the **Run Agent** tab.")
        st.stop()

    # Hero
    first = results[0]["reward"]
    last = results[-1]["reward"]
    best_run = max(results, key=lambda r: r["reward"])
    improvement = last - first

    st.markdown(f"""
    <div class="hero">
        <h1>STRIDE Results</h1>
        <p>{'Agent improved by ' + str(improvement) + '+ points across ' + str(len(results)) + ' runs' if improvement > 0 else str(len(results)) + ' shopping episodes completed'}</p>
    </div>
    """, unsafe_allow_html=True)

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Run 1", f"{first} pts")
    col2.metric(f"Run {len(results)}", f"{last} pts", delta=f"{improvement:+} pts")
    col3.metric("Best Run", f"Run {best_run['run']} ({best_run['reward']} pts)")
    col4.metric("Success Rate", f"{sum(1 for r in results if r['outcome'] == 'purchased')}/{len(results)}")

    st.markdown("")

    # ── Purchases Gallery ───────────────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>🛍️ What STRIDE Bought</h3></div>', unsafe_allow_html=True)
    st.caption("Products purchased across all runs — with links to the real product pages")

    purchased = [r for r in results if r.get("product") and r["outcome"] == "purchased"]

    if purchased:
        # Show in rows of 3
        for i in range(0, len(purchased), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(purchased):
                    r = purchased[i + j]
                    prod = r["product"]
                    pay = r.get("payment", {})
                    name = prod.get("name", "Unknown")
                    price = prod.get("price", "?")
                    brand = prod.get("brand", "?")
                    site = r["strategy"]["site"]
                    reward = r["reward"]
                    live = prod.get("live", False)
                    url = prod.get("url", "")

                    # Generate search URL on the actual site if no direct URL
                    if not url:
                        search_name = name.replace(" ", "+").replace("'", "")
                        site_search = {
                            "goat": f"https://www.goat.com/search?query={search_name}",
                            "stockx": f"https://stockx.com/search?s={search_name}",
                            "amazon": f"https://www.amazon.com/s?k={search_name}",
                            "nike": f"https://www.nike.com/w?q={search_name}",
                            "zappos": f"https://www.zappos.com/search?term={search_name}",
                            "6pm": f"https://www.6pm.com/search?term={search_name}",
                        }
                        url = site_search.get(site, f"https://www.google.com/search?q={search_name}+sneakers&tbm=shop")

                    # Generate image search URL for thumbnail
                    img_search = name.replace(" ", "+")
                    img_url = f"https://www.google.com/search?q={img_search}&tbm=isch"

                    # Payment status
                    if pay.get("success"):
                        tx = pay.get("transaction_hash", "")
                        if tx:
                            pay_html = f'<a href="https://sepolia.basescan.org/tx/{tx}" target="_blank" style="color: #10b981; text-decoration: none; font-size: 0.75rem;">View on BaseScan ↗</a>'
                        else:
                            pay_html = '<span style="color: #10b981; font-size: 0.75rem;">x402 Confirmed</span>'
                    else:
                        pay_html = '<span style="color: #ef4444; font-size: 0.75rem;">Payment failed</span>'

                    source_tag = f'<span class="tag-green tag" style="font-size: 0.65rem;">LIVE</span>' if live else '<span class="tag" style="font-size: 0.65rem;">SIM</span>'

                    with col:
                        st.markdown(f"""
                        <div class="card" style="min-height: 200px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="color: #8b95a5; font-size: 0.7rem;">RUN {r['run']}</span>
                                <span class="tag" style="font-size: 0.65rem;">{site}</span>
                            </div>
                            <div style="color: #e2e8f0; font-weight: 600; font-size: 1rem; margin-bottom: 6px;">{name[:40]}</div>
                            <div style="margin: 8px 0;">
                                <span style="color: #60a5fa; font-size: 1.3rem; font-weight: 700;">${price}</span>
                                <span style="color: #8b95a5; font-size: 0.8rem; margin-left: 8px;">{brand}</span>
                                {source_tag}
                            </div>
                            <div style="margin: 8px 0;">
                                <span class="tag-amber tag" style="font-size: 0.65rem;">{reward} pts</span>
                            </div>
                            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                                <a href="{url}" target="_blank" style="color: #60a5fa; text-decoration: none; font-size: 0.75rem; background: #1e2a3a; padding: 4px 10px; border-radius: 6px;">View Product ↗</a>
                                {pay_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        st.caption("No purchases yet.")

    st.markdown("")

    # ── Reward Curve ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>📈 Reward Curve</h3></div>', unsafe_allow_html=True)
    st.caption("Thompson Sampling learns which site + strategy combo works best for you")

    reward_df = pd.DataFrame({"Run": [r["run"] for r in results], "Reward": [r["reward"] for r in results]})
    st.line_chart(reward_df, x="Run", y="Reward", height=350, color="#60a5fa")

    with st.expander("Reward breakdown (latest run)"):
        breakdown = results[-1].get("reward_breakdown", {})
        if breakdown:
            bd_df = pd.DataFrame({"Component": list(breakdown.keys()), "Points": list(breakdown.values())})
            st.bar_chart(bd_df, x="Component", y="Points", height=250)

    st.markdown("")

    # ── Reasoning Trace ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>🧠 Reasoning Trace</h3></div>', unsafe_allow_html=True)
    st.caption("Watch Claude Sonnet 4.6 think, act, and learn step by step")

    selected_run = st.selectbox(
        "Select run",
        options=[r["run"] for r in results],
        format_func=lambda x: f"Run {x}  |  {results[x-1]['reward']} pts  |  {results[x-1]['outcome']}  |  {results[x-1]['strategy']['site']}",
    )

    run_data = results[selected_run - 1]
    strat = run_data["strategy"]

    # Strategy tags
    st.markdown(f"""
    <div style="margin: 12px 0;">
        <span class="tag">🌐 {strat['site']}</span>
        <span class="tag-purple tag">🔍 {strat['query_style']}</span>
        <span class="tag-amber tag">📊 {strat['filter_strategy']}</span>
        <span class="tag-green tag">🚪 {strat['abandon_threshold']}</span>
    </div>
    """, unsafe_allow_html=True)

    # Product bought
    product = run_data.get("product")
    if product:
        p_name = product.get("name", "?")
        p_price = product.get("price", "?")
        p_brand = product.get("brand", "?")
        live = "LIVE" if product.get("live") else "SIM"
        st.markdown(f"""
        <div class="card-highlight" style="display: flex; align-items: center; gap: 16px;">
            <div style="font-size: 2rem;">🛒</div>
            <div>
                <div style="color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">{p_name}</div>
                <div style="color: #8b95a5; margin-top: 4px;">
                    <span class="tag-green tag">${p_price}</span>
                    <span class="tag">{p_brand}</span>
                    <span class="tag-purple tag">{live}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Reflexion lesson
    if run_data.get("lesson"):
        st.markdown(f"""
        <div class="card" style="border-left: 3px solid #a78bfa;">
            <div style="color: #a78bfa; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Reflexion Lesson</div>
            <div style="color: #e2e8f0; margin-top: 8px;">{run_data['lesson']}</div>
        </div>
        """, unsafe_allow_html=True)

    # Trace steps
    trace = run_data.get("reasoning_trace", [])
    for step in trace:
        step_num = step.get("step", "?")
        thought = step.get("thought", "")
        action = step.get("action", "")

        if thought:
            st.markdown(f"""
            <div class="step-card">
                <div style="color: #60a5fa; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;">Step {step_num} — Thought</div>
                <div style="color: #cbd5e1; margin-top: 6px; font-size: 0.9rem;">{thought}</div>
            </div>
            """, unsafe_allow_html=True)

        if action:
            st.markdown(f"""
            <div class="step-card-action">
                <div style="color: #10b981; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;">Step {step_num} — Action</div>
                <code style="color: #e2e8f0; font-size: 0.9rem;">{action}</code>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # ── Agent's Learned Preferences ───────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>🎰 Agent\'s Learned Preferences</h3></div>', unsafe_allow_html=True)
    st.caption("What the agent currently believes works best for you — based on Thompson Sampling")

    # Show the FINAL state (what the agent learned after all episodes)
    final_state = results[-1].get("bandit_state", {})
    if final_state:
        dim_labels = {
            "site": ("🌐 Best Site", "Which shopping site finds your products fastest"),
            "query_style": ("🔍 Search Strategy", "How specific the search query should be"),
            "filter_strategy": ("📊 Filter Priority", "What to optimize for when comparing results"),
            "abandon_threshold": ("🚪 Patience", "How many failures before trying another site"),
        }

        cols = st.columns(2)
        for i, (dim, arms) in enumerate(final_state.items()):
            label, desc = dim_labels.get(dim, (dim, ""))
            with cols[i % 2]:
                st.markdown(f"**{label}**")
                st.caption(desc)
                bar_data = pd.DataFrame(arms)
                bar_data = bar_data.sort_values("mean", ascending=True)
                st.bar_chart(bar_data, x="arm", y="mean", height=200, color="#60a5fa")

        st.markdown("")

    # Evolution over episodes (collapsible)
    with st.expander("📈 How preferences shifted across episodes"):
        dimensions = ["site", "query_style", "filter_strategy", "abandon_threshold"]
        tabs = st.tabs(["🌐 Site", "🔍 Query", "📊 Filter", "🚪 Patience"])

        for tab, dim in zip(tabs, dimensions):
            with tab:
                rows = []
                for r in results:
                    weights = r.get("bandit_weights", {}).get(dim, {})
                    for arm, weight in weights.items():
                        rows.append({"Run": r["run"], "Arm": arm, "Weight": weight})
                if rows:
                    df = pd.DataFrame(rows)
                    pivot = df.pivot(index="Run", columns="Arm", values="Weight")
                    st.line_chart(pivot, height=250)

    st.markdown("")

    # ── Payment Log ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>💳 Payment Log (x402 on Base Sepolia)</h3></div>', unsafe_allow_html=True)
    st.caption("Real on-chain USDC transactions — click tx hash to verify on BaseScan")

    payment_rows = []
    for r in results:
        pay = r.get("payment", {})
        prod = r.get("product") or {}
        tx = pay.get("transaction_hash", "")
        tx_display = tx[:16] + "..." if tx and tx != "—" else "—"

        payment_rows.append({
            "Run": r["run"],
            "Product": prod.get("name", "—"),
            "Price": f"${prod.get('price', 0)}" if prod.get("price") else "—",
            "Status": "✅ Paid" if pay.get("success") else "❌ " + str(pay.get("reason", "Failed"))[:40],
            "Protocol": pay.get("protocol", "—"),
            "Tx Hash": tx_display,
        })

    pay_df = pd.DataFrame(payment_rows)
    st.dataframe(pay_df, use_container_width=True, hide_index=True)

    st.markdown("")

    # ── Agent UX Endpoints ──────────────────────────────────────────────────
    st.markdown('<div class="section-header"><h3>🌐 Agent UX Endpoints</h3></div>', unsafe_allow_html=True)
    st.caption("Any external agent can discover and interact with STRIDE via these APIs")

    ep1, ep2, ep3 = st.columns(3)
    with ep1:
        st.markdown("""
        <div class="card" style="text-align: center; min-height: 120px;">
            <div style="font-size: 1.5rem; margin-bottom: 8px;">👤</div>
            <div style="color: #e2e8f0; font-weight: 600;">GET /agent-profile</div>
            <div style="color: #8b95a5; font-size: 0.8rem; margin-top: 4px;">User preferences, trust rules, learned RL weights</div>
        </div>
        """, unsafe_allow_html=True)
    with ep2:
        st.markdown("""
        <div class="card" style="text-align: center; min-height: 120px;">
            <div style="font-size: 1.5rem; margin-bottom: 8px;">🗺️</div>
            <div style="color: #e2e8f0; font-weight: 600;">GET /agent-capabilities</div>
            <div style="color: #8b95a5; font-size: 0.8rem; margin-top: 4px;">API contract for all endpoints — sitemap for agents</div>
        </div>
        """, unsafe_allow_html=True)
    with ep3:
        st.markdown("""
        <div class="card" style="text-align: center; min-height: 120px;">
            <div style="font-size: 1.5rem; margin-bottom: 8px;">💰</div>
            <div style="color: #e2e8f0; font-weight: 600;">POST /purchase</div>
            <div style="color: #8b95a5; font-size: 0.8rem; margin-top: 4px;">x402 USDC payment on Base Sepolia</div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("🔌 Test /agent-profile (live)"):
        try:
            import httpx
            resp = httpx.get("http://localhost:4021/agent-profile", timeout=5)
            st.json(resp.json())
        except Exception:
            st.warning("x402 server not running. Start with: `uv run python x402_server.py`")
