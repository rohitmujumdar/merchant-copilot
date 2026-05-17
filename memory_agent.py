"""
Memory Agent

The foundation — every other agent depends on it.
Reads context graph at run start (working memory).
Writes ONLY after run completes (never mid-run).

Two jobs:
1. READ: Load context graph for agents to use
2. WRITE: Update history[], learned_insights[], rl_weights after each run
"""

import json
from datetime import datetime
from pathlib import Path

CONTEXT_GRAPH_PATH = "context_graph.json"

CONTEXT_GRAPH_SCHEMA_VERSION = "1.1"
"""
Schema for context_graph.json (v1.1 — removed unused cohort priors):
{
  "user": {
    "preferences": {"brands": [str], "size": int, "budget": int, "max_delivery_days": int, "style": str},
    "trust_rules": {"max_autonomous_spend": int, "approved_categories": [str], "require_approval_first_n_runs": int}
  },
  "rl_weights": {"site": {...}, "query_style": {...}, ...},
  "history": [{"run": int, "timestamp": str, "strategy": dict, "reward": float, "outcome": str}],
  "learned_insights": [{"run": int, "lesson": str}]   ← always dicts, not plain strings
}
"""


class MemoryAgent:

    def __init__(self, path: str = CONTEXT_GRAPH_PATH):
        self.path = path

    # ------------------------------------------------------------------ #
    # READ — called at start of every run
    # ------------------------------------------------------------------ #

    def load(self) -> dict:
        """Load context graph from disk."""
        with open(self.path) as f:
            return json.load(f)

    def get_working_memory(self) -> dict:
        """
        Load context graph. Returns it ready for agents to use.
        """
        cg = self.load()
        runs = len(cg.get("history", []))
        print(f"[Memory] Loaded context graph. Runs completed: {runs}")
        return cg

    # ------------------------------------------------------------------ #
    # WRITE — called after run completes, never during
    # ------------------------------------------------------------------ #

    def write_run_result(self, run_number: int, strategy: dict,
                         reward: float, outcome: str,
                         bandit_weights: dict, lesson: str):
        """
        Update context graph after a completed run.

        Args:
            run_number: which run just completed (1-10)
            strategy: the strategy the bandit chose this run
            reward: total reward score
            outcome: human-readable outcome ("purchased", "found_not_purchased", etc.)
            bandit_weights: current learned weights from RL bandit
            lesson: plain-English lesson from Reflexion module
        """
        cg = self.load()

        # Append to history
        cg.setdefault("history", []).append({
            "run": run_number,
            "timestamp": datetime.utcnow().isoformat(),
            "strategy": strategy,
            "reward": reward,
            "outcome": outcome,
        })

        # Append lesson
        cg.setdefault("learned_insights", []).append({
            "run": run_number,
            "lesson": lesson,
        })

        # Update RL weights from bandit
        cg["rl_weights"] = bandit_weights

        self._save(cg)
        print(f"[Memory] Run {run_number} saved. Reward: {reward}. Lesson: {lesson}")

    def get_history_summary(self) -> str:
        """
        Return a short summary of past runs for the Shopper Agent's context.
        Helps Claude make better decisions using past experience.
        """
        cg = self.load()
        history = cg.get("history", [])

        if not history:
            return "No previous runs. This is the first run."

        recent = history[-3:]  # last 3 runs
        lines = ["Recent run history:"]
        for h in recent:
            lines.append(
                f"  Run {h['run']}: site={h['strategy'].get('site', '?')}, "
                f"reward={h['reward']}, outcome={h['outcome']}"
            )

        insights = cg.get("learned_insights", [])
        if insights:
            lines.append("Lessons learned:")
            for i in insights[-3:]:
                lines.append(f"  - {i['lesson']}")

        return "\n".join(lines)

    def _save(self, cg: dict):
        """Save context graph to disk."""
        with open(self.path, "w") as f:
            json.dump(cg, f, indent=2)


# --- Test ---
if __name__ == "__main__":
    memory = MemoryAgent()

    print("=== Memory Agent Test ===\n")

    print("--- Loading working memory ---")
    wm = memory.get_working_memory()
    print(f"RL weights: {wm.get('rl_weights')}\n")

    print("--- Writing run 1 result ---")
    memory.write_run_result(
        run_number=1,
        strategy={"site": "amazon", "query_style": "broad",
                  "filter_strategy": "price_first", "abandon_threshold": "after_2_fails"},
        reward=12,
        outcome="captcha_blocked",
        bandit_weights={
            "site": {"zappos": 0.38, "nike": 0.31, "amazon": 0.31},
            "query_style": {"broad": 0.28, "moderate": 0.36, "specific": 0.36},
            "filter_strategy": {"price_first": 0.29, "brand_first": 0.24, "rating_first": 0.24, "size_first": 0.23},
            "abandon_threshold": {"after_1_fail": 0.34, "after_2_fails": 0.33, "after_3_fails": 0.33},
        },
        lesson="Amazon returned CAPTCHA on run 1 — deprioritize Amazon for early runs."
    )

    print("\n--- History summary for Shopper Agent ---")
    print(memory.get_history_summary())
