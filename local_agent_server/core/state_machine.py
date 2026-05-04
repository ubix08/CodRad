"""
Agent state machine and stuck detection.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """States in the agent lifecycle."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    FINISHED = "finished"
    ERROR = "error"
    STUCK = "stuck"


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""


@dataclass
class AgentMetrics:
    """Metrics for agent performance."""
    total_iterations: int = 0
    total_actions: int = 0
    total_thinks: int = 0
    tool_calls: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AgentStateMachine:
    """Manages agent state transitions."""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        AgentState.IDLE: [AgentState.STARTING, AgentState.RUNNING],
        AgentState.STARTING: [AgentState.RUNNING, AgentState.ERROR],
        AgentState.RUNNING: [AgentState.THINKING, AgentState.ACTING, AgentState.FINISHED, AgentState.ERROR],
        AgentState.THINKING: [AgentState.ACTING, AgentState.FINISHED, AgentState.ERROR],
        AgentState.ACTING: [AgentState.WAITING, AgentState.THINKING, AgentState.FINISHED, AgentState.ERROR],
        AgentState.WAITING: [AgentState.THINKING, AgentState.RUNNING, AgentState.STUCK, AgentState.ERROR],
        AgentState.FINISHED: [AgentState.IDLE],
        AgentState.ERROR: [AgentState.IDLE],
        AgentState.STUCK: [AgentState.IDLE, AgentState.RUNNING],
    }
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state = AgentState.IDLE
        self.transition_history: list[StateTransition] = []
        self.metrics = AgentMetrics()
    
    def transition(self, new_state: AgentState, reason: str = "") -> bool:
        """Attempt to transition to a new state."""
        if new_state == self.state:
            return True
        
        # Check if transition is valid
        valid_next_states = self.VALID_TRANSITIONS.get(self.state, [])
        if new_state not in valid_next_states:
            logger.warning(
                f"Invalid state transition for agent {self.agent_id}: "
                f"{self.state} -> {new_state}"
            )
            return False
        
        # Record transition
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            reason=reason
        )
        self.transition_history.append(transition)
        
        self.state = new_state
        logger.info(f"Agent {self.agent_id} transitioned: {transition.from_state} -> {transition.to_state}")
        
        return True
    
    def start(self):
        """Start the agent."""
        self.metrics.start_time = datetime.utcnow()
        self.transition(AgentState.STARTING, "Agent started")
    
    def run(self):
        """Set agent to running."""
        self.transition(AgentState.RUNNING, "Agent running")
    
    def think(self):
        """Set agent to thinking."""
        self.metrics.total_thinks += 1
        self.transition(AgentState.THINKING, "Agent thinking")
    
    def act(self):
        """Set agent to acting."""
        self.metrics.total_actions += 1
        self.transition(AgentState.ACTING, "Agent acting")
    
    def finish(self, summary: str = ""):
        """Finish the agent."""
        self.metrics.end_time = datetime.utcnow()
        self.transition(AgentState.FINISHED, summary)
    
    def error(self, error: str):
        """Set agent to error state."""
        self.metrics.errors += 1
        self.transition(AgentState.ERROR, error)
    
    def get_duration(self) -> Optional[timedelta]:
        """Get the agent's runtime duration."""
        if self.metrics.start_time:
            end = self.metrics.end_time or datetime.utcnow()
            return end - self.metrics.start_time
        return None


class StuckDetector:
    """Detects when an agent is stuck in a loop."""
    
    def __init__(
        self,
        max_repetitions: int = 3,
        max_wait_seconds: int = 300,
        similarity_threshold: float = 0.9,
    ):
        self.max_repetitions = max_repetitions
        self.max_wait_seconds = max_wait_seconds
        self.similarity_threshold = similarity_threshold
        self.last_actions: list[str] = []
        self.last_observations: list[str] = []
        self.stuck_count = 0
        self.last_action_time: Optional[datetime] = None
    
    def record_action(self, action: str):
        """Record an action for stuck detection."""
        self.last_actions.append(action)
        
        # Keep only recent actions
        if len(self.last_actions) > 10:
            self.last_actions = self.last_actions[-10:]
        
        self.last_action_time = datetime.utcnow()
    
    def record_observation(self, observation: str):
        """Record an observation for stuck detection."""
        self.last_observations.append(observation)
        
        # Keep only recent observations
        if len(self.last_observations) > 10:
            self.last_observations = self.last_observations[-10:]
    
    def is_stuck(self) -> bool:
        """Check if the agent is stuck."""
        # Check for repeated actions
        if len(self.last_actions) >= self.max_repetitions:
            recent = self.last_actions[-self.max_repetitions:]
            if len(set(recent)) == 1:  # All same action
                self.stuck_count += 1
                logger.warning(f"Agent stuck: repeated action '{recent[0]}' ({self.stuck_count} times)")
                return True
        
        # Check for timeout
        if self.last_action_time:
            elapsed = (datetime.utcnow() - self.last_action_time).total_seconds()
            if elapsed > self.max_wait_seconds:
                self.stuck_count += 1
                logger.warning(f"Agent stuck: no action for {elapsed}s")
                return True
        
        return False
    
    def reset(self):
        """Reset stuck detection state."""
        self.last_actions = []
        self.last_observations = []
        self.stuck_count = 0
        self.last_action_time = None
