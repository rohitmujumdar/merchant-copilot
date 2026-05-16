"""
Reward function for the RL Shopping Agent.

Calculates a score for each shopping run based on what the agent achieved.
This is the "scorecard" that the RL bandits learn from.
"""


REWARD_TABLE = {
    # Positive outcomes
    "purchase_completed":     25,
    "item_found_full_match":  20,
    "checkout_reached":       15,
    "under_budget":           10,
    "fast_delivery":           5,
    "item_found_partial":     10,

    # Negative outcomes
    "captcha_blocked":       -10,
    "out_of_stock":          -15,
    "over_budget":            -5,
    "wrong_size":             -8,

    # Efficiency
    "per_step_penalty":       -2,
}


def calculate_reward(events: list[str], steps: int) -> dict:
    """
    Calculate total reward from a list of events that happened during a run.

    Args:
        events: list of event names (e.g., ["item_found_full_match", "under_budget", "purchase_completed"])
        steps: number of steps the agent took

    Returns:
        dict with breakdown and total
    """
    breakdown = {}

    for event in events:
        if event in REWARD_TABLE:
            breakdown[event] = REWARD_TABLE[event]

    # Step penalty
    step_cost = steps * REWARD_TABLE["per_step_penalty"]
    breakdown["step_penalty"] = step_cost

    total = sum(breakdown.values())

    return {
        "breakdown": breakdown,
        "total": total,
        "steps": steps,
        "events": events,
    }


# --- Examples ---
if __name__ == "__main__":
    # Great run: found exactly what user wanted, bought it, fast
    great_run = calculate_reward(
        events=["item_found_full_match", "under_budget", "fast_delivery",
                "checkout_reached", "purchase_completed"],
        steps=3
    )
    print(f"Great run: {great_run['total']} points")
    print(f"  Breakdown: {great_run['breakdown']}\n")

    # Bad run: searched around, hit dead ends, found nothing
    bad_run = calculate_reward(
        events=["out_of_stock", "wrong_size", "item_found_partial"],
        steps=8
    )
    print(f"Bad run: {bad_run['total']} points")
    print(f"  Breakdown: {bad_run['breakdown']}\n")

    # Medium run: found something but over budget, didn't buy
    medium_run = calculate_reward(
        events=["item_found_partial", "over_budget"],
        steps=5
    )
    print(f"Medium run: {medium_run['total']} points")
    print(f"  Breakdown: {medium_run['breakdown']}")
