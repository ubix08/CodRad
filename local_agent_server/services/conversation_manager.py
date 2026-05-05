"""Conversation manager service - Manages all conversations using SDK LocalWorkspace."""

import os
import uuid
import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any, Callable, Dict

import logging

from openhands.sdk import Conversation as SDKConversation
from openhands.sdk.workspace import LocalWorkspace

from ..models.schemas import AgentType, ConversationStatus, MessageRole
from .agent_factory import get_agent_factory
from .project_manager import get_project_manager

logger = logging.getLogger(__name__)


# Event callback type for real-time updates
EventCallback = Callable[[str, str, dict], None]  # (conversation_id, event_type, event_data)
_event_callbacks: Dict[str, EventCallback] = {}


def register_event_callback(conversation_id: str, callback: EventCallback) -> None:
    """Register a callback for conversation events."""
    _event_callbacks[conversation_id] = callback


def unregister_event_callback(conversation_id: str) -> None:
    """Unregister a callback for conversation events."""
    _event_callbacks.pop(conversation_id, None)


def emit_event(conversation_id: str, event_type: str, event_data: dict) -> None:
    """Emit an event to registered callbacks."""
    if conversation_id in _event_callbacks:
        try:
            _event_callbacks[conversation_id](conversation_id, event_type, event_data)
        except Exception as e:
            logger.error(f"Error emitting event: {e}")


@dataclass
class Conversation:
    """Represents a conversation with an agent."""
    
    id: str
    workspace_dir: str
    agent_type: AgentType
    enable_browser: bool
    created_at: datetime = field(default_factory=datetime.now)
    status: ConversationStatus = ConversationStatus.CREATED
    title: str = ""
    agent: Any = None
    sdk_conversation: Optional[SDKConversation] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "workspace_dir": self.workspace_dir,
            "status": self.status.value,
            "title": self.title,
            "agent_type": self.agent_type.value,
            "enable_browser": self.enable_browser,
            "created_at": self.created_at,
        }


class ConversationManager:
    """Manages all conversations using SDK LocalWorkspace.
    
    Uses ProjectManager with SDK LocalWorkspace for project management.
    """
    
    def __init__(
        self,
        project_manager: Optional[Any] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the conversation manager.
        
        Args:
            project_manager: Project manager instance (uses SDK LocalWorkspace)
            api_key: API key for LLM (falls back to env var)
        """
        self.project_manager = project_manager or get_project_manager()
        self.conversations: dict[str, Conversation] = {}
        
        # Load API key from environment - check multiple providers
        # Priority: explicit param > OPENHANDS_API_KEY > provider-specific keys
        self.api_key = api_key or os.getenv("OPENHANDS_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        
        # Also check provider-specific API keys
        if not self.api_key:
            for key_env in ["OPENROUTER_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", 
                        "GOOGLE_API_KEY", "NVIDIA_API_KEY", "ANTHROPIC_API_KEY",
                        "OPENAI_API_KEY", "LLM_API_KEY"]:
                if key := os.getenv(key_env):
                    self.api_key = key
                    break
        
        # Load config from environment using new module
        from local_agent_server.core.config import get_provider_default_model
        self.model = os.getenv("LLM_MODEL") or get_provider_default_model()
        self.enable_browser = os.getenv("ENABLE_BROWSER", "true").lower() == "true"
        self.default_agent_type = AgentType.DEFAULT
        
        if not self.api_key:
            logger.warning("No API key configured!")
        
        logger.info(f"ConversationManager initialized (api_key_configured={bool(self.api_key)}, model={self.model})")
    
    def set_api_key(self, api_key: str) -> None:
        """Set the API key."""
        self.api_key = api_key
    
    def set_model(self, model: str) -> None:
        """Set the default model."""
        self.model = model
    
    def create_conversation(
        self,
        project_name: str,
        initial_message: Optional[str] = None,
        agent_type: Optional[AgentType] = None,
        enable_browser: Optional[bool] = None,
        model: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation with an agent.
        
        Uses SDK LocalWorkspace via ProjectManager.
        """
        if not self.api_key:
            raise ValueError("API key not configured")
        
        # Use provided options or defaults
        agent_type = agent_type or self.default_agent_type
        enable_browser = enable_browser if enable_browser is not None else self.enable_browser
        
        conversation_id = str(uuid.uuid4())
        
        # Get project workspace from SDK ProjectManager
        project = self.project_manager.get_project(project_name)
        if not project.exists:
            # Create project if it doesn't exist
            project.create()
        
        # Get SDK LocalWorkspace for this project
        workspace = self.project_manager.get_workspace_for_project(project_name)
        
        # Create agent with exact same config as original
        factory = get_agent_factory()
        agent = factory.create_agent(
            api_key=self.api_key,
            agent_type=agent_type,
            enable_browser=enable_browser,
            model=model or self.model,
        )
        
        # Create SDK conversation with SDK LocalWorkspace
        sdk_conversation = SDKConversation(
            agent=agent,
            workspace=workspace,
        )
        
        conversation = Conversation(
            id=conversation_id,
            workspace_dir=str(workspace.working_dir) if workspace else "",
            agent_type=agent_type,
            enable_browser=enable_browser,
            agent=agent,
            sdk_conversation=sdk_conversation,
        )
        
        # Send initial message if provided
        if initial_message:
            sdk_conversation.send_message(initial_message)
            conversation.title = initial_message[:50]
            conversation.status = ConversationStatus.RUNNING
        
        self.conversations[conversation_id] = conversation
        logger.info(
            f"Created conversation {conversation_id} "
            f"(type={agent_type}, browser={enable_browser})"
        )
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)
    
    def list_conversations(self) -> List[Conversation]:
        """List all conversations."""
        return list(self.conversations.values())
    
    def send_message(self, conversation_id: str, message: str, role: MessageRole = MessageRole.USER) -> None:
        """Send a message to a conversation."""
        conv = self.get_conversation(conversation_id)
        if conv:
            conv.sdk_conversation.send_message(message)
            conv.status = ConversationStatus.RUNNING
            
            # Emit user message event for WebSocket clients
            emit_event(conversation_id, "message", {
                "role": role.value,
                "content": message[:500]
            })
    
    async def run_conversation(self, conversation_id: str) -> None:
        """Run a conversation (process messages).
        
        Uses thread pool to avoid blocking the async event loop.
        Emits events for real-time updates (SDK-compatible).
        """
        import asyncio
        import concurrent.futures
        
        conv = self.get_conversation(conversation_id)
        if conv:
            try:
                # Emit start event
                emit_event(conversation_id, "agent_start", {"conversation_id": conversation_id})
                
                # Run in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                await loop.run_in_executor(executor, conv.sdk_conversation.run)
                
                conv.status = ConversationStatus.STOPPED
                
                # Emit completion event
                emit_event(conversation_id, "agent_finish", {
                    "conversation_id": conversation_id,
                    "status": conv.status.value
                })
            except Exception as e:
                conv.status = ConversationStatus.ERROR
                logger.error(f"Error running conversation {conversation_id}: {e}")
                # Emit error event
                emit_event(conversation_id, "error", {"error": str(e)})
    
    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation.
        
        Note: Sessions are stored in project directories, 
        not deleted when conversation is deleted.
        """
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"Deleted conversation {conversation_id}")
    
    def get_events(self, conversation_id: str) -> List[dict]:
        """Get events from a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return []
        
        events = []
        for event in conv.sdk_conversation.state.events:
            event_dict = {"type": type(event).__name__}
            if hasattr(event, "content"):
                event_dict["content"] = event.content
            if hasattr(event, "action"):
                event_dict["action"] = event.action
            if hasattr(event, "tool"):
                event_dict["tool"] = event.tool
            events.append(event_dict)
        return events
    
    def get_messages(self, conversation_id: str) -> List[dict]:
        """Get messages from a conversation."""
        conv = self.get_conversation(conversation_id)
        if not conv:
            return []
        
        messages = []
        for msg in conv.sdk_conversation.state.messages:
            msg_dict = {
                "content": msg.content,
                "role": getattr(msg, "role", "user"),
            }
            messages.append(msg_dict)
        return messages
    
    def get_stats(self) -> dict:
        """Get conversation statistics."""
        total = len(self.conversations)
        active = sum(1 for c in self.conversations.values() if c.status == ConversationStatus.RUNNING)
        return {
            "total_conversations": total,
            "active_conversations": active,
        }


# Factory function for dependency injection
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        from .project_manager import get_project_manager
        _conversation_manager = ConversationManager(
            project_manager=get_project_manager()
        )
    return _conversation_manager


def set_conversation_manager(manager: ConversationManager) -> None:
    """Set the global conversation manager instance."""
    global _conversation_manager
    _conversation_manager = manager