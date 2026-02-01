from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database import get_db, init_db, TrackedMarket, Alert, Snapshot, Outcome, Trade, PriceSnapshot, OrderBookSnapshot, TrackedUser, UserActivity
from services.trending_categories import get_trending_categories, refresh_trending_categories
from services.market_data import fetch_events_by_tag, fetch_market_details, extract_outcomes_from_event, calculate_probabilities_from_prices
from services.snapshot_service import refresh_all_tracked_markets
from services.alert_detection import detect_shifts, create_alerts
from services.clob_api import fetch_market_trades, fetch_order_book, fetch_price_history, fetch_market_trades_by_market
from services.the_graph_service import fetch_market_transactions, fetch_recent_market_activity
from services.websocket_service import websocket_endpoint, manager
from services.user_activity_service import (
    fetch_and_store_user_activity,
    get_user_activity as get_user_activity_service,
    get_user_summary,
    get_user_markets,
    get_activity_feed,
)
from scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Polymarket Trending Tracker API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()
    start_scheduler()

@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()

# Pydantic models
class TrendingCategory(BaseModel):
    slug: str
    label: str
    score: float
    computed_at: Optional[str] = None

class EventResponse(BaseModel):
    id: str
    slug: str
    title: str
    volume: Optional[float] = None
    tags: List[dict]

class TrackedMarketCreate(BaseModel):
    market_slug: str
    market_id: Optional[str] = None
    title: str
    tag_slug: Optional[str] = None

class TrackedMarketResponse(BaseModel):
    id: int
    market_slug: str
    market_id: Optional[str]
    title: str
    tag_slug: Optional[str]
    created_at: str

class SnapshotResponse(BaseModel):
    id: int
    market_id: int
    outcome_id: int
    polymarket_outcome_id: Optional[str] = None  # Polymarket token ID for frontend matching
    prob: float
    volume: Optional[float]
    liquidity: Optional[float]
    ts: str

class AlertResponse(BaseModel):
    id: int
    market_id: int
    outcome_id: Optional[int]
    prev_prob: float
    new_prob: float
    delta: float
    delta_percent: float
    volume: Optional[float] = None
    volume_impact: Optional[float] = None
    ts: str
    status: str
    market_title: Optional[str] = None

class TradeResponse(BaseModel):
    id: Optional[int] = None
    market_id: int
    outcome_id: Optional[int] = None
    token_id: Optional[str] = None
    outcome_name: Optional[str] = None
    user_address: Optional[str] = None
    amount: float
    price: float
    side: str
    timestamp: str
    trade_id: Optional[str] = None

class OrderBookResponse(BaseModel):
    token_id: str
    outcome_name: Optional[str] = None
    bids: List[dict]
    asks: List[dict]
    timestamp: str

class PriceHistoryResponse(BaseModel):
    timestamp: float
    price: float
    volume: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None

class VolumeChartResponse(BaseModel):
    outcome_id: str
    outcome_name: str
    volume: float
    timestamp: str

class TrackedUserCreate(BaseModel):
    address: str
    name: Optional[str] = None

class TrackedUserResponse(BaseModel):
    address: str
    name: Optional[str] = None
    pseudonym: Optional[str] = None
    profile_image: Optional[str] = None
    created_at: str

class UserActivityResponse(BaseModel):
    id: int
    user_address: str
    activity_type: str
    market_id: Optional[int] = None
    market_slug: str
    market_title: Optional[str] = None
    outcome: Optional[str] = None
    side: Optional[str] = None
    size: float
    usdc_size: float
    price: Optional[float] = None
    timestamp: str
    transaction_hash: str

# API Endpoints

@app.get("/api/trending-categories", response_model=List[TrendingCategory])
async def get_trending_categories_endpoint(db: Session = Depends(get_db)):
    """Get trending categories (cached)."""
    categories = get_trending_categories(db)
    if not categories:
        # Refresh if empty
        await refresh_trending_categories(db)
        categories = get_trending_categories(db)
    return categories

@app.post("/api/trending-categories/refresh")
async def refresh_trending_categories_endpoint(db: Session = Depends(get_db)):
    """Manually refresh trending categories."""
    categories = await refresh_trending_categories(db)
    return {"message": "Categories refreshed", "count": len(categories)}

@app.get("/api/events")
async def get_events(tag_slug: Optional[str] = None, limit: int = 50):
    """Get events, optionally filtered by tag."""
    events = await fetch_events_by_tag(tag_slug, limit=limit) if tag_slug else []
    return {"data": events}

@app.get("/api/market/{market_slug}")
async def get_market(market_slug: str):
    """Get market details."""
    market = await fetch_market_details(market_slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Extract and normalize outcomes
    outcomes = extract_outcomes_from_event(market)
    outcomes = calculate_probabilities_from_prices(outcomes)
    
    return {
        **market,
        "outcomes": outcomes,
        "description": market.get("description") or market.get("question") or market.get("text")
    }

@app.post("/api/tracked-markets", response_model=TrackedMarketResponse)
async def create_tracked_market(
    market: TrackedMarketCreate,
    db: Session = Depends(get_db)
):
    """Add a market to tracking."""
    # Check if already tracked
    existing = db.query(TrackedMarket).filter(
        TrackedMarket.market_slug == market.market_slug
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Market already tracked")
    
    db_market = TrackedMarket(
        market_slug=market.market_slug,
        market_id=market.market_id,
        title=market.title,
        tag_slug=market.tag_slug
    )
    db.add(db_market)
    db.commit()
    db.refresh(db_market)
    
    return TrackedMarketResponse(
        id=db_market.id,
        market_slug=db_market.market_slug,
        market_id=db_market.market_id,
        title=db_market.title,
        tag_slug=db_market.tag_slug,
        created_at=db_market.created_at.isoformat()
    )

@app.get("/api/tracked-markets", response_model=List[TrackedMarketResponse])
async def get_tracked_markets(db: Session = Depends(get_db)):
    """Get all tracked markets."""
    markets = db.query(TrackedMarket).order_by(TrackedMarket.created_at.desc()).all()
    return [
        TrackedMarketResponse(
            id=m.id,
            market_slug=m.market_slug,
            market_id=m.market_id,
            title=m.title,
            tag_slug=m.tag_slug,
            created_at=m.created_at.isoformat()
        )
        for m in markets
    ]

@app.delete("/api/tracked-markets/{market_id}")
async def delete_tracked_market(market_id: int, db: Session = Depends(get_db)):
    """Remove a market from tracking."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    db.delete(market)
    db.commit()
    return {"message": "Market removed from tracking"}

# Tracked users (Polymarket user activity tracking)
@app.post("/api/tracked-users", response_model=TrackedUserResponse)
async def create_tracked_user(
    user: TrackedUserCreate,
    db: Session = Depends(get_db)
):
    """Add a user to track (by Ethereum address)."""
    addr = user.address.strip().lower()
    if not addr:
        raise HTTPException(status_code=400, detail="Address is required")
    existing = db.query(TrackedUser).filter(TrackedUser.address == addr).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already tracked")
    db_user = TrackedUser(address=addr, name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return TrackedUserResponse(
        address=db_user.address,
        name=db_user.name,
        pseudonym=db_user.pseudonym,
        profile_image=db_user.profile_image,
        created_at=db_user.created_at.isoformat()
    )

@app.get("/api/tracked-users", response_model=List[TrackedUserResponse])
async def get_tracked_users(db: Session = Depends(get_db)):
    """Get all tracked users."""
    users = db.query(TrackedUser).order_by(TrackedUser.created_at.desc()).all()
    return [
        TrackedUserResponse(
            address=u.address,
            name=u.name,
            pseudonym=u.pseudonym,
            profile_image=u.profile_image,
            created_at=u.created_at.isoformat()
        )
        for u in users
    ]

@app.delete("/api/tracked-users/{address}")
async def delete_tracked_user(address: str, db: Session = Depends(get_db)):
    """Remove a user from tracking."""
    addr = address.strip().lower()
    user = db.query(TrackedUser).filter(TrackedUser.address == addr).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User removed from tracking"}

@app.get("/api/users/{address}/activity", response_model=List[UserActivityResponse])
async def get_user_activity(
    address: str,
    limit: int = 50,
    offset: int = 0,
    market_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get activity for a user (from stored data)."""
    addr = address.strip().lower()
    activities = get_user_activity_service(db, addr, limit=limit, offset=offset, market_id=market_id)
    return [
        UserActivityResponse(
            id=a.id,
            user_address=a.user_address,
            activity_type=a.activity_type,
            market_id=a.market_id,
            market_slug=a.market_slug or "",
            market_title=a.market_title,
            outcome=a.outcome,
            side=a.side,
            size=a.size,
            usdc_size=a.usdc_size,
            price=a.price,
            timestamp=a.timestamp.isoformat(),
            transaction_hash=a.transaction_hash
        )
        for a in activities
    ]

@app.get("/api/users/{address}/summary")
async def get_user_summary_endpoint(address: str, db: Session = Depends(get_db)):
    """Get aggregated stats for a user."""
    addr = address.strip().lower()
    return get_user_summary(db, addr)

@app.get("/api/users/{address}/markets")
async def get_user_markets_endpoint(address: str, db: Session = Depends(get_db)):
    """Get markets where the user has activity."""
    addr = address.strip().lower()
    return get_user_markets(db, addr)

@app.post("/api/users/{address}/refresh")
async def refresh_user_activity(address: str, db: Session = Depends(get_db)):
    """Manually fetch and store latest activity for a user."""
    addr = address.strip().lower()
    user = db.query(TrackedUser).filter(TrackedUser.address == addr).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not tracked")
    count = await fetch_and_store_user_activity(db, addr, limit=25, offset=0)
    return {"message": "Activity refreshed", "new_activities": count}

@app.get("/api/activity/feed", response_model=List[UserActivityResponse])
async def get_activity_feed_endpoint(
    market_ids: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get recent activity from tracked users, optionally filtered by market IDs (comma-separated)."""
    ids = None
    if market_ids:
        try:
            ids = [int(x.strip()) for x in market_ids.split(",") if x.strip()]
        except ValueError:
            pass
    activities = get_activity_feed(db, market_ids=ids, limit=limit)
    return [
        UserActivityResponse(
            id=a.id,
            user_address=a.user_address,
            activity_type=a.activity_type,
            market_id=a.market_id,
            market_slug=a.market_slug or "",
            market_title=a.market_title,
            outcome=a.outcome,
            side=a.side,
            size=a.size,
            usdc_size=a.usdc_size,
            price=a.price,
            timestamp=a.timestamp.isoformat(),
            transaction_hash=a.transaction_hash
        )
        for a in activities
    ]

@app.get("/api/markets/{market_id}/snapshots", response_model=List[SnapshotResponse])
async def get_market_snapshots(
    market_id: int,
    range_hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get snapshots for a market (includes polymarket_outcome_id for chart matching)."""
    cutoff = datetime.utcnow() - timedelta(hours=range_hours)
    
    snapshots = (
        db.query(Snapshot, Outcome.outcome_id)
        .join(Outcome, Snapshot.outcome_id == Outcome.id)
        .filter(Snapshot.market_id == market_id)
        .filter(Snapshot.ts >= cutoff)
        .order_by(Snapshot.ts.asc())
        .all()
    )
    
    return [
        SnapshotResponse(
            id=s.id,
            market_id=s.market_id,
            outcome_id=s.outcome_id,
            polymarket_outcome_id=outcome_id_str,
            prob=s.prob,
            volume=s.volume,
            liquidity=s.liquidity,
            ts=s.ts.isoformat()
        )
        for s, outcome_id_str in snapshots
    ]

@app.get("/api/alerts", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = None,
    include_all: bool = False,
    db: Session = Depends(get_db)
):
    """Get alerts, optionally filtered by status. Set include_all=true to get all alerts including acknowledged."""
    query = db.query(Alert)
    
    if status:
        query = query.filter(Alert.status == status)
    elif not include_all:
        query = query.filter(Alert.status == "active")
    
    alerts = query.order_by(Alert.ts.desc()).limit(500).all()
    
    # Get market titles
    market_ids = {a.market_id for a in alerts}
    markets = {
        m.id: m.title
        for m in db.query(TrackedMarket).filter(TrackedMarket.id.in_(market_ids)).all()
    }
    
    return [
        AlertResponse(
            id=a.id,
            market_id=a.market_id,
            outcome_id=a.outcome_id,
            prev_prob=a.prev_prob,
            new_prob=a.new_prob,
            delta=a.delta,
            delta_percent=a.delta_percent,
            volume=a.volume,
            volume_impact=a.volume_impact,
            ts=a.ts.isoformat(),
            status=a.status,
            market_title=markets.get(a.market_id)
        )
        for a in alerts
    ]

@app.get("/api/markets/{market_id}/shifts", response_model=List[AlertResponse])
async def get_market_shifts(
    market_id: int,
    db: Session = Depends(get_db)
):
    """Get all shifts (alerts) for a specific market, ordered by volume impact."""
    alerts = (
        db.query(Alert)
        .filter(Alert.market_id == market_id)
        .order_by(Alert.volume_impact.desc().nulls_last(), Alert.ts.desc())
        .all()
    )
    
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    market_title = market.title if market else None
    
    return [
        AlertResponse(
            id=a.id,
            market_id=a.market_id,
            outcome_id=a.outcome_id,
            prev_prob=a.prev_prob,
            new_prob=a.new_prob,
            delta=a.delta,
            delta_percent=a.delta_percent,
            volume=a.volume,
            volume_impact=a.volume_impact,
            ts=a.ts.isoformat(),
            status=a.status,
            market_title=market_title
        )
        for a in alerts
    ]

@app.post("/api/alerts/ack/{alert_id}")
async def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = "acknowledged"
    db.commit()
    return {"message": "Alert acknowledged"}

@app.post("/api/snapshots/refresh")
async def refresh_snapshots(db: Session = Depends(get_db)):
    """Manually trigger snapshot refresh for all tracked markets."""
    await refresh_all_tracked_markets(db)
    
    # Detect shifts and create alerts
    markets = db.query(TrackedMarket).all()
    for market in markets:
        shifts = detect_shifts(db, market.id)
        if shifts:
            create_alerts(db, shifts)
    
    return {"message": "Snapshots refreshed"}

@app.get("/api/markets/{market_id}/trades")
async def get_market_trades(
    market_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get trade history for a market."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Fetch trades from CLOB API
    trades = await fetch_market_trades_by_market(market.market_slug, limit=limit, offset=offset)
    
    # Also get from database if available
    db_trades = (
        db.query(Trade)
        .filter(Trade.market_id == market_id)
        .order_by(Trade.timestamp.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    
    # Combine and deduplicate
    trade_dict = {}
    for trade in trades:
        trade_id = trade.get("id") or trade.get("trade_id")
        if trade_id:
            trade_dict[trade_id] = trade
    
    for db_trade in db_trades:
        if db_trade.trade_id and db_trade.trade_id not in trade_dict:
            trade_dict[db_trade.trade_id] = {
                "id": db_trade.id,
                "market_id": db_trade.market_id,
                "outcome_id": db_trade.outcome_id,
                "token_id": db_trade.token_id,
                "user_address": db_trade.user_address,
                "amount": db_trade.amount,
                "price": db_trade.price,
                "side": db_trade.side,
                "timestamp": db_trade.timestamp.isoformat(),
                "trade_id": db_trade.trade_id
            }
    
    return list(trade_dict.values())[:limit]

@app.get("/api/markets/{market_id}/order-book")
async def get_market_order_book(
    market_id: int,
    db: Session = Depends(get_db)
):
    """Get current order book for a market."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    market_data = await fetch_market_details(market.market_slug)
    if not market_data:
        return {"order_books": []}
    
    outcomes = extract_outcomes_from_event(market_data)
    order_books = []
    
    for outcome in outcomes:
        token_id = outcome.get("id")
        if token_id:
            order_book = await fetch_order_book(token_id)
            if order_book:
                order_book["outcome_name"] = outcome.get("name")
                order_books.append(order_book)
    
    return {"order_books": order_books}

@app.get("/api/markets/{market_id}/price-history")
async def get_market_price_history(
    market_id: int,
    interval: str = "1m",
    range_hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get price history for a market (Gamma API or DB fallback)."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    market_data = await fetch_market_details(market.market_slug)
    price_history = []
    
    if market_data:
        outcomes = extract_outcomes_from_event(market_data)
        start_time = datetime.utcnow() - timedelta(hours=range_hours)
        end_time = datetime.utcnow()
        for outcome in outcomes:
            token_id = outcome.get("id")
            if token_id:
                history = await fetch_price_history(
                    token_id,
                    interval=interval,
                    start_time=start_time,
                    end_time=end_time
                )
                for point in history:
                    point["outcome_id"] = token_id
                    point["outcome_name"] = outcome.get("name")
                price_history.extend(history)
    else:
        cutoff = datetime.utcnow() - timedelta(hours=range_hours)
        snapshots = (
            db.query(PriceSnapshot, Outcome.outcome_id, Outcome.name)
            .join(Outcome, PriceSnapshot.outcome_id == Outcome.id)
            .filter(PriceSnapshot.market_id == market_id)
            .filter(PriceSnapshot.timestamp >= cutoff)
            .order_by(PriceSnapshot.timestamp.asc())
            .all()
        )
        for s, outcome_id_str, outcome_name in snapshots:
            price_history.append({
                "timestamp": int(s.timestamp.timestamp()) if s.timestamp else 0,
                "close": s.close_price or s.price,
                "open": s.open_price,
                "high": s.high_price,
                "low": s.low_price,
                "price": s.close_price or s.price,
                "outcome_id": outcome_id_str,
                "outcome_name": outcome_name,
            })
    
    price_history.sort(key=lambda x: x.get("timestamp", 0))
    return {"data": price_history}

@app.get("/api/markets/{market_id}/outcomes/{outcome_token_id}/price-history")
async def get_outcome_price_history(
    market_id: int,
    outcome_token_id: str,
    range_hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get price history for a single outcome (by Polymarket token ID)."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Resolve outcome_token_id to internal Outcome.id
    outcome = db.query(Outcome).filter(
        Outcome.market_id == market_id,
        Outcome.outcome_id == outcome_token_id
    ).first()
    
    if outcome:
        cutoff = datetime.utcnow() - timedelta(hours=range_hours)
        snapshots = (
            db.query(PriceSnapshot)
            .filter(
                PriceSnapshot.market_id == market_id,
                PriceSnapshot.outcome_id == outcome.id,
                PriceSnapshot.timestamp >= cutoff
            )
            .order_by(PriceSnapshot.timestamp.asc())
            .all()
        )
        data = [
            {
                "timestamp": int(s.timestamp.timestamp()) if s.timestamp else 0,
                "price": s.close_price or s.price,
                "open": s.open_price,
                "high": s.high_price,
                "low": s.low_price,
                "close": s.close_price or s.price,
            }
            for s in snapshots
        ]
    else:
        # Fallback to CLOB API
        start_time = datetime.utcnow() - timedelta(hours=range_hours)
        end_time = datetime.utcnow()
        history = await fetch_price_history(
            outcome_token_id,
            interval="1m",
            start_time=start_time,
            end_time=end_time
        )
        data = [
            {
                "timestamp": p.get("timestamp", 0),
                "price": p.get("close") or p.get("price", 0),
                "open": p.get("open"),
                "high": p.get("high"),
                "low": p.get("low"),
                "close": p.get("close") or p.get("price", 0),
            }
            for p in history
        ]
    
    return {"data": data}

@app.get("/api/markets/{market_id}/volume-chart")
async def get_market_volume_chart(
    market_id: int,
    range_hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get volume chart data by outcome for a market."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Get snapshots with volume data
    cutoff = datetime.utcnow() - timedelta(hours=range_hours)
    
    snapshots = (
        db.query(Snapshot)
        .join(Outcome)
        .filter(Snapshot.market_id == market_id)
        .filter(Snapshot.ts >= cutoff)
        .all()
    )
    
    # Aggregate volume by outcome
    volume_by_outcome = {}
    for snapshot in snapshots:
        outcome_id = snapshot.outcome_id
        if outcome_id not in volume_by_outcome:
            outcome = db.query(Outcome).filter(Outcome.id == outcome_id).first()
            volume_by_outcome[outcome_id] = {
                "outcome_id": str(outcome.outcome_id) if outcome else str(outcome_id),
                "outcome_name": outcome.name if outcome else f"Outcome {outcome_id}",
                "volume": 0
            }
        
        if snapshot.volume:
            volume_by_outcome[outcome_id]["volume"] += snapshot.volume
    
    return {"data": list(volume_by_outcome.values())}

@app.websocket("/ws/market/{market_id}")
async def websocket_market_updates(websocket: WebSocket, market_id: int):
    """WebSocket endpoint for real-time market updates."""
    await websocket_endpoint(websocket, market_id)

@app.get("/api/markets/{market_id}/detail")
async def get_market_detail(
    market_id: int,
    db: Session = Depends(get_db)
):
    """Get comprehensive market details (Gamma API or DB fallback)."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    market_data = await fetch_market_details(market.market_slug)
    if market_data:
        outcomes = extract_outcomes_from_event(market_data)
        recent_trades = await fetch_market_trades_by_market(market.market_slug, limit=10)
        order_books = []
        for outcome in outcomes:
            token_id = outcome.get("id")
            if token_id:
                order_book = await fetch_order_book(token_id)
                if order_book:
                    order_book["outcome_name"] = outcome.get("name")
                    order_books.append(order_book)
        outcomes = calculate_probabilities_from_prices(outcomes)
        return {
            "market": {
                "id": market.id,
                "slug": market.market_slug,
                "title": market.title,
                "tag_slug": market.tag_slug,
                "created_at": market.created_at.isoformat()
            },
            "outcomes": outcomes,
            "recent_trades": recent_trades[:10],
            "order_books": order_books,
            "volume_24h": market_data.get("volume24hr") or market_data.get("volume", 0),
            "liquidity": market_data.get("liquidity") or market_data.get("liquidityClob", 0),
            "description": market_data.get("description") or market_data.get("question") or market_data.get("text"),
            "image": market_data.get("image"),
            "end_date": market_data.get("end_date") or market_data.get("endDate"),
            "resolution_source": market_data.get("resolution_source") or market_data.get("resolutionSource")
        }
    outcomes_db = db.query(Outcome).filter(Outcome.market_id == market_id).all()
    outcomes = []
    for o in outcomes_db:
        last_snap = (
            db.query(Snapshot)
            .filter(Snapshot.market_id == market_id, Snapshot.outcome_id == o.id)
            .order_by(Snapshot.ts.desc())
            .first()
        )
        prob = last_snap.prob if last_snap else 0.5
        outcomes.append({
            "id": o.outcome_id,
            "outcome_id": o.outcome_id,
            "name": o.name,
            "title": o.name,
            "price": prob,
            "prob": prob,
        })
    db_trades = (
        db.query(Trade)
        .filter(Trade.market_id == market_id)
        .order_by(Trade.timestamp.desc())
        .limit(10)
        .all()
    )
    recent_trades = [
        {
            "id": t.id,
            "market_id": t.market_id,
            "outcome_id": t.token_id,
            "amount": t.amount,
            "price": t.price,
            "side": t.side,
            "timestamp": t.timestamp.isoformat(),
            "trade_id": t.trade_id,
        }
        for t in db_trades
    ]
    return {
        "market": {
            "id": market.id,
            "slug": market.market_slug,
            "title": market.title,
            "tag_slug": market.tag_slug,
            "created_at": market.created_at.isoformat()
        },
        "outcomes": outcomes,
        "recent_trades": recent_trades,
        "order_books": [],
        "volume_24h": 0,
        "liquidity": 0,
        "description": None,
        "image": None,
        "end_date": None,
        "resolution_source": None
    }

@app.get("/")
async def root():
    return {"message": "Polymarket Trending Tracker API"}
