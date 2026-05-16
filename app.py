"""
Streamlit Dashboard — Merchant Copilot Shopping Agent

4 components:
  1. Reward curve (line chart across 10 runs)
  2. Reasoning trace viewer (per-run ReAct steps)
  3. Bandit weights display (Thompson Sampling evolution)
  4. Payment log (x402 transaction confirmations)
"""

import json
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Merchant Copilot", page_icon="🛒", layout="wide")

# ── Load results ────────────────────────────────────────────────────────────
@st.cache_data
def load_results() -> list[dict]:
    with open("run_results.json") as f:
        return json.load(f)


def run_live():
    """Run the full loop live and return results."""
    from run_loop import run_full_loop
    return run_full_loop()


# ── Sidebar: controls ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    mode = st.radio("Data source", ["Load from file", "Run live (requires API key)"])

    if mode == "Run live (requires API key)":
        if st.button("▶ Run 10 Episodes", type="primary", use_container_width=True):
            with st.spinner("Running 10 episodes... this takes a few minutes"):
                st.session_state.results = run_live()
                st.rerun()
    else:
        try:
            st.session_state.results = load_results()
        except FileNotFoundError:
            st.error("run_results.json not found. Run the loop first or switch to live mode.")
            st.stop()

    st.divider()
    st.caption("Built for Internet of Agents Hackathon")
    st.caption("RL + Claude Sonnet 4.6 + x402")

results = st.session_state.get("results")
if not results:
    st.info("No results loaded. Choose a data source in the sidebar.")
    st.stop()

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🛒 Merchant Copilot")
st.markdown("**RL shopping agent that gets smarter over 10 runs**")

# Top-level metrics
first = results[0]["reward"]
last = results[-1]["reward"]
best_run = max(results, key=lambda r: r["reward"])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Run 1 Reward", f"{first} pts")
col2.metric("Run 10 Reward", f"{last} pts", delta=f"{last - first:+} pts")
col3.metric("Best Run", f"Run {best_run['run']} ({best_run['reward']} pts)")
col4.metric("Total Runs", len(results))

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 1: Reward Curve
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📈 Reward Curve")
st.caption("Shows how the agent improves across episodes via Thompson Sampling")

reward_df = pd.DataFrame({
    "Run": [r["run"] for r in results],
    "Reward": [r["reward"] for r in results],
})
st.line_chart(reward_df, x="Run", y="Reward", height=300)

# Reward breakdown for latest run
with st.expander("Reward breakdown (latest run)"):
    breakdown = results[-1].get("reward_breakdown", {})
    bd_df = pd.DataFrame({
        "Component": list(breakdown.keys()),
        "Points": list(breakdown.values()),
    })
    st.bar_chart(bd_df, x="Component", y="Points", height=250)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 2: Reasoning Trace Viewer
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🧠 Reasoning Trace")
st.caption("Claude Sonnet 4.6 ReAct loop — think → act → observe")

selected_run = st.selectbox(
    "Select run",
    options=[r["run"] for r in results],
    format_func=lambda x: f"Run {x} — reward {results[x-1]['reward']} pts ({results[x-1]['outcome']})",
)

run_data = results[selected_run - 1]

# Strategy used
strat = run_data["strategy"]
st.markdown(
    f"**Strategy:** site=`{strat['site']}` · query=`{strat['query_style']}` · "
    f"filter=`{strat['filter_strategy']}` · abandon=`{strat['abandon_threshold']}`"
)

# Lesson
if run_data.get("lesson"):
    st.info(f"**Reflexion lesson:** {run_data['lesson']}")

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

# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 3: Bandit Weights
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🎰 Thompson Sampling Bandit Weights")
st.caption("How the 4 independent bandits shift across runs")

# Build weight evolution data
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
            # Pivot for line chart: each arm is a column
            pivot = df.pivot(index="Run", columns="Arm", values="Weight")
            st.line_chart(pivot, height=250)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 4: Payment Log
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("💳 Payment Log (x402)")
st.caption("Transaction confirmations from the payment agent")

payment_rows = []
for r in results:
    pay = r.get("payment", {})
    product = r.get("product") or {}
    payment_rows.append({
        "Run": r["run"],
        "Product": product.get("name", "—"),
        "Price": f"${product.get('price', 0)}" if product.get("price") else "—",
        "Status": "✅ Paid" if pay.get("success") else "❌ " + pay.get("reason", "Failed")[:50],
        "Protocol": pay.get("protocol", "—"),
        "Confirmation": pay.get("confirmation_id", "—"),
        "Tx Hash": pay.get("transaction_hash", "—"),
    })

pay_df = pd.DataFrame(payment_rows)
st.dataframe(pay_df, use_container_width=True, hide_index=True)
