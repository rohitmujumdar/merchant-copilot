"""
Simulated eCommerce Environment

3 fake stores (Zappos, Nike, Amazon) with different product catalogs.
Each store has different strengths — this is what the RL agent learns.

Zappos: Best Nike/Adidas selection, good size availability, moderate prices
Nike.com: Cheapest Nike, limited to Nike only, sometimes slow shipping
Amazon: Widest selection but more CAPTCHAs, variable quality, fastest shipping
"""

import random

# ── Live mode toggle ───────────────────────────────────────────────────────────
# Set True to pull real product data from Zappos / 6pm via Jina.ai reader.
# Nike and Amazon fall back to simulation (JS-heavy / bot-blocked).
LIVE_MODE = True
LIVE_SITES = {"zappos", "6pm", "stockx", "goat"}   # sites that scrape reliably

_live_cache: dict = {}  # cache per site per run so we don't re-fetch mid-episode


# --- Product Catalogs ---

ZAPPOS_CATALOG = [
    {"name": "Nike Air Zoom Pegasus 41", "brand": "Nike", "price": 109, "rating": 4.6, "sizes": [8, 9, 10, 11, 12], "delivery_days": 2, "in_stock": True},
    {"name": "Nike Revolution 7", "brand": "Nike", "price": 74, "rating": 4.2, "sizes": [9, 10, 11], "delivery_days": 3, "in_stock": True},
    {"name": "Adidas Ultraboost Light", "brand": "Adidas", "price": 118, "rating": 4.7, "sizes": [8, 9, 10, 11, 12], "delivery_days": 2, "in_stock": True},
    {"name": "Adidas Runfalcon 5", "brand": "Adidas", "price": 65, "rating": 4.0, "sizes": [10, 11, 12], "delivery_days": 3, "in_stock": True},
    {"name": "Nike Vomero 18", "brand": "Nike", "price": 159, "rating": 4.8, "sizes": [9, 10, 11], "delivery_days": 2, "in_stock": True},
    {"name": "Adidas Supernova Rise", "brand": "Adidas", "price": 140, "rating": 4.5, "sizes": [8, 9, 10], "delivery_days": 2, "in_stock": True},
    {"name": "Nike Winflo 11", "brand": "Nike", "price": 89, "rating": 4.3, "sizes": [8, 9, 10, 11], "delivery_days": 2, "in_stock": True},
]

NIKE_CATALOG = [
    {"name": "Nike Air Zoom Pegasus 41", "brand": "Nike", "price": 99, "rating": 4.6, "sizes": [8, 9, 10, 11], "delivery_days": 4, "in_stock": True},
    {"name": "Nike Revolution 7", "brand": "Nike", "price": 64, "rating": 4.2, "sizes": [9, 10], "delivery_days": 3, "in_stock": True},
    {"name": "Nike Vomero 18", "brand": "Nike", "price": 149, "rating": 4.8, "sizes": [9, 11], "delivery_days": 5, "in_stock": True},
    {"name": "Nike Winflo 11", "brand": "Nike", "price": 79, "rating": 4.3, "sizes": [8, 10, 11], "delivery_days": 3, "in_stock": True},
    {"name": "Nike InfinityRN 4", "brand": "Nike", "price": 112, "rating": 4.5, "sizes": [10, 11, 12], "delivery_days": 4, "in_stock": True},
    {"name": "Nike Structure 26", "brand": "Nike", "price": 139, "rating": 4.4, "sizes": [9, 10], "delivery_days": 5, "in_stock": False},
]

AMAZON_CATALOG = [
    {"name": "Nike Air Zoom Pegasus 41", "brand": "Nike", "price": 114, "rating": 4.4, "sizes": [8, 9, 10, 11, 12], "delivery_days": 1, "in_stock": True},
    {"name": "Adidas Ultraboost Light", "brand": "Adidas", "price": 125, "rating": 4.5, "sizes": [8, 9, 10, 11], "delivery_days": 1, "in_stock": True},
    {"name": "Nike Revolution 7", "brand": "Nike", "price": 69, "rating": 4.0, "sizes": [10, 11], "delivery_days": 1, "in_stock": True},
    {"name": "Adidas Runfalcon 5", "brand": "Adidas", "price": 59, "rating": 3.9, "sizes": [9, 10, 11, 12], "delivery_days": 1, "in_stock": True},
    {"name": "Generic RunPro X200", "brand": "Generic", "price": 35, "rating": 3.2, "sizes": [8, 9, 10, 11, 12], "delivery_days": 1, "in_stock": True},
    {"name": "Nike Winflo 11", "brand": "Nike", "price": 95, "rating": 4.2, "sizes": [9, 10], "delivery_days": 2, "in_stock": True},
    {"name": "Adidas Supernova Rise", "brand": "Adidas", "price": 132, "rating": 4.4, "sizes": [10, 11], "delivery_days": 1, "in_stock": True},
]

STORES = {
    "zappos": {
        "catalog": ZAPPOS_CATALOG,
        "captcha_rate": 0.05,
        "search_noise": 0.1,
        "live_url": "https://www.zappos.com/search?term=nike+adidas+running+sneakers+men",
        "strengths": "Best brand selection, reliable size availability",
    },
    "6pm": {
        "catalog": ZAPPOS_CATALOG,   # similar catalog (both Zappos-owned)
        "captcha_rate": 0.05,
        "search_noise": 0.1,
        "live_url": "https://www.6pm.com/mens-athletic-shoes",
        "strengths": "Discounted Zappos inventory, good for deals",
    },
    "stockx": {
        "catalog": AMAZON_CATALOG,   # fallback if live fails
        "captcha_rate": 0.05,
        "search_noise": 0.05,
        "live_url": "https://stockx.com/sneakers/nike",
        "strengths": "Resale marketplace — hyped shoes, market-driven pricing",
    },
    "goat": {
        "catalog": NIKE_CATALOG,     # fallback if live fails
        "captcha_rate": 0.05,
        "search_noise": 0.05,
        "live_url": "https://www.goat.com/sneakers/brand/nike",
        "strengths": "Premium resale — authenticated sneakers, collector items",
    },
    "nike": {
        "catalog": NIKE_CATALOG,
        "captcha_rate": 0.1,
        "search_noise": 0.05,
        "live_url": None,           # JS-heavy, use simulation
        "strengths": "Cheapest Nike prices, but Nike-only and slower shipping",
    },
    "amazon": {
        "catalog": AMAZON_CATALOG,
        "captcha_rate": 0.2,
        "search_noise": 0.15,
        "live_url": None,           # Bot-blocked, use simulation
        "strengths": "Fastest shipping, widest selection, but more CAPTCHAs",
    },
}


class SimulatedStore:
    """Simulates browsing and searching an ecommerce site."""

    def __init__(self, store_name: str):
        self.name = store_name
        store = STORES[store_name]
        self.catalog = store["catalog"]
        self.captcha_rate = store["captcha_rate"]
        self.search_noise = store["search_noise"]

    def check_captcha(self) -> bool:
        """Returns True if CAPTCHA blocks the agent."""
        return random.random() < self.captcha_rate

    def search(self, query_style: str, preferences: dict) -> list[dict]:
        """
        Search the store. Returns matching products.

        query_style affects how many relevant results come back:
        - "broad": returns everything, lots of noise
        - "moderate": filters by brand
        - "specific": filters by brand + size + price
        """
        results = list(self.catalog)

        # Add noise based on query style
        if query_style == "broad":
            # Returns all products, some irrelevant
            pass
        elif query_style == "moderate":
            # Filter by preferred brands
            brands = preferences.get("brands", [])
            if brands:
                results = [p for p in results if p["brand"] in brands]
        elif query_style == "specific":
            # Filter by brand + size + budget
            brands = preferences.get("brands", [])
            size = preferences.get("size")
            budget = preferences.get("budget")
            if brands:
                results = [p for p in results if p["brand"] in brands]
            if size:
                results = [p for p in results if size in p["sizes"]]
            if budget:
                results = [p for p in results if p["price"] <= budget]

        # Search noise: randomly remove some good results
        if random.random() < self.search_noise:
            if len(results) > 1:
                results.pop(random.randint(0, len(results) - 1))

        return results

    def check_availability(self, product: dict, size: int) -> bool:
        """Check if a specific size is in stock."""
        return product["in_stock"] and size in product["sizes"]

    def get_delivery_estimate(self, product: dict) -> int:
        """Get delivery days for a product."""
        return product["delivery_days"]

    def checkout(self, product: dict) -> dict:
        """Simulate checkout. Returns order confirmation or failure."""
        if not product["in_stock"]:
            return {"success": False, "reason": "out_of_stock"}
        return {
            "success": True,
            "product": product["name"],
            "price": product["price"],
            "brand": product["brand"],
        }


class ShoppingEnvironment:
    """
    The full simulated shopping environment.
    Agent interacts with this — picks a store, searches, evaluates, buys.
    """

    def __init__(self):
        self.stores = {name: SimulatedStore(name) for name in STORES}
        self.step_count = 0
        self.events = []
        self.log = []

    def reset(self):
        """Reset for a new run."""
        self.step_count = 0
        self.events = []
        self.log = []

    def _step(self, action: str, detail: str = ""):
        """Record a step."""
        self.step_count += 1
        self.log.append({"step": self.step_count, "action": action, "detail": detail})

    def enter_store(self, store_name: str) -> dict:
        """Enter a store. Might hit CAPTCHA."""
        self._step("enter_store", store_name)
        store = self.stores[store_name]
        if store.check_captcha():
            self.events.append("captcha_blocked")
            return {"success": False, "reason": "captcha", "store": store_name}
        return {"success": True, "store": store_name}

    def search_products(self, store_name: str, query_style: str,
                        preferences: dict) -> list[dict]:
        """Search for products. Uses live scraping for supported sites, simulation otherwise."""
        self._step("search", f"{store_name} ({query_style})")

        if LIVE_MODE and store_name in LIVE_SITES:
            results = self._search_live(store_name, preferences)
            if results:
                print(f"[LiveMode] {store_name}: {len(results)} real products fetched")
                if not results:
                    self.events.append("out_of_stock")
                return results
            print(f"[LiveMode] {store_name}: scrape failed, falling back to simulation")

        # Simulation fallback
        store = self.stores[store_name]
        results = store.search(query_style, preferences)
        if not results:
            self.events.append("out_of_stock")
        return results

    def _search_live(self, store_name: str, preferences: dict) -> list[dict]:
        """
        Fetch real products via Jina.ai reader.
        Results are cached so a single episode doesn't re-fetch.
        Normalizes to environment.py product format.
        """
        if store_name in _live_cache:
            return _live_cache[store_name]

        try:
            from live_scraper import scrape_real_products
            size = preferences.get("size", 10)
            budget = preferences.get("budget", 120)
            raw = scrape_real_products(store_name, size=size, budget=budget)
            if not raw:
                return []

            # Normalize: add sizes/delivery/in_stock fields the sim expects
            normalized = []
            for p in raw:
                normalized.append({
                    "name": p["name"],
                    "brand": p.get("brand", "Unknown"),
                    "price": p["price"],
                    "rating": p.get("rating", 4.0),
                    "sizes": [size],           # assume size available (live check would require product page)
                    "delivery_days": 2,        # default; real sites need separate lookup
                    "in_stock": True,
                    "url": p.get("url", ""),
                    "live": True,              # tag so dashboard can show "LIVE" badge
                })
            _live_cache[store_name] = normalized
            return normalized
        except Exception as e:
            print(f"[LiveMode] Error: {e}")
            return []

    def evaluate_product(self, product: dict, preferences: dict) -> dict:
        """Evaluate a product against user preferences."""
        self._step("evaluate", product["name"])
        score = {"product": product, "matches": [], "misses": []}

        # Brand match (case-insensitive for live data)
        product_brand = product["brand"].lower()
        pref_brands = [b.lower() for b in preferences.get("brands", [])]
        if product_brand in pref_brands:
            score["matches"].append("brand")
        else:
            score["misses"].append("brand")

        # Price
        budget = preferences.get("budget", 999)
        if product["price"] <= budget:
            score["matches"].append("price")
            self.events.append("under_budget")
        else:
            score["misses"].append("price")
            self.events.append("over_budget")

        # Size
        size = preferences.get("size")
        if size and size in product["sizes"]:
            score["matches"].append("size")
        else:
            score["misses"].append("size")
            self.events.append("wrong_size")

        # Delivery
        max_days = preferences.get("max_delivery_days", 99)
        if product["delivery_days"] <= max_days:
            score["matches"].append("delivery")
            self.events.append("fast_delivery")
        else:
            score["misses"].append("delivery")

        # Classify match
        if len(score["misses"]) == 0:
            self.events.append("item_found_full_match")
        elif len(score["matches"]) >= 2:
            self.events.append("item_found_partial")

        return score

    def attempt_purchase(self, store_name: str, product: dict) -> dict:
        """Try to buy a product."""
        self._step("purchase", product["name"])
        store = self.stores[store_name]
        self.events.append("checkout_reached")
        result = store.checkout(product)
        if result["success"]:
            self.events.append("purchase_completed")
        else:
            self.events.append("out_of_stock")
        return result

    def get_results(self) -> dict:
        """Get the final results of this run."""
        return {
            "events": list(set(self.events)),  # deduplicate
            "steps": self.step_count,
            "log": self.log,
        }


# --- Quick test ---
if __name__ == "__main__":
    env = ShoppingEnvironment()

    preferences = {
        "brands": ["Nike", "Adidas"],
        "size": 10,
        "budget": 120,
        "max_delivery_days": 2,
    }

    print("=== Simulated Shopping Run ===\n")

    # Enter Zappos
    result = env.enter_store("zappos")
    print(f"Enter Zappos: {result}")

    if result["success"]:
        # Search
        products = env.search_products("zappos", "specific", preferences)
        print(f"Found {len(products)} products")

        if products:
            # Evaluate first product
            eval_result = env.evaluate_product(products[0], preferences)
            print(f"Evaluated: {products[0]['name']}")
            print(f"  Matches: {eval_result['matches']}")
            print(f"  Misses: {eval_result['misses']}")

            # Buy if good match
            if not eval_result["misses"]:
                purchase = env.attempt_purchase("zappos", products[0])
                print(f"Purchase: {purchase}")

    results = env.get_results()
    print(f"\nRun complete: {results['steps']} steps, events: {results['events']}")
