"""Updated configuration defaults with temporary directory management."""

import os
from pathlib import Path

# Default directories
DEFAULT_DOWNLOAD_DIR = os.path.join(Path.home(), "Downloads", "fetchx_idm")
DEFAULT_SESSION_DIR = os.path.join(Path.home(), ".fetchx_idm", "sessions")
DEFAULT_LOG_DIR = os.path.join(Path.home(), ".fetchx_idm", "logs")

# NEW: Temporary directory settings
DEFAULT_TEMP_BASE_DIR = os.path.join(Path.home(), ".fetchx_idm", "temp")
DEFAULT_TEMP_CLEANUP_AGE_DAYS = 1  # Clean temp directories older than 1 day
DEFAULT_TEMP_MAX_SIZE_GB = 5  # Maximum temp storage in GB
DEFAULT_AUTO_CLEANUP_TEMP = True  # Automatically clean temp directories

# Default download settings
DEFAULT_MAX_CONNECTIONS = 8
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2

# Default display settings
DEFAULT_PROGRESS_UPDATE_INTERVAL = 0.1
DEFAULT_SHOW_SPEED = True
DEFAULT_SHOW_ETA = True
DEFAULT_SHOW_PERCENTAGE = True

# Default network settings
DEFAULT_USER_AGENT = "FETCHX-IDM/0.1.1 (Multi-threaded Download Manager)"
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30

# Default queue settings
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 3
DEFAULT_QUEUE_SAVE_INTERVAL = 5

# NEW: Cleanup settings
DEFAULT_SESSION_CLEANUP_AGE_DAYS = 30
DEFAULT_LOG_CLEANUP_AGE_DAYS = 7
DEFAULT_AUTO_CLEANUP_ON_START = True

# Logging settings
DEFAULT_LOG_LEVEL = "INFO"

# File size constants
KB = 1024
MB = KB * 1024
GB = MB * 1024

MIN_CHUNK_SIZE = 64 * KB
MAX_CHUNK_SIZE = 10 * MB

# NEW: Temporary directory constants
MIN_TEMP_CLEANUP_AGE_HOURS = 1
MAX_TEMP_CLEANUP_AGE_DAYS = 30
MIN_TEMP_MAX_SIZE_MB = 100
MAX_TEMP_MAX_SIZE_GB = 50
