"""
WebSocket/SSE Event Manager for real-time agent progress streaming.
"""

import asyncio
import json
from enum import Enum
from typing import Any, Callable, Optional
from datetime import datetime
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for real-time streaming."""
    AGENT_STARTED = "agent_started"
    AGENT_THINKING = "agent_thinking"
    AGENT_ACTION = "agent_action"
    AGENT_OBSERVATION = "agent_observation"
    AGENT_THOUGHT = "agent_thought"
    AGENT_ERROR = "agent_error"
    AGENT_FINISHED = "agent_finished"
    CONVERSATION_MESSAGE = "conversation_message"
    CONVERSATION_ERROR = "conversation_error"
    TOKEN_USAGE = "token_usage"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"


class EventManager:
    """Manages WebSocket connections and event streaming."""
    
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}
        self.event_handlers: dict[EventType, list[Callable]] = {}
    
    async def connect(self, conversation_id: str, websocket: WebSocket):
        """Connect a WebSocket client to a conversation."""
        await websocket.accept()
        
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = set()
        
        self.active_connections[conversation_id].add(websocket)
        logger.info(f"WebSocket connected for conversation {conversation_id}")
    
    def disconnect(self, conversation_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].remove(websocket)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
        logger.info(f"WebSocket disconnected for conversation {conversation_id}")
    
    async def broadcast(self, conversation_id: str, event_type: EventType, data: dict[str, Any]):
        """Broadcast an event to all connected clients for a conversation."""
        if conversation_id not in self.active_connections:
            return
        
        message = {
            "type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": conversation_id,
            "data": data,
        }
        
        # Filter out closed connections
        closed_connections = set()
        for websocket in self.active_connections[conversation_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                closed_connections.add(websocket)
        
        # Clean up closed connections
        for ws in closed_connections:
            self.active_connections[conversation_id].discard(ws)
    
    def on_event(self, event_type: EventType, handler: Callable):
        """Register an event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit(self, conversation_id: str, event_type: EventType, data: dict[str, Any]):
        """Emit an event to all handlers and broadcast to WebSocket."""
        # Call registered handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(conversation_id, data)
                    else:
                        handler(conversation_id, data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
        
        # Broadcast to WebSocket clients
        await self.broadcast(conversation_id, event_type, data)


# Global event manager instance
event_manager = EventManager()


# Convenience functions for emitting events
async def emit_agent_started(conversation_id: str, agent_type: str):
    """Emit agent started event."""
    await event_manager.emit(conversation_id, EventType.AGENT_STARTED, {"agent_type": agent_type})


async def emit_agent_action(conversation_id: str, action: str, content: str):
    """Emit agent action event."""
    await event_manager.emit(conversation_id, EventType.AGENT_ACTION, {
        "action": action,
        "content": content,
    })


async def emit_agent_observation(conversation_id: str, observation: str, source: str = "tool"):
    """Emit agent observation event."""
    await event_manager.emit(conversation_id, EventType.AGENT_OBSERVATION, {
        "observation": observation,
        "source": source,
    })


async def emit_agent_error(conversation_id: str, error: str):
    """Emit agent error event."""
    await event_manager.emit(conversation_id, EventType.AGENT_ERROR, {"error": error})


async def emit_agent_finished(conversation_id: str, summary: str, metrics: dict = None):
    """Emit agent finished event."""
    await event_manager.emit(conversation_id, EventType.AGENT_FINISHED, {
        "summary": summary,
        "metrics": metrics or {},
    })


async def emit_token_usage(conversation_id: str, input_tokens: int, output_tokens: int, cost: float):
    """Emit token usage event."""
    await event_manager.emit(conversation_id, EventType.TOKEN_USAGE, {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost,
    })
