"""
Shopper Agent — The agentic core.

Claude does the ReAct reasoning loop step by step:
  Thought → Action → Observation → Thought → Action → ...

The RL bandit picks the strategy (which site, query style, etc.)
Claude decides what to DO within that strategy in real time.

This is what makes it "agentic" — Claude isn't following a script,
it's reasoning about each step based on what it observes.
"""

import json
import anthropic
from dotenv import dotenv_values
from environment import ShoppingEnvironment
from reward import calculate_reward

config = dotenv_values(".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])


def build_system_prompt(context_graph: dict, history_summary: str) -> str:
    prefs = context_graph["user"]["preferences"]
    trust = context_graph["user"]["trust_rules"]

    return f"""You are a personal shopping agent. Your job is to find and buy the best sneaker for the user.

USER PREFERENCES (never violate these):
- Brands: {prefs.get("brands", [])}
- Size: {prefs.get("size")}
- Budget: ${prefs.get("budget")}
- Max delivery: {prefs.get("max_delivery_days")} days
- Max autonomous spend: ${trust.get("max_autonomous_spend")}

{history_summary}

RULES:
- Only shop on approved sites: Zappos, 6pm, Nike, Amazon
- 6pm is a legitimate discount shoe site (owned by Zappos/Amazon)
- Never buy the wrong size
- Never exceed budget
- Abandon a site if you hit a CAPTCHA or dead end
- Be efficient — fewer steps = better reward

You will be given a strategy to follow and a list of available actions.

CRITICAL FORMAT RULE: Each response must contain EXACTLY one Thought + one Action, then STOP.
The system will call the action and return an Observation. Never write "Observation:" yourself.

Format:
Thought: <your reasoning>
Action: <one action from the available list>

STOP HERE. Do not write Observation. Do not write the next Thought.
Wait for the system to call your action and return an Observation.

When the task is complete, output:
Done: <outcome summary>"""


def run_shopping_episode(context_graph: dict, strategy: dict,
                         history_summary: str, run_number: int) -> dict:
    """
    Run one full shopping episode using Claude as the reasoning agent.

    Args:
        context_graph: full context graph from memory agent
        strategy: chosen by RL bandit {site, query_style, filter_strategy, abandon_threshold}
        history_summary: recent run history from memory agent
        run_number: which run this is (1-10)

    Returns:
        dict with reasoning_trace, events, steps, reward, outcome, product
    """

    env = ShoppingEnvironment()
    prefs = context_graph["user"]["preferences"]

    # Map abandon threshold to number
    abandon_map = {"after_1_fail": 1, "after_2_fails": 2, "after_3_fails": 3}
    max_fails = abandon_map.get(strategy["abandon_threshold"], 2)

    # Build initial prompt for Claude
    initial_message = f"""Run #{run_number}. Your strategy this run:
- Site: {strategy["site"]}
- Query style: {strategy["query_style"]} (broad=generic, moderate=brand+size, specific=brand+size+budget)
- Filter: {strategy["filter_strategy"]}
- Abandon after: {max_fails} failure(s)

Available actions:
- ENTER_STORE [site]: Enter zappos, nike, or amazon
- SEARCH [query]: Search for products
- EVALUATE [product_index]: Evaluate a specific product from search results
- PURCHASE [product_index]: Attempt to purchase the product
- ABANDON: Give up on current site, try another
- DONE: End the run

Current search results will be shown after SEARCH.
Start shopping."""

    messages = [{"role": "user", "content": initial_message}]

    reasoning_trace = []
    search_results = []
    current_site = None
    fails = 0
    purchased_product = None
    outcome = "not_found"
    max_steps = 12  # safety limit

    print(f"\n{'='*60}")
    print(f"RUN {run_number} | Site: {strategy['site']} | Query: {strategy['query_style']}")
    print(f"{'='*60}")

    for step in range(max_steps):

        # Call Claude — stop before it hallucinates its own Observation
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            stop_sequences=["Observation:", "observation:"],
            system=build_system_prompt(context_graph, history_summary),
            messages=messages,
        )

        claude_output = response.content[0].text.strip()
        messages.append({"role": "assistant", "content": claude_output})

        print(f"\n{claude_output}")

        # Parse Claude's output
        lines = claude_output.strip().split("\n")
        thought = ""
        action_line = ""
        done_line = ""

        for line in lines:
            if line.startswith("Thought:"):
                thought = line.replace("Thought:", "").strip()
            elif line.startswith("Action:"):
                action_line = line.replace("Action:", "").strip()
            elif line.startswith("Done:"):
                done_line = line.replace("Done:", "").strip()

        # Record trace
        trace_entry = {"step": step + 1, "thought": thought, "action": action_line or done_line}
        reasoning_trace.append(trace_entry)

        # Handle DONE or no action parsed
        if done_line:
            break
        if not action_line:
            # Claude didn't produce a valid action — prompt it to continue
            messages.append({"role": "user", "content": "Please provide your next Action."})
            continue

        # Execute the action in the environment
        observation = execute_action(
            action_line, env, prefs, strategy,
            search_results, current_site, fails, max_fails
        )

        # Update state from observation
        if observation.get("site"):
            current_site = observation["site"]
        if observation.get("results") is not None:
            search_results = observation["results"]
        if observation.get("failed"):
            fails += 1
        if observation.get("purchased"):
            purchased_product = observation["product"]
            outcome = "purchased"
        if observation.get("found"):
            outcome = "found_not_purchased"

        obs_text = observation.get("message", str(observation))
        print(f"Observation: {obs_text}")

        messages.append({"role": "user", "content": f"Observation: {obs_text}"})

        # Stop if purchased
        if observation.get("purchased"):
            break

    # Calculate reward
    result = env.get_results()
    reward_result = calculate_reward(result["events"], result["steps"])

    print(f"\n--- Run {run_number} Complete ---")
    print(f"Outcome: {outcome} | Steps: {result['steps']} | Reward: {reward_result['total']}")

    return {
        "run": run_number,
        "strategy": strategy,
        "reasoning_trace": reasoning_trace,
        "events": result["events"],
        "steps": result["steps"],
        "reward": reward_result["total"],
        "reward_breakdown": reward_result["breakdown"],
        "outcome": outcome,
        "product": purchased_product,
    }


def execute_action(action: str, env: ShoppingEnvironment, prefs: dict,
                   strategy: dict, search_results: list,
                   current_site: str, fails: int, max_fails: int) -> dict:
    """
    Translate Claude's action text into environment calls.
    Returns an observation dict.
    """
    # Strip brackets Claude sometimes adds: "ENTER_STORE [zappos]" → "ENTER_STORE zappos"
    action = action.replace("[", "").replace("]", "")
    action_upper = action.upper()

    # ENTER_STORE
    if action_upper.startswith("ENTER_STORE"):
        parts = action.split()
        site = parts[1].lower() if len(parts) > 1 else strategy["site"]
        result = env.enter_store(site)
        if result["success"]:
            return {"site": site, "message": f"Entered {site}. Ready to search."}
        else:
            return {"failed": True, "message": f"CAPTCHA on {site}. Try another site."}

    # SEARCH
    elif action_upper.startswith("SEARCH"):
        if not current_site:
            return {"message": "You need to enter a store first."}
        results = env.search_products(current_site, strategy["query_style"], prefs)
        if not results:
            return {"results": [], "failed": True,
                    "message": "No results found. Try different query or site."}
        summary = []
        for i, p in enumerate(results):
            summary.append(
                f"[{i}] {p['name']} | ${p['price']} | "
                f"Rating: {p['rating']} | Size {prefs['size']} available: {prefs['size'] in p['sizes']} | "
                f"Delivery: {p['delivery_days']} days | In stock: {p['in_stock']}"
            )
        return {
            "results": results,
            "message": f"Found {len(results)} products:\n" + "\n".join(summary)
        }

    # EVALUATE
    elif action_upper.startswith("EVALUATE"):
        parts = action.split()
        idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if not search_results or idx >= len(search_results):
            return {"message": "Invalid product index."}
        product = search_results[idx]
        eval_result = env.evaluate_product(product, prefs)
        match_pct = len(eval_result["matches"]) / (len(eval_result["matches"]) + len(eval_result["misses"]) + 0.001)
        msg = (f"Evaluated {product['name']}: "
               f"Matches={eval_result['matches']}, Misses={eval_result['misses']}. "
               f"Match score: {match_pct:.0%}")
        if not eval_result["misses"]:
            msg += " — PERFECT MATCH. Ready to purchase."
            return {"message": msg, "found": True}
        return {"message": msg}

    # PURCHASE
    elif action_upper.startswith("PURCHASE"):
        parts = action.split()
        idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if not search_results or idx >= len(search_results):
            return {"message": "Invalid product index."}
        product = search_results[idx]
        result = env.attempt_purchase(current_site, product)
        if result["success"]:
            return {
                "purchased": True,
                "product": product,
                "message": f"Purchase confirmed! {product['name']} for ${product['price']}. Order placed."
            }
        return {"failed": True, "message": f"Purchase failed: {result.get('reason')}"}

    # ABANDON
    elif action_upper.startswith("ABANDON"):
        return {"failed": True, "message": f"Abandoned {current_site}. Try another site."}

    # DONE
    elif action_upper.startswith("DONE"):
        return {"message": "Run complete."}

    return {"message": f"Unknown action: {action}. Use ENTER_STORE, SEARCH, EVALUATE, PURCHASE, ABANDON, or DONE."}


# --- Test ---
if __name__ == "__main__":
    import json
    from memory_agent import MemoryAgent

    # Reset context graph for clean test
    context_graph_fresh = {
        "user": {
            "preferences": {
                "brands": ["Nike", "Adidas"],
                "size": 10,
                "budget": 120,
                "max_delivery_days": 2,
                "style": "running"
            },
            "trust_rules": {
                "max_autonomous_spend": 150,
                "approved_categories": ["footwear"],
                "require_approval_first_n_runs": 3
            }
        },
        "history": [],
        "learned_insights": []
    }

    with open("context_graph.json", "w") as f:
        json.dump(context_graph_fresh, f, indent=2)

    memory = MemoryAgent()
    cg = memory.get_working_memory()
    history_summary = memory.get_history_summary()

    strategy = {
        "site": "zappos",
        "query_style": "specific",
        "filter_strategy": "size_first",
        "abandon_threshold": "after_1_fail"
    }

    result = run_shopping_episode(cg, strategy, history_summary, run_number=1)

    print("\n=== Episode Result ===")
    print(f"Reward: {result['reward']}")
    print(f"Outcome: {result['outcome']}")
    print(f"Steps: {result['steps']}")
    print(f"Product: {result['product']}")
