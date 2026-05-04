"""
Project management for local agent server.

Handles:
- Creating new projects
- Opening existing projects
- Session management per project
- GitHub repo import → creates project
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)

# Default projects root
DEFAULT_PROJECTS_ROOT = os.path.expanduser("~/agent-projects")


class Project:
    """Represents a project."""
    
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.sessions_path = os.path.join(path, ".project", "sessions")
        self.config_path = os.path.join(path, ".project", "config.yaml")
    
    @property
    def exists(self) -> bool:
        return os.path.isdir(self.path)
    
    @property
    def sessions(self) -> list:
        """List all sessions in this project."""
        if not os.path.exists(self.sessions_path):
            return []
        
        sessions = []
        for session_id in os.listdir(self.sessions_path):
            session_dir = os.path.join(self.sessions_path, session_id)
            if os.path.isdir(session_dir):
                # Load session metadata
                meta_path = os.path.join(session_dir, "meta.json")
                if os.path.exists(meta_path):
                    with open(meta_path) as f:
                        sessions.append(json.load(f))
                else:
                    sessions.append({
                        "id": session_id,
                        "created_at": datetime.fromtimestamp(
                            os.path.getctime(session_dir)
                        ).isoformat()
                    })
        return sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)
    
    @property
    def has_agents(self) -> bool:
        """Check if project has .agents directory."""
        agents_path = os.path.join(self.path, ".agents")
        return os.path.isdir(agents_path)
    
    @property
    def has_agents_md(self) -> bool:
        """Check if project has AGENTS.md."""
        return os.path.exists(os.path.join(self.path, "AGENTS.md"))
    
    def create(self) -> bool:
        """Create the project structure."""
        try:
            os.makedirs(self.sessions_path, exist_ok=True)
            
            # Create initial config
            config = {
                "name": self.name,
                "created_at": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Created project: {self.name} at {self.path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return False
    
    def delete(self) -> bool:
        """Delete the project."""
        try:
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            logger.info(f"Deleted project: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete project: {e}")
            return False


class ProjectManager:
    """Manages all projects."""
    
    def __init__(self, projects_root: str = None):
        self.projects_root = projects_root or os.environ.get(
            "PROJECTS_ROOT", 
            DEFAULT_PROJECTS_ROOT
        )
        os.makedirs(self.projects_root, exist_ok=True)
        logger.info(f"ProjectManager initialized: {self.projects_root}")
    
    def list_projects(self) -> list[dict]:
        """List all projects."""
        projects = []
        
        if not os.path.exists(self.projects_root):
            return projects
        
        for name in os.listdir(self.projects_root):
            path = os.path.join(self.projects_root, name)
            if os.path.isdir(path):
                project = Project(name, path)
                projects.append({
                    "id": name,
                    "name": name,
                    "path": path,
                    "has_agents": project.has_agents,
                    "has_agents_md": project.has_agents_md,
                    "sessions_count": len(project.sessions),
                })
        
        return sorted(projects, key=lambda p: p.get("name", ""))
    
    def get_project(self, name: str) -> Project:
        """Get a project by name."""
        path = os.path.join(self.projects_root, name)
        return Project(name, path)
    
    def create_project(self, name: str, path: str = None) -> Project:
        """Create a new project."""
        if path:
            # Use custom path (for GitHub import)
            project_path = path
            project_name = os.path.basename(path)
        else:
            # Create in projects root
            project_path = os.path.join(self.projects_root, name)
            project_name = name
        
        project = Project(project_name, project_path)
        project.create()
        return project
    
    def import_github_repo(self, repo_url: str, access_token: str = None) -> Optional[Project]:
        """Import a GitHub repository as a new project."""
        import subprocess
        
        # Extract repo name from URL
        # https://github.com/owner/repo → repo
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        
        project_path = os.path.join(self.projects_root, repo_name)
        
        # Clone the repo
        cmd = ["git", "clone", repo_url, project_path]
        if access_token:
            # Convert to git URL with token
            auth_url = repo_url.replace("https://", f"https://{access_token}@")
            cmd[1] = auth_url
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return None
            
            # Create project metadata
            project = Project(repo_name, project_path)
            os.makedirs(project.sessions_path, exist_ok=True)
            
            config = {
                "name": repo_name,
                "created_at": datetime.utcnow().isoformat(),
                "imported_from": repo_url,
                "version": "1.0.0"
            }
            with open(project.config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Imported GitHub repo: {repo_name}")
            return project
            
        except Exception as e:
            logger.error(f"Failed to import repo: {e}")
            return None
    
    def delete_project(self, name: str) -> bool:
        """Delete a project."""
        project = self.get_project(name)
        return project.delete()


# Global instance
project_manager = ProjectManager()


def get_project_manager() -> ProjectManager:
    """Get the global project manager."""
    return project_manager
