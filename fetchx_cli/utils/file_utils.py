"""File operation utilities for FETCHX IDM - now using dedicated merger module."""

import os
import shutil
import hashlib
import asyncio
from typing import List, Optional, Callable
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor

from fetchx_cli.core.merger import (
    merge_parts,
    merge_parts_streaming,
    merge_parts_async,
    FileMerger,
)
from fetchx_cli.utils.exceptions import FileException


class FileManager:
    """Handles file operations for downloads."""

    # Thread pool for CPU-bound operations
    _thread_pool = ThreadPoolExecutor(max_workers=2)

    @staticmethod
    def get_filename_from_url(url: str, suggested_name: Optional[str] = None) -> str:
        """Extract filename from URL or use suggested name."""
        if suggested_name:
            return FileManager.sanitize_filename(suggested_name)

        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))

        if not filename or filename == "/":
            filename = "download"

        return FileManager.sanitize_filename(filename)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Remove leading/trailing dots and spaces
        filename = filename.strip(". ")

        # Ensure it's not empty
        if not filename:
            filename = "download"

        # Limit length (most filesystems support 255 chars)
        if len(filename) > 250:
            name, ext = os.path.splitext(filename)
            filename = name[: 250 - len(ext)] + ext

        return filename

    @staticmethod
    def get_unique_filename(filepath: str) -> str:
        """Get a unique filename if file already exists."""
        if not os.path.exists(filepath):
            return filepath

        base, ext = os.path.splitext(filepath)
        counter = 1

        while True:
            new_path = f"{base}({counter}){ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    @staticmethod
    def check_disk_space(directory: str, required_size: int) -> bool:
        """Check if there's enough disk space for download."""
        try:
            free_space = shutil.disk_usage(directory).free
            # Add 10% buffer for safety
            required_with_buffer = required_size * 1.1
            return free_space >= required_with_buffer
        except OSError:
            return False

    @staticmethod
    def ensure_directory(directory: str) -> None:
        """Ensure directory exists."""
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    async def calculate_file_hash(filepath: str, algorithm: str = "sha256") -> str:
        """Calculate hash of a file asynchronously."""

        def _calculate_hash():
            hash_func = hashlib.new(algorithm)
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    hash_func.update(chunk)
            return hash_func.hexdigest()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(FileManager._thread_pool, _calculate_hash)

    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Get file size in bytes."""
        try:
            return os.path.getsize(filepath)
        except OSError:
            return 0

    @staticmethod
    async def verify_file_integrity(
        filepath: str,
        expected_size: Optional[int] = None,
        expected_hash: Optional[str] = None,
        hash_algorithm: str = "sha256",
    ) -> bool:
        """Verify file integrity."""
        try:
            # Check if file exists
            if not os.path.exists(filepath):
                return False

            # Check file size
            if expected_size is not None:
                actual_size = FileManager.get_file_size(filepath)
                if actual_size != expected_size:
                    return False

            # Check file hash
            if expected_hash is not None:
                actual_hash = await FileManager.calculate_file_hash(
                    filepath, hash_algorithm
                )
                if actual_hash.lower() != expected_hash.lower():
                    return False

            return True

        except Exception:
            return False

    @staticmethod
    def get_available_space(directory: str) -> int:
        """Get available disk space in bytes."""
        try:
            return shutil.disk_usage(directory).free
        except OSError:
            return 0

    @staticmethod
    async def atomic_move(source: str, destination: str) -> None:
        """Atomically move a file."""
        try:
            # First try atomic move on same filesystem
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                FileManager._thread_pool, os.rename, source, destination
            )
        except OSError:
            # Fallback to copy+delete for cross-filesystem moves
            await FileManager._copy_and_delete(source, destination)

    @staticmethod
    async def _copy_and_delete(source: str, destination: str) -> None:
        """Copy file and delete source."""
        try:
            # Copy file efficiently
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                FileManager._thread_pool, shutil.copy2, source, destination
            )

            # Verify copy
            if FileManager.get_file_size(source) != FileManager.get_file_size(
                destination
            ):
                raise FileException("Copy verification failed")

            # Delete source
            await loop.run_in_executor(FileManager._thread_pool, os.remove, source)

        except Exception as e:
            # Clean up failed destination
            try:
                if os.path.exists(destination):
                    os.remove(destination)
            except OSError:
                pass
            raise FileException(f"Failed to copy file: {e}")

    @staticmethod
    def create_temp_file(
        directory: str, prefix: str = "fetchx_", suffix: str = ".tmp"
    ) -> str:
        """Create a temporary file."""
        import tempfile

        fd, temp_path = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=suffix)
        os.close(fd)
        return temp_path

    @staticmethod
    async def safe_write(filepath: str, data: bytes) -> None:
        """Safely write data to file with atomic operation."""
        temp_path = FileManager.create_temp_file(os.path.dirname(filepath))

        try:
            # Write data to temp file
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                FileManager._thread_pool, FileManager._write_sync, temp_path, data
            )

            await FileManager.atomic_move(temp_path, filepath)

        except Exception as e:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise FileException(f"Failed to write file safely: {e}")

    @staticmethod
    def _write_sync(filepath: str, data: bytes) -> None:
        """Synchronous write with fsync."""
        with open(filepath, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    @classmethod
    def cleanup_thread_pool(cls):
        """Clean up thread pool on shutdown."""
        if cls._thread_pool:
            cls._thread_pool.shutdown(wait=True)

        # Also cleanup merger thread pool
        FileMerger.cleanup_thread_pool()


# Backward compatibility - expose merge functions at module level
__all__ = [
    "FileManager",
    "merge_parts",
    "merge_parts_streaming",
    "merge_parts_async",
    "FileMerger",
]
