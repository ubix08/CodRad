"""SSE streaming endpoint for real-time agent events."""

import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from local_agent_server.services.conversation_manager import get_conversation_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sse"])


async def generate_events(session_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a session.
    
    This coroutine continuously checks for new events in the conversation
    and yields them as SSE messages.
    """
    from local_agent_server.api.routes.websocket import manager as ws_manager
    
    # Yield initial connection event
    yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"
    
    cm = get_conversation_manager()
    conv = cm.get_conversation(session_id)
    
    if not conv or not conv.sdk_conversation:
        yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
        return
    
    sdk_conv = conv.sdk_conversation
    
    # Track last event count to detect new events
    last_event_count = 0
    max_iterations = 500
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        try:
            # Get current events from SDK conversation
            events = list(sdk_conv.state.events) if hasattr(sdk_conv.state, 'events') else []
            
            # Check if there are new events
            if len(events) > last_event_count:
                # Get new events
                new_events = events[last_event_count:]
                last_event_count = len(events)
                
                for event in new_events:
                    event_type = type(event).__name__
                    
                    # Emit event to WebSocket clients too
                    if ws_manager.active_connections.get(session_id):
                        await ws_manager.send_event(
                            session_id, 
                            "iteration_event",
                            {"event_type": event_type, "event": str(event)[:500]}
                        )
                    
                    # Format as SSE
                    if event_type == "MessageEvent":
                        source = getattr(event, 'source', 'unknown')
                        llm_msg = getattr(event, 'llm_message', None)
                        if llm_msg:
                            content = str(llm_msg)[:300]
                        else:
                            content = ""
                        
                        yield f"event: message\ndata: {json.dumps({'role': source, 'content': content})}\n\n"
                    
                    elif event_type == "ActionEvent":
                        action = getattr(event, 'action', 'unknown')
                        yield f"event: action\ndata: {json.dumps({'action': str(action)[:200]})}\n\n"
                    
                    elif event_type == "SystemPromptEvent":
                        continue  # Skip system prompts
                    else:
                        # Generic event
                        yield f"event: {event_type}\ndata: {json.dumps({'data': str(event)[:200]})}\n\n"
            
            # Check execution status
            status = getattr(sdk_conv.state, 'execution_status', None)
            if status and str(status) == 'completed':
                yield f"event: completed\ndata: {json.dumps({'status': 'completed'})}\n\n"
                break
            
            # Check for error
            # (would need to check SDK state for errors)
            
        except Exception as e:
            logger.error(f"Error in SSE loop: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            break
        
        # Small delay between checks
        await asyncio.sleep(0.5)
    
    yield f"event: done\ndata: {json.dumps({'iterations': iteration})}\n\n"


@router.get("/sse/{session_id}")
async def sse_stream(session_id: str):
    """Server-Sent Events endpoint for real-time session updates.
    
    Polls the SDK conversation state and streams events to the client.
    """
    import asyncio
    import json
    
    async def event_generator():
        from local_agent_server.services.conversation_manager import get_conversation_manager
        
        cm = get_conversation_manager()
        conv = cm.get_conversation(session_id)
        
        if not conv:
            yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
            return
        
        sdk_conv = conv.sdk_conversation
        last_event_count = 0
        
        # Yield initial event
        yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"
        
        while True:
            try:
                # Get events from SDK conversation state
                events = list(sdk_conv.state.events) if hasattr(sdk_conv.state, 'events') else []
                
                # Check if there are new events
                if len(events) > last_event_count:
                    new_events = events[last_event_count:]
                    last_event_count = len(events)
                    
                    for event in new_events:
                        event_type = type(event).__name__
                        
                        # Format different event types
                        if event_type == "MessageEvent":
                            source = getattr(event, 'source', 'unknown')
                            role = "assistant" if source == "agent" else "user"
                            # Get content from llm_message
                            content = ""
                            llm_msg = getattr(event, 'llm_message', None)
                            if llm_msg:
                                text_content = getattr(llm_msg, 'content', None)
                                if text_content:
                                    content = str(text_content[0].text)[:300] if hasattr(text_content[0], 'text') else str(text_content[0])
                            
                            yield f"event: message\ndata: {json.dumps({'role': role, 'content': content})}\n\n"
                        
                        elif event_type == "ActionEvent":
                            action = str(getattr(event, 'action', ''))[:200]
                            observation = str(getattr(event, 'observation', ''))[:500]
                            yield f"event: action\ndata: {json.dumps({'action': action, 'observation': observation})}\n\n"
                        
                        elif event_type == "AgentErrorEvent":
                            error = str(event)
                            yield f"event: error\ndata: {json.dumps({'error': error})}\n\n"
                
                # Check execution status
                status = str(getattr(sdk_conv.state, 'execution_status', 'unknown'))
                if status == 'completed':
                    yield f"event: completed\ndata: {json.dumps({'status': 'completed'})}\n\n"
                    break
                    
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                break
            
            await asyncio.sleep(0.3)
        
        yield f"event: done\ndata: {json.dumps({'session_id': session_id})}\n\n"
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )