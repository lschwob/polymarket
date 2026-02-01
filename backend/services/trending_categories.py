import httpx
from typing import List, Dict
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from database import TrendingCategoryCache
from config import TRENDING_MIN_SCORE, TRENDING_MIN_OCCURRENCES

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

async def fetch_trending_events(limit: int = 100) -> List[Dict]:
    """Fetch trending events from Polymarket Gamma API."""
    async with httpx.AsyncClient() as client:
        url = f"{GAMMA_API_BASE}/events/pagination"
        params = {
            "limit": limit,
            "active": "true",
            "archived": "false",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false"
        }
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

def aggregate_trending_categories(events: List[Dict], top_k: int = 20) -> List[Dict]:
    """
    Aggregate tags from events to compute trending categories.
    Score = sum of event volumes for each tag.
    """
    tag_scores = defaultdict(lambda: {"score": 0.0, "count": 0, "label": None})
    
    for event in events:
        volume = float(event.get("volume24hr") or event.get("volume") or 0)
        tags = event.get("tags", [])
        
        for tag in tags:
            slug = tag.get("slug")
            label = tag.get("label")
            if slug:
                tag_scores[slug]["score"] += float(volume)
                tag_scores[slug]["count"] += 1
                if not tag_scores[slug]["label"]:
                    tag_scores[slug]["label"] = label
    
    # Filter out micro tags (heuristic: min score or min occurrences)
    filtered_tags = [
        {
            "slug": slug,
            "label": info["label"] or slug,
            "score": info["score"],
            "count": info["count"]
        }
        for slug, info in tag_scores.items()
        if info["score"] >= TRENDING_MIN_SCORE and info["count"] >= TRENDING_MIN_OCCURRENCES
    ]
    
    # Sort by score descending and take top K
    sorted_tags = sorted(filtered_tags, key=lambda x: x["score"], reverse=True)
    return sorted_tags[:top_k]

async def refresh_trending_categories(db: Session, top_k: int = 20):
    """Refresh trending categories cache."""
    events = await fetch_trending_events(limit=100)
    categories = aggregate_trending_categories(events, top_k=top_k)
    
    # Clear old cache
    db.query(TrendingCategoryCache).delete()
    
    # Insert new categories
    for cat in categories:
        db_category = TrendingCategoryCache(
            slug=cat["slug"],
            label=cat["label"],
            score=cat["score"],
            computed_at=datetime.utcnow()
        )
        db.add(db_category)
    
    db.commit()
    return categories

def get_trending_categories(db: Session) -> List[Dict]:
    """Get cached trending categories."""
    categories = db.query(TrendingCategoryCache).order_by(TrendingCategoryCache.score.desc()).all()
    return [
        {
            "slug": cat.slug,
            "label": cat.label,
            "score": cat.score,
            "computed_at": cat.computed_at.isoformat() if cat.computed_at else None
        }
        for cat in categories
    ]
