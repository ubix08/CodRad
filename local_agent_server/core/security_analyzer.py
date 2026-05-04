"""
Security analyzer plugin for action validation.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Security levels for actions."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityAnalysis:
    """Result of security analysis."""
    level: SecurityLevel
    allowed: bool
    reason: str
    warnings: list[str]


class SecurityAnalyzer:
    """Analyzes actions for security concerns."""
    
    # Dangerous patterns for different action types
    DANGEROUS_PATTERNS = {
        "terminal": [
            (r"rm\s+-rf\s+/", SecurityLevel.CRITICAL, "Recursive deletion of root"),
            (r"rm\s+-rf\s+/tmp", SecurityLevel.HIGH, "Deletion of tmp directory"),
            (r":\(\)\s*\{\s*:\|\:&\s*\}", SecurityLevel.CRITICAL, "Fork bomb"),
            (r"dd\s+if=/dev/zero", SecurityLevel.HIGH, "Disk write operation"),
            (r">\s*/dev/sd[a-z]", SecurityLevel.CRITICAL, "Direct disk write"),
            (r"chmod\s+-R\s+777", SecurityLevel.MEDIUM, "World-writable permissions"),
            (r"chown\s+-R", SecurityLevel.MEDIUM, "Ownership change"),
            (r"wget.*\|\s*sh", SecurityLevel.HIGH, "Remote code execution"),
            (r"curl.*\|\s*sh", SecurityLevel.HIGH, "Remote code execution"),
            (r"nc\s+-e\s+", SecurityLevel.CRITICAL, "Reverse shell"),
            (r"/etc/passwd", SecurityLevel.CRITICAL, "System file access"),
            (r"sudo\s+rm", SecurityLevel.HIGH, "Privileged deletion"),
            (r"kill\s+-9\s+-1", SecurityLevel.CRITICAL, "Kill all processes"),
        ],
        "file_editor": [
            (r"\.ssh/authorized_keys", SecurityLevel.CRITICAL, "SSH authorized keys modification"),
            (r"\.git/config", SecurityLevel.MEDIUM, "Git config modification"),
            (r"/etc/shadow", SecurityLevel.CRITICAL, "Password file access"),
            (r"\.env", SecurityLevel.MEDIUM, "Environment file access"),
            (r"password|secret|api[_-]?key", SecurityLevel.MEDIUM, "Potential secret exposure"),
        ],
        "http_request": [
            (r"localhost.*admin", SecurityLevel.LOW, "Local admin access"),
            (r"127\.0\.0\.1", SecurityLevel.LOW, "Local network access"),
            (r"10\.\d+\.\d+\.\d+", SecurityLevel.LOW, "Private network access"),
            (r"192\.168\.\d+\.\d+", SecurityLevel.LOW, "Private network access"),
            (r"172\.(1[6-9]|2[0-9]|3[0-1])\.", SecurityLevel.LOW, "Private network access"),
        ],
    }
    
    # Sensitive data patterns
    SENSITIVE_PATTERNS = [
        r"password\s*[=:]\s*\S+",
        r"api[_-]?key\s*[=:]\s*\S+",
        r"secret[_-]?key\s*[=:]\s*\S+",
        r"token\s*[=:]\s*\S+",
        r"bearer\s+\S+",
        r"ghp_[a-zA-Z0-9]{36}",
        r"sk-[a-zA-Z0-9]{48}",
    ]
    
    def analyze_terminal(self, command: str) -> SecurityAnalysis:
        """Analyze terminal command for security concerns."""
        command_lower = command.lower()
        
        for pattern, level, reason in self.DANGEROUS_PATTERNS.get("terminal", []):
            if re.search(pattern, command_lower):
                return SecurityAnalysis(
                    level=level,
                    allowed=level != SecurityLevel.CRITICAL,
                    reason=reason,
                    warnings=[],
                )
        
        return SecurityAnalysis(
            level=SecurityLevel.SAFE,
            allowed=True,
            reason="Command appears safe",
            warnings=[],
        )
    
    def analyze_file_operation(self, path: str, operation: str) -> SecurityAnalysis:
        """Analyze file operation for security concerns."""
        path_lower = path.lower()
        
        for pattern, level, reason in self.DANGEROUS_PATTERNS.get("file_editor", []):
            if re.search(pattern, path_lower):
                return SecurityAnalysis(
                    level=level,
                    allowed=level != SecurityLevel.CRITICAL,
                    reason=reason,
                    warnings=[],
                )
        
        # Check for sensitive data
        warnings = []
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, path_lower):
                warnings.append(f"Path contains potential sensitive data")
                break
        
        return SecurityAnalysis(
            level=SecurityLevel.SAFE if not warnings else SecurityLevel.LOW,
            allowed=True,
            reason="File operation appears safe",
            warnings=warnings,
        )
    
    def analyze_http_request(self, url: str) -> SecurityAnalysis:
        """Analyze HTTP request for security concerns."""
        url_lower = url.lower()
        
        for pattern, level, reason in self.DANGEROUS_PATTERNS.get("http_request", []):
            if re.search(pattern, url_lower):
                return SecurityAnalysis(
                    level=level,
                    allowed=True,  # Always allow but warn
                    reason=reason,
                    warnings=[f"Request to {reason}"],
                )
        
        # Check for HTTPS
        if not url.startswith("https://"):
            return SecurityAnalysis(
                level=SecurityLevel.LOW,
                allowed=True,
                reason="Non-HTTPS request",
                warnings=["Using unencrypted HTTP connection"],
            )
        
        return SecurityAnalysis(
            level=SecurityLevel.SAFE,
            allowed=True,
            reason="Request appears safe",
            warnings=[],
        )
    
    def analyze_action(self, action_type: str, action_data: dict) -> SecurityAnalysis:
        """Analyze any action for security concerns."""
        if action_type == "terminal":
            return self.analyze_terminal(action_data.get("command", ""))
        
        elif action_type == "file_editor":
            return self.analyze_file_operation(
                action_data.get("path", ""),
                action_data.get("command", "")
            )
        
        elif action_type in ["http_request", "browse"]:
            return self.analyze_http_request(action_data.get("url", ""))
        
        # Default: allow unknown actions but warn
        return SecurityAnalysis(
            level=SecurityLevel.LOW,
            allowed=True,
            reason="Unknown action type",
            warnings=[f"Action type '{action_type}' not analyzed"],
        )


# Global analyzer instance
security_analyzer = SecurityAnalyzer()
