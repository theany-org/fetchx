"""High-performance file merger for FETCHX IDM downloads."""

import os
import asyncio
import aiofiles
import tempfile
import shutil
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from fetchx_cli.utils.exceptions import FileException
from fetchx_cli.utils.logging import LoggerMixin


class FileMerger(LoggerMixin):
    """High-performance file merger with multiple strategies."""

    # Thread pool for CPU-bound operations
    _thread_pool = ThreadPoolExecutor(max_workers=2)

    # Size thresholds for different merge strategies
    STREAMING_THRESHOLD = 500 * 1024 * 1024  # 500MB - use streaming merge
    ASYNC_THRESHOLD = 50 * 1024 * 1024  # 50MB - use async merge
    SYNC_THRESHOLD = 10 * 1024 * 1024  # 10MB - use sync merge

    @classmethod
    async def merge_parts(
        cls,
        part_files: List[str],
        output_file: str,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Smart merge parts using optimal strategy based on file size."""
        if not part_files:
            raise FileException("No part files to merge")

        merger = cls()

        # Validate all parts exist
        missing_parts = []
        total_size = 0

        for part_file in part_files:
            if not os.path.exists(part_file):
                missing_parts.append(part_file)
            else:
                total_size += os.path.getsize(part_file)

        if missing_parts:
            raise FileException(f"Missing part files: {', '.join(missing_parts)}")

        merger.log_info(
            f"Starting merge of {len(part_files)} parts",
            total_size=total_size,
            strategy="auto",
        )

        # Choose optimal merge strategy based on total size
        if total_size >= cls.STREAMING_THRESHOLD:
            await merger._merge_streaming(part_files, output_file, progress_callback)
        elif total_size >= cls.ASYNC_THRESHOLD:
            await merger._merge_async(part_files, output_file, progress_callback)
        else:
            await merger._merge_sync(part_files, output_file, progress_callback)

    async def _merge_async(
        self,
        part_files: List[str],
        output_file: str,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Async merge for medium-sized files (50-500MB)."""
        self.log_info("Using async merge strategy")

        # Sort part files to ensure correct order
        sorted_parts = sorted(part_files, key=lambda x: int(x.split(".part")[-1]))

        # Use larger buffer for better performance
        buffer_size = 8 * 1024 * 1024  # 8MB buffer
        temp_file = output_file + ".tmp"

        try:
            bytes_processed = 0
            total_size = sum(os.path.getsize(part) for part in sorted_parts)

            async with aiofiles.open(temp_file, "wb") as output:
                for i, part_file in enumerate(sorted_parts):
                    self.log_debug(
                        f"Merging part {i + 1}/{len(sorted_parts)}: {part_file}"
                    )

                    async with aiofiles.open(part_file, "rb") as part:
                        while True:
                            chunk = await part.read(buffer_size)
                            if not chunk:
                                break

                            await output.write(chunk)
                            bytes_processed += len(chunk)

                            # Progress callback
                            if progress_callback:
                                try:
                                    progress_percentage = (
                                        bytes_processed / total_size
                                    ) * 100
                                    if asyncio.iscoroutinefunction(progress_callback):
                                        await progress_callback(
                                            progress_percentage,
                                            bytes_processed,
                                            total_size,
                                        )
                                    else:
                                        progress_callback(
                                            progress_percentage,
                                            bytes_processed,
                                            total_size,
                                        )
                                except Exception as e:
                                    self.log_warning(f"Progress callback error: {e}")

                # Flush the async file buffer
                await output.flush()

            # Sync fsync for data integrity
            await self._sync_fsync(temp_file)

            # Verify merge
            await self._verify_merge(sorted_parts, temp_file)

            # Atomically move to final location
            await self._atomic_move(temp_file, output_file)

            # Clean up part files
            await self._cleanup_parts(sorted_parts)

            self.log_info("Async merge completed successfully", output_file=output_file)

        except Exception as e:
            # Clean up temp file on error
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
            raise FileException(f"Async merge failed: {e}")

    async def _merge_streaming(
        self,
        part_files: List[str],
        output_file: str,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Streaming merge for large files (>500MB) to minimize memory usage."""
        self.log_info("Using streaming merge strategy for large file")

        sorted_parts = sorted(part_files, key=lambda x: int(x.split(".part")[-1]))

        # Use very large buffer for streaming
        buffer_size = 32 * 1024 * 1024  # 32MB buffer for large files
        temp_file = output_file + ".tmp"

        try:
            bytes_processed = 0
            total_size = sum(os.path.getsize(part) for part in sorted_parts)

            # Use sync I/O for streaming large files (often faster for very large files)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._thread_pool,
                self._streaming_merge_sync,
                sorted_parts,
                temp_file,
                total_size,
                progress_callback,
            )

            # Verify merge
            await self._verify_merge(sorted_parts, temp_file)

            # Atomically move to final location
            os.rename(temp_file, output_file)

            # Clean up part files
            await self._cleanup_parts(sorted_parts)

            self.log_info(
                "Streaming merge completed successfully", output_file=output_file
            )

        except Exception as e:
            # Clean up temp file on error
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
            raise FileException(f"Streaming merge failed: {e}")

    def _streaming_merge_sync(
        self,
        sorted_parts: List[str],
        temp_file: str,
        total_size: int,
        progress_callback: Optional[Callable],
    ) -> None:
        """Synchronous streaming merge for maximum performance on large files."""
        buffer_size = 32 * 1024 * 1024  # 32MB buffer
        bytes_processed = 0

        with open(temp_file, "wb") as output:
            for i, part_file in enumerate(sorted_parts):
                with open(part_file, "rb") as part:
                    while True:
                        chunk = part.read(buffer_size)
                        if not chunk:
                            break

                        output.write(chunk)
                        bytes_processed += len(chunk)

                        # Less frequent progress updates for performance
                        if (
                            progress_callback
                            and bytes_processed % (100 * 1024 * 1024) == 0
                        ):  # Every 100MB
                            try:
                                progress_percentage = (
                                    bytes_processed / total_size
                                ) * 100
                                progress_callback(
                                    progress_percentage, bytes_processed, total_size
                                )
                            except:
                                pass  # Ignore callback errors

            # Force flush and sync
            output.flush()
            os.fsync(output.fileno())

    async def _merge_sync(
        self,
        part_files: List[str],
        output_file: str,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Sync merge for small files (<50MB) - fastest for small files."""
        self.log_info("Using sync merge strategy for small file")

        sorted_parts = sorted(part_files, key=lambda x: int(x.split(".part")[-1]))
        temp_file = output_file + ".tmp"

        try:
            total_size = sum(os.path.getsize(part) for part in sorted_parts)

            # Use thread pool for sync operations
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._thread_pool,
                self._sync_merge_impl,
                sorted_parts,
                temp_file,
                total_size,
                progress_callback,
            )

            # Verify merge
            await self._verify_merge(sorted_parts, temp_file)

            # Atomically move to final location
            os.rename(temp_file, output_file)

            # Clean up part files
            for part_file in sorted_parts:
                try:
                    os.remove(part_file)
                except OSError:
                    pass

            self.log_info("Sync merge completed successfully", output_file=output_file)

        except Exception as e:
            # Clean up temp file on error
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
            raise FileException(f"Sync merge failed: {e}")

    def _sync_merge_impl(
        self,
        sorted_parts: List[str],
        temp_file: str,
        total_size: int,
        progress_callback: Optional[Callable],
    ) -> None:
        """Synchronous merge implementation for small files."""
        buffer_size = 4 * 1024 * 1024  # 4MB buffer for small files
        bytes_processed = 0

        with open(temp_file, "wb") as output:
            for part_file in sorted_parts:
                with open(part_file, "rb") as part:
                    while True:
                        chunk = part.read(buffer_size)
                        if not chunk:
                            break

                        output.write(chunk)
                        bytes_processed += len(chunk)

                        # Progress callback for small files
                        if progress_callback:
                            try:
                                progress_percentage = (
                                    bytes_processed / total_size
                                ) * 100
                                progress_callback(
                                    progress_percentage, bytes_processed, total_size
                                )
                            except:
                                pass

            # Force flush and sync
            output.flush()
            os.fsync(output.fileno())

    async def _sync_fsync(self, filepath: str) -> None:
        """Perform synchronous fsync for data integrity."""

        def sync_fsync():
            with open(filepath, "r+b") as f:
                f.flush()
                os.fsync(f.fileno())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._thread_pool, sync_fsync)

    async def _verify_merge(self, part_files: List[str], merged_file: str) -> None:
        """Verify that the merged file has the correct size."""
        expected_size = sum(os.path.getsize(part) for part in part_files)
        actual_size = os.path.getsize(merged_file)

        if actual_size != expected_size:
            raise FileException(
                f"Merged file size mismatch: expected {expected_size}, got {actual_size}"
            )

        self.log_debug(
            "Merge verification successful",
            expected_size=expected_size,
            actual_size=actual_size,
        )

    async def _atomic_move(self, source: str, destination: str) -> None:
        """Atomically move a file."""
        try:
            # Try atomic move on same filesystem
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._thread_pool, os.rename, source, destination
            )
        except OSError:
            # Fallback to copy+delete for cross-filesystem moves
            await self._copy_and_delete(source, destination)

    async def _copy_and_delete(self, source: str, destination: str) -> None:
        """Copy file and delete source for cross-filesystem moves."""
        try:
            # Copy file efficiently
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._thread_pool,
                shutil.copy2,  # Preserves metadata
                source,
                destination,
            )

            # Verify copy
            if os.path.getsize(source) != os.path.getsize(destination):
                raise FileException("Copy verification failed")

            # Delete source
            await loop.run_in_executor(self._thread_pool, os.remove, source)

        except Exception as e:
            # Clean up failed destination
            try:
                if os.path.exists(destination):
                    os.remove(destination)
            except OSError:
                pass
            raise FileException(f"Failed to copy file: {e}")

    async def _cleanup_parts(self, part_files: List[str]) -> None:
        """Clean up part files after successful merge."""
        cleanup_tasks = []
        for part_file in part_files:
            cleanup_tasks.append(self._cleanup_single_part(part_file))

        await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    async def _cleanup_single_part(self, part_file: str) -> None:
        """Clean up a single part file."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._thread_pool, os.remove, part_file)
        except OSError:
            pass  # Ignore cleanup errors

    @classmethod
    def cleanup_thread_pool(cls):
        """Clean up thread pool on shutdown."""
        if cls._thread_pool:
            cls._thread_pool.shutdown(wait=True)


# Convenience functions for backward compatibility
async def merge_parts(
    part_files: List[str],
    output_file: str,
    progress_callback: Optional[Callable] = None,
) -> None:
    """Merge downloaded parts into final file using optimal strategy."""
    await FileMerger.merge_parts(part_files, output_file, progress_callback)


async def merge_parts_streaming(
    part_files: List[str],
    output_file: str,
    progress_callback: Optional[Callable] = None,
) -> None:
    """Force streaming merge for very large files."""
    merger = FileMerger()
    await merger._merge_streaming(part_files, output_file, progress_callback)


async def merge_parts_async(
    part_files: List[str],
    output_file: str,
    progress_callback: Optional[Callable] = None,
) -> None:
    """Force async merge for medium files."""
    merger = FileMerger()
    await merger._merge_async(part_files, output_file, progress_callback)
