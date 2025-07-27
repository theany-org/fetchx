"""SQLite-based logging system for FETCHX IDM."""

import logging
import sys
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from fetchx_cli.core.database import get_database


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SQLiteLogHandler(logging.Handler):
    """Custom logging handler that writes to SQLite database."""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.db = get_database()
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        """Emit a log record to the database."""
        try:
            with self._lock:
                # Extract module name
                module = record.name

                # Prepare extra data
                extra_data = {}
                if hasattr(record, "extra"):
                    extra_data = record.extra

                # Add exception info if present
                if record.exc_info:
                    extra_data["exception"] = self.format_exception(record.exc_info)

                # Add thread info
                extra_data["thread_id"] = threading.get_ident()
                extra_data["thread_name"] = threading.current_thread().name

                # Add process info
                import os

                extra_data["process_id"] = os.getpid()

                # Store in database
                self.db.add_log(
                    level=record.levelname,
                    module=module,
                    message=record.getMessage(),
                    extra_data=extra_data if extra_data else None,
                )

        except Exception:
            # Don't raise exceptions from logging
            self.handleError(record)

    def format_exception(self, exc_info):
        """Format exception information."""
        import traceback

        return "".join(traceback.format_exception(*exc_info))


class FetchXLogger:
    """Main logger class for FETCHX IDM."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FetchXLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.db = get_database()

        # Set up main logger
        self.logger = logging.getLogger("fetchx")
        self.logger.setLevel(logging.DEBUG)

        # Clear any existing handlers
        self.logger.handlers.clear()

        # Add SQLite handler
        sqlite_handler = SQLiteLogHandler()
        sqlite_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(sqlite_handler)

        # Add console handler for immediate feedback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def debug(self, message: str, module: str = "general", **extra):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, module, extra)

    def info(self, message: str, module: str = "general", **extra):
        """Log info message."""
        self._log(LogLevel.INFO, message, module, extra)

    def warning(self, message: str, module: str = "general", **extra):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, module, extra)

    def error(self, message: str, module: str = "general", **extra):
        """Log error message."""
        self._log(LogLevel.ERROR, message, module, extra)

    def critical(self, message: str, module: str = "general", **extra):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, module, extra)

    def exception(self, message: str, module: str = "general", **extra):
        """Log exception with traceback."""
        extra["include_traceback"] = True
        self.logger.exception(message, extra={"extra": extra})

    def _log(self, level: LogLevel, message: str, module: str, extra: Dict[str, Any]):
        """Internal logging method."""
        # Create logger for specific module
        module_logger = logging.getLogger(f"fetchx.{module}")

        # Map our log levels to logging levels
        level_map = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }

        log_level = level_map[level]
        module_logger.log(log_level, message, extra={"extra": extra})

    def get_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get logs from database."""
        try:
            return self.db.get_logs(level, module, limit, offset)
        except Exception as e:
            self.error(f"Failed to retrieve logs: {e}", "logging")
            return []

    def cleanup_old_logs(self, max_age_days: int = 30) -> int:
        """Clean up old log entries."""
        try:
            deleted_count = self.db.cleanup_old_logs(max_age_days)
            self.info(f"Cleaned up {deleted_count} old log entries", "logging")
            return deleted_count
        except Exception as e:
            self.error(f"Failed to cleanup old logs: {e}", "logging")
            return 0

    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        try:
            # Get logs for stats calculation
            all_logs = self.get_logs(limit=10000)  # Get recent logs for stats

            # Calculate stats
            stats = {
                "total_logs": len(all_logs),
                "level_counts": {},
                "module_counts": {},
                "recent_errors": 0,
                "recent_warnings": 0,
            }

            # Count by level and module
            recent_time = time.time() - (24 * 60 * 60)  # Last 24 hours

            for log in all_logs:
                # Count by level
                level = log["level"]
                stats["level_counts"][level] = stats["level_counts"].get(level, 0) + 1

                # Count by module
                module = log["module"]
                stats["module_counts"][module] = (
                    stats["module_counts"].get(module, 0) + 1
                )

                # Count recent errors and warnings
                if log["timestamp"] > recent_time:
                    if level == "ERROR" or level == "CRITICAL":
                        stats["recent_errors"] += 1
                    elif level == "WARNING":
                        stats["recent_warnings"] += 1

            return stats

        except Exception as e:
            self.error(f"Failed to get log stats: {e}", "logging")
            return {}

    def set_log_level(self, level: str, save_to_config: bool = True):
        """Set the console log level and optionally save to configuration."""
        try:
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }

            if level.upper() in level_map:
                target_level = level_map[level.upper()]
                handler_found = False
                
                # Update console handler level
                for handler in self.logger.handlers:
                    if isinstance(handler, logging.StreamHandler) and not isinstance(
                        handler, SQLiteLogHandler
                    ):
                        handler.setLevel(target_level)
                        handler_found = True
                        break

                if not handler_found:
                    print(f"[FETCHX] Warning: No console handler found to update!", file=sys.stderr)
                
                # Also set the level on any child loggers that might exist
                for name in logging.Logger.manager.loggerDict:
                    if name.startswith("fetchx."):
                        child_logger = logging.getLogger(name)
                        if child_logger.level != logging.NOTSET:
                            # Reset child logger level to inherit from parent
                            child_logger.setLevel(logging.NOTSET)
                            print(f"[FETCHX] Reset child logger '{name}' level to inherit from parent", file=sys.stderr)

                # Save to configuration if requested
                if save_to_config:
                    try:
                        from fetchx_cli.config.settings import get_config
                        config = get_config()
                        config.update_setting("logging", "log_level", level.upper())
                        print(f"[FETCHX] Saved log level '{level.upper()}' to configuration", file=sys.stderr)
                    except Exception as config_error:
                        print(f"[FETCHX] Warning: Could not save log level to config: {config_error}", file=sys.stderr)

                self.info(f"Console log level set to {level.upper()}", "logging")
            else:
                self.warning(f"Invalid log level: {level}. Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL", "logging")

        except Exception as e:
            self.error(f"Failed to set log level: {e}", "logging")
            print(f"[FETCHX] Exception in set_log_level: {e}", file=sys.stderr)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> FetchXLogger:
        """Get logger instance."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger()
        return self._logger

    def log_debug(self, message: str, **extra):
        """Log debug message with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.debug(message, module_name, **extra)

    def log_info(self, message: str, **extra):
        """Log info message with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.info(message, module_name, **extra)

    def log_warning(self, message: str, **extra):
        """Log warning message with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.warning(message, module_name, **extra)

    def log_error(self, message: str, **extra):
        """Log error message with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.error(message, module_name, **extra)

    def log_critical(self, message: str, **extra):
        """Log critical message with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.critical(message, module_name, **extra)

    def log_exception(self, message: str, **extra):
        """Log exception with class name as module."""
        module_name = self.__class__.__name__.lower()
        self.logger.exception(message, module_name, **extra)


# Global logger instance
def get_logger() -> FetchXLogger:
    """Get the global logger instance."""
    return FetchXLogger()


# Convenience functions
def log_debug(message: str, module: str = "general", **extra):
    """Log debug message."""
    get_logger().debug(message, module, **extra)


def log_info(message: str, module: str = "general", **extra):
    """Log info message."""
    get_logger().info(message, module, **extra)


def log_warning(message: str, module: str = "general", **extra):
    """Log warning message."""
    get_logger().warning(message, module, **extra)


def log_error(message: str, module: str = "general", **extra):
    """Log error message."""
    get_logger().error(message, module, **extra)


def log_critical(message: str, module: str = "general", **extra):
    """Log critical message."""
    get_logger().critical(message, module, **extra)


def log_exception(message: str, module: str = "general", **extra):
    """Log exception with traceback."""
    get_logger().exception(message, module, **extra)


# Setup function to initialize logging
def setup_logging(console_level: str = None, save_if_provided: bool = False):
    """Initialize the logging system."""
    logger = get_logger()
    
    # If no level specified, try to load from config
    if console_level is None:
        try:
            from fetchx_cli.config.settings import get_config
            config = get_config()
            console_level = config.get_setting("logging", "log_level")
            print(f"[FETCHX] Loaded log level from config: {console_level}", file=sys.stderr)
            save_to_config = False  # Don't save since we just loaded it
        except Exception as e:
            console_level = "INFO"  # Default fallback
            print(f"[FETCHX] Could not load log level from config, using default INFO: {e}", file=sys.stderr)
            save_to_config = False  # Don't save the default
    else:
        # Level was explicitly provided
        save_to_config = save_if_provided
        if save_if_provided:
            print(f"[FETCHX] Using explicitly provided log level: {console_level}", file=sys.stderr)
    
    # Set the log level
    logger.set_log_level(console_level, save_to_config=save_to_config)
    logger.info("Logging system initialized", "logging")
    return logger
