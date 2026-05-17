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


def run_full_loop(total_runs: int = TOTAL_RUNS) -> list[dict]:
    """
    Run all episodes. Returns list of results for dashboard.

    Design:
      - Episodes 1 through N-1 are SIMULATED exploration (no real payment).
      - Episode N (the final one) is the PURCHASE CANDIDATE — presented to user.
      - Bandit state persists across run_full_loop() calls so learning compounds.

    Output schema: see RUN_RESULTS_SCHEMA_VERSION above.
    """
    memory = MemoryAgent()

    # ── FIX #2: Load persisted bandit state (learning compounds across sessions)
    if Path(BANDIT_STATE_PATH).exists():
        bandit = RLAgent.load(BANDIT_STATE_PATH)
        print("[Bandit] Loaded saved state — continuing from previous learning")
    else:
        bandit = RLAgent()
        print("[Bandit] Fresh start — no previous learning found")

    session_id = uuid.uuid4().hex[:8]

    all_results = []

    print("\n" + "🛒 " * 20)
    print("STRIDE — RL SHOPPING AGENT")
    print(f"Running {total_runs} episodes ({total_runs - 1} exploration + 1 purchase candidate).")
    print("🛒 " * 20 + "\n")

    for run_number in range(1, total_runs + 1):

        print(f"\n{'─'*60}")
        print(f"EPISODE {run_number}/{total_runs}")
        print(f"{'─'*60}")

        # ── 1. MEMORY AGENT: Load context ──────────────────────────
        context_graph = memory.get_working_memory()
        history_summary = memory.get_history_summary()

        # ── 2. RL BANDIT: Pick strategy ────────────────────────────
        strategy = bandit.select_strategy()
        print(f"[Bandit] Strategy: {strategy}")

        # ── 3. AUTH AGENT: Issue credential ────────────────────────
        auth_result = issue_credential(context_graph, session_id, run_number)
        credential = auth_result["credential"]
        print(f"[Auth] Credential issued. Spend cap: ${credential['max_autonomous_spend']}")

        # ── 4. SHOPPER AGENT: Claude does the shopping ─────────────
        run_result = run_shopping_episode(
            context_graph=context_graph,
            strategy=strategy,
            history_summary=history_summary,
            run_number=run_number,
            memory_agent=memory,  # Agent-to-Agent: Shopper can query Memory mid-run
        )

        # ── 5. PAYMENT AGENT: Only fires on FINAL episode ───────────
        # FIX #1: Episodes 1 to N-1 are exploration only. No real payment.
        # Payment only happens on the last episode IF it found a product.
        payment_result = {"success": False, "reason": "Exploration only — no payment"}
        is_final_episode = (run_number == total_runs)

        if is_final_episode and run_result["outcome"] == "purchased" and run_result["product"]:
            product = run_result["product"]
            site_key = strategy["site"] + ".com"
            auth_check = verify_credential(credential, site_key, product["price"])

            if auth_check["cleared"]:
                payment_result = execute_payment(product, credential, auth_check)
                if payment_result["success"]:
                    print(f"[Payment] 🎉 FINAL PURCHASE via x402. ${product['price']} charged. "
                          f"ID: {payment_result.get('confirmation_id')}")
                else:
                    print(f"[Payment] Failed: {payment_result.get('reason')}")
            else:
                print(f"[Auth] Payment blocked: {auth_check['reason']}")
        elif not is_final_episode and run_result["outcome"] == "purchased":
            print(f"[Explore] Found {run_result['product']['name']} @ ${run_result['product']['price']} — simulated (not buying yet)")

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

        # ── 7. REFLEXION: Generate lesson ──────────────────────────
        lesson = generate_reflexion(run_result, context_graph)
        print(f"[Reflexion] Lesson: {lesson}")

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
            "lesson": lesson,
        }
        all_results.append(run_summary)

        # ── Print episode summary ───────────────────────────────────
        print(f"\n{'='*60}")
        print(f"RUN {run_number} SUMMARY")
        print(f"  Outcome:  {run_result['outcome']}")
        print(f"  Reward:   {run_result['reward']} pts")
        print(f"  Steps:    {run_result['steps']}")
        print(f"  Strategy: {strategy['site']} | {strategy['query_style']} | {strategy['filter_strategy']}")
        print(f"  Lesson:   {lesson}")
        print(f"{'='*60}")

    # ── Save bandit state for next session (FIX #2: learning persists) ──
    bandit.save(BANDIT_STATE_PATH)
    print(f"[Bandit] State saved to {BANDIT_STATE_PATH} — learning persists to next run")

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
    if best_run.get("product"):
        print(f"  Best product:  {best_run['product']['name']} @ ${best_run['product']['price']}")
    print(f"  Payment:       Final episode only (episodes 1-{total_runs-1} were exploration)")
    print(f"{'🏆 '*20}\n")

    # Save full results for dashboard
    with open("run_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print("Results saved to run_results.json")

    return all_results


if __name__ == "__main__":
    results = run_full_loop()
