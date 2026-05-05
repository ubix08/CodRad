"""
Remote Conversation Client - Connect to Local Agent Server using SDK-like pattern.

This module provides a RemoteConversation-compatible client that can connect
to the local agent server using WebSocket, similar to the SDK's RemoteConversation.

Usage:
    from local_agent_server.client import RemoteConversationClient
    
    client = RemoteConversationClient(
        server_url="http://localhost:8000",
        session_id="session-123"
    )
    
    # Event callback
    def on_event(event):
        print(f"Event: {event}")
    
    client.on_event = on_event
    client.connect()
    
    # Send message
    client.send_message("Hello, agent!")
    
    # Run agent
    client.run()
    
    # Get events
    events = client.events
"""

import asyncio
import json
import logging
import threading
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConversationEvent:
    """A conversation event received from the server."""
    type: str
    data: Dict[str, Any]


@dataclass  
class RemoteConversationClient:
    """Remote Conversation Client - connects to local agent server.
    
    Similar to SDK's RemoteConversation but connects to custom server.
    """
    
    server_url: str
    session_id: str
    ws_path: str = "/ws"
    
    # Event handling
    on_event: Optional[Callable[[ConversationEvent], None]] = None
    
    # State
    events: List[ConversationEvent] = field(default_factory=list)
    _connected: bool = False
    _ws: Optional[Any] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread: Optional[threading.Thread] = None
    
    def __post_init__(self):
        """Convert http:// to ws:// for WebSocket."""
        self.ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{self.ws_url}{self.ws_path}/{self.session_id}"
    
    def connect(self) -> bool:
        """Connect to the server via WebSocket."""
        import websockets
        
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Run connection in background thread
            def run_ws():
                asyncio.run(self._ws_loop())
            
            self._thread = threading.Thread(target=run_ws, daemon=True)
            self._thread.start()
            
            self._connected = True
            logger.info(f"Connected to {self.ws_url}")
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def _ws_loop(self):
        """WebSocket event loop."""
        import websockets
        
        try:
            async with websockets.connect(self.ws_url) as ws:
                self._ws = ws
                
                # Send connected message
                await ws.send(json.dumps({"type": "connected"}))
                
                # Listen for events
                async for message in ws:
                    try:
                        data = json.loads(message)
                        event = ConversationEvent(
                            type=data.get("type", "unknown"),
                            data=data.get("data", {})
                        )
                        self.events.append(event)
                        
                        # Call event callback
                        if self.on_event:
                            self.on_event(event)
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON: {message}")
                        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._connected = False
    
    def send_message(self, message: str) -> bool:
        """Send a message to the agent."""
        if not self._connected:
            logger.warning("Not connected")
            return False
        
        try:
            self._loop.call_soon_threadsafe(
                asyncio.create_task,
                self._ws.send(json.dumps({
                    "type": "message",
                    "data": {"content": message}
                }))
            )
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    def run(self) -> bool:
        """Tell the server to run the agent."""
        if not self._connected:
            logger.warning("Not connected")
            return False
        
        try:
            self._loop.call_soon_threadsafe(
                asyncio.create_task,
                self._ws.send(json.dumps({
                    "type": "run",
                    "data": {}
                }))
            )
            return True
        except Exception as e:
            logger.error(f"Run error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the server."""
        self._connected = False
        if self._ws:
            self._loop.call_soon_threadsafe(self._ws.close)
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Disconnected")


def create_remote_conversation(
    server_url: str,
    session_id: str,
    on_event: Optional[Callable[[ConversationEvent], None]] = None
) -> RemoteConversationClient:
    """Create a RemoteConversation client.
    
    This is the main entry point - creates a client that can interact
    with the local agent server using SDK-compatible patterns.
    
    Args:
        server_url: The server URL (e.g., http://localhost:8000)
        session_id: The session/conversation ID
        on_event: Optional callback for events
    
    Returns:
        RemoteConversationClient instance
    """
    client = RemoteConversationClient(
        server_url=server_url,
        session_id=session_id
    )
    client.on_event = on_event
    return client