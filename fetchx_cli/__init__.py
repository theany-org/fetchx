"""FETCHX Internet Download Manager - A powerful command-line download manager."""

__version__ = "0.1.0"
__author__ = "FETCHX IDM Team"
__description__ = "A powerful command-line Internet Download Manager"

from .core.downloader import Downloader
from .core.queue import DownloadQueue
from .config.settings import get_config

__all__ = ["Downloader", "DownloadQueue", "get_config"]