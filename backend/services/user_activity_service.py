"""
User activity service: fetch and store Polymarket user activity from data-api.polymarket.com.
"""
import httpx
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import TrackedUser, UserActivity, TrackedMarket

DATA_API_BASE = "https://data-api.polymarket.com"


async def fetch_user_activity_from_api(
    user_address: str,
    limit: int = 25,
    offset: int = 0
) -> List[Dict]:
    """
    Fetch user activity from Polymarket data API.
    
    Args:
        user_address: Ethereum address (proxy wallet)
        limit: Max number of activities to return
        offset: Pagination offset
    
    Returns:
        List of activity dicts (TRADE, REDEEM, etc.)
    """
    async with httpx.AsyncClient() as client:
        url = f"{DATA_API_BASE}/activity"
        params = {
            "user": user_address,
            "limit": limit,
            "offset": offset
        }
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error fetching user activity for {user_address}: {e}")
            return []


def _parse_activity_item(item: Dict, user_address: str) -> Optional[Dict]:
    """Convert API activity item to DB-ready dict."""
    tx_hash = item.get("transactionHash")
    if not tx_hash:
        return None
    ts = item.get("timestamp")
    if ts is None:
        return None
    if isinstance(ts, int):
        timestamp = datetime.utcfromtimestamp(ts)
    else:
        try:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    
    return {
        "user_address": user_address,
        "activity_type": item.get("type", "TRADE"),
        "market_slug": item.get("slug") or item.get("eventSlug") or "",
        "market_title": item.get("title") or "",
        "outcome": item.get("outcome") or None,
        "side": item.get("side") or None,
        "size": float(item.get("size") or 0),
        "usdc_size": float(item.get("usdcSize") or 0),
        "price": float(item.get("price")) if item.get("price") is not None else None,
        "timestamp": timestamp,
        "transaction_hash": tx_hash,
    }


def store_activities(db: Session, user_address: str, activities: List[Dict]) -> int:
    """
    Store activities in DB, skipping duplicates by transaction_hash.
    Resolves market_id from TrackedMarket when market_slug matches.
    Returns count of newly inserted activities.
    """
    count = 0
    for item in activities:
        parsed = _parse_activity_item(item, user_address)
        if not parsed:
            continue
        existing = db.query(UserActivity).filter(
            UserActivity.transaction_hash == parsed["transaction_hash"]
        ).first()
        if existing:
            continue
        market_id = None
        if parsed["market_slug"]:
            m = db.query(TrackedMarket).filter(
                TrackedMarket.market_slug == parsed["market_slug"]
            ).first()
            if not m and item.get("eventSlug"):
                m = db.query(TrackedMarket).filter(
                    TrackedMarket.market_slug == item.get("eventSlug", "")
                ).first()
            if m:
                market_id = m.id
        db_activity = UserActivity(
            user_address=parsed["user_address"],
            activity_type=parsed["activity_type"],
            market_id=market_id,
            market_slug=parsed["market_slug"],
            market_title=parsed["market_title"],
            outcome=parsed["outcome"],
            side=parsed["side"],
            size=parsed["size"],
            usdc_size=parsed["usdc_size"],
            price=parsed["price"],
            timestamp=parsed["timestamp"],
            transaction_hash=parsed["transaction_hash"],
        )
        db.add(db_activity)
        count += 1
    db.commit()
    return count


async def fetch_and_store_user_activity(
    db: Session,
    user_address: str,
    limit: int = 25,
    offset: int = 0
) -> int:
    """
    Fetch user activity from API and store new items in DB.
    Returns number of newly stored activities.
    """
    activities = await fetch_user_activity_from_api(user_address, limit=limit, offset=offset)
    return store_activities(db, user_address, activities)


def get_user_activity(
    db: Session,
    user_address: str,
    limit: int = 50,
    offset: int = 0,
    market_id: Optional[int] = None
) -> List[UserActivity]:
    """Get stored activities for a user, optionally filtered by market_id."""
    q = db.query(UserActivity).filter(UserActivity.user_address == user_address)
    if market_id is not None:
        q = q.filter(UserActivity.market_id == market_id)
    return q.order_by(desc(UserActivity.timestamp)).offset(offset).limit(limit).all()


def get_user_summary(db: Session, user_address: str) -> Dict:
    """
    Aggregate stats for a user: total volume, trade count, markets count,
    top markets by volume, win rate (REDEEM count vs TRADE count as proxy).
    """
    activities = (
        db.query(UserActivity)
        .filter(UserActivity.user_address == user_address)
        .all()
    )
    total_volume = sum(a.usdc_size for a in activities)
    trade_count = sum(1 for a in activities if a.activity_type == "TRADE")
    redeem_count = sum(1 for a in activities if a.activity_type == "REDEEM")
    markets_slug = set(a.market_slug for a in activities if a.market_slug)
    markets_count = len(markets_slug)
    
    # Top markets by volume (sum usdc_size per market_slug)
    vol_sum = func.sum(UserActivity.usdc_size)
    volume_by_market = (
        db.query(UserActivity.market_slug, UserActivity.market_title, vol_sum)
        .filter(UserActivity.user_address == user_address)
        .group_by(UserActivity.market_slug, UserActivity.market_title)
        .order_by(desc(vol_sum))
        .limit(5)
        .all()
    )
    top_markets = [
        {"market_slug": m, "market_title": t or m, "volume": float(v or 0)}
        for m, t, v in volume_by_market
    ]
    
    # Win rate: redeems / (trades + redeems) as simple proxy
    settled = trade_count + redeem_count
    win_rate = (redeem_count / settled * 100) if settled else None
    
    last_activity = (
        db.query(UserActivity)
        .filter(UserActivity.user_address == user_address)
        .order_by(desc(UserActivity.timestamp))
        .first()
    )
    
    return {
        "user_address": user_address,
        "total_volume_usdc": total_volume,
        "trade_count": trade_count,
        "redeem_count": redeem_count,
        "markets_count": markets_count,
        "top_markets": top_markets,
        "win_rate_percent": round(win_rate, 2) if win_rate is not None else None,
        "last_activity_at": last_activity.timestamp.isoformat() if last_activity else None,
    }


def get_activity_feed(
    db: Session,
    market_ids: Optional[List[int]] = None,
    limit: int = 50,
) -> List[UserActivity]:
    """Get recent activity from tracked users, optionally filtered by market_ids."""
    tracked_addresses = [u.address for u in db.query(TrackedUser).all()]
    if not tracked_addresses:
        return []
    query = (
        db.query(UserActivity)
        .filter(UserActivity.user_address.in_(tracked_addresses))
        .order_by(desc(UserActivity.timestamp))
        .limit(limit)
    )
    if market_ids:
        query = query.filter(UserActivity.market_id.in_(market_ids))
    return query.all()


def get_user_markets(db: Session, user_address: str) -> List[Dict]:
    """List markets where the user has activity, with volume per market."""
    vol_sum = func.sum(UserActivity.usdc_size).label("volume")
    rows = (
        db.query(
            UserActivity.market_slug,
            UserActivity.market_title,
            UserActivity.market_id,
            vol_sum,
            func.count(UserActivity.id).label("activity_count"),
        )
        .filter(UserActivity.user_address == user_address)
        .group_by(UserActivity.market_slug, UserActivity.market_title, UserActivity.market_id)
        .order_by(desc(vol_sum))
        .all()
    )
    return [
        {
            "market_slug": r.market_slug,
            "market_title": r.market_title or r.market_slug,
            "market_id": r.market_id,
            "volume": float(r.volume or 0),
            "activity_count": r.activity_count,
        }
        for r in rows
    ]
