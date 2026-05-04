"""
Agent critique/review system for quality assurance.
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CritiqueLevel(str, Enum):
    """Critique severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUGGESTION = "suggestion"


@dataclass
class CritiqueItem:
    """A single critique item."""
    level: CritiqueLevel
    category: str  # code_quality, security, performance, etc.
    message: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CritiqueResult:
    """Result of agent critique."""
    score: float  # 0-100
    items: list[CritiqueItem]
    summary: str
    passed: bool


class AgentCritique:
    """Critiques agent outputs for quality."""
    
    def __init__(self, llm=None):
        self.llm = llm
    
    async def critique_action(self, action: str, action_type: str) -> list[CritiqueItem]:
        """Critique an agent action."""
        critiques = []
        
        # Check for common issues
        if action_type == "terminal":
            # Check for dangerous commands
            if "rm -rf" in action:
                critiques.append(CritiqueItem(
                    level=CritiqueLevel.WARNING,
                    category="safety",
                    message="Recursive delete command detected",
                    suggestion="Consider using more specific delete commands",
                ))
            
            # Check for potential mistakes
            if "git push" in action and "--force" in action:
                critiques.append(CritiqueItem(
                    level=CritiqueLevel.WARNING,
                    category="git",
                    message="Force push detected",
                    suggestion="Avoid force pushes as they can overwrite history",
                ))
        
        elif action_type == "file_editor":
            # Check file operations
            if "delete" in action.lower():
                critiques.append(CritiqueItem(
                    level=CritiqueLevel.INFO,
                    category="file_operation",
                    message="File deletion detected",
                    suggestion="Ensure this file is intentionally being deleted",
                ))
        
        return critiques
    
    async def critique_code(self, code: str, language: str = "python") -> CritiqueResult:
        """Critique code for quality issues."""
        items = []
        score = 100
        
        # Basic checks
        if not code or len(code.strip()) == 0:
            return CritiqueResult(
                score=0,
                items=[],
                summary="No code provided",
                passed=False,
            )
        
        # Check for common issues
        lines = code.split("\n")
        
        # Check for very long lines
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                items.append(CritiqueItem(
                    level=CritiqueLevel.SUGGESTION,
                    category="code_style",
                    message=f"Line {i} exceeds 120 characters ({len(line)} chars)",
                    suggestion="Consider breaking long lines for readability",
                    line_number=i,
                ))
                score -= 0.5
        
        # Check for TODO comments
        if "# TODO" in code or "# FIXME" in code:
            items.append(CritiqueItem(
                level=CritiqueLevel.INFO,
                category="maintenance",
                message="TODO/FIXME comments found",
                suggestion="Address these items or create tracking issues",
            ))
        
        # Check for print statements in Python
        if language == "python" and "print(" in code:
            count = code.count("print(")
            if count > 5:
                items.append(CritiqueItem(
                    level=CritiqueLevel.SUGGESTION,
                    category="code_style",
                    message=f"{count} print statements found",
                    suggestion="Consider using proper logging instead of print statements",
                ))
        
        # Determine if passed
        passed = score >= 70
        
        summary = f"Code review: {len(items)} issues found, score: {score:.1f}/100"
        
        return CritiqueResult(
            score=score,
            items=items,
            summary=summary,
            passed=passed,
        )
    
    async def critique_response(self, response: str) -> CritiqueResult:
        """Critique an agent's text response."""
        items = []
        score = 100
        
        if not response:
            return CritiqueResult(
                score=0,
                items=[],
                summary="Empty response",
                passed=False,
            )
        
        # Check response length
        if len(response) < 10:
            items.append(CritiqueItem(
                level=CritiqueLevel.WARNING,
                category="response_quality",
                message="Response is very short",
                suggestion="Provide more detailed information",
            ))
            score -= 10
        
        # Check for incomplete sentences
        if response.rstrip()[-1] not in ".!?":
            items.append(CritiqueItem(
                level=CritiqueLevel.INFO,
                category="response_quality",
                message="Response doesn't end with proper punctuation",
            ))
            score -= 2
        
        passed = score >= 70
        
        return CritiqueResult(
            score=score,
            items=items,
            summary=f"Response review: score {score:.1f}/100",
            passed=passed,
        )


# Global critique instance
agent_critique = AgentCritique()
