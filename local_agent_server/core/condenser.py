"""
Condenser for LLM summarization of long conversations.
"""

from typing import Optional
import logging

from openhands.sdk.llm import LLM

logger = logging.getLogger(__name__)


class ConversationCondenser:
    """Condenses long conversations using LLM summarization."""
    
    def __init__(self, llm: LLM, max_size: int = 10000):
        self.llm = llm
        self.max_size = max_size
    
    async def condense(self, messages: list) -> list:
        """Condense messages to fit within max_size.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Condensed list of messages
        """
        if not messages:
            return []
        
        # Calculate total size
        total_size = sum(len(str(m)) for m in messages)
        
        if total_size <= self.max_size:
            return messages
        
        logger.info(f"Condensing conversation: {total_size} chars -> {self.max_size}")
        
        # Keep first few messages (system, initial prompt)
        keep_count = min(3, len(messages) // 4)
        kept_messages = messages[:keep_count]
        
        # Summarize the rest
        to_summarize = messages[keep_count:]
        
        if not to_summarize:
            return kept_messages
        
        summary = await self._summarize_messages(to_summarize)
        
        # Create a summary message
        summary_message = {
            "role": "system",
            "content": f"[Earlier conversation summarized: {summary}]"
        }
        
        return kept_messages + [summary_message]
    
    async def _summarize_messages(self, messages: list) -> str:
        """Summarize a list of messages."""
        # Create a prompt for summarization
        conversation_text = "\n".join([
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in messages
        ])
        
        prompt = f"""Summarize this conversation briefly, preserving key information:

{conversation_text}

Provide a concise summary (under 500 words):"""
        
        try:
            # This is a simplified version - in production you'd use the LLM
            # For now, return a placeholder
            summary = f"[Summary of {len(messages)} messages]"
            logger.info(f"Generated summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Failed to summarize: {e}")
            return f"[{len(messages)} messages were omitted]"
    
    async def should_condense(self, messages: list) -> bool:
        """Check if condensation is needed."""
        total_size = sum(len(str(m)) for m in messages)
        return total_size > self.max_size


class LLMSummarizingCondenser:
    """Production condenser using LLM."""
    
    def __init__(self, llm: LLM, max_size: int = 10000):
        self.llm = llm
        self.max_size = max_size
    
    async def condense(self, messages: list) -> list:
        """Condense messages using LLM."""
        if not messages:
            return []
        
        # Check if we need to condense
        total_size = sum(len(str(m)) for m in messages)
        if total_size <= self.max_size:
            return messages
        
        # Keep system messages and first few
        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]
        
        keep_count = min(5, len(other_messages) // 5)
        kept = system_messages + other_messages[:keep_count]
        to_summarize = other_messages[keep_count:]
        
        if not to_summarize:
            return kept
        
        # Summarize middle messages
        summary = await self._llm_summarize(to_summarize)
        
        summary_msg = {
            "role": "system",
            "content": f"[Previous conversation summarized: {summary}]"
        }
        
        return kept + [summary_msg]
    
    async def _llm_summarize(self, messages: list) -> str:
        """Use LLM to summarize messages."""
        conversation = "\n\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')[:500]}"
            for m in messages
        ])
        
        prompt = f"""Summarize this conversation concisely, preserving important details:

{conversation}

Summary:"""
        
        try:
            response = await self.llmachat(
                [{"role": "user", "content": prompt}]
            )
            return response.content[-1].text if response.content else "Summary unavailable"
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return f"[{len(messages)} messages omitted]"
