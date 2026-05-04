"""
Runtime cleanup and resource management.
"""

import os
import shutil
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging
import glob

logger = logging.getLogger(__name__)


class RuntimeCleanup:
    """Manages workspace and resource cleanup."""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.getenv(
            "WORKSPACE_ROOT", 
            "/home/openhands/agent-workspaces"
        )
    
    async def cleanup_workspace(self, workspace_id: str, delete: bool = False):
        """Clean up a workspace."""
        workspace_path = os.path.join(self.workspace_root, workspace_id)
        
        if not os.path.exists(workspace_path):
            return {"success": True, "message": "Workspace not found"}
        
        if delete:
            # Delete entire workspace
            shutil.rmtree(workspace_path)
            logger.info(f"Deleted workspace: {workspace_id}")
            return {"success": True, "message": f"Deleted workspace {workspace_id}"}
        
        # Clean temporary files
        cleaned = 0
        
        # Clean Python cache
        for pycache in glob.glob(f"{workspace_path}/**/__pycache__", recursive=True):
            shutil.rmtree(pycache)
            cleaned += 1
        
        # Clean .pyc files
        for pyc in glob.glob(f"{workspace_path}/**/*.pyc", recursive=True):
            os.remove(pyc)
            cleaned += 1
        
        # Clean node_modules (optionally)
        # for node_modules in glob.glob(f"{workspace_path}/**/node_modules", recursive=True):
        #     shutil.rmtree(node_modules)
        #     cleaned += 1
        
        logger.info(f"Cleaned workspace {workspace_id}: {cleaned} items")
        return {"success": True, "cleaned": cleaned}
    
    async def cleanup_old_workspaces(self, days: int = 7):
        """Clean up workspaces older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0
        
        if not os.path.exists(self.workspace_root):
            return {"success": True, "cleaned": 0}
        
        for workspace in os.listdir(self.workspace_root):
            workspace_path = os.path.join(self.workspace_root, workspace)
            
            if not os.path.isdir(workspace_path):
                continue
            
            # Check modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(workspace_path))
            
            if mtime < cutoff:
                try:
                    shutil.rmtree(workspace_path)
                    cleaned += 1
                    logger.info(f"Deleted old workspace: {workspace}")
                except Exception as e:
                    logger.error(f"Failed to delete {workspace}: {e}")
        
        return {"success": True, "cleaned": cleaned}
    
    async def get_workspace_size(self, workspace_id: str) -> dict:
        """Get workspace size in bytes."""
        workspace_path = os.path.join(self.workspace_root, workspace_id)
        
        if not os.path.exists(workspace_path):
            return {"size": 0, "files": 0}
        
        total_size = 0
        file_count = 0
        
        for dirpath, dirnames, filenames in os.walk(workspace_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except:
                    pass
        
        return {
            "size_bytes": total_size,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "files": file_count,
        }
    
    def list_workspaces(self) -> list:
        """List all workspaces."""
        if not os.path.exists(self.workspace_root):
            return []
        
        workspaces = []
        for workspace in os.listdir(self.workspace_root):
            workspace_path = os.path.join(self.workspace_root, workspace)
            
            if not os.path.isdir(workspace_path):
                continue
            
            stat = os.stat(workspace_path)
            workspaces.append({
                "id": workspace,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        
        return workspaces


# Global cleanup instance
runtime_cleanup = RuntimeCleanup()
