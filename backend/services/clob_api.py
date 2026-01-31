import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta

CLOB_API_BASE = "https://clob.polymarket.com"

async def fetch_market_trades(
    token_id: str,
    limit: int = 100,
    offset: int = 0,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict]:
    """
    Fetch trades for a specific token (outcome).
    
    Args:
        token_id: The token ID (outcome ID) to fetch trades for
        limit: Maximum number of trades to return
        offset: Offset for pagination
        start_time: Optional start time filter
        end_time: Optional end time filter
    
    Returns:
        List of trade dictionaries
    """
    async with httpx.AsyncClient() as client:
        url = f"{CLOB_API_BASE}/trades"
        params = {
            "token_id": token_id,
            "limit": limit,
            "offset": offset
        }
        
        if start_time:
            params["start_time"] = int(start_time.timestamp())
        if end_time:
            params["end_time"] = int(end_time.timestamp())
        
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except httpx.HTTPStatusError as e:
            # If endpoint doesn't exist, try alternative endpoints
            if e.response.status_code == 404:
                # Try alternative endpoint structure
                return await _fetch_trades_alternative(client, token_id, limit, offset)
            raise
        except Exception as e:
            print(f"Error fetching trades for token {token_id}: {e}")
            return []

async def _fetch_trades_alternative(
    client: httpx.AsyncClient,
    token_id: str,
    limit: int,
    offset: int
) -> List[Dict]:
    """Alternative method to fetch trades if primary endpoint fails."""
    # Try different endpoint patterns
    try:
        url = f"{CLOB_API_BASE}/markets/{token_id}/trades"
        params = {"limit": limit, "offset": offset}
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("data", []) if isinstance(data, dict) else data
    except:
        return []

async def fetch_order_book(token_id: str) -> Optional[Dict]:
    """
    Fetch current order book (bids and asks) for a token.
    
    Args:
        token_id: The token ID (outcome ID) to fetch order book for
    
    Returns:
        Dictionary with 'bids' and 'asks' lists, or None if error
    """
    async with httpx.AsyncClient() as client:
        url = f"{CLOB_API_BASE}/book"
        params = {"token_id": token_id}
        
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Normalize response format
            if isinstance(data, dict):
                return {
                    "bids": data.get("bids", []),
                    "asks": data.get("asks", []),
                    "token_id": token_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Try alternative endpoint
                return await _fetch_order_book_alternative(client, token_id)
            print(f"Error fetching order book for token {token_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching order book for token {token_id}: {e}")
            return None

async def _fetch_order_book_alternative(
    client: httpx.AsyncClient,
    token_id: str
) -> Optional[Dict]:
    """Alternative method to fetch order book."""
    try:
        url = f"{CLOB_API_BASE}/markets/{token_id}/book"
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return {
            "bids": data.get("bids", []),
            "asks": data.get("asks", []),
            "token_id": token_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    except:
        return None

async def fetch_price_history(
    token_id: str,
    interval: str = "1m",  # 1m, 5m, 1h, 1d
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000
) -> List[Dict]:
    """
    Fetch historical price data for a token.
    
    Args:
        token_id: The token ID (outcome ID)
        interval: Time interval (1m, 5m, 1h, 1d)
        start_time: Optional start time (defaults to 24h ago)
        end_time: Optional end time (defaults to now)
        limit: Maximum number of data points
    
    Returns:
        List of price history dictionaries with timestamp, price, volume
    """
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(hours=24)
    if end_time is None:
        end_time = datetime.utcnow()
    
    async with httpx.AsyncClient() as client:
        url = f"{CLOB_API_BASE}/price-history"
        params = {
            "token_id": token_id,
            "interval": interval,
            "start_time": int(start_time.timestamp()),
            "end_time": int(end_time.timestamp()),
            "limit": limit
        }
        
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Try alternative endpoint or fallback to calculating from trades
                return await _fetch_price_history_alternative(
                    client, token_id, interval, start_time, end_time
                )
            print(f"Error fetching price history for token {token_id}: {e}")
            return []
        except Exception as e:
            print(f"Error fetching price history for token {token_id}: {e}")
            return []

async def _fetch_price_history_alternative(
    client: httpx.AsyncClient,
    token_id: str,
    interval: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict]:
    """Alternative: calculate price history from trades if endpoint doesn't exist."""
    # Fetch recent trades and aggregate by interval
    trades = await fetch_market_trades(
        token_id,
        limit=1000,
        start_time=start_time,
        end_time=end_time
    )
    
    if not trades:
        return []
    
    # Group trades by interval and calculate OHLC
    # This is a simplified version - in production, use proper OHLC aggregation
    interval_seconds = {
        "1m": 60,
        "5m": 300,
        "1h": 3600,
        "1d": 86400
    }.get(interval, 60)
    
    history = []
    current_bucket = None
    bucket_trades = []
    
    for trade in sorted(trades, key=lambda x: x.get("timestamp", 0)):
        trade_time = trade.get("timestamp", 0)
        if isinstance(trade_time, str):
            try:
                trade_time = datetime.fromisoformat(trade_time.replace("Z", "+00:00")).timestamp()
            except:
                continue
        
        bucket_start = int(trade_time // interval_seconds) * interval_seconds
        
        if current_bucket != bucket_start:
            if current_bucket is not None and bucket_trades:
                # Calculate OHLC for previous bucket
                prices = [float(t.get("price", 0)) for t in bucket_trades if t.get("price")]
                if prices:
                    history.append({
                        "timestamp": current_bucket,
                        "open": prices[0],
                        "high": max(prices),
                        "low": min(prices),
                        "close": prices[-1],
                        "volume": sum(float(t.get("amount", 0)) for t in bucket_trades)
                    })
            current_bucket = bucket_start
            bucket_trades = [trade]
        else:
            bucket_trades.append(trade)
    
    # Add last bucket
    if current_bucket is not None and bucket_trades:
        prices = [float(t.get("price", 0)) for t in bucket_trades if t.get("price")]
        if prices:
            history.append({
                "timestamp": current_bucket,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": sum(float(t.get("amount", 0)) for t in bucket_trades)
            })
    
    return history

async def fetch_market_trades_by_market(
    market_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Fetch all trades for all outcomes of a market.
    Uses Gamma API to get outcome token IDs first, then fetches trades for each.
    """
    from services.market_data import fetch_market_details
    
    market_data = await fetch_market_details(market_id)
    if not market_data:
        return []
    
    all_trades = []
    
    # Extract outcomes from market data
    markets = market_data.get("markets", [])
    if not markets and market_data.get("outcomes"):
        markets = [market_data]
    
    for market in markets:
        outcomes = market.get("outcomes", [])
        for outcome in outcomes:
            token_id = outcome.get("id") or outcome.get("token_id") or outcome.get("outcome_id")
            if token_id:
                trades = await fetch_market_trades(token_id, limit=limit, offset=offset)
                # Add outcome info to each trade
                for trade in trades:
                    trade["outcome_id"] = token_id
                    trade["outcome_name"] = outcome.get("title") or outcome.get("name")
                all_trades.extend(trades)
    
    # Sort by timestamp descending
    all_trades.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return all_trades[:limit]
