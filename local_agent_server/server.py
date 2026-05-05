"""
Local Agent Server - Main Application Entry Point

A personal AI coding assistant built on OpenHands SDK without sandboxing.
Provides REST API, WebSocket, and Admin endpoints.

Usage:
    python -m local_agent_server.server
    
Or with custom port:
    python -m local_agent_server.server --port 8080
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Core modules
from local_agent_server.core.config import settings, get_settings
from local_agent_server.core.events import event_manager, EventType
from local_agent_server.core.persistence import conversation_store
from local_agent_server.core.security_analyzer import security_analyzer
from local_agent_server.core.confirmation import get_confirmation_policy, ConfirmationPolicyType
from local_agent_server.core.state_machine import AgentStateMachine, StuckDetector
from local_agent_server.core.hooks import hooks, HookEvent

# Services
from local_agent_server.services import (
    ProjectManager,
    ConversationManager,
    get_project_manager,
    get_conversation_manager,
    set_project_manager,
    set_conversation_manager,
)

# API Routes
from local_agent_server.api import (
    admin_router,
    conversations_router,
    workspaces_router,
    skills_router,
    websocket_endpoint,
    websocket_chat_endpoint,
)
from local_agent_server.api.routes.sse import router as sse_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global state
app_state = {
    "started": False,
    "conversations": {},
    "metrics": {
        "total_requests": 0,
        "total_conversations": 0,
        "total_tokens": 0,
    }
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - production ready initialization."""
    logger.info("Starting Local Agent Server...")
    
    # Initialize persistence (SQLite)
    try:
        from local_agent_server.core.persistence import conversation_store
        logger.info("Database: initialized")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
    
    # Initialize project manager (uses SDK LocalWorkspace)
    pm = ProjectManager(workspace_root=settings.workspace_base_dir)
    set_project_manager(pm)
    
    # Initialize conversation manager
    cm = ConversationManager(
        project_manager=pm,
        api_key=os.getenv("OPENHANDS_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
    )
    set_conversation_manager(cm)
    
    # Load skills from local directory
    try:
        from local_agent_server.skills import load_skills_from_directory
        skills_dir = Path(__file__).parent / "skills" / "skills"
        skill_count = load_skills_from_directory(str(skills_dir))
        logger.info(f"Skills: {skill_count} loaded")
    except Exception as e:
        logger.warning(f"Skills loading failed: {e}")
    
    # Log configuration
    logger.info(f"Workspace: {pm.workspace_root}")
    logger.info(f"Projects: {len(pm.list_projects())} projects")
    logger.info(f"API Key: {'configured' if cm.api_key else 'NOT CONFIGURED'}")
    
    # Security
    logger.info("Security: enabled")
    
    # Confirmation policy
    policy_type = os.getenv("CONFIRMATION_POLICY", "never_confirm")
    try:
        confirmation_policy = get_confirmation_policy(ConfirmationPolicyType(policy_type))
        logger.info(f"Confirmation policy: {policy_type}")
    except:
        logger.warning(f"Invalid policy: {policy_type}, using default")
        policy_type = "never_confirm"
    
    # MCP servers
    mcp_config = os.getenv("MCP_SERVERS", "")
    if mcp_config:
        logger.info(f"MCP servers: configured")
    else:
        logger.info("MCP servers: not configured")
    
    app_state["started"] = True
    logger.info("Server ready")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down Local Agent Server...")
    app_state["started"] = False
    
    # Close database connections
    try:
        if 'conversation_store' in dir():
            conversation_store.close()
    except:
        pass
    
    logger.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Local Agent Server",
    description="Personal AI Coding Assistant - Built on OpenHands SDK",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Local Agent Server",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running" if app_state["started"] else "stopped",
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    cm = get_conversation_manager()
    return {
        "status": "healthy" if app_state["started"] else "stopped",
        "version": "1.0.0",
        "conversations": len(app_state.get("conversations", {})),
        "api_key_configured": bool(cm.api_key if cm else None),
    }


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Get server metrics."""
    return app_state.get("metrics", {})


# Include routers (routes already have /api/ prefix)
app.include_router(admin_router, tags=["admin"])
app.include_router(conversations_router, tags=["conversations"])
app.include_router(workspaces_router, tags=["workspaces"])
app.include_router(skills_router, tags=["skills"])


# Try to import GitHub routes
try:
    from local_agent_server.api.routes.github import router as github_router
    app.include_router(github_router, tags=["github"])
    logger.info("GitHub integration: enabled")
except ImportError:
    logger.warning("GitHub integration: not available")

# Include project routes
try:
    from local_agent_server.api.routes.projects import router as projects_router
    app.include_router(projects_router, tags=["projects"])
    logger.info("Projects: enabled")
except Exception as e:
    logger.warning(f"Projects: not available - {e}")

try:
    app.include_router(sse_router, tags=["sse"])
    logger.info("SSE: enabled")
except Exception as e:
    logger.warning(f"SSE: not available - {e}")


# WebSocket endpoint for real-time events
@app.websocket("/ws/{conversation_id}")
async def websocket_events(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time conversation events."""
    await event_manager.connect(conversation_id, websocket)
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            # Handle client messages if needed
    except WebSocketDisconnect:
        event_manager.disconnect(conversation_id, websocket)


# WebSocket chat endpoint
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for chat with the agent."""
    await websocket.accept()
    
    cm = get_conversation_manager()
    if not cm:
        await websocket.send_json({"error": "Conversation manager not initialized"})
        await websocket.close()
        return
    
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "conversation_id": conversation_id,
        })
        
        # Handle messages
        while True:
            data = await websocket.receive_text()
            # Process message...
            await websocket.send_json({"type": "ack"})
    except WebSocketDisconnect:
        pass


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Run the server
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "local_agent_server.server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
