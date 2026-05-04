"""
Runtime metrics for agent performance tracking.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationMetrics:
    """Metrics for a single conversation."""
    conversation_id: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    
    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hits: int = 0
    cache_hits_pct: float = 0.0
    
    # LLM calls
    llm_calls: int = 0
    
    # Costs (USD)
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    
    # Timing
    total_duration_seconds: float = 0.0
    
    # Agent actions
    total_actions: int = 0
    tool_calls: dict = field(default_factory=dict)
    errors: int = 0
    
    # State
    iterations: int = 0
    max_iterations: int = 100


@dataclass  
class ServerMetrics:
    """Server-wide metrics."""
    total_conversations: int = 0
    active_conversations: int = 0
    completed_conversations: int = 0
    failed_conversations: int = 0
    
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    
    uptime_start: datetime = field(default_factory=datetime.now)
    
    # By model
    model_usage: dict = field(default_factory=dict)


class MetricsCollector:
    """Collects and tracks metrics."""
    
    def __init__(self):
        self.server_metrics = ServerMetrics()
        self.conversations: dict[str, ConversationMetrics] = {}
    
    def start_conversation(self, conversation_id: str) -> ConversationMetrics:
        """Start tracking a conversation."""
        metrics = ConversationMetrics(conversation_id=conversation_id)
        self.conversations[conversation_id] = metrics
        self.server_metrics.active_conversations += 1
        self.server_metrics.total_conversations += 1
        return metrics
    
    def end_conversation(self, conversation_id: str, status: str = "completed"):
        """End tracking a conversation."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.ended_at = datetime.now()
            m.total_duration_seconds = (m.ended_at - m.started_at).total_seconds()
            
            self.server_metrics.active_conversations -= 1
            if status == "completed":
                self.server_metrics.completed_conversations += 1
            else:
                self.server_metrics.failed_conversations += 1
    
    def record_tool_call(self, conversation_id: str, tool_name: str):
        """Record a tool call."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.total_actions += 1
            m.tool_calls[tool_name] = m.tool_calls.get(tool_name, 0) + 1
    
    def record_tokens(self, conversation_id: str, input_tokens: int = 0, output_tokens: int = 0):
        """Record token usage."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.input_tokens += input_tokens
            m.output_tokens += output_tokens
            m.llm_calls += 1
            
            # Calculate costs (rough estimate)
            # Input: $0.001/1K tokens, Output: $0.005/1K
            m.input_cost = (m.input_tokens / 1000) * 0.001
            m.output_cost = (m.output_tokens / 1000) * 0.005
            m.total_cost = m.input_cost + m.output_cost
    
    def record_cache_hit(self, conversation_id: str):
        """Record a cache hit."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.cache_hits += 1
    
    def record_iteration(self, conversation_id: str):
        """Record an iteration."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.iterations += 1
            if m.iterations >= m.max_iterations:
                logger.warning(f"Conversation {conversation_id} hit max iterations")
    
    def record_error(self, conversation_id: str):
        """Record an error."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            m.errors += 1
    
    def calculate_cache_hit_rate(self, conversation_id: str):
        """Calculate cache hit percentage."""
        if conversation_id in self.conversations:
            m = self.conversations[conversation_id]
            if m.llm_calls > 0:
                m.cache_hits_pct = (m.cache_hits / m.llm_calls) * 100
            return m.cache_hits_pct
        return 0.0
    
    def get_conversation_metrics(self, conversation_id: str) -> Optional[ConversationMetrics]:
        """Get metrics for a conversation."""
        return self.conversations.get(conversation_id)
    
    def get_server_metrics(self) -> ServerMetrics:
        """Get server-wide metrics."""
        self.server_metrics.total_tokens = sum(
            m.input_tokens + m.output_tokens 
            for m in self.conversations.values()
        )
        self.server_metrics.total_cost = sum(
            m.total_cost for m in self.conversations.values()
        )
        return self.server_metrics
    
    def get_summary(self) -> dict:
        """Get metrics summary."""
        metrics = self.get_server_metrics()
        return {
            "total_conversations": metrics.total_conversations,
            "active": metrics.active_conversations,
            "completed": metrics.completed_conversations,
            "failed": metrics.failed_conversations,
            "total_tokens": metrics.total_tokens,
            "total_cost": round(metrics.total_cost, 4),
            "uptime_seconds": (datetime.now() - metrics.uptime_start).total_seconds(),
        }


# Global metrics collector
metrics_collector = MetricsCollector()