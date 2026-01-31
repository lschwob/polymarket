from typing import Dict, Set, List
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
from datetime import datetime

class ConnectionManager:
    """Manages WebSocket connections grouped by market_id."""
    
    def __init__(self):
        # Map market_id -> Set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Map WebSocket -> market_id
        self.connection_markets: Dict[WebSocket, int] = {}
        # Background tasks for broadcasting
        self.broadcast_tasks: Dict[int, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, market_id: int):
        """Accept a new WebSocket connection for a market."""
        await websocket.accept()
        
        if market_id not in self.active_connections:
            self.active_connections[market_id] = set()
        
        self.active_connections[market_id].add(websocket)
        self.connection_markets[websocket] = market_id
        
        # Start broadcast task if not already running
        if market_id not in self.broadcast_tasks:
            self.broadcast_tasks[market_id] = asyncio.create_task(
                self._broadcast_loop(market_id)
            )
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        market_id = self.connection_markets.get(websocket)
        if market_id:
            self.active_connections[market_id].discard(websocket)
            self.connection_markets.pop(websocket, None)
            
            # If no more connections for this market, stop broadcast task
            if not self.active_connections.get(market_id):
                task = self.broadcast_tasks.pop(market_id, None)
                if task:
                    task.cancel()
                self.active_connections.pop(market_id, None)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_market(self, market_id: int, message: dict):
        """Broadcast a message to all connections for a specific market."""
        connections = self.active_connections.get(market_id, set()).copy()
        if not connections:
            return
        
        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def _broadcast_loop(self, market_id: int):
        """Background task that periodically broadcasts market updates."""
        from services.market_data import fetch_market_details
        from services.clob_api import fetch_order_book, fetch_market_trades_by_market
        from database import get_db, TrackedMarket
        from sqlalchemy.orm import Session
        
        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)
        
        try:
            # Get tracked market info
            tracked_market = db.query(TrackedMarket).filter(
                TrackedMarket.id == market_id
            ).first()
            
            if not tracked_market:
                return
            
            while market_id in self.active_connections:
                try:
                    # Fetch latest market data
                    market_data = await fetch_market_details(tracked_market.market_slug)
                    
                    if market_data:
                        # Extract outcomes with current prices
                        outcomes = []
                        markets = market_data.get("markets", [])
                        if not markets and market_data.get("outcomes"):
                            markets = [market_data]
                        
                        for market in markets:
                            market_outcomes = market.get("outcomes", [])
                            for outcome in market_outcomes:
                                price = outcome.get("price", 0)
                                prob = float(price) if price else 0.0
                                
                                outcomes.append({
                                    "id": outcome.get("id") or outcome.get("outcome_id"),
                                    "name": outcome.get("title") or outcome.get("name"),
                                    "price": price,
                                    "prob": prob,
                                    "volume": market.get("volume", 0),
                                    "liquidity": market.get("liquidity", 0)
                                })
                        
                        # Fetch recent trades (last 10)
                        recent_trades = await fetch_market_trades_by_market(
                            tracked_market.market_slug,
                            limit=10
                        )
                        
                        # Prepare update message
                        update_message = {
                            "type": "market_update",
                            "market_id": market_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "outcomes": outcomes,
                                "recent_trades": recent_trades[:10],
                                "volume_24h": market_data.get("volume", 0),
                                "liquidity": market_data.get("liquidity", 0)
                            }
                        }
                        
                        # Broadcast to all connections for this market
                        await self.broadcast_to_market(market_id, update_message)
                    
                    # Wait 5 seconds before next update
                    await asyncio.sleep(5)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Error in broadcast loop for market {market_id}: {e}")
                    await asyncio.sleep(5)
        
        finally:
            db.close()

# Global connection manager instance
manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket, market_id: int):
    """WebSocket endpoint handler."""
    await manager.connect(websocket, market_id)
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal_message({"type": "pong"}, websocket)
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
