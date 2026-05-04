"""
SSO/OAuth Authentication Integration.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import logging
import hashlib
import jwt

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User account."""
    id: str
    email: str
    name: str
    provider: str  # github, google, etc.
    created_at: datetime


class OAuthProvider:
    """Base OAuth provider."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL."""
        raise NotImplementedError
    
    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        raise NotImplementedError
    
    def get_user_info(self, access_token: str) -> User:
        """Get user info from provider."""
        raise NotImplementedError


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(client_id, client_secret, redirect_uri)
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.user_url = "https://api.github.com/user"
    
    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.auth_url}?{query}"
    
    def exchange_code(self, code: str) -> dict:
        import requests
        response = requests.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        return response.json()
    
    def get_user_info(self, access_token: str) -> User:
        import requests
        response = requests.get(
            self.user_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = response.json()
        
        return User(
            id=str(data["id"]),
            email=data.get("email", ""),
            name=data.get("name", ""),
            provider="github",
        )


class AuthManager:
    """Manages authentication."""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.sessions: dict[str, dict] = {}
        self.providers: dict[str, OAuthProvider] = {}
        
        # Initialize configured providers
        self._init_providers()
    
    def _init_providers(self):
        """Initialize OAuth providers from environment."""
        # GitHub
        if os.getenv("GITHUB_OAUTH_CLIENT_ID"):
            self.providers["github"] = GitHubOAuthProvider(
                client_id=os.getenv("GITHUB_OAUTH_CLIENT_ID"),
                client_secret=os.getenv("GITHUB_OAUTH_CLIENT_SECRET"),
                redirect_uri=os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback"),
            )
    
    def create_auth_url(self, provider: str) -> tuple[str, str]:
        """Create OAuth authorization URL."""
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        state = secrets.token_urlsafe(32)
        
        auth_url = self.providers[provider].get_authorization_url(state)
        
        # Store state for verification
        self.sessions[state] = {
            "provider": provider,
            "created_at": datetime.utcnow(),
        }
        
        return auth_url, state
    
    def handle_callback(self, code: str, state: str) -> str:
        """Handle OAuth callback and create session."""
        if state not in self.sessions:
            raise ValueError("Invalid state")
        
        session_data = self.sessions.pop(state)
        provider = session_data["provider"]
        
        # Exchange code for tokens
        tokens = self.providers[provider].exchange_code(code)
        access_token = tokens.get("access_token")
        
        if not access_token:
            raise ValueError("Failed to get access token")
        
        # Get user info
        user = self.providers[provider].get_user_info(access_token)
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        
        self.sessions[session_id] = {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "provider": provider,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=7),
        }
        
        return session_id
    
    def create_token(self, user_id: str) -> str:
        """Create JWT token for user."""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(days=7),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID."""
        session = self.sessions.get(session_id)
        
        if session and session.get("expires_at") > datetime.utcnow():
            return session
        
        return None
    
    def require_auth(self, session_id: str = None, token: str = None) -> dict:
        """Require authentication."""
        session = None
        
        if session_id:
            session = self.get_session(session_id)
        
        if token:
            payload = self.verify_token(token)
            if payload:
                session = {"user_id": payload["user_id"]}
        
        if not session:
            raise PermissionError("Authentication required")
        
        return session


# Global auth manager
auth_manager = AuthManager()
