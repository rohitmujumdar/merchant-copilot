# Merchant Copilot

Agentic copilot that reviews ecommerce product pages and proposes conversion improvements with human-in-the-loop approval.

## Stack
- Python 3.12 via uv
- Anthropic SDK (claude-sonnet-4-6 for analysis)
- Streamlit for UI
- BeautifulSoup4 for HTML parsing

## Run
- `uv run streamlit run app.py`
- `uv run python main.py` for CLI testing

## Architecture
- app.py — Streamlit UI
- agent.py — Claude API call logic (system prompt, structured output parsing)
- mock_pages/ — Pre-built product page HTML for demos

## Key Decisions
- No scraping live sites. We use mock/pasted HTML content.
- No real deployments. The "apply" step is visual only.
- Agent returns structured JSON with issues, proposed fixes, and rationale.
- Human approves/skips each suggestion before anything happens.
- Use claude-sonnet-4-6 for the agent (fast + cheap for hackathon).

## Style
- Move fast, minimal code. This is a hackathon MVP.
- No tests, no types, no docstrings unless asked.
- Streamlit for all UI — no custom HTML/CSS.
- When in doubt, hardcode it.

## Workflow Rules
- Build in vertical slices. Get one thing working end-to-end before starting the next.
- After every working milestone, commit immediately. Don't batch commits.
- When I say "this works", commit it and move on.
- If something breaks, check the last commit diff first before debugging.
- Never refactor working code unless I explicitly ask.
- If I paste an error, fix it. Don't explain what went wrong unless I ask why.
- Keep responses short during building. Code first, explanations only if asked.
- When I say "run it", start the Streamlit server and confirm it's up.
- When I say "stop it", kill the Streamlit process.

## Demo Flow (the thing we're building toward)
1. Merchant pastes product page content (or picks a mock page)
2. Agent analyzes → returns structured issues with proposed fixes
3. Merchant reviews each issue card (current vs proposed, with rationale)
4. Merchant approves or skips each suggestion
5. Summary of approved changes displayed / exportable
