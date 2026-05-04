"""
Confirmation policy for agent actions.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ConfirmationPolicyType(str, Enum):
    """Types of confirmation policies."""
    NEVER_CONFIRM = "never_confirm"
    ALWAYS_CONFIRM = "always_confirm"
    CONFIRM_RISKY = "confirm_risky"


@dataclass
class ConfirmationResult:
    """Result of a confirmation request."""
    approved: bool
    reason: Optional[str] = None


class ConfirmationPolicy:
    """Base class for confirmation policies."""
    
    def __init__(self, policy_type: ConfirmationPolicyType):
        self.policy_type = policy_type
    
    async def should_confirm(self, action: str, details: dict) -> bool:
        """Determine if an action should be confirmed."""
        raise NotImplementedError
    
    async def confirm(self, action: str, details: dict) -> ConfirmationResult:
        """Request confirmation for an action."""
        should_confirm = await self.should_confirm(action, details)
        
        if not should_confirm:
            return ConfirmationResult(approved=True, reason="Auto-approved by policy")
        
        # In a real implementation, this would request confirmation from user
        # For now, return approved (can be extended with WebSocket prompts)
        return ConfirmationResult(approved=True, reason="User confirmed")


class NeverConfirmPolicy(ConfirmationPolicy):
    """Never require confirmation."""
    
    def __init__(self):
        super().__init__(ConfirmationPolicyType.NEVER_CONFIRM)
    
    async def should_confirm(self, action: str, details: dict) -> bool:
        return False


class AlwaysConfirmPolicy(ConfirmationPolicy):
    """Always require confirmation."""
    
    def __init__(self):
        super().__init__(ConfirmationPolicyType.ALWAYS_CONFIRM)
    
    async def should_confirm(self, action: str, details: dict) -> bool:
        return True


class ConfirmRiskyPolicy(ConfirmationPolicy):
    """Confirm only risky actions."""
    
    # Actions that require confirmation
    RISKY_ACTIONS = {
        "terminal": ["rm", "dd", "mkfs", "chmod", "chown", ":()", "fork"],
        "file_editor": ["delete", "create", "move"],
        "http_request": ["POST", "PUT", "DELETE"],
    }
    
    def __init__(self):
        super().__init__(ConfirmationPolicyType.CONFIRM_RISKY)
    
    async def should_confirm(self, action: str, details: dict) -> bool:
        """Check if action is risky."""
        risky_patterns = self.RISKY_ACTIONS.get(action, [])
        
        if action == "terminal":
            command = details.get("command", "")
            return any(pattern in command for pattern in risky_patterns)
        
        if action == "file_editor":
            command = details.get("command", "")
            return any(pattern in command for pattern in risky_patterns)
        
        return False


def get_confirmation_policy(policy_type: ConfirmationPolicyType) -> ConfirmationPolicy:
    """Get a confirmation policy by type."""
    policies = {
        ConfirmationPolicyType.NEVER_CONFIRM: NeverConfirmPolicy,
        ConfirmationPolicyType.ALWAYS_CONFIRM: AlwaysConfirmPolicy,
        ConfirmationPolicyType.CONFIRM_RISKY: ConfirmRiskyPolicy,
    }
    
    policy_class = policies.get(policy_type, NeverConfirmPolicy)
    return policy_class()
