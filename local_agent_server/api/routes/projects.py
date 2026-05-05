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
    from local_agent_server.services.conversation_manager import get_conversation_manager
    pm = get_project_manager()
    project = pm.get_project(project_id)
    
    if not project.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sm = get_session_manager(pm)
    session = sm.create_session(project_id, request.initial_message)
    
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    # Also create SDK conversation immediately so /messages works
    cm = get_conversation_manager()
    
    # Check API key
    if not cm.api_key:
        return {
            "session_id": session.session_id,
            "project_id": project_id,
            "title": request.initial_message[:50] if request.initial_message else "New Session",
            "warning": "No API key - agent won't run"
        }
    
    workspace = pm.get_workspace_for_project(project_id)
    
    if workspace and cm.api_key:
        from openhands.sdk import Conversation as SDKConversation
        from local_agent_server.services.agent_factory import get_agent_factory
        
        factory = get_agent_factory()
        agent = factory.create_agent(
            api_key=cm.api_key,
            agent_type=cm.default_agent_type,
            enable_browser=cm.enable_browser,
            model=cm.model,
        )
        
        # Create SDK conversation NOW
        sdk_conversation = SDKConversation(
            agent=agent,
            workspace=workspace,
        )
        
        # Send initial message if provided
        if request.initial_message:
            sdk_conversation.send_message(message=request.initial_message)
        
        # Store in conversation manager with session_id as key
        from local_agent_server.services.conversation_manager import Conversation as Conv
        conv = Conv(
            id=session.session_id,
            workspace_dir=str(workspace.working_dir),
            agent_type=cm.default_agent_type,
            enable_browser=cm.enable_browser,
            agent=agent,
            sdk_conversation=sdk_conversation,
        )
        cm.conversations[session.session_id] = conv
    
    return {
        "session_id": session.session_id,
        "project_id": project_id,
        "title": request.initial_message[:50] if request.initial_message else "New Session",
    }


@router.get("/{project_id}/sessions/{session_id}")
async def get_session(project_id: str, session_id: str):
    """Get session details and messages from SDK conversation."""
    from local_agent_server.services.conversation_manager import get_conversation_manager
    cm = get_conversation_manager()
    conv = cm.get_conversation(session_id)
    
    # If no conversation in manager, that's okay - return empty
    if not conv or not conv.sdk_conversation:
        return {
            "session_id": session_id,
            "project_id": project_id,
            "workspace_dir": "",
            "messages": [],
        }
    
    # Get messages from SDK state.events
    messages = []
    try:
        sdk_conv = conv.sdk_conversation
        events = list(sdk_conv.state.events) if hasattr(sdk_conv.state, 'events') else []
        
        for event in events:
            # Only look for Message events with content
            event_type = type(event).__name__
            
            # Skip non-message events (SystemPromptEvent, etc)
            if event_type in ('SystemPromptEvent',):
                continue
            
            # For MessageEvent, check the source and llm_message attributes
            if event_type == 'MessageEvent':
                source = getattr(event, 'source', None)
                llm_msg = getattr(event, 'llm_message', None)
                
                if llm_msg:
                    # Get content from the Message object
                    if hasattr(llm_msg, 'content'):
                        # It's a Message with TextContent items
                        content_parts = []
                        for part in getattr(llm_msg, 'content', []):
                            if hasattr(part, 'text'):
                                content_parts.append(part.text)
                            else:
                                content_parts.append(str(part))
                        content = '\n'.join(content_parts) if content_parts else str(llm_msg)
                    else:
                        content = str(llm_msg)
                else:
                    content = None
                
                role = source if source else 'user'
                # Map source to role for frontend (agent -> assistant)
                if role == 'agent':
                    role = 'assistant'
            else:
                # Handle legacy types
                content = getattr(event, 'content', None)
                role = 'assistant'
                if 'User' in event_type:
                    role = 'user'
            
            if not content:
                continue
            content = str(content)[:5000]
            
            # Skip system prompts/tools
            if 'Tools Available:' in content or 'Message from User' in content:
                continue
            
            if content and len(content) > 10:
                messages.append({'role': role, 'content': content})
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
    
    return {
        "session_id": session_id,
        "project_id": project_id,
        "workspace_dir": conv.workspace_dir,
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
    
    # Check if conversation already exists (from create_session)
    existing_conv = cm.get_conversation(session_id)
    
    if not existing_conv:
        # Need to create SDK conversation
        pm = get_project_manager()
        project = pm.get_project(project_id)
        
        if not project.exists:
            return JSONResponse(
                status_code=404,
                content={"error": "Project not found"}
            )
        
        workspace = pm.get_workspace_for_project(project_id)
        
        if not workspace:
            return JSONResponse(
                status_code=404,
                content={"error": "Project workspace not found"}
            )
        
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
        existing_conv = conv
    
    # Run the conversation
    try:
        existing_conv.sdk_conversation.run()
        
        return {
            "status": "completed",
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
    """Send a message to SDK conversation."""
    from local_agent_server.services.conversation_manager import get_conversation_manager
    cm = get_conversation_manager()
    conv = cm.get_conversation(session_id)
    
    if not conv or not conv.sdk_conversation:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Send to SDK conversation
    conv.sdk_conversation.send_message(message=request.message)
    
    return {
        "status": "message_added",
        "session_id": session_id,
    }


# Get messages from session (for frontend polling)
@router.get("/{project_id}/sessions/{session_id}/messages")
async def get_messages(project_id: str, session_id: str):
    """Get messages from session for polling."""
    from local_agent_server.services.conversation_manager import get_conversation_manager
    cm = get_conversation_manager()
    conv = cm.get_conversation(session_id)
    
    if not conv or not conv.sdk_conversation:
        return {"messages": []}
    
    # Extract messages (same logic as get_session but only messages)
    messages = []
    try:
        events = list(conv.sdk_conversation.state.events) if hasattr(conv.sdk_conversation.state, 'events') else []
        
        for event in events:
            event_type = type(event).__name__
            
            if event_type in ('SystemPromptEvent',):
                continue
            
            if event_type == 'MessageEvent':
                source = getattr(event, 'source', None)
                llm_msg = getattr(event, 'llm_message', None)
                
                if llm_msg:
                    if hasattr(llm_msg, 'content'):
                        content_parts = []
                        for part in getattr(llm_msg, 'content', []):
                            if hasattr(part, 'text'):
                                content_parts.append(part.text)
                            else:
                                content_parts.append(str(part))
                        content = '\n'.join(content_parts) if content_parts else str(llm_msg)
                    else:
                        content = str(llm_msg)
                else:
                    content = None
                
                role = source if source else 'user'
                if role == 'agent':
                    role = 'assistant'
                
                if content and len(content) > 10:
                    messages.append({'role': role, 'content': content[:5000]})
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
    
    return {"messages": messages}

