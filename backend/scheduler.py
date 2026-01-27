from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import SessionLocal
from services.trending_categories import refresh_trending_categories
from services.snapshot_service import refresh_all_tracked_markets
from services.alert_detection import detect_shifts, create_alerts
from config import (
    TRENDING_REFRESH_INTERVAL_MINUTES,
    MARKETS_REFRESH_INTERVAL_MINUTES,
    TRENDING_CATEGORIES_TOP_K
)

scheduler = AsyncIOScheduler()

async def job_refresh_trending_categories():
    """Job to refresh trending categories."""
    db = SessionLocal()
    try:
        await refresh_trending_categories(db, top_k=TRENDING_CATEGORIES_TOP_K)
        print("Trending categories refreshed")
    except Exception as e:
        print(f"Error refreshing trending categories: {e}")
    finally:
        db.close()

async def job_refresh_tracked_markets():
    """Job to refresh snapshots and detect shifts every 5 minutes."""
    db = SessionLocal()
    try:
        await refresh_all_tracked_markets(db)
        
        # Detect shifts for all tracked markets
        from database import TrackedMarket
        markets = db.query(TrackedMarket).all()
        for market in markets:
            shifts = detect_shifts(db, market.id)
            if shifts:
                create_alerts(db, shifts)
                print(f"Created {len(shifts)} alerts for market {market.id}")
        
        print("Tracked markets refreshed")
    except Exception as e:
        print(f"Error refreshing tracked markets: {e}")
    finally:
        db.close()

def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            job_refresh_trending_categories,
            trigger=IntervalTrigger(minutes=TRENDING_REFRESH_INTERVAL_MINUTES),
            id="refresh_trending_categories",
            replace_existing=True
        )
        
        scheduler.add_job(
            job_refresh_tracked_markets,
            trigger=IntervalTrigger(minutes=MARKETS_REFRESH_INTERVAL_MINUTES),
            id="refresh_tracked_markets",
            replace_existing=True
        )
        
        scheduler.start()
        print("Scheduler started")

def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
