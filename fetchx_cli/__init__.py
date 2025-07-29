"""FETCHX Internet Download Manager - A powerful command-line download manager."""

from ._version import __version__

__author__ = "FETCHX IDM Team"
__description__ = "A powerful command-line Internet Download Manager"

from .config.settings import get_config
from .core.downloader import Downloader
from .core.queue import DownloadQueue

__all__ = ["Downloader", "DownloadQueue", "get_config"]
