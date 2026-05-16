"""
Thompson Sampling Multi-Bandit RL System

4 independent bandits, each learning a different shopping dimension:
1. Site picker: which ecommerce site to try
2. Query style: how specific the search query should be
3. Filter strategy: what to filter/sort by first
4. Abandon threshold: when to give up on a site

Each bandit maintains a Beta(alpha, beta) distribution per arm.
Thompson Sampling: sample from each arm's distribution, pick the highest.
After reward: update alpha (success) or beta (failure) based on outcome.
"""

import random
import json
from dataclasses import dataclass, field, asdict


@dataclass
class Arm:
    """One option within a bandit. Tracks Beta distribution parameters."""
    name: str
    alpha: float = 1.0  # successes + 1 (prior)
    beta: float = 1.0   # failures + 1 (prior)
    times_chosen: int = 0
    total_reward: float = 0.0

    def sample(self) -> float:
        """Sample from Beta distribution. Higher = more promising."""
        return random.betavariate(self.alpha, self.beta)

    def update(self, reward: float, max_reward: float):
        """
        Update Beta distribution based on normalized reward.
        Reward is normalized to [0, 1] range for Beta distribution.
        """
        normalized = max(0.0, min(1.0, reward / max_reward)) if max_reward > 0 else 0.5
        self.alpha += normalized
        self.beta += (1 - normalized)
        self.times_chosen += 1
        self.total_reward += reward

    @property
    def mean_reward(self) -> float:
        if self.times_chosen == 0:
            return 0.0
        return self.total_reward / self.times_chosen


@dataclass
class Bandit:
    """One decision dimension with multiple arms."""
    name: str
    arms: list[Arm] = field(default_factory=list)

    def select_arm(self) -> Arm:
        """Thompson Sampling: sample each arm, pick highest."""
        samples = [(arm, arm.sample()) for arm in self.arms]
        return max(samples, key=lambda x: x[1])[0]

    def update(self, arm_name: str, reward: float, max_reward: float):
        """Update the chosen arm with the observed reward."""
        for arm in self.arms:
            if arm.name == arm_name:
                arm.update(reward, max_reward)
                return

    def get_weights(self) -> dict:
        """Return current learned preferences (for dashboard)."""
        total_alpha = sum(a.alpha for a in self.arms)
        return {arm.name: round(arm.alpha / total_alpha, 3) for arm in self.arms}


class RLAgent:
    """
    The RL "coach" — 4 Thompson Sampling bandits that learn
    which shopping strategy works best across runs.
    """

    MAX_REWARD = 75.0  # theoretical max single-run reward

    def __init__(self):
        self.bandits = {
            "site": Bandit(
                name="site",
                arms=[
                    Arm(name="zappos"),
                    Arm(name="nike"),
                    Arm(name="amazon"),
                ]
            ),
            "query_style": Bandit(
                name="query_style",
                arms=[
                    Arm(name="broad"),       # "running shoes"
                    Arm(name="moderate"),     # "Nike running shoes men"
                    Arm(name="specific"),     # "Nike Pegasus size 10 under $120"
                ]
            ),
            "filter_strategy": Bandit(
                name="filter_strategy",
                arms=[
                    Arm(name="price_first"),
                    Arm(name="brand_first"),
                    Arm(name="rating_first"),
                    Arm(name="size_first"),
                ]
            ),
            "abandon_threshold": Bandit(
                name="abandon_threshold",
                arms=[
                    Arm(name="after_1_fail"),
                    Arm(name="after_2_fails"),
                    Arm(name="after_3_fails"),
                ]
            ),
        }
        self.run_history = []

    def select_strategy(self) -> dict:
        """Select a full strategy by sampling all 4 bandits."""
        strategy = {}
        for name, bandit in self.bandits.items():
            arm = bandit.select_arm()
            strategy[name] = arm.name
        return strategy

    def update(self, strategy: dict, reward: float):
        """Update all 4 bandits with the reward from this run."""
        for bandit_name, arm_name in strategy.items():
            self.bandits[bandit_name].update(arm_name, reward, self.MAX_REWARD)

    def record_run(self, run_number: int, strategy: dict, reward: float,
                   reward_breakdown: dict, steps: int):
        """Record a completed run for history/dashboard."""
        self.run_history.append({
            "run": run_number,
            "strategy": strategy,
            "reward": reward,
            "reward_breakdown": reward_breakdown,
            "steps": steps,
            "bandit_weights": self.get_all_weights(),
        })

    def get_all_weights(self) -> dict:
        """Get current learned weights for all bandits (for dashboard)."""
        return {name: bandit.get_weights() for name, bandit in self.bandits.items()}

    def get_run_history(self) -> list:
        return self.run_history

    def to_dict(self) -> dict:
        """Serialize full state for saving/loading."""
        return {
            "bandits": {
                name: {
                    "name": bandit.name,
                    "arms": [asdict(arm) for arm in bandit.arms]
                }
                for name, bandit in self.bandits.items()
            },
            "run_history": self.run_history,
        }

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "RLAgent":
        with open(path, "r") as f:
            data = json.load(f)
        agent = cls()
        for name, bandit_data in data["bandits"].items():
            for arm_data, arm in zip(bandit_data["arms"], agent.bandits[name].arms):
                arm.alpha = arm_data["alpha"]
                arm.beta = arm_data["beta"]
                arm.times_chosen = arm_data["times_chosen"]
                arm.total_reward = arm_data["total_reward"]
        agent.run_history = data["run_history"]
        return agent


# --- Quick test ---
if __name__ == "__main__":
    agent = RLAgent()

    print("=== Thompson Sampling RL Agent ===\n")

    # Simulate 10 runs with fake rewards
    for run in range(1, 11):
        strategy = agent.select_strategy()

        # Fake reward: zappos + specific + size_first = best combo
        reward = 0
        if strategy["site"] == "zappos":
            reward += 25
        elif strategy["site"] == "nike":
            reward += 15
        else:
            reward += 5

        if strategy["query_style"] == "specific":
            reward += 15
        elif strategy["query_style"] == "moderate":
            reward += 8
        else:
            reward += 2

        if strategy["filter_strategy"] == "size_first":
            reward += 10
        else:
            reward += 3

        if strategy["abandon_threshold"] == "after_1_fail":
            reward += 5
        else:
            reward += 1

        agent.update(strategy, reward)
        agent.record_run(run, strategy, reward, {}, 5)

        print(f"Run {run:2d} | Strategy: {strategy}")
        print(f"        | Reward: {reward}")
        print(f"        | Weights: {agent.get_all_weights()}\n")

    print("=== Final Learned Preferences ===")
    for name, weights in agent.get_all_weights().items():
        print(f"  {name}: {weights}")
