import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.agents import manager
from app.services.auth_service import decode_token

logger = logging.getLogger("cargo.websocket")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: str = Query(None),
):
    """
    WebSocket endpoint for real-time updates.
    Authentication via query param ticket (or fallback to cookie).
    """
    await websocket.accept()
    
    is_valid = False
    
    # 1. Try Ticket-based Auth (Most reliable behind proxies)
    if ticket:
        from app.services.auth_service import validate_ws_ticket
        user_id = validate_ws_ticket(ticket)
        if user_id:
            is_valid = True

    # 2. Fallback to Cookie-based Auth
    if not is_valid:
        access_token = websocket.cookies.get("access_token")
        if access_token:
            try:
                payload = decode_token(access_token)
                if payload.get("type") == "access":
                    is_valid = True
            except Exception:
                pass

    if not is_valid:
        await websocket.close(code=4001, reason="Invalid or missing authentication")
        return

    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, receive pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
