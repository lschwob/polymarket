import httpx
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

async def fetch_events_by_tag(tag_slug: str, limit: int = 50) -> List[Dict]:
    """Fetch events filtered by tag slug."""
    async with httpx.AsyncClient() as client:
        url = f"{GAMMA_API_BASE}/events/pagination"
        params = {
            "limit": limit,
            "active": "true",
            "archived": "false",
            "tag_slug": tag_slug,
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false"
        }
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

async def fetch_market_details(market_slug_or_id: str) -> Optional[Dict]:
    """Fetch detailed market information (event with markets)."""
    async with httpx.AsyncClient() as client:
        url = f"{GAMMA_API_BASE}/events/{market_slug_or_id}"
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return data if isinstance(data, dict) else None
        except httpx.HTTPStatusError:
            return None
        except Exception:
            return None

def _parse_json_field(obj: Dict, key: str, default: Any = None) -> Any:
    """Parse a field that may be a JSON string or already a list."""
    val = obj.get(key, default)
    if val is None:
        return default
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def extract_outcomes_from_event(event: Dict) -> List[Dict]:
    """Extract outcomes with probabilities from Gamma event data.
    Gamma API returns outcomes/outcomePrices/clobTokenIds as JSON strings per market.
    """
    all_outcomes: List[Dict] = []
    markets = event.get("markets", [])
    if not markets:
        markets = [event] if (event.get("outcomes") or event.get("clobTokenIds")) else []

    for market in markets:
        # Gamma format: outcomes = "[\"Yes\", \"No\"]", outcomePrices = "[\"0.5\", \"0.5\"]", clobTokenIds = "[\"id1\", \"id2\"]"
        names = _parse_json_field(market, "outcomes", [])
        prices = _parse_json_field(market, "outcomePrices", [])
        token_ids = _parse_json_field(market, "clobTokenIds", [])

        if names and (prices or token_ids):
            n = len(names)
            for i in range(n):
                price_str = prices[i] if i < len(prices) else "0.5"
                try:
                    price = float(price_str)
                except (TypeError, ValueError):
                    price = 0.5
                token_id = token_ids[i] if i < len(token_ids) else None
                all_outcomes.append({
                    "id": token_id,
                    "outcome_id": token_id,
                    "name": names[i] if i < len(names) else f"Outcome {i}",
                    "title": names[i] if i < len(names) else f"Outcome {i}",
                    "price": price,
                    "raw_price": price,
                })
            continue

        # Legacy format: outcomes = list of { id, name, price }
        market_outcomes = market.get("outcomes", [])
        if isinstance(market_outcomes, list) and market_outcomes and isinstance(market_outcomes[0], dict):
            for outcome in market_outcomes:
                price = float(outcome.get("price", 0) or 0)
                all_outcomes.append({
                    "id": outcome.get("id") or outcome.get("outcome_id"),
                    "name": outcome.get("title") or outcome.get("name"),
                    "price": price,
                    "raw_price": price,
                })

    total_price = sum(o["price"] for o in all_outcomes)
    if total_price > 0:
        for o in all_outcomes:
            o["prob"] = o["price"] / total_price
    else:
        equal_prob = 1.0 / len(all_outcomes) if all_outcomes else 0
        for o in all_outcomes:
            o["prob"] = equal_prob
    return all_outcomes

def calculate_probabilities_from_prices(outcomes: List[Dict]) -> List[Dict]:
    """Calculate implied probabilities from outcome prices."""
    # Normalize probabilities if they don't sum to 1
    total_prob = sum(outcome.get("prob", 0) for outcome in outcomes)
    
    if total_prob > 0:
        for outcome in outcomes:
            outcome["prob"] = outcome.get("prob", 0) / total_prob
    else:
        # Equal distribution if no prices
        equal_prob = 1.0 / len(outcomes) if outcomes else 0
        for outcome in outcomes:
            outcome["prob"] = equal_prob
    
    return outcomes
