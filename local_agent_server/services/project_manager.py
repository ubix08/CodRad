"""
Project management for local agent server.

Now using SDK's LocalWorkspace for all file operations.
One workspace for all projects - projects are subdirectories.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
import uuid

from openhands.sdk.workspace import LocalWorkspace

logger = logging.getLogger(__name__)

# Default workspace root - single workspace for all projects
DEFAULT_WORKSPACE_ROOT = os.path.expanduser("~/agent-workspace")


class Project:
    """Represents a project (subdirectory in workspace)."""
    
    def __init__(self, name: str, workspace: LocalWorkspace):
        self.name = name
        self.workspace = workspace
        # Project path is subdirectory inside workspace
        self.project_path = Path(workspace.working_dir) / name
    
    @property
    def path(self) -> str:
        return str(self.project_path)
    
    @property
    def exists(self) -> bool:
        return self.project_path.is_dir()
    
    @property
    def sessions(self) -> list:
        """List all sessions in this project."""
        sessions_path = self.project_path / ".project" / "sessions"
        if not sessions_path.exists():
            return []
        
        sessions = []
        for session_dir in sessions_path.iterdir():
            if session_dir.is_dir():
                meta_path = session_dir / "meta.json"
                if meta_path.exists():
                    sessions.append(json.loads(meta_path.read_text()))
                else:
                    sessions.append({
                        "id": session_dir.name,
                        "created_at": datetime.fromtimestamp(
                            session_dir.stat().st_ctime
                        ).isoformat()
                    })
        return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)
    
    @property
    def has_agents(self) -> bool:
        """Check if project has .agents directory."""
        return (self.project_path / ".agents").is_dir()
    
    @property
    def has_agents_md(self) -> bool:
        """Check if project has AGENTS.md."""
        return (self.project_path / "AGENTS.md").exists()
    
    def create(self) -> bool:
        """Create the project structure."""
        try:
            sessions_path = self.project_path / ".project" / "sessions"
            sessions_path.mkdir(parents=True, exist_ok=True)
            
            # Create initial config
            config = {
                "name": self.name,
                "created_at": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
            config_path = self.project_path / ".project" / "config.json"
            config_path.write_text(json.dumps(config, indent=2))
            
            logger.info(f"Created project: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return False
    
    def delete(self) -> bool:
        """Delete the project."""
        try:
            if self.project_path.exists():
                shutil.rmtree(self.project_path)
            logger.info(f"Deleted project: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete project: {e}")
            return False


class ProjectManager:
    """Manages all projects using SDK's LocalWorkspace."""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.environ.get(
            "WORKSPACE_ROOT", 
            DEFAULT_WORKSPACE_ROOT
        )
        
        # Create SDK LocalWorkspace for the base directory
        os.makedirs(self.workspace_root, exist_ok=True)
        self.workspace = LocalWorkspace(working_dir=self.workspace_root)
        
        logger.info(f"ProjectManager initialized: {self.workspace_root}")
    
    @property
    def workspace(self) -> LocalWorkspace:
        return self._workspace
    
    @workspace.setter
    def workspace(self, ws: LocalWorkspace):
        self._workspace = ws
    
    @property
    def projects_root(self) -> str:
        return self.workspace_root
    
    def list_projects(self) -> list[dict]:
        """List all projects."""
        projects = []
        
        if not Path(self.workspace_root).exists():
            return projects
        
        for entry in Path(self.workspace_root).iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                project = Project(entry.name, self.workspace)
                projects.append({
                    "id": entry.name,
                    "name": entry.name,
                    "path": str(entry),
                    "has_agents": project.has_agents,
                    "has_agents_md": project.has_agents_md,
                    "sessions_count": len(project.sessions),
                })
        
        return sorted(projects, key=lambda p: p.get("name", ""))
    
    def get_project(self, name: str) -> Project:
        """Get a project by name."""
        return Project(name, self.workspace)
    
    def create_project(self, name: str, path: str = None) -> Project:
        """Create a new project."""
        if path:
            # Use custom path (for GitHub import)
            project_path = Path(path)
            project_name = project_path.name
        else:
            project_path = Path(self.workspace_root) / name
            project_name = name
        
        project = Project(project_name, self.workspace)
        project.create()
        return project
    
    def import_github_repo(self, repo_url: str, access_token: str = None) -> Optional[Project]:
        """Import a GitHub repository as a new project."""
        # Extract repo name from URL
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        
        project_path = Path(self.workspace_root) / repo_name
        
        # Clone the repo
        cmd = ["git", "clone", repo_url, str(project_path)]
        if access_token:
            auth_url = repo_url.replace("https://", f"https://{access_token}@")
            cmd[2] = auth_url
        
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return None
            
            # Create project metadata
            project = Project(repo_name, self.workspace)
            sessions_path = project.project_path / ".project" / "sessions"
            sessions_path.mkdir(parents=True, exist_ok=True)
            
            config = {
                "name": repo_name,
                "created_at": datetime.utcnow().isoformat(),
                "imported_from": repo_url,
                "version": "1.0.0"
            }
            config_path = project.project_path / ".project" / "config.json"
            config_path.write_text(json.dumps(config, indent=2))
            
            logger.info(f"Imported GitHub repo: {repo_name}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to import repo: {e}")
            return None
    
    def delete_project(self, name: str) -> bool:
        """Delete a project."""
        project = self.get_project(name)
        return project.delete()
    
    def get_workspace_for_project(self, name: str) -> LocalWorkspace:
        """Get SDK LocalWorkspace for a specific project."""
        project = self.get_project(name)
        if project.exists:
            # Create a new LocalWorkspace pointing to project directory
            return LocalWorkspace(working_dir=str(project.project_path))
        return None


# Global instance
_project_manager = None


def get_project_manager() -> ProjectManager:
    """Get the global project manager."""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager


def set_project_manager(manager: ProjectManager) -> None:
    """Set the global project manager."""
    global _project_manager
    _project_manager = manager
