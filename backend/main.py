from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database import get_db, init_db, TrackedMarket, Alert, Snapshot, Outcome
from services.trending_categories import get_trending_categories, refresh_trending_categories
from services.market_data import fetch_events_by_tag, fetch_market_details
from services.snapshot_service import refresh_all_tracked_markets
from services.alert_detection import detect_shifts, create_alerts
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
    return market

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

@app.get("/")
async def root():
    return {"message": "Polymarket Trending Tracker API"}
