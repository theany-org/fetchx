"""Download queue management."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from fetchx_cli.config.settings import get_config
from fetchx_cli.core.database import get_database
from fetchx_cli.core.downloader import Downloader
from fetchx_cli.core.session import SessionManager
from fetchx_cli.utils.exceptions import QueueException


class DownloadStatus(Enum):
    """Download status enumeration."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """Represents an item in the download queue."""

    id: str
    url: str
    filename: Optional[str] = None
    output_dir: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    max_connections: Optional[int] = None
    status: DownloadStatus = DownloadStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    progress_percentage: float = 0.0
    download_speed: float = 0.0
    eta: Optional[float] = None
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, DownloadStatus):
                data[key] = value.value
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueItem":
        """Create from dictionary."""
        # Convert status string back to enum
        if "status" in data:
            data["status"] = DownloadStatus(data["status"])
        return cls(**data)


class QueueManager:
    """SQLite-based queue manager."""

    def __init__(self):
        self.config = get_config().config
        self.db = get_database()

    def add_item(self, item: QueueItem) -> str:
        """Add item to queue."""
        try:
            self.db.add_queue_item(item.to_dict())
            return item.id
        except Exception as e:
            raise QueueException(f"Failed to add item to queue: {e}")

    def get_item(self, item_id: str) -> Optional[QueueItem]:
        """Get item by ID (supports partial ID matching)."""
        try:
            data = self.db.get_queue_item(item_id)
            if data:
                return QueueItem.from_dict(data)
            return None
        except Exception as e:
            raise QueueException(f"Failed to get queue item: {e}")

    def remove_item(self, item_id: str) -> bool:
        """Remove item from queue."""
        try:
            return self.db.remove_queue_item(item_id)
        except Exception as e:
            raise QueueException(f"Failed to remove queue item: {e}")

    def update_item(self, item_id: str, **kwargs) -> bool:
        """Update item properties."""
        try:
            # Convert enum to string if needed
            if "status" in kwargs and isinstance(kwargs["status"], DownloadStatus):
                kwargs["status"] = kwargs["status"].value

            return self.db.update_queue_item(item_id, kwargs)
        except Exception as e:
            raise QueueException(f"Failed to update queue item: {e}")

    def list_items(self, status: Optional[DownloadStatus] = None) -> List[QueueItem]:
        """List items, optionally filtered by status."""
        try:
            status_str = status.value if status else None
            items_data = self.db.list_queue_items(status_str)
            return [QueueItem.from_dict(data) for data in items_data]
        except Exception as e:
            raise QueueException(f"Failed to list queue items: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            return self.db.get_queue_stats()
        except Exception as e:
            raise QueueException(f"Failed to get queue stats: {e}")


class DownloadQueue:
    """Manages download queue and concurrent downloads."""

    def __init__(self):
        self.config = get_config().config
        self.session_manager = SessionManager()
        self.queue_manager = QueueManager()

        self._active_downloads: Dict[str, Downloader] = {}
        self._download_tasks: Dict[str, asyncio.Task] = {}
        self._max_concurrent = self.config.queue.max_concurrent_downloads
        self._is_running = False
        self._queue_task: Optional[asyncio.Task] = None
        self._progress_callbacks: List[Callable] = []

    def add_progress_callback(self, callback: Callable):
        """Add progress callback for queue updates."""
        self._progress_callbacks.append(callback)

    def add_download(
        self,
        url: str,
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        max_connections: Optional[int] = None,
    ) -> str:
        """Add a download to the queue."""
        item_id = str(uuid.uuid4())

        item = QueueItem(
            id=item_id,
            url=url,
            filename=filename,
            output_dir=output_dir,
            headers=headers or {},
            max_connections=max_connections,
        )

        self.queue_manager.add_item(item)
        self._notify_progress()
        return item_id

    def remove_download(self, item_id: str) -> bool:
        """Remove a download from the queue."""
        # Cancel if currently downloading
        if item_id in self._active_downloads or any(
            item_id.startswith(aid) for aid in self._active_downloads.keys()
        ):
            self.cancel_download(item_id)

        # Remove from database
        success = self.queue_manager.remove_item(item_id)
        if success:
            self._notify_progress()
        return success

    def cancel_download(self, item_id: str) -> bool:
        """Cancel an active download."""
        # Find the full item ID if partial ID was provided
        item = self.queue_manager.get_item(item_id)
        if not item:
            return False

        full_item_id = item.id

        # Cancel the download task if it's active
        if full_item_id in self._download_tasks:
            task = self._download_tasks[full_item_id]
            if not task.done():
                task.cancel()

        # Update item status
        success = self.queue_manager.update_item(
            item_id, status=DownloadStatus.CANCELLED, completed_at=time.time()
        )

        if success:
            self._notify_progress()
        return success

    def pause_download(self, item_id: str) -> bool:
        """Pause an active download."""
        # Find the full item ID if partial ID was provided
        item = self.queue_manager.get_item(item_id)
        if not item:
            return False

        full_item_id = item.id

        # Only allow pausing downloads that are currently downloading
        if item.status != DownloadStatus.DOWNLOADING:
            return False

        # Pause the downloader if it's active
        if full_item_id in self._active_downloads:
            downloader = self._active_downloads[full_item_id]
            asyncio.create_task(self._pause_downloader(downloader, full_item_id))

        # Update item status
        success = self.queue_manager.update_item(
            item_id, status=DownloadStatus.PAUSED
        )

        if success:
            self._notify_progress()
        return success

    def resume_download(self, item_id: str) -> bool:
        """Resume a paused download."""
        # Find the full item ID if partial ID was provided
        item = self.queue_manager.get_item(item_id)
        if not item:
            return False

        full_item_id = item.id

        # Only allow resuming paused downloads
        if item.status != DownloadStatus.PAUSED:
            return False

        # Update item status to queued so it will be picked up by the queue processor
        success = self.queue_manager.update_item(
            item_id, status=DownloadStatus.QUEUED
        )

        if success:
            self._notify_progress()
        return success

    async def _pause_downloader(self, downloader, item_id: str):
        """Pause a downloader and save session state."""
        try:
            # Create session to save download state
            session_id = f"session_{item_id}_{int(time.time())}"
            
            # Save session state
            if hasattr(downloader, 'download_info') and downloader.download_info:
                await self.session_manager.create_session(
                    session_id=session_id,
                    url=downloader.url,
                    download_info=downloader.download_info,
                    segments=downloader.segments,
                    headers=downloader.headers
                )
                
                # Update session with current stats
                await self.session_manager.update_session_progress(session_id, downloader.stats)
                
                # Mark session as paused
                await self.session_manager.pause_session(session_id)

            # Pause the actual downloader
            await downloader.pause()
            
        except Exception as e:
            print(f"Error pausing downloader: {e}")

    def get_download(self, item_id: str) -> Optional[QueueItem]:
        """Get download item by ID."""
        return self.queue_manager.get_item(item_id)

    def list_downloads(
        self, status: Optional[DownloadStatus] = None
    ) -> List[QueueItem]:
        """List downloads, optionally filtered by status."""
        return self.queue_manager.list_items(status)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = self.queue_manager.get_stats()
        stats["max_concurrent"] = self._max_concurrent
        return stats

    async def start_queue(self):
        """Start processing the download queue."""
        if self._is_running:
            return

        self._is_running = True
        self._queue_task = asyncio.create_task(self._process_queue())

    async def stop_queue(self):
        """Stop processing the download queue."""
        self._is_running = False

        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass

        # Cancel all active downloads
        for item_id in list(self._active_downloads.keys()):
            await self._cancel_active_download(item_id)

    async def _cancel_active_download(self, item_id: str):
        """Cancel an active download by full ID."""
        if item_id in self._download_tasks:
            task = self._download_tasks[item_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _process_queue(self):
        """Main queue processing loop."""
        while self._is_running:
            try:
                # Start new downloads if under concurrent limit
                while (
                    len(self._active_downloads) < self._max_concurrent
                    and self._has_queued_downloads()
                ):

                    item = self._get_next_queued_item()
                    if item:
                        await self._start_download(item)

                # Check for completed downloads
                await self._check_completed_downloads()

                # Sleep before next iteration
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error and continue
                print(f"Queue processing error: {e}")
                await asyncio.sleep(5)

    def _has_queued_downloads(self) -> bool:
        """Check if there are queued downloads."""
        return len(self.queue_manager.list_items(DownloadStatus.QUEUED)) > 0

    def _get_next_queued_item(self) -> Optional[QueueItem]:
        """Get the next queued download."""
        queued_items = self.queue_manager.list_items(DownloadStatus.QUEUED)
        return queued_items[0] if queued_items else None

    async def _start_download(self, item: QueueItem):
        """Start downloading an item."""
        try:
            # Create downloader
            downloader = Downloader(
                url=item.url,
                output_dir=item.output_dir,
                filename=item.filename,
                headers=item.headers,
            )

            # Add progress callback
            downloader.add_progress_callback(
                lambda stats, item_id=item.id: self._update_item_progress(
                    item_id, stats
                )
            )

            # Update item status
            self.queue_manager.update_item(
                item.id, status=DownloadStatus.DOWNLOADING, started_at=time.time()
            )

            # Store downloader and create task
            self._active_downloads[item.id] = downloader
            task = asyncio.create_task(self._download_wrapper(item, downloader))
            self._download_tasks[item.id] = task

            self._notify_progress()

        except Exception as e:
            self.queue_manager.update_item(
                item.id,
                status=DownloadStatus.FAILED,
                error_message=str(e),
                completed_at=time.time(),
            )
            self._notify_progress()

    async def _download_wrapper(self, item: QueueItem, downloader: Downloader):
        """Wrapper for download execution with error handling."""
        try:
            file_path = await downloader.download(item.max_connections)

            # Mark as completed
            self.queue_manager.update_item(
                item.id,
                status=DownloadStatus.COMPLETED,
                file_path=file_path,
                completed_at=time.time(),
                progress_percentage=100.0,
            )

        except asyncio.CancelledError:
            self.queue_manager.update_item(
                item.id, status=DownloadStatus.CANCELLED, completed_at=time.time()
            )
            raise

        except Exception as e:
            self.queue_manager.update_item(
                item.id,
                status=DownloadStatus.FAILED,
                error_message=str(e),
                completed_at=time.time(),
            )

        finally:
            # Clean up
            if item.id in self._active_downloads:
                del self._active_downloads[item.id]
            if item.id in self._download_tasks:
                del self._download_tasks[item.id]

            self._notify_progress()

    async def _check_completed_downloads(self):
        """Check for and clean up completed downloads."""
        completed_tasks = []

        for item_id, task in self._download_tasks.items():
            if task.done():
                completed_tasks.append(item_id)

        for item_id in completed_tasks:
            if item_id in self._download_tasks:
                del self._download_tasks[item_id]

    def _update_item_progress(self, item_id: str, stats):
        """Update progress for a download item."""
        self.queue_manager.update_item(
            item_id,
            progress_percentage=stats.progress_percentage,
            download_speed=stats.speed,
            eta=stats.eta,
        )
        self._notify_progress()

    def _notify_progress(self):
        """Notify progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(self))
                else:
                    callback(self)
            except Exception:
                pass  # Ignore callback errors
