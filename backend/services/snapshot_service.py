import httpx
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database import TrackedMarket, Snapshot, Outcome

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

async def fetch_market_data(market_slug: str) -> Optional[Dict]:
    """Fetch current market data from Gamma API."""
    async with httpx.AsyncClient() as client:
        url = f"{GAMMA_API_BASE}/events/{market_slug}"
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None

def extract_snapshot_data(market_data: Dict) -> List[Dict]:
    """Extract snapshot data (outcomes with probabilities) from market data."""
    snapshots = []
    
    # Market data might have markets array or direct outcomes
    markets = market_data.get("markets", [])
    if not markets and market_data.get("outcomes"):
        markets = [market_data]
    
    for market in markets:
        outcomes = market.get("outcomes", [])
        volume = market.get("volume") or market_data.get("volume", 0)
        liquidity = market.get("liquidity") or market_data.get("liquidity", 0)
        
        # Calculate total probability for normalization
        total_price = sum(float(outcome.get("price", 0) or 0) for outcome in outcomes)
        
        for outcome in outcomes:
            price = float(outcome.get("price", 0) or 0)
            prob = price / total_price if total_price > 0 else (1.0 / len(outcomes) if outcomes else 0)
            
            snapshots.append({
                "outcome_id": outcome.get("id") or outcome.get("outcome_id"),
                "outcome_name": outcome.get("title") or outcome.get("name"),
                "prob": prob,
                "volume": float(volume),
                "liquidity": float(liquidity) if liquidity else None
            })
    
    return snapshots

async def create_snapshot_for_market(db: Session, market_id: int):
    """Create snapshot for a tracked market."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        return
    
    # Fetch current market data
    market_data = await fetch_market_data(market.market_slug)
    if not market_data:
        return
    
    # Extract snapshot data
    snapshot_data_list = extract_snapshot_data(market_data)
    
    # Create or update outcomes
    outcome_map = {}
    for outcome in market.outcomes:
        outcome_map[outcome.outcome_id] = outcome
    
    for snap_data in snapshot_data_list:
        outcome_id_str = str(snap_data["outcome_id"])
        
        # Get or create outcome
        if outcome_id_str not in outcome_map:
            outcome = Outcome(
                market_id=market_id,
                outcome_id=outcome_id_str,
                name=snap_data["outcome_name"]
            )
            db.add(outcome)
            db.flush()
            outcome_map[outcome_id_str] = outcome
        else:
            outcome = outcome_map[outcome_id_str]
        
        # Create snapshot
        snapshot = Snapshot(
            market_id=market_id,
            outcome_id=outcome.id,
            prob=snap_data["prob"],
            volume=snap_data.get("volume"),
            liquidity=snap_data.get("liquidity"),
            ts=datetime.utcnow()
        )
        db.add(snapshot)
    
    db.commit()

async def refresh_all_tracked_markets(db: Session):
    """Refresh snapshots for all tracked markets."""
    markets = db.query(TrackedMarket).all()
    
    for market in markets:
        try:
            await create_snapshot_for_market(db, market.id)
        except Exception as e:
            print(f"Error creating snapshot for market {market.id}: {e}")
            continue
