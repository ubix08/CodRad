"""
Callback/Hook system for agent lifecycle events.
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Events that can trigger hooks."""
    BEFORE_AGENT_START = "before_agent_start"
    AFTER_AGENT_START = "after_agent_start"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_MESSAGE = "before_message"
    AFTER_MESSAGE = "after_message"
    BEFORE_THINK = "before_think"
    AFTER_THINK = "after_think"
    AGENT_ERROR = "agent_error"
    AGENT_FINISHED = "agent_finished"


class ActionType(str, Enum):
    """Types of actions the agent can take."""
    TERMINAL = "terminal"
    FILE_EDITOR = "file_editor"
    TASK_TRACKER = "task_tracker"
    THINK = "think"
    FINISH = "finish"
    BROWSE = "browse"


@dataclass
class HookContext:
    """Context passed to hooks."""
    conversation_id: str
    agent_type: str
    workspace_dir: str
    event: HookEvent
    action: ActionType = None
    tool_input: dict = field(default_factory=dict)
    tool_output: Any = None
    message: str = ""
    error: str = None
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HookResult:
    """Result from a hook."""
    allowed: bool = True
    modified_input: dict = None
    modified_output: Any = None
    modified_message: str = None
    error_message: str = None
    metadata: dict = field(default_factory=dict)


# Hook function signature: async def hook(context: HookContext) -> HookResult
HookFunction = Callable[[HookContext], Awaitable[HookResult]]


class HookRegistry:
    """Registry for managing hooks."""
    
    def __init__(self):
        self.hooks: dict[HookEvent, list[tuple[str, HookFunction]]] = {}
    
    def register(self, event: HookEvent, name: str, hook: HookFunction):
        """Register a hook for an event."""
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append((name, hook))
        logger.info(f"Registered hook '{name}' for event '{event}'")
    
    def unregister(self, event: HookEvent, name: str):
        """Unregister a hook."""
        if event in self.hooks:
            self.hooks[event] = [(n, h) for n, h in self.hooks[event] if n != name]
            logger.info(f"Unregistered hook '{name}' from event '{event}'")
    
    async def trigger(self, event: HookEvent, context: HookContext) -> HookResult:
        """Trigger all hooks for an event."""
        result = HookResult()
        
        if event not in self.hooks:
            return result
        
        for name, hook in self.hooks[event]:
            try:
                hook_result = await hook(context)
                
                # Merge results
                if not hook_result.allowed:
                    result.allowed = False
                    result.error_message = hook_result.error_message
                
                if hook_result.modified_input:
                    result.modified_input = hook_result.modified_input
                
                if hook_result.modified_output:
                    result.modified_output = hook_result.modified_output
                
                if hook_result.modified_message:
                    result.modified_message = hook_result.modified_message
                    
            except Exception as e:
                logger.error(f"Hook '{name}' failed: {e}")
        
        return result


# Global hook registry
hooks = HookRegistry()


# Example: Security hook
async def security_hook(context: HookContext) -> HookResult:
    """Security hook to validate actions."""
    result = HookResult()
    
    # Block dangerous commands
    if context.action == ActionType.TERMINAL:
        command = context.tool_input.get("command", "")
        
        dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r":(){ :|:& };:",  # Fork bomb
            r"dd\s+if=/dev/zero",
            r">\s*/dev/sd",
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                result.allowed = False
                result.error_message = f"Dangerous command blocked: {command}"
                break
    
    return result


# Example: Logging hook
async def logging_hook(context: HookContext) -> HookResult:
    """Logging hook for all events."""
    logger.info(f"Hook triggered: {context.event} for conversation {context.conversation_id}")
    return HookResult()


# Register default hooks
hooks.register(HookEvent.BEFORE_TOOL_CALL, "security", security_hook)
hooks.register(HookEvent.AFTER_TOOL_CALL, "logging", logging_hook)
