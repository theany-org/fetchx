"""Clipboard monitoring for automatic download detection."""

import asyncio
import re
from typing import Optional, Set, Callable, List
from dataclasses import dataclass
from urllib.parse import urlparse
from fetchx_cli.core.queue import DownloadQueue
from fetchx_cli.utils.network import NetworkUtils
from fetchx_cli.utils.exceptions import FetchXIdmException

try:
    import pyperclip

    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


@dataclass
class ClipboardConfig:
    """Configuration for clipboard monitoring."""
    enabled: bool = True
    auto_download: bool = False
    check_interval: float = 1.0
    url_patterns: List[str] = None
    excluded_domains: List[str] = None
    max_url_length: int = 2048
    notification_callback: Optional[Callable] = None

    def __post_init__(self):
        if self.url_patterns is None:
            self.url_patterns = [
                r'https?://.*\.(zip|rar|7z|tar|gz|bz2|exe|msi|dmg|pkg|deb|rpm|apk)(\?.*)?$',
                r'https?://.*\.(mp4|avi|mkv|mov|wmv|flv|webm|m4v)(\?.*)?$',
                r'https?://.*\.(mp3|wav|flac|aac|ogg|wma|m4a)(\?.*)?$',
                r'https?://.*\.(jpg|jpeg|png|gif|bmp|tiff|svg|webp)(\?.*)?$',
                r'https?://.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf)(\?.*)?$',
                r'https?://drive\.google\.com/.*',
                r'https?://.*\.dropbox\.com/.*',
                r'https?://.*\.mediafire\.com/.*',
                r'https?://.*\.mega\.nz/.*',
                r'https?://.*\.4shared\.com/.*',
                r'https?://.*\.rapidshare\.com/.*',
                r'https?://.*\.uploaded\.net/.*',
                r'https?://.*\.zippyshare\.com/.*',
                r'https?://.*\.sendspace\.com/.*',
                r'https?://.*\.fileserve\.com/.*',
                r'https?://.*\.hotfile\.com/.*',
                r'https?://.*\.filesonic\.com/.*',
                r'https?://.*\.wupload\.com/.*',
                r'https?://.*\.putlocker\.com/.*',
                r'https?://.*\.sockshare\.com/.*',
                r'https?://.*github\.com/.*/releases/.*',
                r'https?://.*\.sourceforge\.net/.*',
            ]

        if self.excluded_domains is None:
            self.excluded_domains = [
                'google.com',
                'youtube.com',
                'facebook.com',
                'twitter.com',
                'instagram.com',
                'reddit.com',
                'stackoverflow.com',
                'github.com/explore',
                'github.com/topics',
                'linkedin.com',
                'amazon.com',
                'ebay.com',
                'wikipedia.org',
                'news.ycombinator.com',
            ]


class ClipboardMonitor:
    """Monitors clipboard for download URLs."""

    def __init__(self, config: ClipboardConfig = None):
        if not CLIPBOARD_AVAILABLE:
            raise FetchXIdmException("Clipboard monitoring requires pyperclip. Install with: pip install pyperclip")

        self.config = config or ClipboardConfig()
        self.queue = DownloadQueue()
        self._is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_clipboard_content = ""
        self._seen_urls: Set[str] = set()
        self._url_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.config.url_patterns]

    async def start(self):
        """Start clipboard monitoring."""
        if self._is_running:
            return

        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        if self.config.notification_callback:
            self.config.notification_callback("📋 Clipboard monitoring started")

    async def stop(self):
        """Stop clipboard monitoring."""
        self._is_running = False

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self.config.notification_callback:
            self.config.notification_callback("📋 Clipboard monitoring stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._is_running:
            try:
                # Get clipboard content
                clipboard_content = await self._get_clipboard_content()

                if clipboard_content and clipboard_content != self._last_clipboard_content:
                    self._last_clipboard_content = clipboard_content

                    # Check for URLs
                    urls = self._extract_urls(clipboard_content)
                    for url in urls:
                        if await self._should_process_url(url):
                            await self._handle_detected_url(url)

                await asyncio.sleep(self.config.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.config.notification_callback:
                    self.config.notification_callback(f"⚠️ Clipboard monitor error: {e}")
                await asyncio.sleep(self.config.check_interval * 2)

    async def _get_clipboard_content(self) -> Optional[str]:
        """Get clipboard content asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(None, pyperclip.paste)
            return content.strip() if content else None
        except Exception:
            return None

    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        if not text or len(text) > self.config.max_url_length:
            return []

        # Simple URL extraction
        url_pattern = re.compile(
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            re.IGNORECASE
        )

        urls = url_pattern.findall(text)
        return [url.rstrip('.,;:!?") ') for url in urls]

    async def _should_process_url(self, url: str) -> bool:
        """Check if URL should be processed."""
        try:
            # Basic validation
            if not NetworkUtils.is_valid_url(url):
                return False

            # Check if already seen
            if url in self._seen_urls:
                return False

            # Check URL length
            if len(url) > self.config.max_url_length:
                return False

            # Check excluded domains
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            for excluded in self.config.excluded_domains:
                if excluded.lower() in domain:
                    return False

            # Check if URL matches download patterns
            for pattern in self._url_patterns:
                if pattern.search(url):
                    self._seen_urls.add(url)
                    return True

            # Additional heuristic checks
            if await self._is_likely_download_url(url):
                self._seen_urls.add(url)
                return True

            return False

        except Exception:
            return False

    async def _is_likely_download_url(self, url: str) -> bool:
        """Use heuristics to determine if URL is likely a download."""
        try:
            # Check for download-related keywords in URL
            download_keywords = [
                'download', 'dl', 'get', 'file', 'attachment',
                'media', 'content', 'resource', 'asset', 'binary'
            ]

            url_lower = url.lower()
            for keyword in download_keywords:
                if keyword in url_lower:
                    return True

            # Check for direct file URLs (with extensions)
            common_extensions = [
                '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
                '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.apk',
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg',
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.iso', '.img', '.bin', '.torrent'
            ]

            for ext in common_extensions:
                if ext in url_lower:
                    return True

            return False

        except Exception:
            return False

    async def _handle_detected_url(self, url: str):
        """Handle a detected download URL."""
        try:
            if self.config.auto_download:
                # Automatically add to queue
                item_id = self.queue.add_download(url)

                if self.config.notification_callback:
                    self.config.notification_callback(
                        f"📥 Auto-added to queue: {url[:50]}... (ID: {item_id[:8]})"
                    )
            else:
                # Just notify
                if self.config.notification_callback:
                    self.config.notification_callback(
                        f"🔗 Download URL detected: {url[:50]}... (Use 'fetchx add' to download)"
                    )

        except Exception as e:
            if self.config.notification_callback:
                self.config.notification_callback(f"❌ Error processing URL: {e}")

    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            'is_running': self._is_running,
            'urls_seen': len(self._seen_urls),
            'config': {
                'auto_download': self.config.auto_download,
                'check_interval': self.config.check_interval,
                'patterns_count': len(self.config.url_patterns)
            }
        }


class ClipboardService:
    """Service for managing clipboard monitoring."""

    _instance: Optional[ClipboardMonitor] = None

    @classmethod
    def get_instance(cls, config: ClipboardConfig = None) -> ClipboardMonitor:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = ClipboardMonitor(config)
        return cls._instance

    @classmethod
    def is_available(cls) -> bool:
        """Check if clipboard monitoring is available."""
        return CLIPBOARD_AVAILABLE

    @classmethod
    async def start_monitoring(cls, config: ClipboardConfig = None):
        """Start clipboard monitoring."""
        if not cls.is_available():
            raise FetchXIdmException(
                "Clipboard monitoring requires pyperclip. Install with: pip install pyperclip"
            )

        monitor = cls.get_instance(config)
        await monitor.start()
        return monitor

    @classmethod
    async def stop_monitoring(cls):
        """Stop clipboard monitoring."""
        if cls._instance:
            await cls._instance.stop()
            cls._instance = None


# Utility functions for CLI integration
def create_notification_callback(interface):
    """Create a notification callback for CLI interface."""

    def callback(message: str):
        interface.print_info(message)

    return callback


def create_clipboard_config(auto_download: bool = False,
                            check_interval: float = 1.0,
                            notification_callback: Optional[Callable] = None) -> ClipboardConfig:
    """Create clipboard configuration."""
    return ClipboardConfig(
        enabled=True,
        auto_download=auto_download,
        check_interval=check_interval,
        notification_callback=notification_callback
    )