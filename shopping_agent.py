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

    # Guardrails: user-specific instructions
    color = prefs.get("color", "")
    specific_product = prefs.get("specific_product", "")
    custom_instructions = prefs.get("custom_instructions", "")
    excluded_brands = prefs.get("excluded_brands", [])

    original_query = context_graph.get("user", {}).get("original_query", "")
    feedback = context_graph.get("user", {}).get("feedback", "")

    guardrails = ""
    if original_query:
        guardrails += f"\n- ORIGINAL USER REQUEST: \"{original_query}\" — use these exact terms when searching."
    if color:
        guardrails += f"\n- REQUIRED COLOR: {color} — only buy this color. Skip products that don't match."
    if specific_product:
        guardrails += f"\n- SPECIFIC PRODUCT REQUESTED: {specific_product} — prioritize finding this exact product."
    if custom_instructions:
        guardrails += f"\n- USER INSTRUCTIONS: {custom_instructions} — you MUST follow these."
    if excluded_brands:
        guardrails += f"\n- EXCLUDED BRANDS: {excluded_brands} — never buy from these brands."
    if feedback:
        guardrails += f"\n- USER REJECTED LAST RESULT: \"{feedback}\" — adjust your search to match this feedback."

    return f"""You are a personal shopping agent. Your job is to find and buy the best sneaker for the user.

USER PREFERENCES (never violate these):
- Brands: {prefs.get("brands", [])}
- Size: {prefs.get("size")}
- Budget: ${prefs.get("budget")}
- Max delivery: {prefs.get("max_delivery_days")} days
- Max autonomous spend: ${trust.get("max_autonomous_spend")}
{guardrails}

{history_summary}

GUARDRAILS — HARD RULES (violating these = failed run):
- Only buy products that match the user's preferred brands
- If a specific product or color is requested, ONLY buy that. Do not substitute.
- If user said "ask before buying X", you must output: NEED_APPROVAL [product name, price, reason] instead of PURCHASE
- Never buy the wrong size
- Never exceed budget

RULES:
- Only shop on approved sites: Zappos, 6pm, StockX, GOAT, Nike, Amazon
- 6pm is a discount shoe site, StockX and GOAT are sneaker resale marketplaces
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
                         history_summary: str, run_number: int,
                         memory_agent=None) -> dict:
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

    # Site registry with real URLs (the "internet" the agent navigates)
    site_registry = {
        "zappos": "https://www.zappos.com",
        "6pm": "https://www.6pm.com",
        "stockx": "https://stockx.com",
        "goat": "https://www.goat.com",
        "nike": "https://www.nike.com",
        "amazon": "https://www.amazon.com",
    }

    # Build initial prompt for Claude
    original_query = context_graph.get("user", {}).get("original_query", "")
    query_line = f"\nUser is looking for: \"{original_query}\"\nUse these terms in your SEARCH queries.\n" if original_query else ""

    initial_message = f"""Run #{run_number}. Your strategy this run:
- Site: {strategy["site"]} ({site_registry.get(strategy["site"], "")})
- Query style: {strategy["query_style"]} (broad=generic, moderate=brand+size, specific=brand+size+budget)
- Filter: {strategy["filter_strategy"]}
- Abandon after: {max_fails} failure(s)
{query_line}

Available actions:
- NAVIGATE [url]: Navigate to a shopping site (zappos, 6pm, stockx, goat, nike, amazon)
- SEARCH [query]: Search for products on current site
- EVALUATE [product_index]: Evaluate a specific product from search results
- PURCHASE [product_index]: Attempt to purchase the product
- ASK_MEMORY [question]: Ask the Memory Agent about past runs (prices, best sites, lessons)
- NEED_APPROVAL [product_index, reason]: Flag a product that doesn't match user's exact request — pauses for human review
- ABANDON: Give up on current site, try another
- DONE: End the run

You are browsing the real internet. NAVIGATE loads a real site. SEARCH returns live inventory.
ASK_MEMORY lets you query past experience before making decisions.
Start shopping."""

    messages = [{"role": "user", "content": initial_message}]

    reasoning_trace = []
    search_results = []
    current_site = None
    fails = 0
    purchased_product = None
    outcome = "not_found"
    max_steps = 8  # safety limit (lower = faster demo)

    print(f"\n{'='*60}")
    print(f"RUN {run_number} | Site: {strategy['site']} | Query: {strategy['query_style']}")
    print(f"{'='*60}")

    for step in range(max_steps):

        # Call Claude — stop before it hallucinates its own Observation
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
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
            search_results, current_site, fails, max_fails,
            memory_agent=memory_agent
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


def _handle_memory_query(memory_agent, question: str) -> dict:
    """
    Agent-to-Agent Protocol: Shopper Agent queries Memory Agent mid-run.
    Memory Agent responds with relevant history/insights.
    This is a real inter-agent communication — not just sequential handoff.
    """
    context = memory_agent.get_working_memory()
    history = context.get("history", [])
    insights = context.get("learned_insights", [])

    # Build a concise memory response
    response_parts = []

    # Recent run history
    if history:
        last_3 = history[-3:]
        for h in last_3:
            response_parts.append(
                f"Run {h.get('run', '?')}: {h.get('site', '?')} → "
                f"reward {h.get('reward', 0)} ({h.get('outcome', '?')})"
            )

    # Learned lessons
    if insights:
        insight_strs = [i if isinstance(i, str) else i.get("lesson", str(i)) for i in insights[-3:]]
        response_parts.append(f"Lessons learned: {'; '.join(insight_strs)}")

    # Best known prices from history
    best_prices = {}
    for h in history:
        if h.get("outcome") == "purchased" and h.get("reward", 0) > 0:
            site = h.get("site", "?")
            reward = h.get("reward", 0)
            if site not in best_prices or reward > best_prices[site]:
                best_prices[site] = reward
    if best_prices:
        response_parts.append(
            f"Best rewards by site: {', '.join(f'{s}={r}pts' for s, r in best_prices.items())}"
        )

    if not response_parts:
        memory_response = "No prior history available. This is an early run."
    else:
        memory_response = "\n".join(response_parts)

    return {"message": f"[Memory Agent responds]: {memory_response}"}


def execute_action(action: str, env: ShoppingEnvironment, prefs: dict,
                   strategy: dict, search_results: list,
                   current_site: str, fails: int, max_fails: int,
                   memory_agent=None) -> dict:
    """
    Translate Claude's action text into environment calls.
    Returns an observation dict.
    """
    # Strip brackets Claude sometimes adds: "NAVIGATE [zappos]" → "NAVIGATE zappos"
    action = action.replace("[", "").replace("]", "")
    action_upper = action.upper()

    # Site URL registry
    site_urls = {
        "zappos": "https://www.zappos.com",
        "6pm": "https://www.6pm.com",
        "stockx": "https://stockx.com",
        "goat": "https://www.goat.com",
        "nike": "https://www.nike.com",
        "amazon": "https://www.amazon.com",
    }

    # NAVIGATE (replaces ENTER_STORE — shows real URLs)
    if action_upper.startswith("NAVIGATE") or action_upper.startswith("ENTER_STORE"):
        parts = action.split()
        site = parts[1].lower() if len(parts) > 1 else strategy["site"]
        # Strip .com if user typed it
        site = site.replace(".com", "").replace("https://", "").replace("www.", "")
        result = env.enter_store(site)
        url = site_urls.get(site, f"https://{site}.com")
        if result["success"]:
            return {"site": site, "message": f"Navigated to {url} — page loaded. Ready to search."}
        else:
            return {"failed": True, "message": f"Blocked by bot detection on {url}. Try another site."}

    # ASK_MEMORY — Agent-to-Agent protocol: Shopper queries Memory Agent mid-run
    elif action_upper.startswith("ASK_MEMORY"):
        question = action.replace("ASK_MEMORY", "").strip()
        if memory_agent:
            return _handle_memory_query(memory_agent, question)
        return {"message": "Memory Agent unavailable. Continue shopping."}

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
            color_info = f" | Color: {p['color']}" if p.get('color') else ""
            summary.append(
                f"[{i}] {p['name']} | ${p['price']} | "
                f"Rating: {p['rating']} | Size {prefs['size']} available: {prefs['size'] in p['sizes']}{color_info} | "
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

    # NEED_APPROVAL — agent flags a product that doesn't match exact request
    elif action_upper.startswith("NEED_APPROVAL"):
        parts = action.split()
        idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if search_results and idx < len(search_results):
            product = search_results[idx]
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Doesn't match exact request"
            return {
                "message": f"APPROVAL NEEDED: {product['name']} (${product['price']}) — {reason}. "
                           f"In a production system, this would pause for human approval. "
                           f"For demo: skipping this product. Find a better match or ABANDON.",
                "needs_approval": True,
            }
        return {"message": "Invalid product index for approval request."}

    # ABANDON
    elif action_upper.startswith("ABANDON"):
        return {"failed": True, "message": f"Abandoned {current_site}. Try another site."}

    # DONE
    elif action_upper.startswith("DONE"):
        return {"message": "Run complete."}

    return {"message": f"Unknown action: {action}. Use NAVIGATE, SEARCH, EVALUATE, PURCHASE, ASK_MEMORY, ABANDON, or DONE."}


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
