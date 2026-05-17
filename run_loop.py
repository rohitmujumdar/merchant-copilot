"""
Run Loop — Orchestrator

Wires all 5 agents together and runs 10 shopping episodes.
This is the main entry point for the demo.

Flow per episode:
  Memory Agent (read) →
  RL Bandit (pick strategy) →
  Auth Agent (issue credential) →
  Shopper Agent (Claude ReAct loop) →
  Payment Agent (if purchased) →
  RL Reward Agent (score + update bandit) →
  Reflexion (generate lesson) →
  Memory Agent (write results)
"""

import json
import uuid
from pathlib import Path
from dotenv import dotenv_values
import anthropic

from memory_agent import MemoryAgent
from rl_bandit import RLAgent
from shopping_agent import run_shopping_episode
from reward import calculate_reward
from auth_agent import issue_credential, verify_credential
from payment_agent import execute_payment

config = dotenv_values(".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])

TOTAL_RUNS = 3
BANDIT_STATE_PATH = "bandit_state.json"


def generate_reflexion(run_result: dict, context_graph: dict) -> str:
    """
    After each run, Claude writes a plain-English lesson.
    This is the Reflexion module — closes the cognitive loop.
    """
    prompt = f"""You are analyzing a shopping agent run. Write ONE concise lesson (max 15 words) for the next run.

Run outcome: {run_result['outcome']}
Site used: {run_result['strategy']['site']}
Query style: {run_result['strategy']['query_style']}
Filter strategy: {run_result['strategy']['filter_strategy']}
Reward: {run_result['reward']}
Events: {run_result['events']}

Write only the lesson, no preamble."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


RUN_RESULTS_SCHEMA_VERSION = "1.0"
"""
Schema for run_results.json (FROZEN — v1.0):
  Each element: {
    "run": int,
    "strategy": {"site": str, "query_style": str, "filter_strategy": str, "abandon_threshold": str},
    "reward": int,
    "reward_breakdown": {"event_name": int, ...},
    "steps": int,
    "outcome": str,       # "purchased" | "found_not_purchased" | "not_found"
    "product": dict|null, # {"name", "brand", "price", "rating", "sizes", ...}
    "payment": dict,      # {"success": bool, ...}
    "reasoning_trace": [{"step": int, "thought": str, "action": str}, ...],
    "bandit_weights": {"site": {...}, "query_style": {...}, ...},
    "lesson": str
  }
Do NOT rename/remove fields without bumping the version.
"""


def run_full_loop(total_runs: int = TOTAL_RUNS, status_callback=None) -> list[dict]:
    """
    Run all episodes. Returns list of results for dashboard.

    Design:
      - ALL episodes are SIMULATED exploration (no real payment).
      - After loop, best candidate is presented to human for approval.
      - Bandit state persists across run_full_loop() calls so learning compounds.

    Args:
      status_callback: optional fn(message: str) called at key moments for live UI updates.

    Output schema: see RUN_RESULTS_SCHEMA_VERSION above.
    """
    def log(msg: str):
        print(msg)
        if status_callback:
            status_callback(msg)
    memory = MemoryAgent()

    # ── FIX #2: Load persisted bandit state (learning compounds across sessions)
    if Path(BANDIT_STATE_PATH).exists():
        bandit = RLAgent.load(BANDIT_STATE_PATH)
        log("[Bandit] Loaded saved state — continuing from previous learning")
    else:
        bandit = RLAgent()
        log("[Bandit] Fresh start — no previous learning found")

    session_id = uuid.uuid4().hex[:8]

    all_results = []

    log(f"🛒 Starting {total_runs} exploration episodes...")

    for run_number in range(1, total_runs + 1):

        log(f"━━━ Episode {run_number}/{total_runs} ━━━")

        # ── 1. MEMORY AGENT: Load context ──────────────────────────
        context_graph = memory.get_working_memory()
        history_summary = memory.get_history_summary()

        # ── 2. RL BANDIT: Pick strategy ────────────────────────────
        strategy = bandit.select_strategy()
        log(f"🎰 Strategy: {strategy['site']} | {strategy['query_style']} | {strategy['filter_strategy']}")

        # ── 3. AUTH AGENT: Issue credential ────────────────────────
        auth_result = issue_credential(context_graph, session_id, run_number)
        credential = auth_result["credential"]
        log(f"🔑 Auth issued (cap: ${credential['max_autonomous_spend']})")

        # ── 4. SHOPPER AGENT: Claude does the shopping ─────────────
        log(f"🔍 Shopping on {strategy['site']}...")
        run_result = run_shopping_episode(
            context_graph=context_graph,
            strategy=strategy,
            history_summary=history_summary,
            run_number=run_number,
            memory_agent=memory,  # Agent-to-Agent: Shopper can query Memory mid-run
        )

        # ── 5. NO AUTO-PAYMENT — all episodes are exploration ─────────
        # Payment requires explicit human approval via the Streamlit UI.
        payment_result = {"success": False, "reason": "Awaiting human approval"}
        if run_result["outcome"] == "purchased" and run_result["product"]:
            log(f"✅ Found: {run_result['product']['name']} @ ${run_result['product']['price']}")
        elif run_result["outcome"] == "found_not_purchased":
            log(f"⚠️ Found product but didn't match criteria well")
        else:
            log(f"❌ No product found on {strategy['site']}")

        run_result["payment"] = payment_result

        # ── 6. RL REWARD AGENT: Score + update bandit ──────────────
        bandit.update(strategy, run_result["reward"])
        bandit_weights = bandit.get_all_weights()
        bandit.record_run(
            run_number=run_number,
            strategy=strategy,
            reward=run_result["reward"],
            reward_breakdown=run_result["reward_breakdown"],
            steps=run_result["steps"],
        )
        log(f"📊 Reward: {run_result['reward']} pts ({run_result['steps']} steps)")

        # ── 7. REFLEXION: Generate lesson ──────────────────────────
        lesson = generate_reflexion(run_result, context_graph)
        log(f"💡 Lesson: {lesson}")

        # ── 8. MEMORY AGENT: Write results ─────────────────────────
        memory.write_run_result(
            run_number=run_number,
            strategy=strategy,
            reward=run_result["reward"],
            outcome=run_result["outcome"],
            bandit_weights=bandit_weights,
            lesson=lesson,
        )

        # ── Collect for dashboard ───────────────────────────────────
        run_summary = {
            "run": run_number,
            "strategy": strategy,
            "reward": run_result["reward"],
            "reward_breakdown": run_result["reward_breakdown"],
            "steps": run_result["steps"],
            "outcome": run_result["outcome"],
            "product": run_result["product"],
            "payment": payment_result,
            "reasoning_trace": run_result["reasoning_trace"],
            "bandit_weights": bandit_weights,
            "bandit_state": bandit.get_detailed_state(),
            "lesson": lesson,
        }
        all_results.append(run_summary)

    # ── Save bandit state for next session (learning persists) ──
    bandit.save(BANDIT_STATE_PATH)
    log(f"🧠 Bandit state saved — learning persists to next run")

    # ── Identify best candidate for human approval ──────────────────
    purchased_runs = [r for r in all_results if r["outcome"] == "purchased" and r.get("product")]
    best_candidate = max(purchased_runs, key=lambda r: r["reward"]) if purchased_runs else None

    # Tag the best candidate's product with the site so payment can verify
    if best_candidate and best_candidate.get("product"):
        best_candidate["product"]["site"] = best_candidate["strategy"]["site"]

    # ── Final summary ───────────────────────────────────────────────
    rewards = [r["reward"] for r in all_results]
    best_idx = rewards.index(max(rewards))
    best_run = all_results[best_idx]

    print(f"\n{'🏆 '*20}")
    print(f"ALL {total_runs} RUNS COMPLETE")
    print(f"  Run 1 reward:  {rewards[0]} pts")
    print(f"  Run {total_runs} reward: {rewards[-1]} pts")
    print(f"  Improvement:   {rewards[-1] - rewards[0]:+} pts")
    print(f"  Best run:      Run {best_idx+1} ({max(rewards)} pts)")
    if best_candidate:
        print(f"  Best product:  {best_candidate['product']['name']} @ ${best_candidate['product']['price']}")
    print(f"  Payment:       NONE — awaiting human approval in UI")
    print(f"{'🏆 '*20}\n")

    # Save full results for dashboard
    output = {
        "runs": all_results,
        "best_candidate": best_candidate,
    }
    with open("run_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print("Results saved to run_results.json")

    return output


def execute_approved_purchase(product: dict, context_graph: dict) -> dict:
    """
    Execute payment AFTER the user has explicitly approved the product.
    Called from the Streamlit UI when user clicks "Buy This".
    """
    session_id = "approved-" + uuid.uuid4().hex[:8]
    auth_result = issue_credential(context_graph, session_id, run_number=99)
    credential = auth_result["credential"]
    site_key = product.get("site", product.get("_strategy_site", "zappos")) + ".com"
    auth_check = verify_credential(credential, site_key, product["price"])

    if auth_check["cleared"]:
        result = execute_payment(product, credential, auth_check)
        if result["success"]:
            print(f"[Payment] ✅ Approved purchase: ${product['price']} for {product['name']}")
        return result
    return {"success": False, "reason": auth_check.get("reason", "Auth failed")}


def apply_rejection_feedback(feedback: str, last_strategy: dict):
    """
    Called when user rejects the best candidate.
    Applies negative reward to the bandit + stores feedback for next run.
    """
    # Penalize the strategy that produced the rejected product
    if Path(BANDIT_STATE_PATH).exists():
        bandit = RLAgent.load(BANDIT_STATE_PATH)
        bandit.update(last_strategy, reward=-30)  # strong negative signal
        bandit.save(BANDIT_STATE_PATH)
        print(f"[Bandit] Applied -30 penalty to strategy: {last_strategy}")

    # Store feedback so the shopping agent sees it next run
    memory = MemoryAgent()
    cg = memory.load()
    cg["user"]["feedback"] = feedback
    memory._save(cg)
    print(f"[Memory] Stored rejection feedback: {feedback}")


if __name__ == "__main__":
    results = run_full_loop()
