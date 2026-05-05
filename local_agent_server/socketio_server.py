"""
Socket.IO Agent Server - Implements the full OpenHands SDK agent-server protocol.

This module provides WebSocket communication using the official SDK protocol:
- Endpoint: /socket.io/
- Events: oh_user_action (client->server), oh_event (server->client)
- Uses Socket.IO with Engine.IO version 4

Reference: https://docs.openhands.dev/openhands/usage/developers/websocket-connection
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from socketio import Server, logger
from socketio.asyncio_server import AsyncServer
from socketio.asyncio_manager import AsyncManager

from local_agent_server.services.conversation_manager import (
    get_conversation_manager,
    ConversationManager,
)
from local_agent_server.services.agent_factory import get_agent_factory
from local_agent_server.services.project_manager import get_project_manager

# Disable socketio debug logging
logger.setLevel(logging.WARNING)

# Create Socket.IO server with proper configuration
sio = Server(
    async_mode='asyncio',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False,
)

# Store active conversations by session_id
active_conversations: Dict[str, Dict[str, Any]] = {}


def setup_socketio_events():
    """Set up all Socket.IO event handlers."""
    
    @sio.on('connect')
    async def connect(sid, environ, auth):
        """Handle new WebSocket connection."""
        # Get parameters from query string
        query_params = environ.get('QUERY_STRING', '')
        params = {}
        for param in query_params.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        conversation_id = params.get('conversation_id')
        latest_event_id = int(params.get('latest_event_id', '-1'))
        
        print(f"[SocketIO] Client connected: sid={sid}, conversation_id={conversation_id}")
        
        return True
    
    @sio.on('oh_user_action')
    async def handle_user_action(sid, data):
        """Handle user action from client.
        
        Expected payload:
        {
            "type": "message",
            "source": "user",
            "message": "Hello, agent!"
        }
        """
        print(f"[SocketIO] User action: {data}")
        
        # Get conversation_id from the client's session
        conv_id = sio.get_session(sid).get('conversation_id')
        if not conv_id:
            await sio.emit('oh_event', {
                "type": "error",
                "error": "No conversation_id specified"
            }, room=sid)
            return
        
        cm = get_conversation_manager()
        conv = cm.get_conversation(conv_id)
        
        if not conv:
            # Create new conversation
            try:
                project_manager = get_project_manager()
                project = project_manager.get_project("default")
                if not project.exists:
                    project_manager.create_project("default")
                workspace = project_manager.get_workspace_for_project("default")
                
                factory = get_agent_factory()
                api_key = cm.api_key
                if not api_key:
                    api_key = cm.api_key or "demo-key"
                
                agent = factory.create_agent(api_key=api_key)
                
                from openhands.sdk import Conversation as SDKConversation
                sdk_conv = SDKConversation(agent=agent, workspace=workspace)
                
                from local_agent_server.services.conversation_manager import Conversation as LocalConv
                local_conv = LocalConv(
                    id=conv_id,
                    workspace_dir=str(workspace.working_dir),
                    agent_type=cm.default_agent_type,
                    enable_browser=cm.enable_browser,
                    agent=agent,
                    sdk_conversation=sdk_conv,
                )
                cm.conversations[conv_id] = local_conv
                conv = local_conv
            except Exception as e:
                await sio.emit('oh_event', {
                    "type": "error",
                    "error": f"Failed to create conversation: {str(e)}"
                }, room=sid)
                return
        
        # Handle different action types
        action_type = data.get('type', 'message')
        
        if action_type == 'message':
            # Send user message
            message = data.get('message', '')
            conv.sdk_conversation.send_message(message)
            
            # Run the agent
            await run_agent_async(conv, sid)
        
        elif action_type == 'observation':
            # Handle observation (result of tool execution)
            observation = data.get('observation', '')
            action_id = data.get('action_id')
            print(f"[SocketIO] Observation for {action_id}: {observation[:100]}")
        
        elif action_type == 'message_append':
            # Append additional message
            message = data.get('message', '')
            conv.sdk_conversation.send_message(message)
        
        else:
            print(f"[SocketIO] Unknown action type: {action_type}")
    
    @sio.on('oh_action_obs')
    async def handle_action_observation(sid, data):
        """Handle action observation from client.
        
        This is sent after tool execution completes.
        Expected payload:
        {
            "observation": "tool output",
            "action_id": "evt-123"
        }
        """
        print(f"[SocketIO] Action observation: {data}")
        
        # Forward to conversation if needed
        # Note: This is handled by the SDK internally
    
    @sio.on('disconnect')
    async def disconnect(sid):
        """Handle disconnection."""
        print(f"[SocketIO] Client disconnected: sid={sid}")
        
        # Clean up session
        if sid in active_conversations:
            del active_conversations[sid]
    
    @sio.on('disconnecting')
    async def disconnecting(sid, environ):
        """Handle disconnection."""
        print(f"[SocketIO] Client disconnecting: sid={sid}")


async def run_agent_async(conv, sid):
    """Run the agent asynchronously and emit events."""
    import concurrent.futures
    
    # Run in thread pool
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    try:
        await loop.run_in_executor(executor, conv.sdk_conversation.run)
        
        # Emit completion event
        await sio.emit('oh_event', {
            "type": "message",
            "source": "agent",
            "message": "Task completed",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, room=sid)
        
    except Exception as e:
        # Emit error event
        await sio.emit('oh_event', {
            "type": "error",
            "source": "agent",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, room=sid)


def create_socketio_app():
    """Create and return the Socket.IO server instance."""
    setup_socketio_events()
    return sio