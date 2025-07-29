# FetchX

A fast, powerful command-line download manager for modern Python environments.

## Features

- **Multi-threaded downloads** with configurable connections
- **Queue management** with persistent SQLite storage  
- **Resume capability** for interrupted downloads
- **Rich terminal interface** with real-time progress tracking
- **Comprehensive configuration** with backup/restore options
- **Smart cleanup** and maintenance tools

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install from source
```bash
git clone https://github.com/theany-org/fetchx.git
cd fetchx
pip install -e .
```

### Verify installation
```bash
fetchx --version
```

## Quick Start

### Download a file
```bash
# Basic download
fetchx download https://example.com/file.zip

# Download with custom settings
fetchx download https://example.com/file.zip \
  --output ~/Downloads \
  --connections 4 \
  --filename custom_name.zip
```

### Queue management
```bash
# Add downloads to queue
fetchx add https://example.com/file1.zip
fetchx add https://example.com/file2.mp4 --connections 6

# View queue status
fetchx queue

# Process queue
fetchx start
```

### Configuration
```bash
# View current configuration
fetchx config

# Update download settings
fetchx config --section download --key max_connections --value 8

# Export/import configuration
fetchx config --export backup.json
fetchx config --import-config backup.json
```

## Commands

| Command | Description |
|---------|-------------|
| `download <url>` | Download a file directly |
| `add <url>` | Add download to queue |
| `queue` | Show queue status |
| `start` | Process download queue |
| `cancel <id>` | Cancel a download |
| `remove <id>` | Remove download from queue |
| `config` | Manage configuration |
| `logs` | View application logs |
| `stats` | Show usage statistics |
| `cleanup` | Clean old files and data |

## Configuration

FetchX uses a hierarchical configuration system with the following main sections:

### Download Settings
- `max_connections`: Maximum concurrent connections (default: 8)
- `timeout`: Network timeout in seconds (default: 30)
- `chunk_size`: Download chunk size (default: 2MB)
- `max_retries`: Maximum retry attempts (default: 3)

### Queue Settings  
- `max_concurrent_downloads`: Simultaneous downloads (default: 3)
- `save_interval`: Queue persistence frequency (default: 5s)

### Path Settings
- `download_dir`: Default download directory
- `session_dir`: Session storage location
- `log_dir`: Log file location

Use `fetchx config --section <section>` to view specific settings.

## Performance Tips

### Internet Speed Recommendations
- **< 10 Mbps**: Use 1-2 connections
- **10-50 Mbps**: Use 2-4 connections  
- **50-100 Mbps**: Use 4-6 connections
- **100+ Mbps**: Use 6-8 connections

### Server-Specific Optimization
```bash
# High-performance servers (CDNs)
fetchx config --section download --key max_connections --value 8

# Rate-limited servers 
fetchx config --section download --key max_connections --value 2
fetchx config --section download --key retry_delay --value 5

# Unreliable connections
fetchx config --section download --key max_retries --value 10
fetchx config --section download --key timeout --value 120
```

## Development

### Requirements
- Python 3.8+
- Dependencies listed in `requirements.txt`

### Running from source
```bash
python -m fetchx_cli.main --help
```

### Testing
```bash
pip install -r requirements.txt
python -m pytest
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE.md](./LICENSE.md) for details.
