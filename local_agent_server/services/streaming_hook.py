"""Streaming hook for real-time agent events."""

import logging
from typing import Any

from openhands.sdk.hooks import (
    HookDefinition,
    HookEventType,
    HookDecision,
    create_hook_callback,
)

logger = logging.getLogger(__name__)


async def emit_to_websocket(event_data: dict):
    """Placeholder - will be set by the route when registering."""
    pass


def create_streaming_hook(session_id: str):
    """Create a hook that emits agent events to WebSocket."""
    
    async def on_tool_use(event, decision: HookDecision) -> HookDecision:
        """Called before tool use."""
        # Emit tool use event
        event_data = {
            "tool": event.get("tool_name", "unknown"),
            "arguments": str(event.get("arguments", {}))[:500],
            "phase": "pre_tool_use",
        }
        try:
            await emit_to_websocket(session_id, "agent_thinking", event_data)
        except Exception as e:
            logger.error(f"Error emitting tool_use event: {e}")
        
        return decision
    
    async def on_tool_result(event, result: Any) -> Any:
        """Called after tool use."""
        # Emit tool result event
        result_str = str(result)[:1000] if result else ""
        event_data = {
            "result": result_str,
            "phase": "post_tool_use",
        }
        try:
            await emit_to_websocket(session_id, "tool_result", event_data)
        except Exception as e:
            logger.error(f"Error emitting tool_result event: {e}")
        
        return result
    
    async def on_user_prompt(event, message: str) -> str:
        """Called when user submits a prompt."""
        event_data = {
            "message": message[:500],
            "phase": "user_prompt",
        }
        try:
            await emit_to_websocket(session_id, "user_message", event_data)
        except Exception as e:
            logger.error(f"Error emitting user_prompt event: {e}")
        
        return message
    
    async def on_llm_chunk(event, chunk: str) -> str:
        """Called when LLM emits a chunk (streaming)."""
        event_data = {
            "chunk": chunk,
            "phase": "llm_chunk",
        }
        try:
            await emit_to_websocket(session_id, "llm_stream", event_data)
        except Exception as e:
            logger.error(f"Error emitting llm_chunk event: {e}")
        
        return chunk
    
    return [
        # These would need to be registered with appropriate event types
        # The actual implementation depends on SDK 1.19 hook API
    ]