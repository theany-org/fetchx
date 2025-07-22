"""SQLite database manager for FETCHX IDM."""

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fetchx_cli.utils.exceptions import DatabaseException


class DatabaseManager:
    """SQLite database manager with connection pooling and thread safety."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._local = threading.local()

        # Database path
        home_dir = Path.home()
        self.db_dir = home_dir / ".fetchx_idm"
        self.db_dir.mkdir(exist_ok=True)
        self.db_path = self.db_dir / "fetchx.db"

        # Initialize database
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(self.db_path), check_same_thread=False, timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys=ON")

        return self._local.connection

    @contextmanager
    def get_cursor(self, commit=True):
        """Context manager for database operations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Database operation failed: {e}")
        finally:
            cursor.close()

    def _init_database(self):
        """Initialize database tables."""
        with self.get_cursor() as cursor:
            # Queue items table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS queue_items (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT,
                    output_dir TEXT,
                    headers TEXT,  -- JSON string
                    max_connections INTEGER,
                    status TEXT NOT NULL DEFAULT 'queued',
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    error_message TEXT,
                    progress_percentage REAL DEFAULT 0.0,
                    download_speed REAL DEFAULT 0.0,
                    eta REAL,
                    file_path TEXT
                )
            """
            )

            # Sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    download_info TEXT,  -- JSON string
                    segments TEXT,       -- JSON string
                    stats TEXT,          -- JSON string
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    headers TEXT         -- JSON string
                )
            """
            )

            # Settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    section TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    value_type TEXT NOT NULL,  -- 'str', 'int', 'float', 'bool'
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (section, key)
                )
            """
            )

            # Logs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    extra_data TEXT  -- JSON string for additional data
                )
            """
            )

            # Create indexes for better performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_items(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_queue_created ON queue_items(created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")

    def close_all_connections(self):
        """Close all thread-local connections."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection

    # Queue operations
    def add_queue_item(self, item_data: Dict[str, Any]) -> str:
        """Add item to download queue."""
        with self.get_cursor() as cursor:
            # Convert dict/list fields to JSON
            headers_json = json.dumps(item_data.get("headers", {}))

            cursor.execute(
                """
                INSERT INTO queue_items (
                    id, url, filename, output_dir, headers, max_connections,
                    status, created_at, started_at, completed_at, error_message,
                    progress_percentage, download_speed, eta, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item_data["id"],
                    item_data["url"],
                    item_data.get("filename"),
                    item_data.get("output_dir"),
                    headers_json,
                    item_data.get("max_connections"),
                    item_data.get("status", "queued"),
                    item_data.get("created_at", time.time()),
                    item_data.get("started_at"),
                    item_data.get("completed_at"),
                    item_data.get("error_message"),
                    item_data.get("progress_percentage", 0.0),
                    item_data.get("download_speed", 0.0),
                    item_data.get("eta"),
                    item_data.get("file_path"),
                ),
            )
        return item_data["id"]

    def get_queue_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get queue item by ID (supports partial ID)."""
        with self.get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT * FROM queue_items WHERE id LIKE ? LIMIT 1", (f"{item_id}%",)
            )
            row = cursor.fetchone()
            if row:
                return self._queue_row_to_dict(row)
            return None

    def update_queue_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """Update queue item."""
        if not updates:
            return False

        with self.get_cursor() as cursor:
            # Handle special fields that need JSON encoding
            if "headers" in updates:
                updates["headers"] = json.dumps(updates["headers"])

            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(item_id)

            query = f"UPDATE queue_items SET {', '.join(set_clauses)} WHERE id LIKE ?"
            cursor.execute(query, values)

            return cursor.rowcount > 0

    def remove_queue_item(self, item_id: str) -> bool:
        """Remove queue item."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM queue_items WHERE id LIKE ?", (f"{item_id}%",))
            return cursor.rowcount > 0

    def list_queue_items(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List queue items, optionally filtered by status."""
        with self.get_cursor(commit=False) as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM queue_items WHERE status = ? ORDER BY created_at",
                    (status,),
                )
            else:
                cursor.execute("SELECT * FROM queue_items ORDER BY created_at")

            return [self._queue_row_to_dict(row) for row in cursor.fetchall()]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self.get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT status, COUNT(*) as count FROM queue_items GROUP BY status"
            )
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) as total FROM queue_items")
            total = cursor.fetchone()["total"]

            active_count = status_counts.get("downloading", 0)

            # Ensure all statuses are represented
            all_statuses = [
                "queued",
                "downloading",
                "paused",
                "completed",
                "failed",
                "cancelled",
            ]
            for status in all_statuses:
                if status not in status_counts:
                    status_counts[status] = 0

            return {
                "total_downloads": total,
                "active_downloads": active_count,
                "status_counts": status_counts,
            }

    def _queue_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert queue table row to dictionary."""
        data = dict(row)
        # Parse JSON fields
        if data["headers"]:
            try:
                data["headers"] = json.loads(data["headers"])
            except json.JSONDecodeError:
                data["headers"] = {}
        else:
            data["headers"] = {}
        return data

    # Session operations
    def add_session(self, session_data: Dict[str, Any]) -> str:
        """Add download session."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (
                    session_id, url, download_info, segments, stats,
                    created_at, updated_at, status, headers
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_data["session_id"],
                    session_data["url"],
                    json.dumps(session_data.get("download_info", {})),
                    json.dumps(session_data.get("segments", [])),
                    json.dumps(session_data.get("stats", {})),
                    session_data.get("created_at", time.time()),
                    session_data.get("updated_at", time.time()),
                    session_data.get("status", "active"),
                    json.dumps(session_data.get("headers", {})),
                ),
            )
        return session_data["session_id"]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        with self.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return self._session_row_to_dict(row)
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session."""
        if not updates:
            return False

        # Always update the updated_at timestamp
        updates["updated_at"] = time.time()

        with self.get_cursor() as cursor:
            # Handle JSON fields
            for field in ["download_info", "segments", "stats", "headers"]:
                if field in updates and not isinstance(updates[field], str):
                    updates[field] = json.dumps(updates[field])

            set_clauses = []
            values = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(session_id)

            query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?"
            cursor.execute(query, values)

            return cursor.rowcount > 0

    def list_sessions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions, optionally filtered by status."""
        with self.get_cursor(commit=False) as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")

            return [self._session_row_to_dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return cursor.rowcount > 0

    def cleanup_old_sessions(self, max_age_days: int = 30):
        """Clean up old sessions."""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM sessions 
                WHERE status IN ('completed', 'failed') AND updated_at < ?
            """,
                (cutoff_time,),
            )

    def _session_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert session table row to dictionary."""
        data = dict(row)
        # Parse JSON fields
        for field in ["download_info", "segments", "stats", "headers"]:
            if data[field]:
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    data[field] = {} if field != "segments" else []
            else:
                data[field] = {} if field != "segments" else []
        return data

    # Settings operations
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        with self.get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT value, value_type FROM settings WHERE section = ? AND key = ?",
                (section, key),
            )
            row = cursor.fetchone()
            if row:
                return self._convert_setting_value(row["value"], row["value_type"])
            return default

    def set_setting(self, section: str, key: str, value: Any) -> None:
        """Set a setting value."""
        value_type = self._get_value_type(value)
        value_str = str(value)

        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO settings (section, key, value, value_type, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (section, key, value_str, value_type, time.time()),
            )

    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings grouped by section."""
        with self.get_cursor(commit=False) as cursor:
            cursor.execute("SELECT section, key, value, value_type FROM settings")

            result = {}
            for row in cursor.fetchall():
                section = row["section"]
                if section not in result:
                    result[section] = {}
                result[section][row["key"]] = self._convert_setting_value(
                    row["value"], row["value_type"]
                )

            return result

    def _get_value_type(self, value: Any) -> str:
        """Get the type string for a value."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        else:
            return "str"

    def _convert_setting_value(self, value_str: str, value_type: str) -> Any:
        """Convert string value back to original type."""
        if value_type == "bool":
            return value_str.lower() in ("true", "1", "yes")
        elif value_type == "int":
            return int(value_str)
        elif value_type == "float":
            return float(value_str)
        else:
            return value_str

    # Logging operations
    def add_log(
        self, level: str, module: str, message: str, extra_data: Optional[Dict] = None
    ) -> None:
        """Add log entry."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO logs (timestamp, level, module, message, extra_data)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    time.time(),
                    level,
                    module,
                    message,
                    json.dumps(extra_data) if extra_data else None,
                ),
            )

    def get_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get log entries with optional filtering."""
        with self.get_cursor(commit=False) as cursor:
            query = "SELECT * FROM logs"
            params = []

            conditions = []
            if level:
                conditions.append("level = ?")
                params.append(level)
            if module:
                conditions.append("module = ?")
                params.append(module)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)

            logs = []
            for row in cursor.fetchall():
                log_data = dict(row)
                if log_data["extra_data"]:
                    try:
                        log_data["extra_data"] = json.loads(log_data["extra_data"])
                    except json.JSONDecodeError:
                        log_data["extra_data"] = {}
                logs.append(log_data)

            return logs

    def cleanup_old_logs(self, max_age_days: int = 30) -> int:
        """Clean up old log entries."""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_time,))
            return cursor.rowcount


# Global database instance
def get_database() -> DatabaseManager:
    """Get the global database instance."""
    return DatabaseManager()
