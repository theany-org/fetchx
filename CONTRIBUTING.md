# Contributing to FETCHX IDM

Thank you for your interest in contributing to FETCHX IDM! This document provides comprehensive guidelines for contributing to this high-performance download manager.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Standards](#documentation-standards)
- [Submitting Changes](#submitting-changes)
- [Performance Considerations](#performance-considerations)
- [Security Guidelines](#security-guidelines)

## 🤝 Code of Conduct

### Our Standards

- **Be respectful** and inclusive in all interactions
- **Focus on constructive feedback** and collaborative problem-solving
- **Respect different viewpoints** and experiences
- **Accept responsibility** for mistakes and learn from them
- **Help maintain a welcoming environment** for all contributors

### Unacceptable Behavior

- Harassment, trolling, or discriminatory language
- Personal attacks or inflammatory comments
- Sharing private information without permission
- Any behavior that would be inappropriate in a professional setting

## 🚀 Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.8+** (3.9+ recommended for development)
- **Git** for version control
- **pip** and **virtualenv** for dependency management
- **Basic understanding** of async/await programming
- **Familiarity** with SQLite and aiohttp

### First Contribution Ideas

Good starting points for new contributors:

- 📝 **Documentation improvements** (typos, clarity, examples)
- 🐛 **Bug fixes** from the issue tracker
- 🧪 **Test coverage improvements** 
- 🎨 **CLI interface enhancements**
- 📊 **Performance optimizations**
- 🔧 **Configuration options** additions

## 🛠 Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/fetchx.git
cd fetchx

# Add upstream remote
git remote add upstream https://github.com/YOUR_USERNAME/fetchx.git
```

### 2. Create Development Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -e .[dev]
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
# Test the installation
python -m fetchx_cli.main --version
fetchx --version
```

## 📁 Project Structure

```
fetchx-idm/
├── fetchx_cli/                 # Main application package
│   ├── cli/                   # Command-line interface
│   │   ├── commands.py        # CLI command definitions
│   │   ├── interface.py       # Rich terminal interface
│   │   └── validators.py      # Input validation
│   ├── config/                # Configuration management
│   │   ├── defaults.py        # Default configuration values
│   │   └── settings.py        # Settings management with SQLite
│   ├── core/                  # Core functionality
│   │   ├── connection.py      # Connection management
│   │   ├── database.py        # SQLite database manager
│   │   ├── downloader.py      # Main download engine
│   │   ├── queue.py           # Download queue management
│   │   └── session.py         # Session persistence
│   ├── utils/                 # Utility modules
│   │   ├── clipboard.py       # Clipboard monitoring (optional)
│   │   ├── exceptions.py      # Custom exception classes
│   │   ├── file_utils.py      # File operations
│   │   ├── logging.py         # SQLite-based logging
│   │   ├── merger.py          # Intelligent file merger
│   │   ├── network.py         # HTTP client utilities
│   │   ├── optimizations.py   # Performance optimizations
│   │   └── progress.py        # Progress tracking
│   ├── __init__.py
│   └── main.py               # Entry point
├── .github/                  # GitHub workflows and templates
├── requirements.txt          # Production dependencies
├── pyproject.toml           # Project configuration
├── setup.py                 # Package setup
└── README.md                # Main documentation
```

### Key Architecture Principles

1. **Modular Design**: Each component has a single responsibility
2. **Async/Await**: All I/O operations are asynchronous
3. **SQLite Persistence**: Database-backed for reliability
4. **Performance First**: Optimized for maximum throughput
5. **Error Resilience**: Comprehensive error handling and recovery

## ⚡ Development Workflow

### 1. Create Feature Branch

```bash
# Update your fork
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 2. Development Cycle

```bash
# Make your changes
# Edit files...

# Run code formatting
black fetchx_cli/
isort fetchx_cli/

# Run linting
flake8 fetchx_cli/
mypy fetchx_cli/

# Test your changes manually
python -m fetchx_cli.main download https://httpbin.org/bytes/1024 --connections 2
```

### 3. Commit Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Feature additions
git commit -m "feat: add bandwidth limiting support"
git commit -m "feat(cli): add --max-speed option to download command"

# Bug fixes
git commit -m "fix: resolve segment merge issue for large files"
git commit -m "fix(network): handle connection timeout properly"

# Performance improvements
git commit -m "perf: optimize chunk size for better throughput"
git commit -m "perf(merger): use streaming merge for files >500MB"

# Documentation
git commit -m "docs: update README with new configuration options"
git commit -m "docs(api): add docstrings to ConnectionManager"

# Refactoring
git commit -m "refactor: extract common network utilities"

# Breaking changes
git commit -m "feat!: migrate to SQLite-based configuration system"
```

### 4. Push and Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
# Use the provided PR template
```

## 🎯 Code Standards

### Python Style Guide

We follow **PEP 8** with these specific guidelines:

#### Formatting
```python
# Use Black for automatic formatting
black fetchx_cli/

# Line length: 88 characters (Black default)
# Use double quotes for strings
# Use trailing commas in multi-line structures
```

#### Import Organization
```python
# Use isort for import sorting
isort fetchx_cli/

# Order: standard library, third-party, local imports
import asyncio
import os
from typing import Optional, Dict, List

import aiohttp
import click
from rich.console import Console

from fetchx_cli.utils.exceptions import DownloadException
from fetchx_cli.config.settings import get_config
```

#### Type Hints
```python
# Always use type hints for function signatures
async def download_segment(
    self, 
    segment: DownloadSegment,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """Download a specific segment with progress tracking."""
    pass

# Use modern type hint syntax (Python 3.9+)
def process_items(items: list[dict[str, any]]) -> dict[str, list[int]]:
    pass
```

#### Docstrings
```python
def download_file(url: str, output_dir: Optional[str] = None) -> str:
    """Download a file from the specified URL.
    
    Args:
        url: The URL to download from
        output_dir: Directory to save the file (optional)
        
    Returns:
        Path to the downloaded file
        
    Raises:
        DownloadException: If the download fails
        NetworkException: If network error occurs
        
    Examples:
        >>> download_file("https://example.com/file.zip")
        "/path/to/file.zip"
        
        >>> download_file("https://example.com/file.zip", "/custom/dir")
        "/custom/dir/file.zip"
    """
    pass
```

#### Error Handling
```python
# Use specific exception types
try:
    result = await some_operation()
except aiohttp.ClientError as e:
    raise NetworkException(f"Network error: {e}") from e
except FileNotFoundError as e:
    raise FileException(f"File not found: {e}") from e

# Use logging for debugging
logger.debug("Starting operation", extra={"url": url, "connections": connections})

# Always clean up resources
async with aiohttp.ClientSession() as session:
    # Use session
    pass
```

#### Async Best Practices
```python
# Use async/await consistently
async def download_multiple(urls: list[str]) -> list[str]:
    tasks = [download_single(url) for url in urls]
    return await asyncio.gather(*tasks)

# Handle cancellation properly
try:
    await long_running_operation()
except asyncio.CancelledError:
    logger.info("Operation cancelled")
    await cleanup()
    raise

# Use async context managers
async def process_download():
    async with ConnectionManager(url) as manager:
        await manager.download()
```

### Performance Guidelines

#### Memory Efficiency
```python
# Use generators for large datasets
def process_large_file(filename: str):
    with open(filename, 'r') as f:
        for line in f:  # Don't load entire file
            yield process_line(line)

# Stream data instead of loading all at once
async def stream_download(url: str):
    async with session.get(url) as response:
        async for chunk in response.content.iter_chunked(1024*1024):
            yield chunk
```

#### I/O Optimization
```python
# Use appropriate buffer sizes
BUFFER_SIZE = 8 * 1024 * 1024  # 8MB for large files
BUFFER_SIZE = 64 * 1024        # 64KB for small files

# Batch database operations
async def update_multiple_items(items: list[Item]):
    async with db.transaction():
        for item in items:
            await db.update(item)
```

## 📚 Documentation Standards

### Code Documentation

#### Docstring Format
```python
class EnhancedDownloader:
    """High-performance download manager with multi-connection support.
    
    This class provides advanced downloading capabilities including:
    - Multi-connection parallel downloading
    - Intelligent file merging strategies
    - Progress tracking and callbacks
    - Resume/pause functionality
    
    Attributes:
        url: The URL to download from
        output_dir: Directory to save downloaded files
        config: Configuration manager instance
        
    Example:
        >>> downloader = EnhancedDownloader("https://example.com/file.zip")
        >>> await downloader.download(connections=4)
        "/path/to/file.zip"
    """
    
    async def download(self, max_connections: Optional[int] = None) -> str:
        """Download the file with specified number of connections.
        
        Args:
            max_connections: Maximum number of parallel connections to use.
                If None, uses the configured default.
                
        Returns:
            Path to the downloaded file.
            
        Raises:
            DownloadException: If the download fails.
            NetworkException: If network connectivity issues occur.
            InsufficientSpaceException: If there's not enough disk space.
            
        Note:
            The optimal number of connections depends on network speed
            and server capabilities. Start with 4-6 connections for
            most scenarios.
        """
```

### README Updates

When adding features, update the README:

```markdown
## New Feature Documentation

### Description
Brief description of what the feature does.

### Usage
```bash
# Command examples
fetchx new-command --option value
```

### Configuration
```bash
# Configuration options
fetchx config --section new --key option --value value
```

### Examples
Real-world usage examples.
```

## 🚀 Submitting Changes

### Pull Request Process

1. **Ensure CI passes**: All tests, linting, and formatting checks
2. **Update documentation**: README, docstrings, comments
3. **Add tests**: For new features and bug fixes
4. **Update changelog**: Add entry to CHANGELOG.md
5. **Request review**: Tag relevant maintainers

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Performance improvement
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Performance benchmarks run (if applicable)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Code is commented and documented
- [ ] Changes are covered by tests
- [ ] All tests pass locally
- [ ] Documentation updated

## Performance Impact
Describe any performance implications.

## Breaking Changes
List any breaking changes and migration steps.
```

### Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **Code review** by at least one maintainer
3. **Performance review** for performance-critical changes
4. **Documentation review** for user-facing changes
5. **Security review** for security-related changes

## 🔒 Security Guidelines

### Security Best Practices

1. **Input validation**: Validate all user inputs
2. **SQL injection prevention**: Use parameterized queries
3. **Path traversal prevention**: Sanitize file paths
4. **Credential handling**: Never log sensitive information
5. **Dependency scanning**: Keep dependencies updated

### Secure Coding Examples

```python
# Input validation
def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValidationException("Only HTTP/HTTPS URLs allowed")
    return url

# Safe file operations
def safe_filename(filename: str) -> str:
    # Remove path traversal attempts
    filename = os.path.basename(filename)
    # Sanitize dangerous characters
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Credential handling
logger.debug("Making request", extra={"url": url})  # Good
logger.debug(f"Token: {token}")  # Bad - logs sensitive data
```

### Security Review Requirements

Security-sensitive changes require:

1. **Security-focused code review**
2. **Penetration testing** (if applicable)
3. **Dependency vulnerability scan**
4. **Documentation of security implications**

Thank you for contributing to FETCHX IDM! Your contributions help make this the best download manager available. 🚀