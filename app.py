import streamlit as st

# -- Page config (must be first Streamlit call) --
st.set_page_config(page_title="Merchant Copilot", page_icon="🛒", layout="wide")

# -- Session state: this persists across reruns --
# Streamlit reruns the whole script on every interaction (button click, input change).
# Session state is how you keep data alive between reruns.
if "issues" not in st.session_state:
    st.session_state.issues = []
if "approved" not in st.session_state:
    st.session_state.approved = {}
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False


# -- Mock agent response (replace with real Claude call on hackathon day) --
def mock_analyze(page_content: str) -> list[dict]:
    """Simulates what Claude would return. Replace with real API call later."""
    return [
        {
            "element": "Product Title",
            "current": "Blue Shirt Men's",
            "problem": "Generic, not benefit-focused, missing key search terms",
            "proposed": "Men's Premium Wrinkle-Free Oxford Shirt — All-Day Comfort",
            "rationale": "Leading with benefits increases click-through by 15-30%. Includes search terms customers actually use.",
            "impact": "high",
        },
        {
            "element": "Product Description",
            "current": "A shirt. Available in blue. Made of cotton.",
            "problem": "Too short, doesn't answer 'why buy this', not scannable",
            "proposed": "Crafted from 100% organic cotton, this wrinkle-free oxford keeps you looking sharp from morning meetings to evening drinks. Machine washable. Available in 5 colors.",
            "rationale": "Descriptions that address use-cases and care instructions reduce return rates and increase add-to-cart by 20%.",
            "impact": "high",
        },
        {
            "element": "CTA Button",
            "current": "Submit",
            "problem": "Vague action word, doesn't create urgency or clarity",
            "proposed": "Add to Cart — Free Shipping",
            "rationale": "Specific CTAs with value props (free shipping) outperform generic buttons by 2-3x in conversion studies.",
            "impact": "medium",
        },
        {
            "element": "Trust Signals",
            "current": "None visible",
            "problem": "No reviews, ratings, or return policy shown above the fold",
            "proposed": "Add: ⭐ 4.8/5 (2,341 reviews) • Free 30-day returns • In stock",
            "rationale": "Trust signals reduce purchase anxiety. 92% of consumers read reviews before buying.",
            "impact": "high",
        },
    ]


# -- UI Layout --
st.title("🛒 Merchant Copilot")
st.markdown("*AI-powered product page analysis for ecommerce merchants*")

# Sidebar for input
with st.sidebar:
    st.header("Input")
    page_content = st.text_area(
        "Paste your product page content (HTML or text)",
        height=300,
        placeholder="Paste product page content here...\n\nExample:\nTitle: Blue Shirt Men's\nPrice: $29.99\nDescription: A shirt. Available in blue.",
    )

    analyze_btn = st.button("🔍 Analyze Page", type="primary", use_container_width=True)

    if analyze_btn and page_content:
        st.session_state.issues = mock_analyze(page_content)
        st.session_state.approved = {}
        st.session_state.analyzed = True

    if analyze_btn and not page_content:
        st.warning("Paste some content first!")

# Main content area
if not st.session_state.analyzed:
    # Empty state
    st.info("👈 Paste product page content in the sidebar and click **Analyze Page** to get started.")
else:
    # Results header
    issues = st.session_state.issues
    n_approved = sum(1 for v in st.session_state.approved.values() if v == "approved")
    n_skipped = sum(1 for v in st.session_state.approved.values() if v == "skipped")

    col1, col2, col3 = st.columns(3)
    col1.metric("Issues Found", len(issues))
    col2.metric("Approved", n_approved)
    col3.metric("Skipped", n_skipped)

    st.divider()

    # Issue cards
    for i, issue in enumerate(issues):
        status = st.session_state.approved.get(i, "pending")

        # Color-code by status
        if status == "approved":
            icon = "✅"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "⚠️"

        with st.expander(f"{icon} **{issue['element']}** — {issue['problem'][:50]}...", expanded=(status == "pending")):
            # Impact badge
            impact_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            st.caption(f"Impact: {impact_colors.get(issue['impact'], '')} {issue['impact'].upper()}")

            # Current vs proposed
            left, right = st.columns(2)
            with left:
                st.markdown("**Current:**")
                st.error(issue["current"])
            with right:
                st.markdown("**Proposed:**")
                st.success(issue["proposed"])

            # Rationale
            st.markdown(f"**Why this matters:** {issue['rationale']}")

            # Action buttons
            if status == "pending":
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
                with btn_col1:
                    if st.button("✅ Approve", key=f"approve_{i}", use_container_width=True):
                        st.session_state.approved[i] = "approved"
                        st.rerun()
                with btn_col2:
                    if st.button("⏭️ Skip", key=f"skip_{i}", use_container_width=True):
                        st.session_state.approved[i] = "skipped"
                        st.rerun()
            else:
                st.caption(f"Status: {status.upper()}")

    # Summary section
    st.divider()
    if n_approved > 0:
        st.subheader("📋 Approved Changes Summary")
        for i, issue in enumerate(issues):
            if st.session_state.approved.get(i) == "approved":
                st.markdown(f"- **{issue['element']}**: {issue['current']} → {issue['proposed']}")

        if st.button("📥 Export Approved Changes", type="primary"):
            import json
            approved_issues = [
                issues[i] for i in range(len(issues))
                if st.session_state.approved.get(i) == "approved"
            ]
            st.download_button(
                "Download JSON",
                data=json.dumps(approved_issues, indent=2),
                file_name="approved_changes.json",
                mime="application/json",
            )
