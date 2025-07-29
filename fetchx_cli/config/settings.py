"""Enhanced configuration management with temporary directory support."""

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from fetchx_cli.core.database import get_database

from .defaults import *


@dataclass
class DownloadSettings:
    """Download-specific settings."""

    max_connections: int = DEFAULT_MAX_CONNECTIONS
    chunk_size: int = DEFAULT_CHUNK_SIZE
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: int = DEFAULT_RETRY_DELAY
    user_agent: str = DEFAULT_USER_AGENT
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT
    read_timeout: int = DEFAULT_READ_TIMEOUT


@dataclass
class DisplaySettings:
    """Display and progress settings."""

    progress_update_interval: float = DEFAULT_PROGRESS_UPDATE_INTERVAL
    show_speed: bool = DEFAULT_SHOW_SPEED
    show_eta: bool = DEFAULT_SHOW_ETA
    show_percentage: bool = DEFAULT_SHOW_PERCENTAGE


@dataclass
class QueueSettings:
    """Queue management settings."""

    max_concurrent_downloads: int = DEFAULT_MAX_CONCURRENT_DOWNLOADS
    save_interval: int = DEFAULT_QUEUE_SAVE_INTERVAL


@dataclass
class PathSettings:
    """Path and directory settings."""

    download_dir: str = DEFAULT_DOWNLOAD_DIR
    session_dir: str = DEFAULT_SESSION_DIR
    log_dir: str = DEFAULT_LOG_DIR
    temp_base_dir: str = DEFAULT_TEMP_BASE_DIR  # NEW


@dataclass
class TempSettings:
    """NEW: Temporary directory management settings."""

    cleanup_age_days: int = DEFAULT_TEMP_CLEANUP_AGE_DAYS
    max_size_gb: int = DEFAULT_TEMP_MAX_SIZE_GB
    auto_cleanup: bool = DEFAULT_AUTO_CLEANUP_TEMP
    cleanup_on_start: bool = DEFAULT_AUTO_CLEANUP_ON_START


@dataclass
class CleanupSettings:
    """NEW: General cleanup settings."""

    session_cleanup_age_days: int = DEFAULT_SESSION_CLEANUP_AGE_DAYS
    log_cleanup_age_days: int = DEFAULT_LOG_CLEANUP_AGE_DAYS
    auto_cleanup_on_start: bool = DEFAULT_AUTO_CLEANUP_ON_START


@dataclass
class FolderSettings:
    """Organized folder structure settings."""

    use_organized_folders: bool = DEFAULT_USE_ORGANIZED_FOLDERS
    organize_by_extension: bool = DEFAULT_ORGANIZE_BY_EXTENSION
    custom_download_dir: Optional[str] = DEFAULT_CUSTOM_DOWNLOAD_DIR


@dataclass
class LoggingSettings:
    """Logging configuration settings."""

    log_level: str = DEFAULT_LOG_LEVEL


@dataclass
class AppConfig:
    """Main application configuration with temporary directory support."""

    download: DownloadSettings
    display: DisplaySettings
    queue: QueueSettings
    paths: PathSettings
    temp: TempSettings  # NEW
    cleanup: CleanupSettings  # NEW
    folders: FolderSettings  # NEW
    logging: LoggingSettings  # NEW

    def __init__(self):
        self.download = DownloadSettings()
        self.display = DisplaySettings()
        self.queue = QueueSettings()
        self.paths = PathSettings()
        self.temp = TempSettings()  # NEW
        self.cleanup = CleanupSettings()  # NEW
        self.folders = FolderSettings()  # NEW
        self.logging = LoggingSettings()  # NEW


class ConfigManager:
    """Enhanced configuration manager with temporary directory support."""

    def __init__(self):
        self.db = get_database()
        self.config = self._load_config()
        self._ensure_directories()

    def _load_config(self) -> AppConfig:
        """Load configuration from database or create default."""
        try:
            # Get all settings from database
            all_settings = self.db.get_all_settings()

            # Create config object
            config = AppConfig()

            # Load all sections
            sections = ["download", "display", "queue", "paths", "temp", "cleanup", "folders", "logging"]

            for section in sections:
                if section in all_settings:
                    section_data = all_settings[section]
                    config_section = getattr(config, section)

                    for key, value in section_data.items():
                        if hasattr(config_section, key):
                            setattr(config_section, key, value)

            # If no settings exist, save defaults
            if not all_settings:
                self._save_defaults(config)

            return config

        except Exception as e:
            print(f"Warning: Error loading config from database: {e}. Using defaults.")
            config = AppConfig()
            try:
                self._save_defaults(config)
            except Exception as save_error:
                print(f"Warning: Could not save default config: {save_error}")
            return config

    def _save_defaults(self, config: AppConfig):
        """Save default configuration to database."""
        try:
            # Save all sections
            sections = {
                "download": asdict(config.download),
                "display": asdict(config.display),
                "queue": asdict(config.queue),
                "paths": asdict(config.paths),
                "temp": asdict(config.temp),  # NEW
                "cleanup": asdict(config.cleanup),  # NEW
                "folders": asdict(config.folders),  # NEW
                "logging": asdict(config.logging),  # NEW
            }

            for section_name, section_dict in sections.items():
                for key, value in section_dict.items():
                    self.db.set_setting(section_name, key, value)

        except Exception as e:
            print(f"Warning: Could not save default config: {e}")

    def save_config(self) -> None:
        """Save current configuration to database."""
        try:
            self._save_defaults(self.config)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        directories = [
            self.config.paths.download_dir,
            self.config.paths.session_dir,
            self.config.paths.log_dir,
            self.config.paths.temp_base_dir,  # NEW
        ]

        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                print(f"Warning: Could not create directory {directory}: {e}")

    def update_setting(self, section: str, key: str, value: Any) -> None:
        """Update a specific setting with validation."""
        try:
            # Validate section and key exist
            if not hasattr(self.config, section):
                raise ValueError(f"Unknown section: {section}")

            section_obj = getattr(self.config, section)
            if not hasattr(section_obj, key):
                raise ValueError(f"Unknown setting key: {key}")

            # Get current value to determine type
            current_value = getattr(section_obj, key)

            # Convert value to correct type
            if isinstance(current_value, bool):
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "on")
            elif isinstance(current_value, int):
                value = int(value)
            elif isinstance(current_value, float):
                value = float(value)
            # String values are used as-is

            # NEW: Additional validation for temp settings
            if section == "temp":
                if key == "cleanup_age_days" and value < 0:
                    raise ValueError("Cleanup age must be non-negative")
                elif key == "max_size_gb" and value < 0.1:
                    raise ValueError("Max size must be at least 0.1 GB")

            # NEW: Validation for cleanup settings
            if section == "cleanup":
                if "age_days" in key and value < 0:
                    raise ValueError("Cleanup age must be non-negative")

            # NEW: Validation for logging settings
            if section == "logging":
                if key == "log_level":
                    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    if value.upper() not in valid_levels:
                        raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
                    value = value.upper()  # Normalize to uppercase

            # Update in memory
            setattr(section_obj, key, value)

            # Update in database
            self.db.set_setting(section, key, value)

        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid value for {section}.{key}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to update setting: {e}")

    def get_setting(self, section: str, key: str) -> Any:
        """Get a specific setting value."""
        try:
            if not hasattr(self.config, section):
                raise ValueError(f"Unknown section: {section}")

            section_obj = getattr(self.config, section)
            if not hasattr(section_obj, key):
                raise ValueError(f"Unknown setting key: {key}")

            return getattr(section_obj, key)

        except Exception as e:
            raise ValueError(f"Failed to get setting: {e}")

    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings."""
        try:
            return self.db.get_all_settings()
        except Exception as e:
            print(f"Warning: Could not get settings from database: {e}")
            return self._config_to_dict()

    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert config object to dictionary."""
        return {
            "download": asdict(self.config.download),
            "display": asdict(self.config.display),
            "queue": asdict(self.config.queue),
            "paths": asdict(self.config.paths),
            "temp": asdict(self.config.temp),  # NEW
            "cleanup": asdict(self.config.cleanup),  # NEW
            "folders": asdict(self.config.folders),  # NEW
            "logging": asdict(self.config.logging),  # NEW
        }

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        try:
            # Create new default config
            self.config = AppConfig()

            # Save to database (this will overwrite existing settings)
            self._save_defaults(self.config)

            # Ensure directories exist
            self._ensure_directories()

        except Exception as e:
            raise ValueError(f"Failed to reset settings: {e}")

    def export_config(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return self._config_to_dict()

    def import_config(self, config_data: Dict[str, Any]) -> None:
        """Import configuration from dictionary."""
        try:
            # Validate and apply settings
            for section, settings in config_data.items():
                if hasattr(self.config, section):
                    for key, value in settings.items():
                        try:
                            self.update_setting(section, key, value)
                        except ValueError as e:
                            print(
                                f"Warning: Skipping invalid setting {section}.{key}: {e}"
                            )
                else:
                    print(f"Warning: Unknown section {section}, skipping")

        except Exception as e:
            raise ValueError(f"Failed to import config: {e}")

    def validate_paths(self) -> Dict[str, bool]:
        """Validate that all configured paths are accessible."""
        results = {}

        paths_to_check = {
            "download_dir": self.config.paths.download_dir,
            "session_dir": self.config.paths.session_dir,
            "log_dir": self.config.paths.log_dir,
            "temp_base_dir": self.config.paths.temp_base_dir,  # NEW
        }

        for name, path in paths_to_check.items():
            try:
                # Try to create directory if it doesn't exist
                os.makedirs(path, exist_ok=True)

                # Try to write a test file
                test_file = os.path.join(path, ".test_write")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)

                results[name] = True

            except (OSError, IOError, PermissionError):
                results[name] = False

        return results

    def get_temp_usage_info(self) -> Dict[str, Any]:
        """NEW: Get temporary directory usage information."""
        temp_base = self.config.paths.temp_base_dir

        if not os.path.exists(temp_base):
            return {
                "exists": False,
                "total_size": 0,
                "directory_count": 0,
                "file_count": 0,
                "old_directories": 0,
            }

        try:
            import time

            cutoff_time = time.time() - (
                self.config.temp.cleanup_age_days * 24 * 60 * 60
            )

            total_size = 0
            directory_count = 0
            file_count = 0
            old_directories = 0

            for item in os.listdir(temp_base):
                item_path = os.path.join(temp_base, item)
                if os.path.isdir(item_path):
                    directory_count += 1

                    # Check if directory is old
                    if os.path.getmtime(item_path) < cutoff_time:
                        old_directories += 1

                    # Calculate directory size
                    for root, dirs, files in os.walk(item_path):
                        file_count += len(files)
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except OSError:
                                pass

            return {
                "exists": True,
                "total_size": total_size,
                "directory_count": directory_count,
                "file_count": file_count,
                "old_directories": old_directories,
                "max_size_bytes": self.config.temp.max_size_gb * 1024 * 1024 * 1024,
                "needs_cleanup": old_directories > 0
                or total_size > (self.config.temp.max_size_gb * 1024 * 1024 * 1024),
            }

        except OSError:
            return {
                "exists": True,
                "error": "Could not read temporary directory",
                "total_size": 0,
                "directory_count": 0,
                "file_count": 0,
                "old_directories": 0,
            }


# Global config instance
_config_manager = None


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config() -> None:
    """Reload the global configuration."""
    global _config_manager
    _config_manager = ConfigManager()
