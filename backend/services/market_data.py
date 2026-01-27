import httpx
from typing import List, Dict, Optional
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
            "order": "volume",
            "ascending": "false"
        }
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

async def fetch_market_details(market_slug_or_id: str) -> Optional[Dict]:
    """Fetch detailed market information."""
    async with httpx.AsyncClient() as client:
        # Try by slug first
        url = f"{GAMMA_API_BASE}/events/{market_slug_or_id}"
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            # If not found, try alternative endpoints
            return None

def extract_outcomes_from_event(event: Dict) -> List[Dict]:
    """Extract outcomes with probabilities from event data."""
    outcomes = []
    
    # Event might have markets array
    markets = event.get("markets", [])
    if not markets:
        # Try direct market data
        markets = [event] if event.get("outcomes") else []
    
    for market in markets:
        market_outcomes = market.get("outcomes", [])
        for outcome in market_outcomes:
            price = outcome.get("price", 0)
            prob = float(price) if price else 0.0
            
            outcomes.append({
                "id": outcome.get("id") or outcome.get("outcome_id"),
                "name": outcome.get("title") or outcome.get("name"),
                "price": price,
                "prob": prob
            })
    
    return outcomes

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
