"""Organized folder structure management for FetchX IDM.

This module provides automatic file categorization and organized folder structure
similar to other Internet Download Managers. Files are automatically sorted into
appropriate category folders based on their file extensions.
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

from fetchx_cli.utils.file_utils import FileManager
from fetchx_cli.utils.logging import LoggerMixin


class FolderManager(LoggerMixin):
    """Manages organized folder structure for downloads with automatic categorization."""

    # File extension mappings to categories
    CATEGORY_EXTENSIONS = {
        "Compressed": {
            ".7z", ".zip", ".rar", ".tar", ".gz", ".bz2", ".xz", ".lzma", 
            ".lz", ".z", ".cab", ".ace", ".arj", ".lha", ".lzh", ".sit",
            ".sitx", ".sea", ".dd", ".dmg", ".hqx", ".cpt"
        },
        "Programs": {
            ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".snap", ".flatpak",
            ".appimage", ".run", ".bin", ".app", ".bat", ".cmd", ".com", ".scr",
            ".vbs", ".ps1", ".sh", ".command", ".jar", ".apk", ".ipa"
        },
        "Music": {
            ".mp3", ".flac", ".wav", ".aac", ".ogg", ".wma", ".m4a", ".opus",
            ".aiff", ".au", ".ra", ".amr", ".ac3", ".dts", ".ape", ".mpc",
            ".tta", ".wv", ".caf", ".m4p", ".m4b"
        },
        "Video": {
            ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
            ".mpg", ".mpeg", ".3gp", ".3g2", ".asf", ".rm", ".rmvb", ".vob",
            ".ts", ".mts", ".m2ts", ".divx", ".xvid", ".ogv", ".f4v", ".swf"
        },
        "Documents": {
            ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages", ".tex",
            ".xls", ".xlsx", ".ods", ".numbers", ".ppt", ".pptx", ".odp",
            ".keynote", ".epub", ".mobi", ".azw", ".azw3", ".fb2", ".lit",
            ".pdb", ".tcr", ".chm", ".hlp", ".info", ".man"
        },
        "Images": {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
            ".svg", ".ico", ".cur", ".psd", ".ai", ".eps", ".raw", ".cr2",
            ".nef", ".orf", ".sr2", ".k25", ".kdc", ".dcr", ".mrw", ".raf",
            ".x3f", ".rw2", ".rwl", ".iiq", ".3fr", ".fff", ".srw", ".arw"
        },
        "Archives": {
            ".iso", ".img", ".bin", ".cue", ".nrg", ".mdf", ".mds", ".toast",
            ".vcd", ".cdi", ".b5t", ".b6t", ".bwt", ".ccd", ".clone", ".dao",
            ".dxp", ".gi", ".lcd", ".mdx", ".pdi", ".tao", ".uif", ".vc4", ".000"
        },
        "Data": {
            ".csv", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf",
            ".log", ".db", ".sqlite", ".sql", ".bak", ".tmp", ".cache", ".dat",
            ".bin", ".hex", ".dump", ".backup"
        }
    }

    def __init__(self, base_download_dir: Optional[str] = None):
        """Initialize folder manager with base download directory.
        
        Args:
            base_download_dir: Base directory for downloads. If None, uses OS default.
        """
        if base_download_dir is None or base_download_dir == "None":
            self.base_download_dir = self._get_default_downloads_dir()
        else:
            self.base_download_dir = base_download_dir
        self.fetchx_root = os.path.join(self.base_download_dir, "FetchX")
        
        # Create reverse lookup for faster categorization
        self._extension_to_category = {}
        for category, extensions in self.CATEGORY_EXTENSIONS.items():
            for ext in extensions:
                self._extension_to_category[ext.lower()] = category

    def _get_default_downloads_dir(self) -> str:
        """Get the OS-specific default Downloads directory.
        
        Returns:
            Path to the default Downloads directory for the current OS.
        """
        system = platform.system().lower()
        
        if system == "windows":
            # Windows: Use USERPROFILE/Downloads or HOMEDRIVE/HOMEPATH/Downloads
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            
            # Try to get the actual Downloads folder from Windows registry/known folders
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                    downloads_dir = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
            except (ImportError, OSError, FileNotFoundError):
                # Fallback to standard location
                pass
                
        elif system == "darwin":  # macOS
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            
        else:  # Linux and other Unix-like systems
            # Try XDG user directories first
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            
            try:
                # Check XDG user directories config
                xdg_config = os.path.join(os.path.expanduser("~"), ".config", "user-dirs.dirs")
                if os.path.exists(xdg_config):
                    with open(xdg_config, 'r') as f:
                        for line in f:
                            if line.startswith('XDG_DOWNLOAD_DIR='):
                                xdg_path = line.split('=', 1)[1].strip().strip('"\'')
                                if xdg_path.startswith('$HOME/'):
                                    downloads_dir = os.path.join(os.path.expanduser("~"), 
                                                                xdg_path[6:])
                                elif xdg_path.startswith('/'):
                                    downloads_dir = xdg_path
                                break
            except (OSError, IOError):
                # Fallback to standard location
                pass

        # Ensure the directory exists
        try:
            FileManager.ensure_directory(downloads_dir)
        except OSError as e:
            self.log_warning(f"Could not create default downloads directory {downloads_dir}: {e}")
            # Ultimate fallback
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        return downloads_dir

    def get_category_for_file(self, filename: str) -> str:
        """Determine the category for a file based on its extension.
        
        Args:
            filename: Name of the file including extension.
            
        Returns:
            Category name (e.g., "Music", "Video", "Documents", "Other").
        """
        if not filename:
            return "Other"
            
        # Get file extension (everything after the last dot, lowercased)
        _, ext = os.path.splitext(filename.lower())
        
        if not ext:
            return "Other"
            
        # Look up category
        category = self._extension_to_category.get(ext, "Other")
        
        self.log_debug(f"Categorized file '{filename}' as '{category}' (extension: {ext})")
        return category

    def get_category_folder_path(self, category: str) -> str:
        """Get the full path to a category folder.
        
        Args:
            category: Category name (e.g., "Music", "Video").
            
        Returns:
            Full path to the category folder.
        """
        return os.path.join(self.fetchx_root, category)

    def get_organized_path_for_file(self, filename: str) -> Tuple[str, str]:
        """Get the organized destination path for a file.
        
        Args:
            filename: Name of the file including extension.
            
        Returns:
            Tuple of (category, full_file_path) where the file should be saved.
        """
        category = self.get_category_for_file(filename)
        category_folder = self.get_category_folder_path(category)
        file_path = os.path.join(category_folder, filename)
        
        return category, file_path

    def ensure_category_folders(self) -> Dict[str, bool]:
        """Create all category folders if they don't exist.
        
        Returns:
            Dictionary mapping category names to creation success status.
        """
        results = {}
        
        # Ensure main FetchX folder exists
        try:
            FileManager.ensure_directory(self.fetchx_root)
            self.log_info(f"Created/verified FetchX root directory: {self.fetchx_root}")
        except OSError as e:
            self.log_error(f"Failed to create FetchX root directory: {e}")
            return {"root": False}

        # Create all category folders
        categories = list(self.CATEGORY_EXTENSIONS.keys()) + ["Other"]
        
        for category in categories:
            category_path = self.get_category_folder_path(category)
            try:
                FileManager.ensure_directory(category_path)
                results[category] = True
                self.log_debug(f"Created/verified category folder: {category_path}")
            except OSError as e:
                self.log_error(f"Failed to create category folder {category}: {e}")
                results[category] = False

        return results

    def get_organized_download_path(self, filename: str, ensure_unique: bool = True) -> str:
        """Get the complete organized path where a file should be downloaded.
        
        Args:
            filename: Original filename including extension.
            ensure_unique: If True, modify filename to avoid conflicts.
            
        Returns:
            Full path where the file should be saved.
        """
        # Ensure category folders exist
        self.ensure_category_folders()
        
        # Get organized path
        category, file_path = self.get_organized_path_for_file(filename)
        
        # Make filename unique if requested
        if ensure_unique:
            file_path = FileManager.get_unique_filename(file_path)
            
        self.log_info(f"Organized download path: {filename} -> {file_path} (category: {category})")
        return file_path

    def move_file_to_organized_location(self, source_path: str, filename: Optional[str] = None) -> str:
        """Move an existing file to its organized location.
        
        Args:
            source_path: Current path of the file.
            filename: Override filename (uses basename of source_path if None).
            
        Returns:
            New path where the file was moved.
            
        Raises:
            OSError: If the move operation fails.
        """
        if not os.path.exists(source_path):
            raise OSError(f"Source file does not exist: {source_path}")
            
        if filename is None:
            filename = os.path.basename(source_path)
            
        # Get organized destination
        destination_path = self.get_organized_download_path(filename, ensure_unique=True)
        
        try:
            # Use atomic move
            shutil.move(source_path, destination_path)
            self.log_info(f"Moved file to organized location: {source_path} -> {destination_path}")
            return destination_path
        except (OSError, shutil.Error) as e:
            self.log_error(f"Failed to move file to organized location: {e}")
            raise OSError(f"Failed to move file to organized location: {e}")

    def get_folder_info(self) -> Dict[str, Dict[str, any]]:
        """Get information about the organized folder structure.
        
        Returns:
            Dictionary with information about each category folder.
        """
        info = {
            "root_path": self.fetchx_root,
            "base_downloads_dir": self.base_download_dir,
            "categories": {}
        }
        
        categories = list(self.CATEGORY_EXTENSIONS.keys()) + ["Other"]
        
        for category in categories:
            category_path = self.get_category_folder_path(category)
            category_info = {
                "path": category_path,
                "exists": os.path.exists(category_path),
                "file_count": 0,
                "total_size": 0,
                "extensions": list(self.CATEGORY_EXTENSIONS.get(category, set()))
            }
            
            if category_info["exists"]:
                try:
                    # Count files and calculate size
                    for item in os.listdir(category_path):
                        item_path = os.path.join(category_path, item)
                        if os.path.isfile(item_path):
                            category_info["file_count"] += 1
                            try:
                                category_info["total_size"] += os.path.getsize(item_path)
                            except OSError:
                                pass
                except OSError:
                    pass
                    
            info["categories"][category] = category_info
            
        return info

    def validate_permissions(self) -> Dict[str, bool]:
        """Validate that we have proper permissions for the organized folders.
        
        Returns:
            Dictionary mapping paths to permission status.
        """
        results = {}
        
        # Check base downloads directory
        results["base_downloads"] = self._check_directory_permissions(self.base_download_dir)
        
        # Check FetchX root
        results["fetchx_root"] = self._check_directory_permissions(self.fetchx_root)
        
        # Check each category folder
        categories = list(self.CATEGORY_EXTENSIONS.keys()) + ["Other"]
        for category in categories:
            category_path = self.get_category_folder_path(category)
            results[f"category_{category.lower()}"] = self._check_directory_permissions(category_path)
            
        return results

    def _check_directory_permissions(self, path: str) -> bool:
        """Check if we have read/write permissions for a directory.
        
        Args:
            path: Directory path to check.
            
        Returns:
            True if we have proper permissions, False otherwise.
        """
        try:
            # Ensure directory exists
            FileManager.ensure_directory(path)
            
            # Test write permissions by creating a temporary file
            test_file = os.path.join(path, ".fetchx_permission_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            return True
        except (OSError, IOError, PermissionError):
            return False

    def cleanup_empty_folders(self) -> Dict[str, int]:
        """Remove empty category folders.
        
        Returns:
            Dictionary with cleanup statistics.
        """
        results = {"removed": 0, "errors": 0}
        
        if not os.path.exists(self.fetchx_root):
            return results
            
        categories = list(self.CATEGORY_EXTENSIONS.keys()) + ["Other"]
        
        for category in categories:
            category_path = self.get_category_folder_path(category)
            
            try:
                if os.path.exists(category_path) and os.path.isdir(category_path):
                    # Check if directory is empty
                    if not os.listdir(category_path):
                        os.rmdir(category_path)
                        results["removed"] += 1
                        self.log_info(f"Removed empty category folder: {category_path}")
            except OSError as e:
                results["errors"] += 1
                self.log_warning(f"Failed to remove empty folder {category_path}: {e}")
                
        return results

    def get_statistics(self) -> Dict[str, any]:
        """Get comprehensive statistics about the organized folder structure.
        
        Returns:
            Dictionary with detailed statistics.
        """
        stats = {
            "total_files": 0,
            "total_size": 0,
            "categories": {},
            "largest_category": {"name": None, "size": 0, "files": 0},
            "extension_distribution": {}
        }
        
        folder_info = self.get_folder_info()
        
        for category, info in folder_info["categories"].items():
            if info["exists"]:
                stats["total_files"] += info["file_count"]
                stats["total_size"] += info["total_size"]
                
                stats["categories"][category] = {
                    "files": info["file_count"],
                    "size": info["total_size"]
                }
                
                # Track largest category
                if info["total_size"] > stats["largest_category"]["size"]:
                    stats["largest_category"] = {
                        "name": category,
                        "size": info["total_size"],
                        "files": info["file_count"]
                    }
                    
                # Count extensions in this category (if we can access the folder)
                try:
                    category_path = info["path"]
                    if os.path.exists(category_path):
                        for item in os.listdir(category_path):
                            if os.path.isfile(os.path.join(category_path, item)):
                                _, ext = os.path.splitext(item.lower())
                                if ext:
                                    stats["extension_distribution"][ext] = stats["extension_distribution"].get(ext, 0) + 1
                except OSError:
                    pass
                    
        return stats