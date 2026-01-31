import httpx
from typing import List, Dict, Optional
from datetime import datetime
import os

THE_GRAPH_API_KEY = os.getenv("THE_GRAPH_API_KEY", "")
THE_GRAPH_ENDPOINT = f"https://gateway.thegraph.com/api/{THE_GRAPH_API_KEY}/subgraphs/id/Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp"

async def query_graphql(query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
    """
    Execute a GraphQL query against The Graph subgraph.
    
    Args:
        query: GraphQL query string
        variables: Optional variables for the query
    
    Returns:
        Response data or None if error
    """
    if not THE_GRAPH_API_KEY:
        print("Warning: THE_GRAPH_API_KEY not set. The Graph queries will fail.")
        return None
    
    async with httpx.AsyncClient() as client:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        try:
            response = await client.post(
                THE_GRAPH_ENDPOINT,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                return None
            
            return data.get("data")
        except Exception as e:
            print(f"Error executing GraphQL query: {e}")
            return None

async def fetch_market_transactions(
    market_id: str,
    limit: int = 100,
    skip: int = 0
) -> List[Dict]:
    """
    Fetch on-chain transactions (redemptions) for a market.
    
    Args:
        market_id: The market ID or condition ID
        limit: Maximum number of transactions
        skip: Offset for pagination
    
    Returns:
        List of transaction dictionaries
    """
    query = """
    query GetMarketTransactions($marketId: String!, $limit: Int!, $skip: Int!) {
      redemptions(
        where: { condition: $marketId }
        first: $limit
        skip: $skip
        orderBy: timestamp
        orderDirection: desc
      ) {
        id
        condition
        redeemer
        payout
        timestamp
        transaction {
          id
          blockNumber
        }
      }
    }
    """
    
    variables = {
        "marketId": market_id,
        "limit": limit,
        "skip": skip
    }
    
    data = await query_graphql(query, variables)
    if not data:
        return []
    
    return data.get("redemptions", [])

async def fetch_user_activity(
    user_address: str,
    limit: int = 100,
    skip: int = 0
) -> List[Dict]:
    """
    Fetch activity for a specific user address.
    
    Args:
        user_address: Ethereum address of the user
        limit: Maximum number of transactions
        skip: Offset for pagination
    
    Returns:
        List of user activity dictionaries
    """
    query = """
    query GetUserActivity($userAddress: String!, $limit: Int!, $skip: Int!) {
      redemptions(
        where: { redeemer: $userAddress }
        first: $limit
        skip: $skip
        orderBy: timestamp
        orderDirection: desc
      ) {
        id
        condition
        redeemer
        payout
        timestamp
        transaction {
          id
          blockNumber
        }
      }
    }
    """
    
    variables = {
        "userAddress": user_address.lower(),
        "limit": limit,
        "skip": skip
    }
    
    data = await query_graphql(query, variables)
    if not data:
        return []
    
    return data.get("redemptions", [])

async def fetch_market_volume_stats(
    market_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Optional[Dict]:
    """
    Fetch aggregated volume statistics for a market.
    
    Args:
        market_id: The market ID or condition ID
        start_time: Optional start time filter
        end_time: Optional end time filter
    
    Returns:
        Dictionary with volume statistics
    """
    query = """
    query GetMarketVolume($marketId: String!, $startTime: BigInt, $endTime: BigInt) {
      redemptions(
        where: { 
          condition: $marketId
          timestamp_gte: $startTime
          timestamp_lte: $endTime
        }
        orderBy: timestamp
        orderDirection: desc
      ) {
        payout
        timestamp
      }
    }
    """
    
    variables = {
        "marketId": market_id
    }
    
    if start_time:
        variables["startTime"] = int(start_time.timestamp())
    if end_time:
        variables["endTime"] = int(end_time.timestamp())
    
    data = await query_graphql(query, variables)
    if not data:
        return None
    
    redemptions = data.get("redemptions", [])
    
    total_volume = sum(float(r.get("payout", 0)) for r in redemptions)
    transaction_count = len(redemptions)
    
    return {
        "market_id": market_id,
        "total_volume": total_volume,
        "transaction_count": transaction_count,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None
    }

async def fetch_recent_market_activity(
    market_id: str,
    hours: int = 24,
    limit: int = 50
) -> List[Dict]:
    """
    Fetch recent activity for a market (last N hours).
    
    Args:
        market_id: The market ID or condition ID
        hours: Number of hours to look back
        limit: Maximum number of transactions
    
    Returns:
        List of recent activity dictionaries
    """
    from datetime import timedelta
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    query = """
    query GetRecentActivity($marketId: String!, $startTime: BigInt!, $limit: Int!) {
      redemptions(
        where: { 
          condition: $marketId
          timestamp_gte: $startTime
        }
        first: $limit
        orderBy: timestamp
        orderDirection: desc
      ) {
        id
        condition
        redeemer
        payout
        timestamp
        transaction {
          id
          blockNumber
        }
      }
    }
    """
    
    variables = {
        "marketId": market_id,
        "startTime": int(start_time.timestamp()),
        "limit": limit
    }
    
    data = await query_graphql(query, variables)
    if not data:
        return []
    
    return data.get("redemptions", [])
