"""
File system restrictions and sandboxing for local execution.
"""

import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FileRestrictions:
    """File system restrictions configuration."""
    allowed_paths: list[str]  # List of allowed path patterns
    blocked_paths: list[str]   # List of blocked path patterns
    max_file_size: int        # Max file size in bytes
    readonly_patterns: list[str]  # Patterns for read-only files
    
    def is_allowed(self, path: str) -> bool:
        """Check if a path is allowed."""
        path_obj = Path(path).resolve()
        
        # Check blocked patterns first
        for pattern in self.blocked_paths:
            if self._match_pattern(str(path_obj), pattern):
                return False
        
        # Check allowed patterns
        if not self.allowed_paths:
            return True  # No restrictions
        
        for pattern in self.allowed_paths:
            if self._match_pattern(str(path_obj), pattern):
                return True
        
        return False
    
    def is_readonly(self, path: str) -> bool:
        """Check if a path is read-only."""
        for pattern in self.readonly_patterns:
            if self._match_pattern(path, pattern):
                return True
        return False
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match a path against a pattern (supports wildcards)."""
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("**", ".*")
        regex_pattern = regex_pattern.replace("*", "[^/]*")
        regex_pattern = regex_pattern.replace("?", "[^/]")
        
        return bool(re.match(f"^{regex_pattern}$", path, re.IGNORECASE))


class FileSystemSandbox:
    """File system sandbox for restricting file access."""
    
    DEFAULT_RESTRICTIONS = FileRestrictions(
        allowed_paths=[
            "/home/*/agent-workspaces/*",  # User workspaces
            "/tmp/*",
            "/workspace/*",
        ],
        blocked_paths=[
            "/etc/passwd",
            "/etc/shadow",
            "/etc/sudoers",
            "/root/.ssh/*",
            "/home/*/.ssh/*",
            "/.git/config",
            "**/.git/credentials",
            "**/id_rsa*",
            "**/id_ed25519*",
        ],
        max_file_size=100 * 1024 * 1024,  # 100MB
        readonly_patterns=[
            "/etc/*",
            "/usr/bin/*",
            "/usr/lib/*",
        ],
    )
    
    def __init__(self, restrictions: Optional[FileRestrictions] = None):
        self.restrictions = restrictions or self.DEFAULT_RESTRICTIONS
    
    def check_path(self, path: str) -> bool:
        """Check if a path is allowed."""
        return self.restrictions.is_allowed(path)
    
    def check_readonly(self, path: str) -> bool:
        """Check if a path is read-only."""
        return self.restrictions.is_readonly(path)
    
    def sanitize_path(self, path: str, workspace_root: str) -> str:
        """Sanitize and validate a path within workspace."""
        # Resolve to absolute path
        abs_path = os.path.abspath(os.path.join(workspace_root, path))
        
        # Check it's within workspace
        workspace_resolved = os.path.abspath(workspace_root)
        if not abs_path.startswith(workspace_resolved):
            logger.warning(f"Path {path} outside workspace, restricting to {workspace_root}")
            abs_path = workspace_resolved
        
        # Check restrictions
        if not self.check_path(abs_path):
            raise PermissionError(f"Access denied to path: {path}")
        
        return abs_path
    
    def check_file_size(self, file_path: str) -> bool:
        """Check if file size is within limits."""
        try:
            size = os.path.getsize(file_path)
            return size <= self.restrictions.max_file_size
        except OSError:
            return True  # Allow if we can't check
    
    def get_safe_workspace(self, workspace_id: str) -> str:
        """Get and create workspace directory."""
        workspace_root = os.getenv("WORKSPACE_ROOT", "/home/openhands/agent-workspaces")
        workspace_path = os.path.join(workspace_root, workspace_id)
        
        # Ensure workspace exists
        os.makedirs(workspace_path, exist_ok=True)
        
        return workspace_path


# Global sandbox instance
file_sandbox = FileSystemSandbox()
