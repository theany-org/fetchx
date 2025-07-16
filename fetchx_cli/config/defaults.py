"""Default configuration values for FETCHX IDM."""

import os
from pathlib import Path

# Default directories
DEFAULT_DOWNLOAD_DIR = os.path.join(Path.home(), "Downloads", "fetchx_idm")
DEFAULT_SESSION_DIR = os.path.join(Path.home(), ".fetchx_idm", "sessions")
DEFAULT_LOG_DIR = os.path.join(Path.home(), ".fetchx_idm", "logs")

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
DEFAULT_USER_AGENT = "FETCHX-IDM/0.1.0 (Multi-threaded Download Manager)"
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30

# Default queue settings
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 3
DEFAULT_QUEUE_SAVE_INTERVAL = 5

# File size constants
KB = 1024
MB = KB * 1024
GB = MB * 1024

MIN_CHUNK_SIZE = 64 * KB
MAX_CHUNK_SIZE = 10 * MB
