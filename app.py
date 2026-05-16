"""
Streamlit Dashboard — Merchant Copilot Shopping Agent

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

st.set_page_config(page_title="Merchant Copilot", page_icon="🛒", layout="wide")

CONTEXT_GRAPH_PATH = Path("context_graph.json")
RUN_RESULTS_PATH = Path("run_results.json")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# ── Session state defaults ──────────────────────────────────────────────────
if "screen" not in st.session_state:
    # Auto-detect: if context graph has no history, show onboarding
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


# ── Sidebar navigation ─────────────────────────────────────────────────────
with st.sidebar:
    st.title("🛒 Merchant Copilot")
    st.caption("RL Shopping Agent + x402 Payments")
    st.divider()

    screen = st.radio(
        "Navigate",
        ["onboarding", "run", "results"],
        format_func=lambda x: {"onboarding": "👤 Setup Preferences", "run": "🏃 Run Agent", "results": "📊 Results Dashboard"}[x],
        index=["onboarding", "run", "results"].index(st.session_state.screen),
    )
    st.session_state.screen = screen

    st.divider()

    # Show current preferences if they exist
    if CONTEXT_GRAPH_PATH.exists():
        cg = json.loads(CONTEXT_GRAPH_PATH.read_text())
        prefs = cg.get("user", {}).get("preferences", {})
        if prefs.get("brands"):
            st.markdown("**Current Profile**")
            st.caption(f"Brands: {', '.join(prefs.get('brands', []))}")
            st.caption(f"Size: {prefs.get('size', '?')}")
            st.caption(f"Budget: ${prefs.get('budget', '?')}")
            st.caption(f"Style: {prefs.get('style', '?')}")
            trust = cg.get("user", {}).get("trust_rules", {})
            st.caption(f"Spend cap: ${trust.get('max_autonomous_spend', '?')}")

    st.divider()
    st.caption("Internet of Agents Hackathon")
    st.caption("Claude Sonnet 4.6 + Thompson Sampling + x402")


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1: ONBOARDING — Chat with Claude to set preferences
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.screen == "onboarding":
    st.header("👤 Tell your shopping agent about yourself")
    st.markdown("Chat naturally — the agent will learn your preferences and set up your profile.")

    SYSTEM_PROMPT = """You are the onboarding assistant for Merchant Copilot, a personal shopping agent.
Your job: have a friendly conversation to learn the user's shopping preferences.

You need to extract:
- brands (list of preferred brands, e.g. Nike, Adidas, New Balance)
- size (shoe size, numeric)
- budget (max they want to spend, in dollars)
- max_delivery_days (how fast they need it)
- style (running, casual, basketball, etc.)
- max_autonomous_spend (max the agent can spend without asking — usually same or slightly above budget)

Be conversational and friendly. Ask follow-up questions if needed. Once you have ALL the info,
respond with EXACTLY this format at the end of your message (the system will parse it):

PREFERENCES_JSON:
{"brands": ["Nike", "Adidas"], "size": 10, "budget": 120, "max_delivery_days": 2, "style": "running", "max_autonomous_spend": 150}

Only output the JSON block when you have ALL fields. Until then, keep chatting."""

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Show initial greeting if empty
    if not st.session_state.chat_history:
        greeting = "Hey! I'm your personal shopping agent. I'll learn what you like and find the best deals across the internet. Let's start — what kind of shoes are you looking for?"
        st.session_state.chat_history.append({"role": "assistant", "content": greeting})
        st.rerun()

    # Chat input
    if user_input := st.chat_input("Tell me what you're looking for..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        # Call Claude
        with st.chat_message("assistant"):
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

            # Check if preferences were extracted
            if "PREFERENCES_JSON:" in reply:
                try:
                    json_str = reply.split("PREFERENCES_JSON:")[1].strip()
                    # Handle case where JSON is followed by more text
                    if "\n\n" in json_str:
                        json_str = json_str.split("\n\n")[0]
                    prefs = json.loads(json_str)

                    # Write to context graph
                    cg = json.loads(CONTEXT_GRAPH_PATH.read_text()) if CONTEXT_GRAPH_PATH.exists() else {"user": {}, "history": [], "learned_insights": []}
                    cg["user"]["preferences"] = {
                        "brands": prefs["brands"],
                        "size": prefs["size"],
                        "budget": prefs["budget"],
                        "max_delivery_days": prefs["max_delivery_days"],
                        "style": prefs["style"],
                    }
                    cg["user"]["trust_rules"] = {
                        "max_autonomous_spend": prefs.get("max_autonomous_spend", prefs["budget"] + 30),
                        "approved_categories": ["footwear"],
                        "require_approval_first_n_runs": 3,
                    }
                    CONTEXT_GRAPH_PATH.write_text(json.dumps(cg, indent=2))

                    st.session_state.preferences_extracted = True
                    st.success("Profile saved! Head to **Run Agent** to start shopping.")
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass  # Claude didn't output valid JSON yet, keep chatting

    # Quick setup option
    with st.expander("Or quick setup (skip chat)"):
        with st.form("quick_setup"):
            col1, col2 = st.columns(2)
            with col1:
                brands = st.multiselect("Brands", ["Nike", "Adidas", "New Balance", "HOKA", "Brooks", "Asics", "Reebok"], default=["Nike", "Adidas"])
                size = st.number_input("Shoe size", min_value=5, max_value=16, value=10)
                style = st.selectbox("Style", ["running", "casual", "basketball", "trail", "walking"])
            with col2:
                budget = st.number_input("Budget ($)", min_value=30, max_value=500, value=120)
                max_days = st.number_input("Max delivery days", min_value=1, max_value=7, value=2)
                spend_cap = st.number_input("Agent spend cap ($)", min_value=30, max_value=500, value=150)

            if st.form_submit_button("Save Profile", type="primary"):
                cg = json.loads(CONTEXT_GRAPH_PATH.read_text()) if CONTEXT_GRAPH_PATH.exists() else {"user": {}, "history": [], "learned_insights": []}
                cg["user"]["preferences"] = {
                    "brands": brands,
                    "size": size,
                    "budget": budget,
                    "max_delivery_days": max_days,
                    "style": style,
                }
                cg["user"]["trust_rules"] = {
                    "max_autonomous_spend": spend_cap,
                    "approved_categories": ["footwear"],
                    "require_approval_first_n_runs": 3,
                }
                CONTEXT_GRAPH_PATH.write_text(json.dumps(cg, indent=2))
                st.success("Profile saved! Head to **Run Agent** to start shopping.")
                st.session_state.preferences_extracted = True


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2: RUN AGENT — Execute shopping loop
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.screen == "run":
    st.header("🏃 Run Shopping Agent")

    # Check prerequisites
    if not CONTEXT_GRAPH_PATH.exists():
        st.warning("Set up your preferences first in the **Setup Preferences** tab.")
        st.stop()

    cg = json.loads(CONTEXT_GRAPH_PATH.read_text())
    if not cg.get("user", {}).get("preferences", {}).get("brands"):
        st.warning("Set up your preferences first in the **Setup Preferences** tab.")
        st.stop()

    prefs = cg["user"]["preferences"]
    trust = cg["user"]["trust_rules"]

    # Show what the agent knows
    st.markdown("**Your agent knows:**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Brands", ", ".join(prefs.get("brands", [])))
    col2.metric("Size", prefs.get("size", "?"))
    col3.metric("Budget", f"${prefs.get('budget', '?')}")
    col4.metric("Spend Cap", f"${trust.get('max_autonomous_spend', '?')}")

    st.divider()

    col_run, col_load = st.columns(2)

    with col_run:
        num_runs = st.slider("Number of episodes", min_value=3, max_value=10, value=10)
        if st.button("▶ Run Agent Live", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Starting...")
            results_container = st.container()

            try:
                from run_loop import run_full_loop

                # We can't easily stream run_loop, so run all and display after
                with st.spinner(f"Running {num_runs} episodes — agent is shopping across real websites..."):
                    results = run_full_loop(total_runs=num_runs)

                st.session_state.results = results
                progress_bar.progress(100, text="Complete!")
                st.success(f"Done! {num_runs} episodes completed. Go to **Results Dashboard** to see the learning curve.")

            except Exception as e:
                st.error(f"Run failed: {e}")

    with col_load:
        st.markdown("**Or load previous results:**")
        if st.button("📂 Load from run_results.json", use_container_width=True):
            if RUN_RESULTS_PATH.exists():
                st.session_state.results = json.loads(RUN_RESULTS_PATH.read_text())
                st.success(f"Loaded {len(st.session_state.results)} runs. Go to **Results Dashboard**.")
            else:
                st.error("No run_results.json found. Run the agent first.")


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 3: RESULTS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.screen == "results":
    st.header("📊 Results Dashboard")

    # Load results
    results = st.session_state.get("results")
    if not results and RUN_RESULTS_PATH.exists():
        results = json.loads(RUN_RESULTS_PATH.read_text())
        st.session_state.results = results

    if not results:
        st.info("No results yet. Run the agent first in the **Run Agent** tab.")
        st.stop()

    # ── Top metrics ─────────────────────────────────────────────────────────
    first = results[0]["reward"]
    last = results[-1]["reward"]
    best_run = max(results, key=lambda r: r["reward"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Run 1", f"{first} pts")
    col2.metric(f"Run {len(results)}", f"{last} pts", delta=f"{last - first:+} pts")
    col3.metric("Best Run", f"Run {best_run['run']} ({best_run['reward']} pts)")
    col4.metric("Success Rate", f"{sum(1 for r in results if r['outcome'] == 'purchased')}/{len(results)}")

    st.divider()

    # ── Component 1: Reward Curve ───────────────────────────────────────────
    st.subheader("📈 Reward Curve")
    st.caption("Watch the agent get smarter — Thompson Sampling learns which strategies work")

    reward_df = pd.DataFrame({
        "Run": [r["run"] for r in results],
        "Reward": [r["reward"] for r in results],
    })
    st.line_chart(reward_df, x="Run", y="Reward", height=300)

    with st.expander("Reward breakdown (latest run)"):
        breakdown = results[-1].get("reward_breakdown", {})
        if breakdown:
            bd_df = pd.DataFrame({
                "Component": list(breakdown.keys()),
                "Points": list(breakdown.values()),
            })
            st.bar_chart(bd_df, x="Component", y="Points", height=250)

    st.divider()

    # ── Component 2: Reasoning Trace ────────────────────────────────────────
    st.subheader("🧠 Reasoning Trace")
    st.caption("Claude Sonnet 4.6 ReAct loop — watch the agent think, act, and observe")

    selected_run = st.selectbox(
        "Select run",
        options=[r["run"] for r in results],
        format_func=lambda x: f"Run {x} — {results[x-1]['reward']} pts ({results[x-1]['outcome']}) — {results[x-1]['strategy']['site']}",
    )

    run_data = results[selected_run - 1]

    # Strategy
    strat = run_data["strategy"]
    st.markdown(
        f"**Strategy:** site=`{strat['site']}` · query=`{strat['query_style']}` · "
        f"filter=`{strat['filter_strategy']}` · abandon=`{strat['abandon_threshold']}`"
    )

    # Product bought
    product = run_data.get("product")
    if product:
        p_name = product.get("name", "?")
        p_price = product.get("price", "?")
        p_brand = product.get("brand", "?")
        live = " (LIVE)" if product.get("live") else ""
        st.success(f"Bought: **{p_name}** — ${p_price} — {p_brand}{live}")

    # Lesson
    if run_data.get("lesson"):
        st.info(f"**Reflexion:** {run_data['lesson']}")

    # Trace steps
    trace = run_data.get("reasoning_trace", [])
    for step in trace:
        step_num = step.get("step", "?")
        thought = step.get("thought", "")
        action = step.get("action", "")

        with st.container():
            st.markdown(f"**Step {step_num}**")
            if thought:
                st.markdown(f"💭 *{thought}*")
            if action:
                st.code(action, language=None)

    st.divider()

    # ── Component 3: Bandit Weights ─────────────────────────────────────────
    st.subheader("🎰 Thompson Sampling Bandit Weights")
    st.caption("How the 4 independent bandits shift their preferences across runs")

    dimensions = ["site", "query_style", "filter_strategy", "abandon_threshold"]
    tabs = st.tabs([d.replace("_", " ").title() for d in dimensions])

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

    st.divider()

    # ── Component 4: Payment Log ────────────────────────────────────────────
    st.subheader("💳 Payment Log (x402)")
    st.caption("On-chain transaction confirmations on Base Sepolia")

    payment_rows = []
    for r in results:
        pay = r.get("payment", {})
        prod = r.get("product") or {}
        tx = pay.get("transaction_hash", "")
        tx_display = tx[:10] + "..." if tx and tx != "—" else "—"

        payment_rows.append({
            "Run": r["run"],
            "Product": prod.get("name", "—"),
            "Price": f"${prod.get('price', 0)}" if prod.get("price") else "—",
            "Status": "✅ Paid" if pay.get("success") else "❌ " + str(pay.get("reason", "Failed"))[:40],
            "Protocol": pay.get("protocol", "—"),
            "Confirmation": pay.get("confirmation_id", "—"),
            "Tx Hash": tx_display,
        })

    pay_df = pd.DataFrame(payment_rows)
    st.dataframe(pay_df, use_container_width=True, hide_index=True)

    # ── Agent UX Endpoints ──────────────────────────────────────────────────
    st.divider()
    st.subheader("🌐 Agent UX Endpoints")
    st.caption("These endpoints let any external agent interact with this system — UX for the Internet of Agents")

    ep_col1, ep_col2, ep_col3 = st.columns(3)
    with ep_col1:
        st.markdown("**`GET /agent-profile`**")
        st.caption("Who is the user? What are they allowed to do? What has the system learned?")
    with ep_col2:
        st.markdown("**`GET /agent-capabilities`**")
        st.caption("What actions are available? API contract for each endpoint.")
    with ep_col3:
        st.markdown("**`POST /purchase`**")
        st.caption("Buy a product via x402 USDC payment on Base Sepolia.")

    if st.button("Test /agent-profile"):
        try:
            import httpx
            resp = httpx.get("http://localhost:4021/agent-profile", timeout=5)
            st.json(resp.json())
        except Exception:
            st.warning("x402 server not running. Start it with: `uv run python x402_server.py`")
