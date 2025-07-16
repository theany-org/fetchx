"""Ultra high-performance connection management for maximum download speeds."""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Dict, Callable

import aiofiles
import aiohttp

from fetchx_cli.utils.exceptions import ConnectionException
from fetchx_cli.utils.logging import LoggerMixin
from fetchx_cli.utils.network import HttpClient


@dataclass
class DownloadSegment:
    """Represents a download segment."""

    id: int
    start: int
    end: int
    downloaded: int = 0
    completed: bool = False
    retry_count: int = 0
    file_path: str = ""
    is_paused: bool = False
    speed: float = 0.0
    eta: Optional[float] = None


class ConnectionManager(LoggerMixin):
    """Ultra high-performance connection manager optimized for maximum speed."""

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = HttpClient(
            timeout=self.timeout, user_agent=self.headers.get("User-Agent")
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def download_segment(
        self, segment: DownloadSegment, progress_callback: Optional[Callable] = None
    ) -> bool:
        """Ultra-optimized segment download for maximum performance."""
        if not self._client:
            raise ConnectionException("Connection manager not initialized")

        retry_count = 0

        while retry_count <= self.max_retries:
            response = None

            try:
                # Quick pause check
                if segment.is_paused:
                    await asyncio.sleep(0.05)  # Minimal sleep
                    continue

                # Calculate current start position
                current_start = segment.start + segment.downloaded

                # Quick completion check
                if segment.end != -1 and current_start > segment.end:
                    segment.completed = True
                    return True

                # Get response
                response = await self._client.download_range(
                    self.url, current_start, segment.end, self.headers
                )

                if response is None:
                    raise ConnectionException(f"No response for segment {segment.id}")

                # ULTRA-OPTIMIZED DOWNLOAD CORE
                success = await self._ultra_fast_download(
                    segment, response, progress_callback
                )

                if success:
                    # Quick completion check
                    if segment.end != -1:
                        expected_size = segment.end - segment.start + 1
                        if segment.downloaded >= expected_size * 0.99:  # 99% threshold
                            segment.completed = True
                            return True
                    else:
                        segment.completed = True
                        return True

            except asyncio.CancelledError:
                segment.is_paused = True
                raise

            except Exception as e:
                retry_count += 1
                segment.retry_count = retry_count

                if retry_count > self.max_retries:
                    raise ConnectionException(
                        f"Segment {segment.id} failed after {self.max_retries} retries: {e}"
                    )

                # Quick retry delay
                await asyncio.sleep(min(self.retry_delay * retry_count, 5))

            finally:
                if response and not response.closed:
                    try:
                        response.close()
                    except:
                        pass

        return False

    async def _ultra_fast_download(
        self,
        segment: DownloadSegment,
        response: aiohttp.ClientResponse,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """Ultra-optimized download core - maximum performance."""

        # PERFORMANCE SETTINGS - Optimized for speed
        CHUNK_SIZE = 2 * 1024 * 1024  # 2MB chunks for maximum throughput
        FILE_BUFFER = 16 * 1024 * 1024  # 16MB file buffer
        PROGRESS_INTERVAL = 50 * 1024 * 1024  # Update every 50MB
        TIME_INTERVAL = 5.0  # Or every 5 seconds

        # File mode - append for resume, write for new
        mode = "ab" if segment.downloaded > 0 else "wb"

        # Performance tracking
        start_time = time.time()
        last_update_time = start_time
        bytes_since_update = 0
        total_start_bytes = segment.downloaded

        try:
            # Ultra-optimized file operations
            async with aiofiles.open(
                segment.file_path, mode, buffering=FILE_BUFFER
            ) as f:

                # Streamlined download loop - minimal overhead
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break

                    # Ultra-fast pause check (no function calls)
                    if segment.is_paused:
                        return False

                    # Write immediately - no buffering delays
                    await f.write(chunk)

                    # Update counters
                    chunk_size = len(chunk)
                    segment.downloaded += chunk_size
                    bytes_since_update += chunk_size

                    # Minimal progress updates for maximum speed
                    current_time = time.time()
                    time_diff = current_time - last_update_time

                    if (
                        bytes_since_update >= PROGRESS_INTERVAL
                        or time_diff >= TIME_INTERVAL
                    ):
                        # Efficient speed calculation
                        if time_diff > 0:
                            segment.speed = bytes_since_update / time_diff

                            # Quick ETA calculation
                            if segment.end != -1 and segment.speed > 0:
                                remaining = (
                                    segment.end - segment.start + 1
                                ) - segment.downloaded
                                segment.eta = remaining / segment.speed

                        # Single progress callback with accumulated bytes
                        if progress_callback:
                            try:
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(
                                        segment.id, bytes_since_update
                                    )
                                else:
                                    progress_callback(segment.id, bytes_since_update)
                            except:
                                pass  # Ignore errors for speed

                        # Reset counters
                        bytes_since_update = 0
                        last_update_time = current_time

                # Final update for remaining bytes
                if bytes_since_update > 0 and progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(segment.id, bytes_since_update)
                        else:
                            progress_callback(segment.id, bytes_since_update)
                    except:
                        pass

                # Force flush to disk
                await f.flush()

                return True

        except Exception as e:
            self.log_error(f"Download error for segment {segment.id}: {e}")
            return False

    async def pause_segment(self, segment: DownloadSegment):
        """Pause a segment download."""
        segment.is_paused = True

    async def resume_segment(self, segment: DownloadSegment):
        """Resume a segment download."""
        segment.is_paused = False
