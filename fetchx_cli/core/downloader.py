"""Enhanced download engine with temporary directory management."""

import asyncio
import os
import shutil
from pathlib import Path
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from fetchx_cli.config.settings import get_config
from fetchx_cli.core.connection import ConnectionManager, DownloadSegment
from fetchx_cli.core.merger import FileMerger
from fetchx_cli.utils.exceptions import (DownloadException,
                                         InsufficientSpaceException,
                                         NetworkException)
from fetchx_cli.utils.file_utils import FileManager
from fetchx_cli.utils.folder_manager import FolderManager
from fetchx_cli.utils.logging import LoggerMixin
from fetchx_cli.utils.network import HttpClient, NetworkUtils


@dataclass
class DownloadInfo:
    """Download information and metadata."""

    url: str
    filename: str
    file_path: str
    temp_dir: str  # NEW: Temporary directory for this download
    total_size: Optional[int] = None
    supports_ranges: bool = False
    content_type: Optional[str] = None
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class SegmentProgress:
    """Detailed progress information for a download segment."""

    segment_id: int
    downloaded: int
    total_size: int
    speed: float
    eta: Optional[float]
    status: str  # downloading, completed, failed, paused
    retry_count: int = 0
    start_byte: int = 0
    end_byte: int = 0
    elapsed_time: float = 0
    last_update: float = field(default_factory=time.time)


@dataclass
class DownloadStats:
    """Enhanced download statistics with detailed segment tracking."""

    start_time: float = field(default_factory=time.time)
    downloaded: int = 0
    total_size: Optional[int] = None
    speed: float = 0.0
    eta: Optional[float] = None
    segments: Dict[int, SegmentProgress] = field(default_factory=dict)
    is_paused: bool = False
    active_connections: int = 0
    completed_connections: int = 0
    total_connections: int = 0
    temp_dir: Optional[str] = None  # NEW: Track temp directory

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_size and self.total_size > 0:
            return min((self.downloaded / self.total_size) * 100, 100.0)
        return 0.0

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time."""
        return time.time() - self.start_time


class EnhancedDownloader(LoggerMixin):
    """Enhanced download engine with temporary directory management."""

    def __init__(
        self,
        url: str,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        use_organized_folders: bool = True,
    ):
        self.url = url
        self.headers = headers or {}
        self.config = get_config().config
        self.use_organized_folders = use_organized_folders

        # Setup folder management
        if self.use_organized_folders and not output_dir:
            # Use organized folder structure
            self.folder_manager = FolderManager()
            self.output_dir = None  # Will be determined per file
        else:
            # Use traditional single directory approach
            self.folder_manager = None
            self.output_dir = output_dir or self.config.paths.download_dir
            FileManager.ensure_directory(self.output_dir)

        # Initialize state
        self.download_info: Optional[DownloadInfo] = None
        self.stats = DownloadStats()
        self.segments: List[DownloadSegment] = []
        self.is_paused = False
        self.is_cancelled = False
        self._progress_callbacks: List[Callable] = []
        self._segment_tasks: List[asyncio.Task] = []
        self._connection_managers: List[ConnectionManager] = []

        # Suggested filename
        self._suggested_filename = filename

        # Enhanced performance tracking
        self._speed_samples = []
        self._last_speed_calculation = time.time()
        self._segment_progress_lock = asyncio.Lock()
        self._last_progress_update = time.time()

        # NEW: Temporary directory management
        self._temp_dir: Optional[str] = None
        self._temp_base_dir = self._get_temp_base_dir()

    def _get_temp_base_dir(self) -> str:
        """Get the base temporary directory for FETCHX downloads."""
        # Create a dedicated temp directory for FETCHX
        temp_base = os.path.join(Path.home(), ".fetchx_idm", "temp")
        FileManager.ensure_directory(temp_base)
        return temp_base

    def _create_temp_directory(self, filename: str) -> str:
        """Create a unique temporary directory for this download."""
        # Create a unique temp directory based on filename and timestamp
        safe_filename = FileManager.sanitize_filename(filename)
        timestamp = int(time.time())
        temp_dir_name = f"{safe_filename}_{timestamp}_{os.getpid()}"

        temp_dir = os.path.join(self._temp_base_dir, temp_dir_name)
        FileManager.ensure_directory(temp_dir)

        self.log_info(f"Created temporary directory: {temp_dir}", temp_dir=temp_dir)
        return temp_dir

    def _cleanup_temp_directory(self):
        """Clean up the temporary directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                self.log_info(f"Cleaned up temporary directory: {self._temp_dir}")
            except OSError as e:
                self.log_warning(f"Failed to clean up temp directory: {e}")

    def add_progress_callback(self, callback: Callable):
        """Add progress callback."""
        self._progress_callbacks.append(callback)

    async def get_download_info(self) -> DownloadInfo:
        """Get download information from server."""
        async with HttpClient(
            timeout=self.config.download.connect_timeout,
            user_agent=self.config.download.user_agent,
        ) as client:

            try:
                info = await client.get_file_info(self.url, self.headers)
            except Exception as e:
                raise NetworkException(f"Failed to get file info: {e}")

            # Determine filename
            filename = self._suggested_filename
            if not filename:
                filename = info.get("filename")
            if not filename:
                filename = FileManager.get_filename_from_url(self.url)

            filename = FileManager.sanitize_filename(filename)

            # Create temporary directory for this download
            temp_dir = self._create_temp_directory(filename)
            self._temp_dir = temp_dir

            # Determine final file path
            if self.folder_manager:
                # Use organized folder structure
                file_path = self.folder_manager.get_organized_download_path(filename, ensure_unique=True)
                self.log_info(f"Using organized folder structure for: {filename}", 
                            category=self.folder_manager.get_category_for_file(filename),
                            organized_path=file_path)
            else:
                # Use traditional single directory approach
                file_path = os.path.join(self.output_dir, filename)
                file_path = FileManager.get_unique_filename(file_path)

            # Check disk space (both temp and final locations)
            if info.get("content_length"):
                # Check temp directory space
                if not FileManager.check_disk_space(temp_dir, info["content_length"]):
                    self._cleanup_temp_directory()
                    raise InsufficientSpaceException(
                        "Insufficient disk space in temporary directory"
                    )

                # Check final directory space
                final_dir = os.path.dirname(file_path) if self.folder_manager else self.output_dir
                if not FileManager.check_disk_space(
                    final_dir, info["content_length"]
                ):
                    self._cleanup_temp_directory()
                    raise InsufficientSpaceException(
                        "Insufficient disk space for download"
                    )

            self.download_info = DownloadInfo(
                url=self.url,
                filename=os.path.basename(file_path),
                file_path=file_path,
                temp_dir=temp_dir,
                total_size=info.get("content_length"),
                supports_ranges=info.get("supports_ranges", False),
                content_type=info.get("content_type"),
                last_modified=info.get("last_modified"),
                etag=info.get("etag"),
                headers=info.get("headers", {}),
            )

            # Update stats with temp directory info
            self.stats.temp_dir = temp_dir

            return self.download_info

    def _create_segments(self, num_connections: int) -> List[DownloadSegment]:
        """Create download segments using temporary directory."""
        if not self.download_info or not self.download_info.total_size:
            # Single segment for unknown size or no range support
            segment = DownloadSegment(
                id=0,
                start=0,
                end=-1,  # Download until end
                file_path=os.path.join(
                    self.download_info.temp_dir, f"{self.download_info.filename}.part0"
                ),
            )
            return [segment]

        if not self.download_info.supports_ranges or num_connections <= 1:
            # Single segment download in temp directory
            segment = DownloadSegment(
                id=0,
                start=0,
                end=self.download_info.total_size - 1,
                file_path=os.path.join(
                    self.download_info.temp_dir, f"{self.download_info.filename}.part0"
                ),
            )
            return [segment]

        # Multi-segment download in temp directory
        total_size = self.download_info.total_size
        segment_size = total_size // num_connections
        segments = []

        for i in range(num_connections):
            start = i * segment_size

            if i == num_connections - 1:
                # Last segment gets remainder
                end = total_size - 1
            else:
                end = start + segment_size - 1

            segment = DownloadSegment(
                id=i,
                start=start,
                end=end,
                file_path=os.path.join(
                    self.download_info.temp_dir,
                    f"{self.download_info.filename}.part{i}",
                ),
            )
            segments.append(segment)

        return segments

    async def _segment_progress_callback(self, segment_id: int, bytes_downloaded: int):
        """Enhanced progress callback with detailed segment tracking."""
        async with self._segment_progress_lock:
            # Update overall downloaded
            self.stats.downloaded += bytes_downloaded

            # Find the corresponding segment
            segment = None
            for s in self.segments:
                if s.id == segment_id:
                    segment = s
                    break

            if not segment:
                return

            # Update or create segment progress
            if segment_id not in self.stats.segments:
                segment_size = (
                    segment.end - segment.start + 1 if segment.end != -1 else 0
                )
                self.stats.segments[segment_id] = SegmentProgress(
                    segment_id=segment_id,
                    downloaded=0,
                    total_size=segment_size,
                    speed=0.0,
                    eta=None,
                    status="downloading",
                    start_byte=segment.start,
                    end_byte=segment.end,
                )

            segment_progress = self.stats.segments[segment_id]
            segment_progress.downloaded += bytes_downloaded
            segment_progress.last_update = time.time()
            segment_progress.elapsed_time = (
                segment_progress.last_update - self.stats.start_time
            )

            # Calculate segment speed
            if segment_progress.elapsed_time > 0:
                segment_progress.speed = (
                    segment_progress.downloaded / segment_progress.elapsed_time
                )

                # Calculate segment ETA
                if segment_progress.total_size > 0 and segment_progress.speed > 0:
                    remaining = (
                        segment_progress.total_size - segment_progress.downloaded
                    )
                    segment_progress.eta = remaining / segment_progress.speed

            # Update segment status based on actual segment state
            if segment.completed:
                segment_progress.status = "completed"
            elif segment.is_paused:
                segment_progress.status = "paused"
            elif segment.retry_count > 0:
                segment_progress.status = "retrying"
            else:
                segment_progress.status = "downloading"

            segment_progress.retry_count = segment.retry_count

            # Update overall statistics
            self._update_overall_stats()

            # Throttled progress callbacks (update every 100ms)
            current_time = time.time()
            if current_time - self._last_progress_update >= 0.1:
                self._last_progress_update = current_time
                await self._notify_progress_callbacks()

    def _update_overall_stats(self):
        """Update overall download statistics based on segment data."""
        # Count connection states
        self.stats.active_connections = len(
            [s for s in self.stats.segments.values() if s.status == "downloading"]
        )

        self.stats.completed_connections = len(
            [s for s in self.stats.segments.values() if s.status == "completed"]
        )

        self.stats.total_connections = len(self.stats.segments)

        # Calculate overall speed (sum of all active segment speeds)
        active_speeds = [
            s.speed
            for s in self.stats.segments.values()
            if s.status == "downloading" and s.speed > 0
        ]

        if active_speeds:
            self.stats.speed = sum(active_speeds)
        else:
            # Fallback calculation
            elapsed = self.stats.elapsed_time
            self.stats.speed = self.stats.downloaded / elapsed if elapsed > 0 else 0

        # Calculate overall ETA
        if self.stats.total_size and self.stats.speed > 0:
            remaining = self.stats.total_size - self.stats.downloaded
            self.stats.eta = remaining / self.stats.speed

    async def _notify_progress_callbacks(self):
        """Notify all progress callbacks with current stats."""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.stats)
                else:
                    callback(self.stats)
            except Exception as e:
                self.log_warning(f"Progress callback error: {e}")

    async def download(self, max_connections: Optional[int] = None) -> str:
        """Start the download process with enhanced tracking."""
        if not NetworkUtils.is_valid_url(self.url):
            raise DownloadException(f"Invalid URL: {self.url}")

        # Get download info
        if not self.download_info:
            await self.get_download_info()

        # Determine number of connections
        if max_connections is None:
            max_connections = self.config.download.max_connections

        # Create segments
        self.segments = self._create_segments(max_connections)
        self.stats.total_size = self.download_info.total_size
        self.stats.total_connections = len(self.segments)

        self.log_info(
            f"Starting download with {len(self.segments)} segments",
            segments=len(self.segments),
            total_size=self.stats.total_size,
            temp_dir=self.download_info.temp_dir,
        )

        try:
            # Create connection managers for each segment
            tasks = []
            for segment in self.segments:
                conn_manager = ConnectionManager(
                    self.url,
                    self.headers,
                    self.config.download.timeout,
                    self.config.download.max_retries,
                    self.config.download.retry_delay,
                )
                self._connection_managers.append(conn_manager)

                task = asyncio.create_task(
                    self._download_segment_with_manager(conn_manager, segment)
                )
                tasks.append(task)

            self._segment_tasks = tasks

            # Wait for all segments to complete
            await asyncio.gather(*tasks)

            # Mark all segments as completed
            for segment_id in self.stats.segments:
                self.stats.segments[segment_id].status = "completed"

            # Update final stats
            self.stats.completed_connections = self.stats.total_connections
            self.stats.active_connections = 0

            # Merge segments and move to final location
            await self._finalize_download()

            self.log_info(
                "Download completed successfully",
                file_path=self.download_info.file_path,
            )
            return self.download_info.file_path

        except Exception as e:
            # Clean up on failure
            await self._cleanup_segments()
            self._cleanup_temp_directory()
            self.log_error(f"Download failed: {e}")
            raise DownloadException(f"Download failed: {e}")

    async def _finalize_download(self):
        """Merge segments and move final file to destination."""
        temp_final_path = os.path.join(
            self.download_info.temp_dir, self.download_info.filename
        )

        if len(self.segments) > 1:
            # Merge segments in temp directory
            part_files = [segment.file_path for segment in self.segments]

            self.log_info(
                "Merging segments in temporary directory", part_count=len(part_files)
            )

            # Progress callback for merge operation
            def merge_progress_callback(
                percentage: float, bytes_processed: int, total_size: int
            ):
                self.log_debug(
                    f"Merge progress: {percentage:.1f}% ({bytes_processed}/{total_size} bytes)"
                )

            try:
                await FileMerger.merge_parts(
                    part_files, temp_final_path, merge_progress_callback
                )
                self.log_info("File merge completed in temp directory")
            except Exception as e:
                self.log_error(f"File merge failed: {e}")
                raise DownloadException(f"Failed to merge segments: {e}")
        else:
            # Single file - just rename in temp directory
            os.rename(self.segments[0].file_path, temp_final_path)

        # Move final file from temp to destination
        self.log_info(
            f"Moving file from temp to final location: {self.download_info.file_path}"
        )

        try:
            # Use atomic move operation
            await FileManager.atomic_move(temp_final_path, self.download_info.file_path)
            self.log_info("File successfully moved to final destination")
        except Exception as e:
            self.log_error(f"Failed to move file to final destination: {e}")
            raise DownloadException(f"Failed to move file to destination: {e}")
        finally:
            # Clean up temp directory
            self._cleanup_temp_directory()

    async def _download_segment_with_manager(
        self, conn_manager: ConnectionManager, segment: DownloadSegment
    ):
        """Download a single segment with its own connection manager."""
        async with conn_manager:
            try:
                await conn_manager.download_segment(
                    segment, self._segment_progress_callback
                )
                self.log_debug(f"Segment {segment.id} completed", segment_id=segment.id)
            except Exception as e:
                self.log_error(
                    f"Segment {segment.id} failed: {e}", segment_id=segment.id
                )
                # Update segment status
                if segment.id in self.stats.segments:
                    self.stats.segments[segment.id].status = "failed"
                raise DownloadException(f"Segment {segment.id} failed: {e}")

    async def _cleanup_segments(self):
        """Clean up segment files on failure."""
        for segment in self.segments:
            try:
                if os.path.exists(segment.file_path):
                    os.remove(segment.file_path)
            except OSError:
                pass

    async def pause(self):
        """Pause the download."""
        self.is_paused = True
        self.stats.is_paused = True

        self.log_info("Pausing download")

        # Pause all segments
        for segment in self.segments:
            segment.is_paused = True
            if segment.id in self.stats.segments:
                self.stats.segments[segment.id].status = "paused"

        # Update stats
        self.stats.active_connections = 0

        # Cancel all running tasks
        for task in self._segment_tasks:
            if not task.done():
                task.cancel()

    async def resume(self):
        """Resume the download."""
        if not self.is_paused:
            return

        self.is_paused = False
        self.stats.is_paused = False

        self.log_info("Resuming download")

        # Resume all segments
        for segment in self.segments:
            if not segment.completed:
                segment.is_paused = False
                if segment.id in self.stats.segments:
                    self.stats.segments[segment.id].status = "downloading"

        # Update stats
        self._update_overall_stats()

        # Restart incomplete segments
        incomplete_segments = [s for s in self.segments if not s.completed]
        if incomplete_segments:
            tasks = []
            for segment in incomplete_segments:
                conn_manager = ConnectionManager(
                    self.url,
                    self.headers,
                    self.config.download.timeout,
                    self.config.download.max_retries,
                    self.config.download.retry_delay,
                )

                task = asyncio.create_task(
                    self._download_segment_with_manager(conn_manager, segment)
                )
                tasks.append(task)

            self._segment_tasks = tasks
            await asyncio.gather(*tasks, return_exceptions=True)

    async def cancel(self):
        """Cancel the download."""
        self.is_cancelled = True
        self.log_info("Cancelling download")
        await self.pause()
        await self._cleanup_segments()
        self._cleanup_temp_directory()

    def get_stats(self) -> DownloadStats:
        """Get current download statistics."""
        return self.stats

    def get_segment_info(self) -> List[Dict]:
        """Get detailed information about all segments."""
        segment_info = []
        for segment in self.segments:
            # Get progress info if available
            progress_info = self.stats.segments.get(segment.id)

            info = {
                "id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "downloaded": (
                    progress_info.downloaded if progress_info else segment.downloaded
                ),
                "total_size": (
                    segment.end - segment.start + 1 if segment.end != -1 else 0
                ),
                "progress_percentage": 0.0,
                "speed": progress_info.speed if progress_info else segment.speed,
                "eta": progress_info.eta if progress_info else segment.eta,
                "completed": segment.completed,
                "paused": segment.is_paused,
                "retry_count": segment.retry_count,
                "status": (
                    progress_info.status
                    if progress_info
                    else ("completed" if segment.completed else "downloading")
                ),
                "elapsed_time": progress_info.elapsed_time if progress_info else 0,
                "temp_file": segment.file_path,  # NEW: Show temp file location
            }

            if info["total_size"] > 0:
                info["progress_percentage"] = (
                    info["downloaded"] / info["total_size"]
                ) * 100

            segment_info.append(info)

        return segment_info

    def get_connection_summary(self) -> Dict[str, any]:
        """Get a summary of all connections."""
        segments = self.get_segment_info()

        return {
            "total_connections": len(segments),
            "active_connections": len(
                [s for s in segments if s["status"] == "downloading"]
            ),
            "completed_connections": len([s for s in segments if s["completed"]]),
            "paused_connections": len([s for s in segments if s["paused"]]),
            "failed_connections": len([s for s in segments if s["status"] == "failed"]),
            "total_speed": sum(s["speed"] for s in segments),
            "total_downloaded": sum(s["downloaded"] for s in segments),
            "average_progress": (
                sum(s["progress_percentage"] for s in segments) / len(segments)
                if segments
                else 0
            ),
            "temp_directory": (
                self.download_info.temp_dir if self.download_info else None
            ),  # NEW
        }


# For backwards compatibility
Downloader = EnhancedDownloader
