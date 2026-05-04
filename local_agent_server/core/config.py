"""Core configuration for Local Agent Server."""

import os
from typing import Optional
from enum import Enum
from dataclasses import dataclass

# Server configuration
SERVER_NAME = "local-agent-server"
SERVER_VERSION = "1.0.0"

# API configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPEN_ROUTER = "openrouter"
    NVIDIA = "nvidia"
    OPENAI = "openai"
    OLLAMA = "ollama"


# LLM configuration - Support multiple providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
DEFAULT_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")  # Provider-specific endpoints

# LLM configuration parameters
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "1.0"))

# Provider-specific API key and endpoint mappings
LLM_PROVIDER_CONFIGS = {
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-5-20250929",
    },
    "google": {
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "default_model": "gemini-2.0-flash-exp",
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "cerebras": {
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
    },
    "openrouter": {
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url": "",  # Empty - litellm routes automatically
        "default_model": "openrouter/google/gemini-2.0-flash-001",
    },
    "nvidia": {
        "api_key_env": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "nvidia/llama-3.3-nemotron-70b-instruct",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
}

# Helper to get API key from multiple possible env vars
def get_llm_api_key() -> Optional[str]:
    """Get API key from environment - check multiple possible vars."""
    # First check explicit LLM_API_KEY
    if api_key := os.getenv("LLM_API_KEY"):
        return api_key
    
    # Then check provider-specific config
    provider_config = LLM_PROVIDER_CONFIGS.get(LLM_PROVIDER, {})
    if api_key_env := provider_config.get("api_key_env"):
        if api_key := os.getenv(api_key_env):
            return api_key
    
    # Fallback to legacy env vars
    for var in ["OPENHANDS_API_KEY", "ANTHROPIC_API_KEY"]:
        if api_key := os.getenv(var):
            return api_key
    
    return None


def get_provider_base_url() -> str:
    """Get the base URL for the configured provider."""
    # Check explicit LLM_BASE_URL env var first (user override)
    explicit_url = os.getenv("LLM_BASE_URL", "")
    if explicit_url:
        return explicit_url
    
    # Then use provider config
    provider_config = LLM_PROVIDER_CONFIGS.get(LLM_PROVIDER, {})
    return provider_config.get("base_url", "")


def get_provider_default_model() -> str:
    """Get the default model for the configured provider."""
    # Check explicit LLM_MODEL env var first (user override)
    explicit_model = os.getenv("LLM_MODEL", "")
    if explicit_model:
        return explicit_model
    
    # Then use provider-specific default
    provider_config = LLM_PROVIDER_CONFIGS.get(LLM_PROVIDER, {})
    return provider_config.get("default_model", "claude-sonnet-4.6")


# Agent configuration
DEFAULT_AGENT_TYPE = os.getenv("DEFAULT_AGENT_TYPE", "default")
ENABLE_BROWSER = os.getenv("ENABLE_BROWSER", "true").lower() == "true"

# Workspace configuration
WORKSPACE_BASE_DIR = os.getenv("WORKSPACE_BASE_DIR", os.path.expanduser("~/agent-workspaces"))

# Security configuration
API_KEY_HEADER = "Authorization"
API_KEY_PREFIX = "Bearer"
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else None


class Settings:
    """Server settings class."""
    
    def __init__(self):
        self.name = SERVER_NAME
        self.version = SERVER_VERSION
        self.host = API_HOST
        self.port = API_PORT
        self.llm_provider = LLM_PROVIDER
        self.default_model = get_provider_default_model()
        self.llm_base_url = get_provider_base_url()
        self.llm_temperature = LLM_TEMPERATURE
        self.llm_max_tokens = LLM_MAX_TOKENS
        self.llm_top_p = LLM_TOP_P
        self.default_agent_type = DEFAULT_AGENT_TYPE
        self.enable_browser = ENABLE_BROWSER
        self.workspace_base_dir = WORKSPACE_BASE_DIR
        self.auth_enabled = AUTH_ENABLED
        self.cors_origins = CORS_ORIGINS
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "host": self.host,
            "port": self.port,
            "llm_provider": self.llm_provider,
            "default_model": self.default_model,
            "llm_base_url": self.llm_base_url,
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens,
            "llm_top_p": self.llm_top_p,
            "default_agent_type": self.default_agent_type,
            "enable_browser": self.enable_browser,
            "workspace_base_dir": self.workspace_base_dir,
            "auth_enabled": self.auth_enabled,
            "cors_origins": self.cors_origins,
        }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings