"""WebSocket API for real-time event streaming."""

import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketState
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # session_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
        logger.info(f"WebSocket connected for session: {session_id}")
    
    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.info(f"WebSocket disconnected for session: {session_id}")
    
    async def send_event(self, session_id: str, event_type: str, data: dict):
        """Send event to all clients watching this session."""
        if session_id not in self.active_connections:
            return
        
        message = json.dumps({
            "type": event_type,
            "data": data
        })
        
        # Copy to avoid modification during iteration
        connections = list(self.active_connections[session_id])
        for ws in connections:
            try:
                await ws.send_json({
                    "type": event_type,
                    "data": data
                })
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                self.disconnect(session_id, ws)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time session events."""
    await manager.connect(session_id, websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Handle ping/pong or commands
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


# Function to emit events from anywhere in the app
async def emit_session_event(session_id: str, event_type: str, data: dict):
    """Emit an event to all WebSocket clients watching a session."""
    await manager.send_event(session_id, event_type, data)