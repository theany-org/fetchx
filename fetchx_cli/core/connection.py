"""Connection management for multi-threaded downloads."""

import asyncio
import aiofiles
import aiohttp
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from fetchx_cli.utils.network import HttpClient
from fetchx_cli.utils.exceptions import ConnectionException
from fetchx_cli.utils.logging import LoggerMixin

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
    """Manages individual download connections."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None,
                 timeout: int = 30, max_retries: int = 3, retry_delay: int = 2):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = HttpClient(timeout=self.timeout,
                                user_agent=self.headers.get('User-Agent'))
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def download_segment(self, segment: DownloadSegment,
                             progress_callback: Optional[Callable] = None) -> bool:
        """Download a specific segment with improved error handling."""
        if not self._client:
            raise ConnectionException("Connection manager not initialized")

        retry_count = 0
        last_downloaded = segment.downloaded

        self.log_debug(f"Starting download for segment {segment.id}",
                      segment_id=segment.id, start=segment.start, end=segment.end)

        while retry_count <= self.max_retries:
            try:
                # Check if paused
                if segment.is_paused:
                    self.log_debug(f"Segment {segment.id} is paused, waiting...")
                    await asyncio.sleep(1)
                    continue

                # Calculate current start position (resume from where we left off)
                current_start = segment.start + segment.downloaded

                # Skip if already completed
                if current_start > segment.end:
                    segment.completed = True
                    self.log_info(f"Segment {segment.id} already completed", segment_id=segment.id)
                    return True

                self.log_debug(f"Downloading segment {segment.id} from {current_start} to {segment.end}")

                # Download the remaining part of the segment
                response = await self._client.download_range(
                    self.url, current_start, segment.end, self.headers
                )

                if response is None:
                    raise ConnectionException(f"Failed to get response for segment {segment.id}")

                # Open file in append mode for resuming
                mode = 'ab' if segment.downloaded > 0 else 'wb'

                async with aiofiles.open(segment.file_path, mode) as f:
                    # Track progress
                    chunk_count = 0
                    start_time = asyncio.get_event_loop().time()

                    try:
                        # Use aiohttp's content reading method properly
                        async for chunk in response.content.iter_chunked(8192):
                            if not chunk:
                                break

                            # Check if paused
                            if segment.is_paused:
                                await response.close()
                                self.log_debug(f"Segment {segment.id} paused during download")
                                return False

                            await f.write(chunk)
                            segment.downloaded += len(chunk)
                            chunk_count += 1

                            # Calculate speed periodically
                            if chunk_count % 100 == 0:  # Every 100 chunks
                                current_time = asyncio.get_event_loop().time()
                                elapsed = current_time - start_time
                                if elapsed > 0:
                                    bytes_in_period = segment.downloaded - last_downloaded
                                    segment.speed = bytes_in_period / elapsed

                                    # Calculate ETA for this segment
                                    remaining_bytes = (segment.end - segment.start + 1) - segment.downloaded
                                    if segment.speed > 0:
                                        segment.eta = remaining_bytes / segment.speed

                            # Call progress callback
                            if progress_callback:
                                try:
                                    if asyncio.iscoroutinefunction(progress_callback):
                                        await progress_callback(segment.id, len(chunk))
                                    else:
                                        progress_callback(segment.id, len(chunk))
                                except Exception as e:
                                    self.log_warning(f"Progress callback error: {e}", segment_id=segment.id)

                    except Exception as e:
                        self.log_error(f"Error reading response content: {e}", segment_id=segment.id)
                        raise
                    finally:
                        # Ensure response is closed
                        if not response.closed:
                            await response.close()

                segment.completed = True
                self.log_info(f"Segment {segment.id} completed successfully",
                             segment_id=segment.id, downloaded=segment.downloaded)
                return True

            except asyncio.CancelledError:
                self.log_info(f"Segment {segment.id} download cancelled", segment_id=segment.id)
                segment.is_paused = True
                raise

            except Exception as e:
                retry_count += 1
                segment.retry_count = retry_count

                self.log_warning(f"Segment {segment.id} failed (attempt {retry_count}): {e}",
                               segment_id=segment.id, retry_count=retry_count)

                if retry_count > self.max_retries:
                    self.log_error(f"Segment {segment.id} failed after {self.max_retries} retries",
                                 segment_id=segment.id)
                    raise ConnectionException(f"Failed to download segment {segment.id} after {self.max_retries} retries: {e}")

                # Wait before retrying
                await asyncio.sleep(self.retry_delay * retry_count)

        return False

    async def pause_segment(self, segment: DownloadSegment):
        """Pause a segment download."""
        segment.is_paused = True
        self.log_info(f"Segment {segment.id} paused", segment_id=segment.id)

    async def resume_segment(self, segment: DownloadSegment):
        """Resume a segment download."""
        segment.is_paused = False
        self.log_info(f"Segment {segment.id} resumed", segment_id=segment.id)