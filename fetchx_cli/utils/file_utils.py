"""Improved file operation utilities with better performance."""

import os
import shutil
import hashlib
import asyncio
import aiofiles
from typing import List, Optional
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
from fetchx_cli.utils.exceptions import FileException

class FileManager:
    """Handles file operations for downloads with improved performance."""

    # Thread pool for CPU-bound operations
    _thread_pool = ThreadPoolExecutor(max_workers=2)

    @staticmethod
    def get_filename_from_url(url: str, suggested_name: Optional[str] = None) -> str:
        """Extract filename from URL or use suggested name."""
        if suggested_name:
            return FileManager.sanitize_filename(suggested_name)

        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))

        if not filename or filename == '/':
            filename = "download"

        return FileManager.sanitize_filename(filename)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Ensure it's not empty
        if not filename:
            filename = "download"

        # Limit length (most filesystems support 255 chars)
        if len(filename) > 250:
            name, ext = os.path.splitext(filename)
            filename = name[:250-len(ext)] + ext

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
    async def merge_parts(part_files: List[str], output_file: str) -> None:
        """Merge downloaded parts into final file with optimized performance."""
        if not part_files:
            raise FileException("No part files to merge")

        # Sort part files to ensure correct order
        sorted_parts = sorted(part_files, key=lambda x: int(x.split('.part')[-1]))

        # Validate all parts exist
        missing_parts = []
        for part_file in sorted_parts:
            if not os.path.exists(part_file):
                missing_parts.append(part_file)

        if missing_parts:
            raise FileException(f"Missing part files: {', '.join(missing_parts)}")

        try:
            # Use larger buffer for better performance
            buffer_size = 8 * 1024 * 1024  # 8MB buffer

            async with aiofiles.open(output_file, 'wb') as output:
                bytes_written = 0

                for part_file in sorted_parts:
                    async with aiofiles.open(part_file, 'rb') as part:
                        while True:
                            chunk = await part.read(buffer_size)
                            if not chunk:
                                break
                            await output.write(chunk)
                            bytes_written += len(chunk)

                # Ensure all data is written to disk
                await output.fsync()

            # Verify the merged file size
            expected_size = sum(os.path.getsize(part) for part in sorted_parts)
            actual_size = os.path.getsize(output_file)

            if actual_size != expected_size:
                raise FileException(f"Merged file size mismatch: expected {expected_size}, got {actual_size}")

            # Clean up part files after successful merge
            cleanup_tasks = []
            for part_file in sorted_parts:
                cleanup_tasks.append(FileManager._cleanup_part_file(part_file))

            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        except Exception as e:
            # Clean up incomplete output file
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
            except OSError:
                pass
            raise FileException(f"Failed to merge parts: {e}")

    @staticmethod
    async def _cleanup_part_file(part_file: str):
        """Clean up a part file asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(FileManager._thread_pool, os.remove, part_file)
        except OSError:
            pass  # Ignore cleanup errors

    @staticmethod
    async def merge_parts_streaming(part_files: List[str], output_file: str) -> None:
        """Merge parts using streaming approach for very large files."""
        if not part_files:
            raise FileException("No part files to merge")

        sorted_parts = sorted(part_files, key=lambda x: int(x.split('.part')[-1]))

        try:
            # Use even larger buffer for streaming
            buffer_size = 16 * 1024 * 1024  # 16MB buffer

            with open(output_file, 'wb') as output:
                for part_file in sorted_parts:
                    if not os.path.exists(part_file):
                        raise FileException(f"Part file not found: {part_file}")

                    with open(part_file, 'rb') as part:
                        while True:
                            chunk = part.read(buffer_size)
                            if not chunk:
                                break
                            output.write(chunk)

                output.flush()
                os.fsync(output.fileno())

            # Clean up part files
            for part_file in sorted_parts:
                try:
                    os.remove(part_file)
                except OSError:
                    pass

        except Exception as e:
            # Clean up incomplete output file
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
            except OSError:
                pass
            raise FileException(f"Failed to merge parts: {e}")

    @staticmethod
    async def calculate_file_hash(filepath: str, algorithm: str = 'sha256') -> str:
        """Calculate hash of a file asynchronously."""
        def _calculate_hash():
            hash_func = hashlib.new(algorithm)
            with open(filepath, 'rb') as f:
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
    async def verify_file_integrity(filepath: str, expected_size: Optional[int] = None,
                                  expected_hash: Optional[str] = None,
                                  hash_algorithm: str = 'sha256') -> bool:
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
                actual_hash = await FileManager.calculate_file_hash(filepath, hash_algorithm)
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
                FileManager._thread_pool,
                os.rename,
                source,
                destination
            )
        except OSError:
            # Fallback to copy+delete for cross-filesystem moves
            await FileManager._copy_and_delete(source, destination)

    @staticmethod
    async def _copy_and_delete(source: str, destination: str) -> None:
        """Copy file and delete source."""
        try:
            # Copy file with progress
            buffer_size = 8 * 1024 * 1024  # 8MB buffer

            async with aiofiles.open(source, 'rb') as src:
                async with aiofiles.open(destination, 'wb') as dst:
                    while True:
                        chunk = await src.read(buffer_size)
                        if not chunk:
                            break
                        await dst.write(chunk)
                    await dst.fsync()

            # Verify copy
            if FileManager.get_file_size(source) != FileManager.get_file_size(destination):
                raise FileException("Copy verification failed")

            # Delete source
            loop = asyncio.get_event_loop()
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
    def create_temp_file(directory: str, prefix: str = "fetchx_", suffix: str = ".tmp") -> str:
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
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(data)
                await f.fsync()

            await FileManager.atomic_move(temp_path, filepath)

        except Exception as e:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise FileException(f"Failed to write file safely: {e}")

    @classmethod
    def cleanup_thread_pool(cls):
        """Clean up thread pool on shutdown."""
        if cls._thread_pool:
            cls._thread_pool.shutdown(wait=True)