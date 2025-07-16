"""Configuration management for FETCHX IDM with SQLite."""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
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


@dataclass
class AppConfig:
    """Main application configuration."""

    download: DownloadSettings
    display: DisplaySettings
    queue: QueueSettings
    paths: PathSettings

    def __init__(self):
        self.download = DownloadSettings()
        self.display = DisplaySettings()
        self.queue = QueueSettings()
        self.paths = PathSettings()


class ConfigManager:
    """Manages application configuration using SQLite."""

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

            # Load download settings
            if "download" in all_settings:
                download_data = all_settings["download"]
                for key, value in download_data.items():
                    if hasattr(config.download, key):
                        setattr(config.download, key, value)

            # Load display settings
            if "display" in all_settings:
                display_data = all_settings["display"]
                for key, value in display_data.items():
                    if hasattr(config.display, key):
                        setattr(config.display, key, value)

            # Load queue settings
            if "queue" in all_settings:
                queue_data = all_settings["queue"]
                for key, value in queue_data.items():
                    if hasattr(config.queue, key):
                        setattr(config.queue, key, value)

            # Load path settings
            if "paths" in all_settings:
                paths_data = all_settings["paths"]
                for key, value in paths_data.items():
                    if hasattr(config.paths, key):
                        setattr(config.paths, key, value)

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
            # Save download settings
            download_dict = asdict(config.download)
            for key, value in download_dict.items():
                self.db.set_setting("download", key, value)

            # Save display settings
            display_dict = asdict(config.display)
            for key, value in display_dict.items():
                self.db.set_setting("display", key, value)

            # Save queue settings
            queue_dict = asdict(config.queue)
            for key, value in queue_dict.items():
                self.db.set_setting("queue", key, value)

            # Save path settings
            paths_dict = asdict(config.paths)
            for key, value in paths_dict.items():
                self.db.set_setting("paths", key, value)

        except Exception as e:
            print(f"Warning: Could not save default config: {e}")

    def save_config(self) -> None:
        """Save current configuration to database."""
        try:
            self._save_defaults(self.config)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert config object to dictionary."""
        return {
            "download": asdict(self.config.download),
            "display": asdict(self.config.display),
            "queue": asdict(self.config.queue),
            "paths": asdict(self.config.paths),
        }

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        directories = [
            self.config.paths.download_dir,
            self.config.paths.session_dir,  # Still needed for compatibility
            self.config.paths.log_dir,  # Still needed for compatibility
        ]

        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                print(f"Warning: Could not create directory {directory}: {e}")

    def update_setting(self, section: str, key: str, value: Any) -> None:
        """Update a specific setting."""
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
