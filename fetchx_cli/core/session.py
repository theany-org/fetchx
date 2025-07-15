"""Session management for download."""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from fetchx_cli.core.downloader import DownloadInfo, DownloadStats
from fetchx_cli.core.connection import DownloadSegment
from fetchx_cli.core.database import get_database
from fetchx_cli.utils.exceptions import SessionException
from fetchx_cli.config.settings import get_config

@dataclass
class SessionData:
    """Represents a download session."""
    session_id: str
    url: str
    download_info: Dict[str, Any]
    segments: List[Dict[str, Any]]
    stats: Dict[str, Any]
    created_at: float
    updated_at: float
    status: str = "active"  # active, paused, completed, failed
    headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """Create from dictionary."""
        return cls(**data)

class SessionManager:
    """Manages download sessions for persistence using SQLite."""

    def __init__(self):
        self.config = get_config().config
        self.db = get_database()

    def create_session(self, session_id: str, url: str, download_info: DownloadInfo,
                      segments: List[DownloadSegment], headers: Optional[Dict[str, str]] = None) -> SessionData:
        """Create a new download session."""
        session_data = {
            'session_id': session_id,
            'url': url,
            'download_info': asdict(download_info) if download_info else {},
            'segments': [asdict(segment) for segment in segments],
            'stats': asdict(DownloadStats()),
            'created_at': time.time(),
            'updated_at': time.time(),
            'status': 'active',
            'headers': headers or {}
        }

        try:
            self.db.add_session(session_data)
            return SessionData.from_dict(session_data)
        except Exception as e:
            raise SessionException(f"Failed to create session: {e}")

    def update_session(self, session_id: str, stats: Optional[DownloadStats] = None,
                      segments: Optional[List[DownloadSegment]] = None,
                      status: Optional[str] = None) -> bool:
        """Update an existing session."""
        try:
            updates = {}

            if stats:
                updates['stats'] = asdict(stats)

            if segments:
                updates['segments'] = [asdict(segment) for segment in segments]

            if status:
                updates['status'] = status

            if updates:
                return self.db.update_session(session_id, updates)
            return True

        except Exception as e:
            raise SessionException(f"Failed to update session: {e}")

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        try:
            data = self.db.get_session(session_id)
            if data:
                return SessionData.from_dict(data)
            return None
        except Exception as e:
            raise SessionException(f"Failed to get session: {e}")

    def list_sessions(self, status: Optional[str] = None) -> List[SessionData]:
        """List all sessions, optionally filtered by status."""
        try:
            sessions_data = self.db.list_sessions(status)
            return [SessionData.from_dict(data) for data in sessions_data]
        except Exception as e:
            raise SessionException(f"Failed to list sessions: {e}")

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            return self.db.delete_session(session_id)
        except Exception as e:
            raise SessionException(f"Failed to delete session: {e}")

    def cleanup_old_sessions(self, max_age_days: int = 30):
        """Clean up old completed/failed sessions."""
        try:
            self.db.cleanup_old_sessions(max_age_days)
        except Exception as e:
            raise SessionException(f"Failed to cleanup old sessions: {e}")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        try:
            sessions = self.list_sessions()
            stats = {
                'total_sessions': len(sessions),
                'active_sessions': len([s for s in sessions if s.status == 'active']),
                'completed_sessions': len([s for s in sessions if s.status == 'completed']),
                'failed_sessions': len([s for s in sessions if s.status == 'failed']),
                'paused_sessions': len([s for s in sessions if s.status == 'paused'])
            }
            return stats
        except Exception as e:
            raise SessionException(f"Failed to get session stats: {e}")

    def pause_session(self, session_id: str) -> bool:
        """Mark session as paused."""
        return self.update_session(session_id, status='paused')

    def resume_session(self, session_id: str) -> bool:
        """Mark session as active."""
        return self.update_session(session_id, status='active')

    def complete_session(self, session_id: str) -> bool:
        """Mark session as completed."""
        return self.update_session(session_id, status='completed')

    def fail_session(self, session_id: str, error_message: Optional[str] = None) -> bool:
        """Mark session as failed."""
        updates = {'status': 'failed'}
        if error_message:
            # Store error message in stats
            session = self.get_session(session_id)
            if session:
                stats = session.stats.copy()
                stats['error_message'] = error_message
                updates['stats'] = stats

        try:
            return self.db.update_session(session_id, updates)
        except Exception as e:
            raise SessionException(f"Failed to fail session: {e}")

    def get_active_sessions(self) -> List[SessionData]:
        """Get all active sessions."""
        return self.list_sessions('active')

    def get_resumable_sessions(self) -> List[SessionData]:
        """Get sessions that can be resumed."""
        return self.list_sessions('paused')

    def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return self.get_session(session_id) is not None

    def get_sessions_by_url(self, url: str) -> List[SessionData]:
        """Get all sessions for a specific URL."""
        try:
            all_sessions = self.list_sessions()
            return [session for session in all_sessions if session.url == url]
        except Exception as e:
            raise SessionException(f"Failed to get sessions by URL: {e}")

    def update_session_progress(self, session_id: str, stats: DownloadStats) -> bool:
        """Update session with current download progress."""
        return self.update_session(session_id, stats=stats)