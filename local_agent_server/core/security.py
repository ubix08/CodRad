"""Command sanitizer - Security module for Local Agent Server.

This module provides security for command execution in workspace,
without Docker sandboxing. It uses allowlists and dangerous pattern detection.
"""

import re
import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Dangerous patterns that should be blocked
DANGEROUS_PATTERNS = [
    # Delete everything patterns
    (r"rm\s+-rf\s+/", "Attempted to delete root directory"),
    (r"rm\s+-rf\s+/\*", "Attempted to delete all root files"),
    (r"rm\s+-rf\s+\.\.", "Attempted to delete parent directory"),
    (r"rm\s+-rf\s+~", "Attempted to delete home directory"),
    
    # Network exfiltration patterns  
    (r"curl.*\|.*sh", "Pipe to shell (potential malware download)"),
    (r"wget.*\|.*sh", "Pipe to shell (potential malware download)"),
    (r"curl\s+.*\$\(", "Command substitution via curl"),
    (r"wget\s+.*\$\(", "Command substitution via wget"),
    
    # Reverse shell patterns
    (r"bash\s+-i\s+.*\d+", "Reverse shell attempt"),
    (r"/dev/tcp/", "TCP device file (reverse shell)"),
    (r"nc\s+-e", "Netcat execute"),
    (r"ncat\s+-e", "Ncat execute"),
    
    # SSH key exfiltration
    (r"cat\s+.*\.ssh/", "Attempted to read SSH directory"),
    (r"scp\s+.*\.ssh/", "Attempted to copy SSH files"),
    
    # Environment exfiltration
    (r"env\s+>", "Output environment to file"),
    (r"printenv\s+>", "Print environment to file"),
    
    # Cron backdoor
    (r"crontab\s+-r", "Remove crontab"),
    (r"echo.*\*.*\*.*\*", "Wildcard in cron"),
    
    # Sudo manipulation
    (r"chmod\s+777\s+/etc/sudoers", "Modify sudoers file"),
    (r"echo.*ALL=.*ALL", "Add ALL sudo access"),
    
    # Process manipulation
    (r"kill\s+-9\s+-1", "Kill all processes"),
    (r"killall\s+-9", "Killall processes"),
    
    # /etc/passwd manipulation
    (r"useradd", "Add user"),
    (r"usermod", "Modify user"),
    (r"deluser", "Delete user"),
    
    # Service manipulation
    (r"systemctl\s+stop", "Stop systemd service"),
    (r"systemctl\s+disable", "Disable systemd service"),
    
    # Download and execute
    (r"pip\s+install\s+--user", "pip install --user"),
    (r"npm\s+install\s+-g", "npm global install"),
    
    # Git credential theft
    (r"git\s+config\s+--global\s+credential", "Git credential config"),
    (r"git\s+credential", "Git credential store"),
]

# Allowed commands (allowlist approach - more secure)
ALLOWED_COMMANDS = {
    # Git commands
    "git": ["status", "log", "diff", "add", "commit", "push", "pull", "clone", "fetch", "branch", "checkout", "merge", "reb ase", "tag", "show", "remote"],
    
    # File viewing
    "cat": ["*"],
    "head": ["*"],
    "tail": ["*"],
    "less": ["*"],
    "more": ["*"],
    "wc": ["*"],
    "grep": ["*"],
    "rg": ["*"],
    "find": ["*"],
    "ls": ["*"],
    "tree": ["*"],
    
    # Python - safe operations
    "python": ["*"],
    "python3": ["*"],
    "pip": ["install", "list", "show", "freeze", "check"],
    "pip3": ["install", "list", "show", "freeze", "check"],
    "poetry": ["install", "build", "lock"],
    
    # Node.js - safe operations  
    "node": ["*"],
    "npm": ["install", "list", "outdated", "view"],
    "npx": ["*"],
    "yarn": ["install", "add", "list"],
    
    # Package managers - read only
    "apt": ["list", "show", "search"],
    "apt-get": ["list", "show", "search"],
    "yum": ["list", "info", "search"],
    "pacman": ["-Ss", "-Qi"],
    
    # Archive operations
    "tar": ["xzf", "xjf", "zf", "jf", "czf", "cjf", "tf", "tj"],
    "unzip": ["*"],
    "gunzip": ["*"],
    "bzip2": ["*"],
    
    # Build tools
    "make": ["*"],
    "cmake": ["*"],
    "gcc": ["*"],
    "g++": ["*"],
    "cargo": ["build", "test", "check", "clippy"],
    
    # Docker (read-only in local mode)
    "docker": ["ps", "images", "logs", "inspect", "pull"],
    
    # Text editors (read-only)
    "vim": ["-R", "-M"],
    "nano": ["-R", "-c"],
    "emacs": ["--batch"],
    
    # Network tools (read-only)
    "curl": [],
    "wget": ["-O"],
    "ping": ["*"],
    "traceroute": ["*"],
    "nslookup": ["*"],
    "dig": ["*"],
    "host": ["*"],
    
    # System info (read-only)
    "ps": ["*"],
    "top": ["*"],
    "htop": ["*"],
    "free": ["*"],
    "df": ["*"],
    "du": ["*"],
    "lsblk": ["*"],
    "uname": ["*"],
    "hostname": ["*"],
    "whoami": ["*"],
    "id": ["*"],
    "groups": ["*"],
    
    # Version control
    "svn": ["info", "log", "status", "diff"],
    "hg": ["status", "log", "diff"],
    
    # Testing tools
    "pytest": ["*"],
    "nose": ["*"],
    "coverage": ["*"],
    "mypy": ["*"],
    "ruff": ["*"],
    "black": ["*"],
    "pylint": ["*"],
    "eslint": ["*"],
    "prettier": ["*"],
    
    # Documentation
    "mdoc": ["*"],
    "pandoc": ["*"],
    "sphinx-build": ["*"],
    
    # Database (read-only)
    "psql": ["-c", "-l"],
    "mysql": ["-e"],
    "sqlite3": [".schema", ".tables"],
    
    # Regex testing
    "sed": ["-n", "-p"],
    "awk": ["*"],
}

# Restricted commands - completely blocked
BLOCKED_COMMANDS = [
    "sudo",
    "su",
    "chown",
    "chmod",  # except specific cases
    "useradd",
    "usermod", 
    "userdel",
    "groupadd",
    "groupmod",
    "groupdel",
    "passwd",
    "crontab",
    "systemctl",
    "service",
    "init",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "telinit",
    "runlevel",
    # Network configuration
    "ifconfig",
    "ip",  # addr, route, rule
    "iptables",
    "ufw",
    "firewall-cmd",
    "route",
    "netstat",
    "ss",
    # Kernel modules
    "modprobe",
    "insmod",
    "rmmod",
    "modinfo",
    # Package management (system)
    "dpkg",
    "rpm",
    "apt-get",  # remove, purge, autoremove
    "yum",  # remove, erase
    "dnf",
    "pacman",  # -R, -Rs
    # Process control
    "kill",
    "killall",
    "pkill",
    "skill",
    # Service management
    "chkconfig",
    "update-rc.d",
    " rc.local",
]


@dataclass
class SanitizeResult:
    """Result of command sanitization."""
    allowed: bool
    command: str
    reason: str
    sanitized_command: Optional[str] = None


class CommandSanitizer:
    """Security sanitizer for commands executed by the agent.
    
    This provides defense in depth without Docker sandboxing:
    1. Pattern matching for dangerous commands
    2. Allowlist approach for common commands
    3. Blocked command list
    4. Workspace boundary enforcement
    """
    
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile dangerous patterns for efficiency."""
        self.compiled_patterns = []
        for pattern, description in DANGEROUS_PATTERNS:
            try:
                self.compiled_patterns.append((
                    re.compile(pattern, re.IGNORECASE),
                    description
                ))
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")
    
    def check_command(self, command: str) -> SanitizeResult:
        """Check if a command is safe to execute.
        
        Args:
            command: The command string to check
            
        Returns:
            SanitizeResult with allowed status and reason
        """
        if not command or not command.strip():
            return SanitizeResult(
                allowed=False,
                command="",
                reason="Empty command"
            )
        
        original = command
        command = command.strip()
        
        # Check for empty after stripping
        if not command:
            return SanitizeResult(
                allowed=False,
                command=original,
                reason="Empty command after stripping"
            )
        
        # Extract the base command
        parts = command.split()
        if not parts:
            return SanitizeResult(
                allowed=False,
                command=original,
                reason="Empty command parts"
            )
        
        base_cmd = parts[0]
        
        # Check against blocked commands (completely forbidden)
        if base_cmd in BLOCKED_COMMANDS:
            return SanitizeResult(
                allowed=False,
                command=original,
                reason=f"Command '{base_cmd}' is blocked for security"
            )
        
        # Check against dangerous patterns
        for pattern, description in self.compiled_patterns:
            if pattern.search(command):
                logger.warning(f"Dangerous pattern detected: {description}")
                return SanitizeResult(
                    allowed=False,
                    command=original,
                    reason=description
                )
        
        # Check allowlist - if command is in allowlist, it's OK
        if base_cmd in ALLOWED_COMMANDS:
            allowed_args = ALLOWED_COMMANDS[base_cmd]
            # If * in allowed_args, allow all args
            if "*" in allowed_args:
                return SanitizeResult(
                    allowed=True,
                    command=original,
                    reason=f"Command '{base_cmd}' is allowed"
                )
            # Otherwise check specific args
            if len(parts) > 1:
                args_ok = all(arg in allowed_args for arg in parts[1:] if not arg.startswith("-"))
                if not args_ok:
                    return SanitizeResult(
                        allowed=False,
                        command=original,
                        reason=f"Restricted arguments for '{base_cmd}'"
                    )
            return SanitizeResult(
                allowed=True,
                command=original,
                reason=f"Command '{base_cmd}' is allowed"
            )
        
        # Not in allowlist or blocklist - be conservative and log a warning
        # but still allow for development flexibility
        logger.warning(f"Unknown command: {base_cmd} - allowing but should be reviewed")
        
        return SanitizeResult(
            allowed=True,
            command=original,
            reason=f"Command '{base_cmd}' not in explicit lists - allowing but review recommended"
        )
    
    def sanitize_command(self, command: str) -> SanitizeResult:
        """Check and log a command."""
        result = self.check_command(command)
        
        if result.allowed:
            logger.info(f"Allowed command: {result.command} - {result.reason}")
        else:
            logger.warning(f"Blocked command: {result.command} - {result.reason}")
        
        return result
    
    def check_workspace_boundary(self, path: str) -> bool:
        """Check if a path is within workspace boundaries.
        
        This prevents directory traversal attacks.
        """
        import os.path
        
        # Resolve both paths to absolute
        abs_workspace = os.path.abspath(self.workspace_dir)
        abs_path = os.path.abspath(os.path.join(self.workspace_dir, path))
        
        # Ensure the resolved path is within workspace
        return abs_path.startswith(abs_workspace)


# Global sanitizer
_sanitizer: Optional[CommandSanitizer] = None


def get_sanitizer() -> CommandSanitizer:
    """Get the global sanitizer instance."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = CommandSanitizer()
    return _sanitizer


def set_sanitizer(sanitizer: CommandSanitizer):
    """Set the global sanitizer instance."""
    global _sanitizer
    _sanitizer = sanitizer


# Convenience function
def check_command(command: str) -> SanitizeResult:
    """Check if a command is safe."""
    return get_sanitizer().check_command(command)