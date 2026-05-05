"""Agent factory service - Creates OpenHands agents with exact same config as original agent-server."""

import os
import logging
from pathlib import Path
from typing import Optional, List

from openhands.sdk import LLM, Agent, AgentContext
from openhands.sdk.context import Skill
from openhands.tools.preset.default import get_default_tools
from pydantic import SecretStr

from ..models.schemas import AgentType
from ..core.config import (
    LLM_PROVIDER,
    get_llm_api_key,
    get_provider_base_url,
    get_provider_default_model,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TOP_P,
)

logger = logging.getLogger(__name__)

# System prompt that matches original agent-server
PLANNING_AGENT_INSTRUCTION = """<IMPORTANT_PLANNING_BOUNDARIES>
You are a planning agent. Your role is to:
1. Understand the user's goal
2. Break down the task into steps
3. Execute each step using available tools
4. When done, use the "finish" action with a summary

Important rules:
- Always confirm before making irreversible changes
- Keep track of what you've done
- Ask for clarification if the goal is unclear
</IMPORTANT_PLANNING_BOUNDARIES>"""

DEFAULT_SYSTEM_PROMPT = """You are an expert AI coding assistant.

Your role:
1. Write clean, well-documented code
2. Use type hints in Python
3. Add docstrings to all public functions
4. Handle errors gracefully
5. Write tests for new features
6. Keep functions under 50 lines

When editing files:
- Use absolute paths in the workspace
- Create directories as needed
- Always verify changes work

When completing a task:
- Summarize what was done
- Use the finish action
"""


class AgentFactory:
    """Factory for creating OpenHands agents.
    
    Replicates the exact behavior from:
    openhands/app_server/app_conversation/live_status_app_conversation_service.py
    """
    
    def __init__(self):
        self.default_model = get_provider_default_model()
        self.default_enable_browser = os.getenv("ENABLE_BROWSER", "true").lower() == "true"
        self.default_agent_type = AgentType.DEFAULT
        
    def create_llm(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> LLM:
        """Create an LLM instance with full configuration."""
        # For OpenRouter, litellm handles routing automatically - don't pass base_url
        effective_model = model or self.default_model
        
        # Get base_url from parameter or environment
        final_base_url = base_url or os.getenv("LLM_BASE_URL", "") or os.getenv("OPENAI_BASE_URL", "")
        
        if effective_model and effective_model.startswith("openrouter/"):
            final_base_url = ""  # Empty allows litellm to route automatically
        
        return LLM(
            usage_id="local-agent",
            model=effective_model,
            api_key=SecretStr(api_key),
            base_url=final_base_url,
        )
    
    def get_tools(self, agent_type: AgentType, enable_browser: bool = True):
        """Get tools for the agent type.
        
        Matches original get_default_tools() and get_planning_tools() calls.
        """
        if agent_type == AgentType.PLANNING:
            # Planning agent uses limited tools
            from openhands.tools.task_tracker import TaskTrackerTool
            return [TaskTrackerTool]
        else:
            # Default/code agent uses full toolset
            return get_default_tools(enable_browser=enable_browser)
    
    def load_skills(self) -> List[Skill]:
        """Load skills from local directories.
        
        Loads skills from our local skills system.
        """
        skills: List[Skill] = []
        
        # Get our skill registry
        from ..skills import get_skill_registry
        registry = get_skill_registry()
        
        # Convert our Skill to SDK Skill format
        for skill_meta in registry.list_skills():
            skill_obj = registry.get_skill(skill_meta.name)
            if skill_obj:
                skill = Skill(
                    name=skill_obj.name,
                    content=skill_obj.get_prompt(),
                    trigger=None,  # Skills always available to agent
                )
                skills.append(skill)
        
        logger.info(f"Loaded {len(skills)} skills from local registry")
        return skills
    
    def build_system_message_suffix(
        self,
        agent_type: AgentType,
        custom_suffix: Optional[str] = None,
    ) -> str:
        """Build the effective system_message_suffix.
        
        Matches original lines 1379-1396.
        """
        suffix = custom_suffix or ""
        
        # Add web host context if available
        web_url = os.getenv("WEB_URL")
        if web_url:
            suffix += f"\n\n<HOST>\n{web_url}\n</HOST>"
        
        # Add planning agent instruction if needed
        if agent_type == AgentType.PLANNING:
            if suffix:
                suffix = f"{PLANNING_AGENT_INSTRUCTION}\n\n{suffix}"
            else:
                suffix = PLANNING_AGENT_INSTRUCTION
        
        return suffix
    
    def create_agent(
        self,
        api_key: str,
        agent_type: AgentType = AgentType.DEFAULT,
        enable_browser: Optional[bool] = None,
        model: Optional[str] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> Agent:
        """Create an OpenHands agent with exact same config as original.
        
        This replicates the behavior from:
        openhands/app_server/app_conversation/live_status_app_conversation_service.py
        lines ~1400-1425
        """
        enable_browser = enable_browser if enable_browser is not None else self.default_enable_browser
        
        # 1. Create LLM
        llm = self.create_llm(api_key, model)
        logger.info(f"Created LLM: model={model or self.default_model}")
        
        # 2. Get tools - EXACT same as original (line 1405)
        tools = self.get_tools(agent_type, enable_browser)
        logger.info(f"Loaded {len(tools)} tools (browser={enable_browser}, type={agent_type})")
        
        # 3. ONLY load default skill - NOT all skills!
        # Skills are triggered on-demand, not loaded into context
        
        # 4. Add default skill (acts as system prompt)
        default_skill = Skill(
            name="coding-assistant",
            content=custom_system_prompt or DEFAULT_SYSTEM_PROMPT,
            trigger=None,  # Always active
        )
        # Only default skill in context
        
        # 5. Build system_message_suffix
        effective_suffix = self.build_system_message_suffix(agent_type)
        
        # 6. Create AgentContext (matches original line 1415-1418)
        # ORIGINAL OPENHANDS BEHAVIOR:
        # - load_public_skills=True: loads skills from GitHub repo on-demand
        # - load_user_skills=True: loads skills from ~/.openhands/skills/
        # - Skills are triggered by keywords in user message
        from openhands.sdk.context import AgentContext
        agent_context = AgentContext(
            skills=[default_skill],
            system_message_suffix=effective_suffix,
            load_public_skills=True,  # Enable public skills
            load_user_skills=True,  # Enable user skills
        )
        
        # 7. Create Agent (matches original line 1421)
        agent = Agent(
            llm=llm,
            tools=tools,
            agent_context=agent_context,
        )
        
        logger.info(
            f"Created agent: type={agent_type}, "
            f"skills=1 (triggered on-demand), "
            f"tools={len(tools)}"
        )
        
        return agent


# Singleton instance
agent_factory = AgentFactory()


def get_agent_factory() -> AgentFactory:
    """Get the global agent factory instance."""
    return agent_factory