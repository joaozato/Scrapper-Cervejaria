import asyncio
import logging
from datetime import datetime, timezone
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger("cargo.agents")


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        for conn in disconnected:
            self.active_connections.discard(conn)


# Global connection manager
manager = ConnectionManager()


async def notify_disponibilidade_change(action: str, data: dict):
    """Agent 1: Notify all clients when a disponibilidade changes."""
    await manager.broadcast({
        "type": "disponibilidade_update",
        "action": action,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def notify_dashboard_refresh(dashboard_data: dict):
    """Agent 2: Send dashboard refresh with updated aggregations."""
    await manager.broadcast({
        "type": "dashboard_refresh",
        "data": dashboard_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def notify_ranking_update(ranking_data: list):
    """Agent 3: Send ranking update when availability changes."""
    await manager.broadcast({
        "type": "ranking_update",
        "data": ranking_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def notify_realtime_status(realtime_data: dict):
    """Agent 3b: Send real-time availability status."""
    await manager.broadcast({
        "type": "realtime_status",
        "data": realtime_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
