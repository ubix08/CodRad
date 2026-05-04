"""
Conversation persistence using SQLite.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging
import threading

logger = logging.getLogger(__name__)


class ConversationStore:
    """SQLite-based conversation persistence."""
    
    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                workspace_dir TEXT,
                status TEXT,
                title TEXT,
                agent_type TEXT,
                enable_browser INTEGER,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                event_type TEXT,
                event_data TEXT,
                created_at TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        conn.commit()
        logger.info(f"Initialized conversation database at {self.db_path}")
    
    def save_conversation(self, conversation_id: str, workspace_dir: str, 
                          title: str, agent_type: str, enable_browser: bool,
                          status: str = "running", metadata: dict = None):
        """Save or update a conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO conversations 
            (id, workspace_dir, status, title, agent_type, enable_browser, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (conversation_id, workspace_dir, status, title, agent_type, 
               int(enable_browser), now, now, json.dumps(metadata or {})))
        
        conn.commit()
        logger.info(f"Saved conversation {conversation_id}")
    
    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get a conversation by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM conversations WHERE id = ?
        """, (conversation_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_conversations(self, limit: int = 100) -> list[dict]:
        """List all conversations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and its messages."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM events WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        
        conn.commit()
        logger.info(f"Deleted conversation {conversation_id}")
    
    def save_message(self, message_id: str, conversation_id: str, 
                     role: str, content: str, metadata: dict = None):
        """Save a message."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO messages (id, conversation_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (message_id, conversation_id, role, content, now, json.dumps(metadata or {})))
        
        # Update conversation timestamp
        cursor.execute("""
            UPDATE conversations SET updated_at = ? WHERE id = ?
        """, (now, conversation_id))
        
        conn.commit()
    
    def get_messages(self, conversation_id: str) -> list[dict]:
        """Get all messages for a conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC
        """, (conversation_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def save_event(self, conversation_id: str, event_type: str, event_data: dict):
        """Save an event."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO events (conversation_id, event_type, event_data, created_at)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, event_type, json.dumps(event_data), now))
        
        conn.commit()
    
    def get_events(self, conversation_id: str, limit: int = 100) -> list[dict]:
        """Get events for a conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM events WHERE conversation_id = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (conversation_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close the database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()


# Global store instance
conversation_store = ConversationStore()
