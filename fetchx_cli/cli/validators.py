"""Input validation for CLI commands."""

from urllib.parse import urlparse
from fetchx_cli.utils.exceptions import ValidationException


class Validators:
    """Input validation utilities."""

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format."""
        if not url:
            raise ValidationException("URL cannot be empty")

        # Add protocol if missing
        if not url.startswith(("http://", "https://", "ftp://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValidationException("Invalid URL format")

            if parsed.scheme not in ("http", "https", "ftp"):
                raise ValidationException("URL must use HTTP, HTTPS, or FTP protocol")
        except Exception as e:
            raise ValidationException(f"Invalid URL: {e}")

        return url

    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate filename."""
        if not filename:
            raise ValidationException("Filename cannot be empty")

        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            raise ValidationException(
                f"Filename contains invalid characters: {invalid_chars}"
            )

        # Check filename length
        if len(filename) > 255:
            raise ValidationException("Filename too long (max 255 characters)")

        # Remove leading/trailing whitespace and dots
        filename = filename.strip(" .")

        if not filename:
            raise ValidationException(
                "Filename cannot be empty after removing invalid characters"
            )

        return filename

    @staticmethod
    def validate_positive_int(value: str, name: str) -> int:
        """Validate positive integer."""
        try:
            int_value = int(value)
            if int_value <= 0:
                raise ValidationException(f"{name} must be positive")
            return int_value
        except ValueError:
            raise ValidationException(f"{name} must be a valid integer")

    @staticmethod
    def validate_connections(connections: int) -> int:
        """Validate number of connections."""
        if not isinstance(connections, int):
            try:
                connections = int(connections)
            except (ValueError, TypeError):
                raise ValidationException("Number of connections must be an integer")

        if connections < 1:
            raise ValidationException("Number of connections must be at least 1")
        if connections > 32:
            raise ValidationException("Number of connections cannot exceed 32")
        return connections

    @staticmethod
    def validate_path(path: str) -> str:
        """Validate file path."""
        if not path:
            raise ValidationException("Path cannot be empty")

        # Check for invalid characters in path
        invalid_chars = '<>"|?*'
        if any(char in path for char in invalid_chars):
            raise ValidationException(
                f"Path contains invalid characters: {invalid_chars}"
            )

        return path
