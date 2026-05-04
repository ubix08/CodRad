"""
Session management for projects.

Each project can have multiple sessions (conversations).
Sessions store message history in JSON files.
"""

import os
import json
from datetime import datetime
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class Session:
    """Represents a conversation session within a project."""
    
    def __init__(self, project_name: str, session_id: str, project_root: str):
        self.project_name = project_name
        self.session_id = session_id
        self.project_root = project_root
        self.sessions_path = os.path.join(project_root, ".project", "sessions", session_id)
        self.messages_path = os.path.join(self.sessions_path, "messages.json")
        self.meta_path = os.path.join(self.sessions_path, "meta.json")
    
    @property
    def exists(self) -> bool:
        return os.path.isdir(self.sessions_path)
    
    def create(self, initial_message: str = None) -> bool:
        """Create a new session."""
        try:
            os.makedirs(self.sessions_path, exist_ok=True)
            
            # Create meta.json
            meta = {
                "id": self.session_id,
                "project_name": self.project_name,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "title": initial_message[:50] if initial_message else "New Session",
            }
            with open(self.meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            
            # Create empty messages.json
            with open(self.messages_path, "w") as f:
                json.dump([], f)
            
            logger.info(f"Created session: {self.session_id} in project {self.project_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False
    
    def get_messages(self) -> list:
        """Get all messages in this session."""
        if not os.path.exists(self.messages_path):
            return []
        
        try:
            with open(self.messages_path) as f:
                return json.load(f)
        except:
            return []
    
    def add_message(self, role: str, content: str, metadata: dict = None) -> bool:
        """Add a message to the session."""
        try:
            messages = self.get_messages()
            messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            })
            
            with open(self.messages_path, "w") as f:
                json.dump(messages, f, indent=2)
            
            # Update meta
            self._update_meta(last_message=content[:100])
            return True
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            return False
    
    def _update_meta(self, **kwargs):
        """Update session metadata."""
        if not os.path.exists(self.meta_path):
            return
        
        try:
            with open(self.meta_path) as f:
                meta = json.load(f)
            
            meta.update(kwargs)
            meta["updated_at"] = datetime.utcnow().isoformat()
            
            with open(self.meta_path, "w") as f:
                json.dump(meta, f, indent=2)
        except:
            pass
    
    def get_meta(self) -> dict:
        """Get session metadata."""
        if not os.path.exists(self.meta_path):
            return {}
        
        try:
            with open(self.meta_path) as f:
                return json.load(f)
        except:
            return {}
    
    def get_workspace_dir(self) -> str:
        """Get the workspace directory for this session (project root)."""
        return self.project_root


class SessionManager:
    """Manages sessions within projects."""
    
    def __init__(self, project_manager):
        self.project_manager = project_manager
    
    def create_session(self, project_name: str, initial_message: str = None) -> Optional[Session]:
        """Create a new session in a project."""
        project = self.project_manager.get_project(project_name)
        
        if not project.exists:
            logger.error(f"Project does not exist: {project_name}")
            return None
        
        # Generate session ID
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session = Session(project_name, session_id, project.path)
        
        if session.create(initial_message):
            return session
        
        return None
    
    def get_session(self, project_name: str, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        project = self.project_manager.get_project(project_name)
        
        if not project.exists:
            return None
        
        session = Session(project_name, session_id, project.path)
        
        if session.exists:
            return session
        
        return None
    
    def list_sessions(self, project_name: str) -> list:
        """List all sessions in a project."""
        project = self.project_manager.get_project(project_name)
        
        if not project.exists:
            return []
        
        return project.sessions
    
    def delete_session(self, project_name: str, session_id: str) -> bool:
        """Delete a session."""
        session = self.get_session(project_name, session_id)
        
        if not session:
            return False
        
        try:
            import shutil
            if os.path.exists(session.sessions_path):
                shutil.rmtree(session.sessions_path)
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False


# Global instance - will be initialized with project_manager
_session_manager = None


def get_session_manager(project_manager) -> SessionManager:
    """Get the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(project_manager)
    return _session_manager
