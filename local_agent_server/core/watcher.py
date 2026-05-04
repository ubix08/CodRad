"""
File system watcher using inotify (Linux) or polling.
"""

import os
import asyncio
from pathlib import Path
from typing import Callable, Optional
import logging
import time

logger = logging.getLogger(__name__)

# Try to use inotify, fall back to polling
try:
    import inotify.adapters
    INOTIFY_AVAILABLE = True
except ImportError:
    INOTIFY_AVAILABLE = False
    logger.warning("inotify not available, using polling")


class FileWatcher:
    """Watch file system for changes."""
    
    def __init__(self, workspace_dir: str, callback: Callable = None):
        self.workspace_dir = workspace_dir
        self.callback = callback
        self._running = False
        self._task = None
    
    async def start(self):
        """Start watching."""
        self._running = True
        
        if INOTIFY_AVAILABLE:
            self._task = asyncio.create_task(self._watch_inotify())
        else:
            self._task = asyncio.create_task(self._watch_polling())
        
        logger.info(f"File watcher started for {self.workspace_dir}")
    
    async def stop(self):
        """Stop watching."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("File watcher stopped")
    
    async def _watch_inotify(self):
        """Watch using inotify (Linux)."""
        i = inotify.adapters.Inotify()
        i.add_watch(self.workspace_dir)
        
        for event in i.event_gen():
            if not self._running:
                break
            
            if event:
                (_, event_types, path, filename) = event
                
                event_data = {
                    "path": os.path.join(path, filename),
                    "events": event_types,
                }
                
                if self.callback:
                    await self.callback(event_data)
    
    async def _watch_polling(self):
        """Watch using polling (fallback)."""
        file_mtimes = {}
        
        while self._running:
            try:
                for root, dirs, files in os.walk(self.workspace_dir):
                    for f in files:
                        fpath = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(fpath)
                            
                            if fpath in file_mtimes:
                                if mtime != file_mtimes[fpath]:
                                    # File changed
                                    if self.callback:
                                        await self.callback({
                                            "path": fpath,
                                            "events": ["modify"],
                                        })
                            
                            file_mtimes[fpath] = mtime
                        except:
                            pass
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(1)  # Poll every second


class FileWatcherManager:
    """Manages multiple file watchers."""
    
    def __init__(self):
        self.watchers: dict[str, FileWatcher] = {}
    
    async def watch(self, workspace_id: str, workspace_dir: str, callback: Callable = None):
        """Start watching a workspace."""
        if workspace_id in self.watchers:
            await self.stop(workspace_id)
        
        watcher = FileWatcher(workspace_dir, callback)
        await watcher.start()
        self.watchers[workspace_id] = watcher
        logger.info(f"Started watching workspace: {workspace_id}")
    
    async def stop(self, workspace_id: str):
        """Stop watching a workspace."""
        if workspace_id in self.watchers:
            await self.watchers[workspace_id].stop()
            del self.watchers[workspace_id]
            logger.info(f"Stopped watching workspace: {workspace_id}")
    
    async def stop_all(self):
        """Stop all watchers."""
        for workspace_id in list(self.watchers.keys()):
            await self.stop(workspace_id)


# Global watcher manager
file_watcher_manager = FileWatcherManager()
