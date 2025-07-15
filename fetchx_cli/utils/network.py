"""Network utilities for FETCHX IDM."""

import aiohttp
import asyncio
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse
from fetchx_cli.utils.exceptions import NetworkException, ConnectionException, AuthenticationException

class NetworkUtils:
    """Network utility functions."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def parse_content_range(content_range: str) -> Tuple[int, int, int]:
        """Parse Content-Range header."""
        # Format: bytes start-end/total
        try:
            parts = content_range.replace('bytes ', '').split('/')
            range_part = parts[0]
            total = int(parts[1]) if parts[1] != '*' else 0

            start, end = map(int, range_part.split('-'))
            return start, end, total
        except (ValueError, IndexError):
            raise NetworkException(f"Invalid Content-Range header: {content_range}")

    @staticmethod
    def build_range_header(start: int, end: Optional[int] = None) -> str:
        """Build Range header for partial content requests."""
        if end is not None:
            return f"bytes={start}-{end}"
        return f"bytes={start}-"

    @staticmethod
    def parse_content_disposition(content_disposition: str) -> Optional[str]:
        """Extract filename from Content-Disposition header."""
        try:
            if 'filename=' in content_disposition:
                # Handle both quoted and unquoted filenames
                parts = content_disposition.split('filename=')
                if len(parts) > 1:
                    filename = parts[1].strip()
                    # Remove quotes if present
                    if filename.startswith('"') and filename.endswith('"'):
                        filename = filename[1:-1]
                    elif filename.startswith("'") and filename.endswith("'"):
                        filename = filename[1:-1]
                    return filename
        except Exception:
            pass
        return None

class HttpClient:
    """Async HTTP client for downloads."""

    def __init__(self, timeout: int = 30, user_agent: str = None):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.user_agent = user_agent or "FETCHX-IDM/0.1.0"
        self._session = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers={'User-Agent': self.user_agent}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def get_file_info(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get file information using HEAD request."""
        if not self._session:
            raise ConnectionException("HTTP client not initialized")

        request_headers = headers or {}

        try:
            async with self._session.head(url, headers=request_headers) as response:
                if response.status == 401:
                    raise AuthenticationException("Authentication required")

                if response.status >= 400:
                    raise NetworkException(f"HTTP {response.status}: {response.reason}")

                # Extract file information
                info = {
                    'url': str(response.url),
                    'status': response.status,
                    'headers': dict(response.headers),
                    'supports_ranges': 'bytes' in response.headers.get('Accept-Ranges', ''),
                    'content_length': None,
                    'filename': None,
                    'content_type': response.headers.get('Content-Type'),
                    'last_modified': response.headers.get('Last-Modified'),
                    'etag': response.headers.get('ETag')
                }

                # Parse content length
                if 'Content-Length' in response.headers:
                    try:
                        info['content_length'] = int(response.headers['Content-Length'])
                    except ValueError:
                        pass

                # Parse filename from Content-Disposition
                if 'Content-Disposition' in response.headers:
                    filename = NetworkUtils.parse_content_disposition(
                        response.headers['Content-Disposition']
                    )
                    if filename:
                        info['filename'] = filename

                return info

        except aiohttp.ClientError as e:
            raise NetworkException(f"Network error: {e}")
        except asyncio.TimeoutError:
            raise NetworkException("Request timeout")

    async def download_range(self, url: str, start: int, end: Optional[int] = None,
                           headers: Optional[Dict[str, str]] = None) -> aiohttp.ClientResponse:
        """Download a specific byte range."""
        if not self._session:
            raise ConnectionException("HTTP client not initialized")

        request_headers = headers or {}
        request_headers['Range'] = NetworkUtils.build_range_header(start, end)

        try:
            response = await self._session.get(url, headers=request_headers)

            if response.status == 401:
                await response.close()
                raise AuthenticationException("Authentication required")

            if response.status not in (200, 206):
                await response.close()
                raise NetworkException(f"HTTP {response.status}: {response.reason}")

            return response

        except aiohttp.ClientError as e:
            raise NetworkException(f"Network error: {e}")
        except asyncio.TimeoutError:
            raise NetworkException("Request timeout")

    async def test_connection(self, url: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Test if connection to URL is possible."""
        try:
            info = await self.get_file_info(url, headers)
            return info['status'] < 400
        except Exception:
            return False