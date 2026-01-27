from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Alert, TrackedMarket, Snapshot, Outcome
from config import (
    ABSOLUTE_DELTA_THRESHOLD,
    RELATIVE_DELTA_THRESHOLD,
    MIN_VOLUME_THRESHOLD,
    ALERT_COOLDOWN_MINUTES,
    SHIFT_DETECTION_WINDOW_HOURS
)

def detect_shifts(db: Session, market_id: int) -> List[Dict]:
    """
    Detect significant probability shifts for a market.
    Returns list of alerts to create.
    """
    market = db.query(TrackedMarket).filter(TrackedMarket.id == market_id).first()
    if not market:
        return []
    
    # Get recent snapshots (configurable window)
    cutoff_time = datetime.utcnow() - timedelta(hours=SHIFT_DETECTION_WINDOW_HOURS)
    recent_snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.market_id == market_id)
        .filter(Snapshot.ts >= cutoff_time)
        .order_by(Snapshot.ts.desc())
        .all()
    )
    
    if len(recent_snapshots) < 2:
        return []
    
    # Group by outcome
    outcome_snapshots = {}
    for snapshot in recent_snapshots:
        outcome_id = snapshot.outcome_id
        if outcome_id not in outcome_snapshots:
            outcome_snapshots[outcome_id] = []
        outcome_snapshots[outcome_id].append(snapshot)
    
    alerts_to_create = []
    
    for outcome_id, snapshots in outcome_snapshots.items():
        if len(snapshots) < 2:
            continue
        
        # Get most recent and previous snapshot
        latest = snapshots[0]
        previous = snapshots[-1]
        
        # Check cooldown - don't alert if recent alert exists
        cooldown_cutoff = datetime.utcnow() - timedelta(minutes=ALERT_COOLDOWN_MINUTES)
        recent_alert = (
            db.query(Alert)
            .filter(Alert.market_id == market_id)
            .filter(Alert.outcome_id == outcome_id)
            .filter(Alert.ts >= cooldown_cutoff)
            .filter(Alert.status == "active")
            .first()
        )
        
        if recent_alert:
            continue
        
        # Check volume threshold
        if latest.volume and latest.volume < MIN_VOLUME_THRESHOLD:
            continue
        
        # Calculate delta
        prev_prob = previous.prob
        new_prob = latest.prob
        delta = new_prob - prev_prob
        delta_percent = (delta / prev_prob * 100) if prev_prob > 0 else 0
        
        # Check thresholds
        absolute_shift = abs(delta) >= ABSOLUTE_DELTA_THRESHOLD
        relative_shift = abs(delta_percent) >= (RELATIVE_DELTA_THRESHOLD * 100)
        
        if absolute_shift or relative_shift:
            # Calculate volume impact (quantify shift by volume)
            volume = latest.volume or 0
            volume_impact = abs(delta) * volume  # Impact = magnitude of change * volume
            
            alerts_to_create.append({
                "market_id": market_id,
                "outcome_id": outcome_id,
                "prev_prob": prev_prob,
                "new_prob": new_prob,
                "delta": delta,
                "delta_percent": delta_percent,
                "volume": volume,
                "volume_impact": volume_impact
            })
    
    return alerts_to_create

def create_alerts(db: Session, alerts_data: List[Dict]):
    """Create alert records in database."""
    for alert_data in alerts_data:
        alert = Alert(
            market_id=alert_data["market_id"],
            outcome_id=alert_data.get("outcome_id"),
            prev_prob=alert_data["prev_prob"],
            new_prob=alert_data["new_prob"],
            delta=alert_data["delta"],
            delta_percent=alert_data["delta_percent"],
            volume=alert_data.get("volume"),
            volume_impact=alert_data.get("volume_impact"),
            ts=datetime.utcnow(),
            status="active"
        )
        db.add(alert)
    
    db.commit()
