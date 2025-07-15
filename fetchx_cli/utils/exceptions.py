"""Custom exception classes for FETCHX IDM."""

class FetchXIdmException(Exception):
    """Base exception for FETCHX IDM."""
    pass

class DownloadException(FetchXIdmException):
    """Exception raised during download operations."""
    pass

class ConnectionException(FetchXIdmException):
    """Exception raised during connection operations."""
    pass

class FileException(FetchXIdmException):
    """Exception raised during file operations."""
    pass

class QueueException(FetchXIdmException):
    """Exception raised during queue operations."""
    pass

class SessionException(FetchXIdmException):
    """Exception raised during session operations."""
    pass

class ValidationException(FetchXIdmException):
    """Exception raised during input validation."""
    pass

class NetworkException(FetchXIdmException):
    """Exception raised during network operations."""
    pass

class AuthenticationException(FetchXIdmException):
    """Exception raised during authentication."""
    pass

class RangeNotSupportedException(DownloadException):
    """Exception raised when server doesn't support range requests."""
    pass

class InsufficientSpaceException(FileException):
    """Exception raised when there's insufficient disk space."""
    pass

class DatabaseException(FetchXIdmException):
    """Exception raised during database operations."""
    pass