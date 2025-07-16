"""Improved download engine with better performance."""

import os
import asyncio
import time
import math
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass, field
from fetchx_cli.core.connection import ConnectionManager, DownloadSegment
from fetchx_cli.utils.network import HttpClient, NetworkUtils
from fetchx_cli.utils.file_utils import FileManager
from fetchx_cli.utils.exceptions import (
    DownloadException,
    NetworkException,
    InsufficientSpaceException,
)
from fetchx_cli.config.settings import get_config


@dataclass
class DownloadInfo:
    """Download information and metadata."""

    url: str
    filename: str
    file_path: str
    total_size: Optional[int] = None
    supports_ranges: bool = False
    content_type: Optional[str] = None
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class DownloadStats:
    """Download statistics."""

    start_time: float = field(default_factory=time.time)
    downloaded: int = 0
    total_size: Optional[int] = None
    speed: float = 0.0
    eta: Optional[float] = None
    segments_completed: int = 0
    segments_total: int = 0
    last_update: float = field(default_factory=time.time)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_size and self.total_size > 0:
            return (self.downloaded / self.total_size) * 100
        return 0.0

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time."""
        return time.time() - self.start_time


class ImprovedDownloader:
    """Improved download engine with better performance."""

    def __init__(
        self,
        url: str,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.url = url
        self.headers = headers or {}
        self.config = get_config().config

        # Setup paths
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
        self._segment_locks: Dict[int, asyncio.Lock] = {}

        # Suggested filename
        self._suggested_filename = filename

        # Performance improvements
        self._speed_samples = []
        self._last_speed_calculation = time.time()

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
            file_path = os.path.join(self.output_dir, filename)
            file_path = FileManager.get_unique_filename(file_path)

            # Check disk space
            if info.get("content_length"):
                if not FileManager.check_disk_space(
                    self.output_dir, info["content_length"]
                ):
                    raise InsufficientSpaceException(
                        "Insufficient disk space for download"
                    )

            self.download_info = DownloadInfo(
                url=self.url,
                filename=os.path.basename(file_path),
                file_path=file_path,
                total_size=info.get("content_length"),
                supports_ranges=info.get("supports_ranges", False),
                content_type=info.get("content_type"),
                last_modified=info.get("last_modified"),
                etag=info.get("etag"),
                headers=info.get("headers", {}),
            )

            return self.download_info

    def _calculate_optimal_connections(
        self, file_size: Optional[int], max_connections: int
    ) -> int:
        """Calculate optimal number of connections based on file size."""
        if not file_size or not self.download_info.supports_ranges:
            return 1

        # Minimum segment size should be at least 1MB
        min_segment_size = 1024 * 1024

        # Calculate optimal connections based on file size
        if file_size < min_segment_size:
            return 1
        elif file_size < min_segment_size * 2:
            return 2
        elif file_size < min_segment_size * 4:
            return 4
        elif file_size < min_segment_size * 8:
            return 8
        elif file_size < min_segment_size * 16:
            return 16
        else:
            return min(max_connections, 32)

    def _create_segments(self, num_connections: int) -> List[DownloadSegment]:
        """Create optimized download segments."""
        if not self.download_info or not self.download_info.total_size:
            # Single segment for unknown size
            return [
                DownloadSegment(
                    id=0,
                    start=0,
                    end=-1,
                    file_path=f"{self.download_info.file_path}.part0",
                )
            ]

        if not self.download_info.supports_ranges or num_connections <= 1:
            # Single segment download
            return [
                DownloadSegment(
                    id=0,
                    start=0,
                    end=self.download_info.total_size - 1,
                    file_path=f"{self.download_info.file_path}.part0",
                )
            ]

        # Multi-segment download with optimized sizing
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

            segments.append(
                DownloadSegment(
                    id=i,
                    start=start,
                    end=end,
                    file_path=f"{self.download_info.file_path}.part{i}",
                )
            )

        return segments

    async def _segment_progress_callback(self, segment_id: int, bytes_downloaded: int):
        """Handle progress updates from segments with improved speed calculation."""
        async with self._segment_locks.get(segment_id, asyncio.Lock()):
            self.stats.downloaded += bytes_downloaded

            # Update timestamp
            current_time = time.time()
            self.stats.last_update = current_time

            # Calculate speed with smoothing
            if current_time - self._last_speed_calculation >= 0.5:  # Update every 500ms
                elapsed = self.stats.elapsed_time
                if elapsed > 0:
                    instant_speed = self.stats.downloaded / elapsed

                    # Add to speed samples for smoothing
                    self._speed_samples.append(instant_speed)
                    if len(self._speed_samples) > 10:  # Keep last 10 samples
                        self._speed_samples.pop(0)

                    # Calculate average speed
                    self.stats.speed = sum(self._speed_samples) / len(
                        self._speed_samples
                    )

                    # Calculate ETA
                    if self.stats.total_size and self.stats.speed > 0:
                        remaining = self.stats.total_size - self.stats.downloaded
                        self.stats.eta = remaining / self.stats.speed

                self._last_speed_calculation = current_time

        # Notify progress callbacks (throttled)
        if current_time - getattr(self, "_last_callback", 0) >= 0.1:  # 100ms throttle
            self._last_callback = current_time
            for callback in self._progress_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self.stats)
                    else:
                        callback(self.stats)
                except Exception:
                    pass

    async def download(self, max_connections: Optional[int] = None) -> str:
        """Start the download process with optimizations."""
        if not NetworkUtils.is_valid_url(self.url):
            raise DownloadException(f"Invalid URL: {self.url}")

        # Get download info
        if not self.download_info:
            await self.get_download_info()

        # Calculate optimal connections
        if max_connections is None:
            max_connections = self.config.download.max_connections

        optimal_connections = self._calculate_optimal_connections(
            self.download_info.total_size, max_connections
        )

        # Create segments
        self.segments = self._create_segments(optimal_connections)
        self.stats.segments_total = len(self.segments)
        self.stats.total_size = self.download_info.total_size

        # Initialize segment locks
        for segment in self.segments:
            self._segment_locks[segment.id] = asyncio.Lock()

        # Start download with connection pooling
        semaphore = asyncio.Semaphore(optimal_connections)

        async def download_segment_with_semaphore(segment):
            async with semaphore:
                async with ConnectionManager(
                    self.url,
                    self.headers,
                    self.config.download.timeout,
                    self.config.download.max_retries,
                    self.config.download.retry_delay,
                ) as conn_manager:
                    await self._download_segment(conn_manager, segment)

        try:
            # Start all segment downloads concurrently
            tasks = [
                asyncio.create_task(download_segment_with_semaphore(segment))
                for segment in self.segments
            ]
            self._segment_tasks = tasks

            # Wait for all segments to complete
            await asyncio.gather(*tasks)

            # Merge segments if multiple parts
            if len(self.segments) > 1:
                await self._merge_segments_optimized()
            else:
                # Rename single part file
                os.rename(self.segments[0].file_path, self.download_info.file_path)

            return self.download_info.file_path

        except Exception as e:
            # Clean up on failure
            await self._cleanup_segments()
            raise DownloadException(f"Download failed: {e}")

    async def _download_segment(
        self, conn_manager: ConnectionManager, segment: DownloadSegment
    ):
        """Download a single segment with improved error handling."""
        try:
            await conn_manager.download_segment(
                segment, self._segment_progress_callback
            )
            self.stats.segments_completed += 1
        except Exception as e:
            raise DownloadException(f"Segment {segment.id} failed: {e}")

    async def _merge_segments_optimized(self):
        """Merge downloaded segments with optimized I/O."""
        part_files = [
            segment.file_path for segment in sorted(self.segments, key=lambda s: s.id)
        ]

        # Use larger buffer for faster merging
        buffer_size = 1024 * 1024  # 1MB buffer

        try:
            with open(self.download_info.file_path, "wb") as output_file:
                for part_file in part_files:
                    if not os.path.exists(part_file):
                        raise DownloadException(f"Part file missing: {part_file}")

                    with open(part_file, "rb") as part:
                        while True:
                            chunk = part.read(buffer_size)
                            if not chunk:
                                break
                            output_file.write(chunk)

            # Clean up part files after successful merge
            for part_file in part_files:
                try:
                    os.remove(part_file)
                except OSError:
                    pass

        except Exception as e:
            raise DownloadException(f"Failed to merge segments: {e}")

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
        for task in self._segment_tasks:
            if not task.done():
                task.cancel()

    async def cancel(self):
        """Cancel the download."""
        self.is_cancelled = True
        await self.pause()
        await self._cleanup_segments()

    def get_stats(self) -> DownloadStats:
        """Get current download statistics."""
        return self.stats


# For backwards compatibility
Downloader = ImprovedDownloader
