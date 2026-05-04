"""API Key authentication for Local Agent Server."""

import os
import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Define the API key header
API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)


class AuthConfig:
    """Authentication configuration."""
    
    def __init__(self):
        # Support multiple API keys from environment
        # Can be comma-separated list for multiple keys
        self._api_keys: set[str] = set()
        
        # Try to load from environment - support multiple providers
        # Primary API key for the LLM service
        self._primary_key = os.getenv("OPENHANDS_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        
        # Load additional API keys for authentication
        api_keys_env = os.getenv("API_KEYS", "")
        if api_keys_env:
            self._api_keys.update(k.strip() for k in api_keys_env.split(",") if k.strip())
        
        # Also accept the LLM API key as a valid auth key (for convenience)
        if self._primary_key:
            self._api_keys.add(self._primary_key)
        
        # Flag to enable/disable auth (for development)
        self.enabled = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    
    def validate_key(self, key: str) -> bool:
        """Validate an API key."""
        if not self.enabled:
            return True
        
        if not key:
            return False
        
        # Remove "Bearer " prefix if present
        if key.startswith("Bearer "):
            key = key[7:]
        
        return key in self._api_keys
    
    @property
    def is_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.enabled
    
    @property
    def has_keys(self) -> bool:
        """Check if any API keys are configured."""
        return len(self._api_keys) > 0


# Global auth config
_auth_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """Get the global auth config instance."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig()
    return _auth_config


async def verify_api_key(request: Request) -> str:
    """Verify the API key from a request.
    
    Args:
        request: The FastAPI request
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If authentication fails
    """
    config = get_auth_config()
    
    # Skip auth if disabled
    if not config.is_enabled:
        return "dev"
    
    # Get API key from header
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header:
        # Check query parameter as fallback
        auth_header = request.query_params.get("api_key", "")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_api_key",
                "message": "API key is required. Provide it in Authorization header or api_key query param.",
                "header": "Authorization: Bearer <your-api-key>",
            }
        )
    
    # Validate the key
    if not config.validate_key(auth_header):
        logger.warning(f"Invalid API key attempt from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_api_key",
                "message": "The provided API key is not valid.",
            }
        )
    
    # Return the key (without Bearer prefix)
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return auth_header


def create_auth_dependency():
    """Create a FastAPI dependency for authentication.
    
    Usage:
        @router.post("/endpoint")
        async def endpoint(api_key: str = Depends(verify_api_key)):
            ...
    """
    from fastapi import Depends
    
    async def verify():
        from fastapi import Request
        # This will be overridden with the actual request
        return await verify_api_key(Request)
    
    return Depends(verify_api_key)

