"""
Live Scraper — Real product data using Jina.ai reader + Claude extraction.

Drop-in replacement for environment.py's catalog.
Uses Jina.ai (free, no key) to fetch pages, Claude to extract structured data.

Usage:
    from live_scraper import scrape_real_products
    products = scrape_real_products('zappos', size=10, budget=120)
"""

import re
import httpx
import json
from dotenv import dotenv_values
import anthropic

config = dotenv_values(".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])

SEARCH_URLS = {
    "zappos":  "https://www.zappos.com/search?term=nike+adidas+running+sneakers+men",
    "6pm":     "https://www.6pm.com/men-running-shoes/CK_XARC81wEY0O4BwAEC4gIEAQIDGA.zso",
    "stockx":  "https://stockx.com/sneakers/nike",
    "goat":    "https://www.goat.com/sneakers/brand/nike",
    "nike":    "https://www.nike.com/w/mens-running-shoes-37v7jznik1zy7ok",
    "amazon":  "https://www.amazon.com/s?k=nike+adidas+running+shoes+men",
}

def _parse_zappos_markdown(text: str, site: str) -> list[dict]:
    """
    Parse Jina.ai reader output from Zappos / 6pm.
    Zappos: '[Nike - Run Swift 3. Color Black. $85.00. 4.4 out of 5 stars](url)'
    6pm:    '[Nike - Shoe Name. Color X. On sale for $75.00. MSRP $100. 4.2 out of 5 stars](url)'
    """
    products = []
    # Handles both regular price and "On sale for $X" formats
    pattern = re.compile(
        r'\[(Nike|Adidas|New Balance|HOKA|Brooks|Asics|Reebok|adidas) - ([^.]+)\.'  # brand - name
        r'[^\]]*?(?:On sale for )?\$([\d,]+\.?\d*)\.'                               # price (sale or regular)
        r'.*?([\d.]+) out of 5 stars\]'                                              # rating
        r'\((https://[^\)]+)\)',                                                      # url
        re.IGNORECASE
    )
    seen = set()
    for m in pattern.finditer(text):
        brand, name, price_str, rating, url = m.groups()
        price = float(price_str.replace(",", ""))
        key = name.strip()
        if key in seen:
            continue
        seen.add(key)
        products.append({
            "name": f"{brand} {name.strip()}",
            "price": price,
            "rating": float(rating),
            "brand": brand,
            "url": url,
        })
        if len(products) >= 6:
            break
    return products


def _parse_stockx(text: str) -> list[dict]:
    """Parse StockX: 'Nike Product Name Lowest Ask $PRICE'"""
    products = []
    pattern = re.compile(r'(Nike [^\]]{5,60}?) Lowest Ask \$(\d+)', re.IGNORECASE)
    seen = set()
    for m in pattern.finditer(text):
        name, price_str = m.groups()
        name = name.strip()
        if name in seen:
            continue
        seen.add(name)
        products.append({
            "name": name,
            "price": float(price_str),
            "rating": 4.5,  # StockX doesn't show ratings; use default
            "brand": "Nike",
            "url": "",
        })
        if len(products) >= 6:
            break
    return products


def _parse_goat(text: str) -> list[dict]:
    """Parse GOAT: '[Product Name $PRICE ![Image'"""
    products = []
    pattern = re.compile(r'\[([^\]]*?Nike[^\]]*?) \$(\d+) !\[', re.IGNORECASE)
    seen = set()
    for m in pattern.finditer(text):
        raw_name, price_str = m.groups()
        # Clean trailing date fragments
        name = re.sub(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d*\s*$', '', raw_name).strip()
        name = re.sub(r'\s*\d{4}\s*$', '', name).strip()
        if name in seen:
            continue
        seen.add(name)
        products.append({
            "name": name,
            "price": float(price_str),
            "rating": 4.5,  # GOAT doesn't show ratings; use default
            "brand": "Nike",
            "url": "",
        })
        if len(products) >= 6:
            break
    return products


def _claude_extract(raw: str) -> list[dict]:
    """Fallback: use Claude to extract product data from raw page text."""
    extraction = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": EXTRACT_PROMPT.format(content=raw)
        }]
    )
    raw_json = extraction.content[0].text.strip()
    if raw_json.startswith("```"):
        raw_json = "\n".join(raw_json.split("\n")[1:-1])
    return json.loads(raw_json)


EXTRACT_PROMPT = """Extract up to 5 sneaker products from this webpage content.
Return ONLY a valid JSON array, no other text, no markdown.
Each product must have: name, price (float), rating (float 1-5), brand, url

Rules:
- Only include products with a clear numeric price
- brand must be one of: Nike, Adidas, New Balance, HOKA, Brooks, Asics, Reebok
- Skip products with no price or no rating
- urls should be full absolute URLs

Content:
{content}

Return ONLY this format (no markdown, no explanation):
[{{"name": "Product Name", "price": 99.99, "rating": 4.5, "brand": "Nike", "url": "https://..."}}]"""


def scrape_real_products(site: str, size: int = 10, budget: int = 120) -> list[dict]:
    """
    Scrape real products from a retail site.
    Returns list of product dicts in environment.py format.
    Falls back to empty list on any failure.
    """
    url = SEARCH_URLS.get(site, SEARCH_URLS["zappos"])
    jina_url = f"https://r.jina.ai/{url}"

    try:
        print(f"[LiveScraper] Fetching {site} ({url[:60]}...)")
        resp = httpx.get(jina_url, headers={"Accept": "text/plain"}, timeout=25)
        if resp.status_code != 200:
            print(f"[LiveScraper] HTTP {resp.status_code} — falling back")
            return []
        # Product listings appear deep in the page — find where they start
        full = resp.text
        if site in ("stockx", "goat"):
            # These sites have products scattered; use more text
            raw = full[:30000]
        else:
            listing_start = full.find("out of 5 stars")
            if listing_start > 0:
                raw = full[max(0, listing_start - 200): listing_start + 8000]
            else:
                raw = full[:8000]
    except Exception as e:
        print(f"[LiveScraper] Fetch failed: {e}")
        return []

    try:
        if site == "stockx":
            products = _parse_stockx(raw)
        elif site == "goat":
            products = _parse_goat(raw)
        else:
            products = _parse_zappos_markdown(raw, site)
        if not products:
            # Fallback: use Claude if regex parse fails
            products = _claude_extract(raw)
    except Exception as e:
        print(f"[LiveScraper] Extraction failed: {e}")
        return []

    # Normalize to environment.py format
    # Brand normalization: title-case so "adidas" → "Adidas", "nike" → "Nike"
    normalized = []
    for p in products[:5]:
        try:
            raw_brand = p.get("brand", "Unknown")
            brand = raw_brand.title() if raw_brand.lower() in ("nike", "adidas", "hoka", "asics", "reebok", "brooks") else raw_brand
            normalized.append({
                "name": p["name"],
                "price": float(p["price"]),
                "rating": float(p.get("rating", 4.0)),
                "brand": brand,
                "sizes": [size],  # Real scraping would check size availability
                "delivery_days": 2,
                "in_stock": True,
                "url": p.get("url", ""),
            })
        except (KeyError, ValueError):
            continue

    print(f"[LiveScraper] Got {len(normalized)} products from {site}")
    return normalized


if __name__ == "__main__":
    print("=== LIVE SCRAPER TEST ===\n")

    for site in ["zappos", "nike"]:
        print(f"\n--- {site.upper()} ---")
        products = scrape_real_products(site, size=10, budget=120)
        for p in products:
            within_budget = "✅" if p["price"] <= 120 else "❌ over"
            print(f"  {p['name']} | ${p['price']} | Rating: {p['rating']} | {within_budget}")
