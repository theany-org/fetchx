# FETCHX - Internet Download Manager

A powerful command-line Internet Download Manager built with Python.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install the package:
```bash
pip install -e .
```

## Usage

### Basic Commands

#### Add a download to the queue
```bash
python -m fetchx_cli.main add https://example.com/file.zip
```

#### Show queue status
```bash
python -m fetchx_cli.main queue
```

#### Start processing the queue
```bash
python -m fetchx_cli.main start
```

#### Download a file directly (bypass queue)
```bash
python -m fetchx_cli.main download https://example.com/file.zip
```

#### Cancel a download
```bash
python -m fetchx_cli.main cancel <item_id>
```

#### Remove a download from queue
```bash
python -m fetchx_cli.main remove <item_id>
```

#### Manage configuration
```bash
# Show all configuration
python -m fetchx_cli.main config

# Show specific setting
python -m fetchx_cli.main config --section download --key max_connections

# Update setting
python -m fetchx_cli.main config --section download --key max_connections --value 8
```

### Advanced Options

#### Download with custom options
```bash
python -m fetchx_cli.main download https://example.com/file.zip \
  --output ~/Downloads \
  --filename my_file.zip \
  --connections 8 \
  --header "Authorization: Bearer token"
```

#### Add to queue with options
```bash
python -m fetchx_cli.main add https://example.com/file.zip \
  --output ~/Downloads \
  --filename my_file.zip \
  --connections 4
```

## Troubleshooting

### If the queue appears empty after adding downloads:

1. Check if the session directory exists:
```bash
ls -la ~/.fetchx_idm/sessions/
```

2. Run the debug test:
```bash
python test_fetchx.py
```

3. Check configuration:
```bash
python -m fetchx_cli.main config
```

### Common Issues

1. **Queue not persisting**: Make sure you have write permissions to `~/.fetchx_idm/sessions/`
2. **Import errors**: Ensure all dependencies are installed with `pip install -r requirements.txt`
3. **URL validation errors**: URLs should include protocol (http/https)

## Configuration

The application stores configuration in `~/.fetchx_idm/config.json` and queue data in `~/.fetchx_idm/sessions/queue.json`.

Default directories:
- Downloads: `~/Downloads/fetchx_idm/`
- Sessions: `~/.fetchx_idm/sessions/`
- Logs: `~/.fetchx_idm/logs/`

## Features

- Multi-threaded downloads with configurable connections
- Download queue management with persistence
- Resume capability for interrupted downloads
- Progress tracking with speed and ETA display
- Configuration management
- Support for custom headers and authentication
- Automatic file naming and collision handling

## Requirements

- Python 3.8+
- aiohttp
- aiofiles
- click
- rich
- humanfriendly
- pyperclip (optional, for clipboard monitoring)