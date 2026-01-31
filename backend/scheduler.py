from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import SessionLocal, TrackedMarket, PriceSnapshot, Trade, OrderBookSnapshot
from services.trending_categories import refresh_trending_categories
from services.snapshot_service import refresh_all_tracked_markets
from services.alert_detection import detect_shifts, create_alerts
from services.clob_api import fetch_price_history, fetch_market_trades_by_market, fetch_order_book
from services.market_data import fetch_market_details, extract_outcomes_from_event
from datetime import datetime, timedelta
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

async def job_fetch_price_snapshots():
    """Job to fetch high-resolution price snapshots every 1 minute."""
    db = SessionLocal()
    try:
        markets = db.query(TrackedMarket).all()
        
        for market in markets:
            try:
                market_data = await fetch_market_details(market.market_slug)
                if not market_data:
                    continue
                
                outcomes = extract_outcomes_from_event(market_data)
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(minutes=1)
                
                for outcome in outcomes:
                    token_id = outcome.get("id")
                    if not token_id:
                        continue
                    
                    # Fetch price history for 1m interval
                    history = await fetch_price_history(
                        token_id,
                        interval="1m",
                        start_time=start_time,
                        end_time=end_time,
                        limit=1
                    )
                    
                    if history:
                        point = history[0]
                        # Find or create outcome in database
                        from database import Outcome
                        db_outcome = db.query(Outcome).filter(
                            Outcome.market_id == market.id,
                            Outcome.outcome_id == token_id
                        ).first()
                        
                        if not db_outcome:
                            db_outcome = Outcome(
                                market_id=market.id,
                                outcome_id=token_id,
                                name=outcome.get("name", "Unknown")
                            )
                            db.add(db_outcome)
                            db.flush()
                        
                        # Create price snapshot
                        price = point.get("close") or point.get("price", 0)
                        snapshot = PriceSnapshot(
                            market_id=market.id,
                            outcome_id=db_outcome.id,
                            token_id=token_id,
                            price=float(price),
                            volume=point.get("volume"),
                            open_price=point.get("open"),
                            high_price=point.get("high"),
                            low_price=point.get("low"),
                            close_price=point.get("close"),
                            interval="1m",
                            timestamp=datetime.fromtimestamp(point.get("timestamp", end_time.timestamp()))
                        )
                        db.add(snapshot)
                
                db.commit()
            except Exception as e:
                print(f"Error fetching price snapshots for market {market.id}: {e}")
                db.rollback()
        
        print("Price snapshots fetched")
    except Exception as e:
        print(f"Error in price snapshots job: {e}")
    finally:
        db.close()

async def job_fetch_recent_trades():
    """Job to fetch recent trades every 5 minutes."""
    db = SessionLocal()
    try:
        markets = db.query(TrackedMarket).all()
        
        for market in markets:
            try:
                trades = await fetch_market_trades_by_market(market.market_slug, limit=50)
                
                for trade_data in trades:
                    trade_id = trade_data.get("id") or trade_data.get("trade_id")
                    if not trade_id:
                        continue
                    
                    # Check if trade already exists
                    existing = db.query(Trade).filter(Trade.trade_id == str(trade_id)).first()
                    if existing:
                        continue
                    
                    # Find outcome
                    outcome_token_id = trade_data.get("outcome_id") or trade_data.get("token_id")
                    if not outcome_token_id:
                        continue
                    
                    from database import Outcome
                    db_outcome = db.query(Outcome).filter(
                        Outcome.market_id == market.id,
                        Outcome.outcome_id == str(outcome_token_id)
                    ).first()
                    
                    # Create trade record
                    trade = Trade(
                        market_id=market.id,
                        outcome_id=db_outcome.id if db_outcome else None,
                        token_id=str(outcome_token_id),
                        user_address=trade_data.get("user") or trade_data.get("user_address"),
                        amount=float(trade_data.get("amount", 0)),
                        price=float(trade_data.get("price", 0)),
                        side=trade_data.get("side", "buy"),
                        trade_id=str(trade_id)
                    )
                    
                    if "timestamp" in trade_data:
                        if isinstance(trade_data["timestamp"], str):
                            trade.timestamp = datetime.fromisoformat(trade_data["timestamp"].replace("Z", "+00:00"))
                        else:
                            trade.timestamp = datetime.fromtimestamp(trade_data["timestamp"])
                    
                    db.add(trade)
                
                db.commit()
            except Exception as e:
                print(f"Error fetching trades for market {market.id}: {e}")
                db.rollback()
        
        print("Recent trades fetched")
    except Exception as e:
        print(f"Error in trades job: {e}")
    finally:
        db.close()

async def job_cleanup_old_data():
    """Job to cleanup old data (older than 30 days) every 30 minutes."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        # Cleanup old price snapshots
        deleted_snapshots = db.query(PriceSnapshot).filter(
            PriceSnapshot.timestamp < cutoff
        ).delete()
        
        # Cleanup old trades (keep last 1000 per market)
        markets = db.query(TrackedMarket).all()
        for market in markets:
            trades = db.query(Trade).filter(
                Trade.market_id == market.id
            ).order_by(Trade.timestamp.desc()).all()
            
            if len(trades) > 1000:
                trades_to_delete = trades[1000:]
                for trade in trades_to_delete:
                    db.delete(trade)
        
        # Cleanup old order book snapshots
        deleted_orderbooks = db.query(OrderBookSnapshot).filter(
            OrderBookSnapshot.timestamp < cutoff
        ).delete()
        
        db.commit()
        print(f"Cleanup: deleted {deleted_snapshots} price snapshots, {deleted_orderbooks} order book snapshots")
    except Exception as e:
        print(f"Error in cleanup job: {e}")
        db.rollback()
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
        
        scheduler.add_job(
            job_fetch_price_snapshots,
            trigger=IntervalTrigger(minutes=1),
            id="fetch_price_snapshots",
            replace_existing=True
        )
        
        scheduler.add_job(
            job_fetch_recent_trades,
            trigger=IntervalTrigger(minutes=5),
            id="fetch_recent_trades",
            replace_existing=True
        )
        
        scheduler.add_job(
            job_cleanup_old_data,
            trigger=IntervalTrigger(minutes=30),
            id="cleanup_old_data",
            replace_existing=True
        )
        
        scheduler.start()
        print("Scheduler started")

def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
