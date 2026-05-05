"""
Project management API routes.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from local_agent_server.services.project_manager import get_project_manager, Project
from local_agent_server.services.session_manager import get_session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


# Request/Response models
class CreateProjectRequest(BaseModel):
    name: str


class ImportGithubRequest(BaseModel):
    repo_url: str
    access_token: str = None


class CreateSessionRequest(BaseModel):
    initial_message: str = None


class SendMessageRequest(BaseModel):
    message: str


# Project endpoints
@router.get("")
async def list_projects():
    """List all projects."""
    pm = get_project_manager()
    return {"projects": pm.list_projects()}


@router.post("")
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    pm = get_project_manager()
    project = pm.create_project(request.name)
    return {
        "id": project.name,
        "name": project.name,
        "path": project.path,
    }


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    pm = get_project_manager()
    project = pm.get_project(project_id)
    
    if not project.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "id": project.name,
        "name": project.name,
        "path": project.path,
        "has_agents": project.has_agents,
        "has_agents_md": project.has_agents_md,
        "sessions": project.sessions,
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    pm = get_project_manager()
    success = pm.delete_project(project_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete project")
    
    return {"status": "deleted", "project_id": project_id}


@router.post("/import/github")
async def import_github_repo(request: ImportGithubRequest):
    """Import a GitHub repository as a new project."""
    pm = get_project_manager()
    project = pm.import_github_repo(request.repo_url, request.access_token)
    
    if not project:
        raise HTTPException(status_code=500, detail="Failed to import repository")
    
    return {
        "id": project.name,
        "name": project.name,
        "path": project.path,
    }


# Session endpoints
@router.get("/{project_id}/sessions")
async def list_sessions(project_id: str):
    """List all sessions in a project."""
    pm = get_project_manager()
    project = pm.get_project(project_id)
    
    if not project.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sm = get_session_manager(pm)
    sessions = sm.list_sessions(project_id)
    
    return {"sessions": sessions}


@router.post("/{project_id}/sessions")
async def create_session(project_id: str, request: CreateSessionRequest):
    """Create a new session in a project."""
    pm = get_project_manager()
    project = pm.get_project(project_id)
    
    if not project.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sm = get_session_manager(pm)
    session = sm.create_session(project_id, request.initial_message)
    
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    return {
        "session_id": session.session_id,
        "project_id": project_id,
        "title": request.initial_message[:50] if request.initial_message else "New Session",
    }


@router.get("/{project_id}/sessions/{session_id}")
async def get_session(project_id: str, session_id: str):
    """Get session details and messages."""
    pm = get_project_manager()
    sm = get_session_manager(pm)
    session = sm.get_session(project_id, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get messages from session file (primary)
    messages = session.get_messages()
    
    # If no messages from file, try SDK state.events (fallback)
    if not messages:
        from local_agent_server.services.conversation_manager import get_conversation_manager
        cm = get_conversation_manager()
        conv = cm.get_conversation(session_id)
        if conv and conv.sdk_conversation and hasattr(conv.sdk_conversation.state, 'events'):
            try:
                # SDK stores events in state.events
                events = conv.sdk_conversation.state.events
                messages = []
                for event in events:
                    # Events have content, convert to dict
                    if hasattr(event, 'content'):
                        messages.append({
                            'role': getattr(event, 'sender', 'user'),
                            'content': str(event.content)[:5000],
                        })
            except Exception:
                pass
    
    return {
        "session_id": session.session_id,
        "project_id": project_id,
        "workspace_dir": session.get_workspace_dir(),
        "meta": session.get_meta(),
        "messages": messages,
    }


@router.delete("/{project_id}/sessions/{session_id}")
async def delete_session(project_id: str, session_id: str):
    """Delete a session."""
    pm = get_project_manager()
    sm = get_session_manager(pm)
    success = sm.delete_session(project_id, session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "deleted", "session_id": session_id}


# Run session (start agent)
@router.post("/{project_id}/sessions/{session_id}/run")
async def run_session(project_id: str, session_id: str):
    """Run a session (start the agent)."""
    from local_agent_server.services.conversation_manager import get_conversation_manager
    from fastapi.responses import JSONResponse
    
    cm = get_conversation_manager()
    
    if not cm.api_key:
        return JSONResponse(
            status_code=500,
            content={"error": "No API key configured"}
        )
    
    # Create or get conversation for this session
    # Use session_id as conversation_id
    existing_conv = cm.get_conversation(session_id)
    
    # Get session to check for initial message
    pm = get_project_manager()
    sm = get_session_manager(pm)
    session = sm.get_session(project_id, session_id)
    initial_message = ""
    if session:
        msgs = session.get_messages()
        if msgs:
            # Get first user message as initial
            for m in msgs:
                if m.get('role') == 'user':
                    initial_message = m.get('content', '')
                    break
    
    if not existing_conv:
        # Get project workspace
        project = pm.get_project(project_id)
        
        if not project.exists:
            return JSONResponse(
                status_code=404,
                content={"error": "Project not found"}
            )
        
        # Get workspace for project
        workspace = pm.get_workspace_for_project(project_id)
        
        if not workspace:
            return JSONResponse(
                status_code=404,
                content={"error": "Project workspace not found"}
            )
        
        # Create agent and conversation
        from openhands.sdk import Conversation as SDKConversation
        from local_agent_server.services.agent_factory import get_agent_factory
        
        factory = get_agent_factory()
        agent = factory.create_agent(
            api_key=cm.api_key,
            agent_type=cm.default_agent_type,
            enable_browser=cm.enable_browser,
            model=cm.model,
        )
        
        # Create SDK conversation
        sdk_conversation = SDKConversation(
            agent=agent,
            workspace=workspace,
        )
        
        # Add initial message if exists
        if initial_message:
            sdk_conversation.send_message(message=initial_message)
        
        # Create conversation in manager
        from local_agent_server.services.conversation_manager import Conversation as Conv
        conv = Conv(
            id=session_id,
            workspace_dir=str(workspace.working_dir),
            agent_type=cm.default_agent_type,
            enable_browser=cm.enable_browser,
            agent=agent,
            sdk_conversation=sdk_conversation,
        )
        
        cm.conversations[session_id] = conv
    
    # Run the conversation - SDK stores messages natively in state.events
    try:
        cm.conversations[session_id].sdk_conversation.run()
        return {
            "status": "started",
            "session_id": session_id,
            "project_id": project_id,
        }
    except Exception as e:
        logger.error(f"Run session error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# Send message to session
@router.post("/{project_id}/sessions/{session_id}/messages")
async def send_message(project_id: str, session_id: str, request: SendMessageRequest):
    """Send a message to a session - adds to SDK conversation."""
    # First add to session for persistence
    pm = get_project_manager()
    sm = get_session_manager(pm)
    session = sm.get_session(project_id, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Add to session file
    session.add_message("user", request.message)
    
    # Also add to SDK conversation if it exists
    from local_agent_server.services.conversation_manager import get_conversation_manager
    cm = get_conversation_manager()
    conv = cm.get_conversation(session_id)
    
    if conv and conv.sdk_conversation:
        # SDK-native way: send message to conversation
        conv.sdk_conversation.send_message(message=request.message)
    
    return {
        "status": "message_added",
        "session_id": session_id,
    }
