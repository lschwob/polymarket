from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database import get_db, init_db, TrackedMarket, Alert, Snapshot, Outcome, Trade, PriceSnapshot, OrderBookSnapshot
from services.trending_categories import get_trending_categories, refresh_trending_categories
from services.market_data import fetch_events_by_tag, fetch_market_details, extract_outcomes_from_event, calculate_probabilities_from_prices
from services.snapshot_service import refresh_all_tracked_markets
from services.alert_detection import detect_shifts, create_alerts
from services.clob_api import fetch_market_trades, fetch_order_book, fetch_price_history, fetch_market_trades_by_market
from services.the_graph_service import fetch_market_transactions, fetch_recent_market_activity
from services.websocket_service import websocket_endpoint, manager
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

@app.get("/api/markets/{market_id}/snapshots", response_model=List[SnapshotResponse])
async def get_market_snapshots(
    market_id: int,
    range_hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get snapshots for a market."""
    cutoff = datetime.utcnow() - timedelta(hours=range_hours)
    
    snapshots = (
        db.query(Snapshot)
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
            prob=s.prob,
            volume=s.volume,
            liquidity=s.liquidity,
            ts=s.ts.isoformat()
        )
        for s in snapshots
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
    
    # Get market details to find outcome token IDs
    market_data = await fetch_market_details(market.market_slug)
    if not market_data:
        raise HTTPException(status_code=404, detail="Market data not found")
    
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
    """Get price history for a market."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Get market details to find outcome token IDs
    market_data = await fetch_market_details(market.market_slug)
    if not market_data:
        raise HTTPException(status_code=404, detail="Market data not found")
    
    outcomes = extract_outcomes_from_event(market_data)
    start_time = datetime.utcnow() - timedelta(hours=range_hours)
    end_time = datetime.utcnow()
    
    price_history = []
    
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
    
    # Sort by timestamp
    price_history.sort(key=lambda x: x.get("timestamp", 0))
    
    return {"data": price_history}

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
    """Get comprehensive market details including outcomes, current prices, and stats."""
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Get market data from Gamma API
    market_data = await fetch_market_details(market.market_slug)
    if not market_data:
        raise HTTPException(status_code=404, detail="Market data not found")
    
    # Extract outcomes
    outcomes = extract_outcomes_from_event(market_data)
    
    # Get recent trades (last 10)
    recent_trades = await fetch_market_trades_by_market(market.market_slug, limit=10)
    
    # Get order books for all outcomes
    order_books = []
    for outcome in outcomes:
        token_id = outcome.get("id")
        if token_id:
            order_book = await fetch_order_book(token_id)
            if order_book:
                order_book["outcome_name"] = outcome.get("name")
                order_books.append(order_book)
    
    # Normalize outcomes probabilities
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
        "volume_24h": market_data.get("volume", 0),
        "liquidity": market_data.get("liquidity", 0),
        "description": market_data.get("description") or market_data.get("question") or market_data.get("text"),
        "image": market_data.get("image"),
        "end_date": market_data.get("end_date") or market_data.get("endDate"),
        "resolution_source": market_data.get("resolution_source") or market_data.get("resolutionSource")
    }

@app.get("/")
async def root():
    return {"message": "Polymarket Trending Tracker API"}
