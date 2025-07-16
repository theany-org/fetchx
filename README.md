# FETCHX - Internet Download Manager

A professional-grade, ultra-fast command-line Internet Download Manager built with Python. Features advanced multi-threaded downloads, intelligent file merging, comprehensive queue management, and enterprise-level monitoring capabilities.

## 🚀 Key Features

### **Core Performance**
- **Ultra-Fast Downloads**: Up to 100x performance improvement with optimized multi-connection downloading
- **Smart File Merging**: Intelligent strategy selection based on file size (sync/async/streaming)
- **Advanced Progress Tracking**: Real-time segment monitoring with detailed connection statistics
- **Resume Capability**: Robust pause/resume functionality for interrupted downloads

### **Enterprise Management**
- **Persistent Queue System**: SQLite-backed download queue with full ACID compliance
- **Comprehensive Configuration**: Hierarchical settings with validation and backup/restore
- **Advanced Logging**: Structured logging with real-time monitoring and export capabilities
- **Performance Analytics**: Detailed statistics and performance metrics

### **Professional CLI**
- **Rich Terminal Interface**: Color-coded tables, progress bars, and interactive displays
- **Real-time Monitoring**: Live connection tracking with enhanced visualization
- **Data Management**: Export/import capabilities for configuration and analytics
- **Intelligent Cleanup**: Automated maintenance with configurable retention policies

## 📊 Performance Metrics

- **Download Speed**: 300-2000+ KB/s per segment (vs 3-4 KB/s in basic implementations)
- **Optimal Connections**: Auto-configurable (recommended: 4-8 connections)
- **Memory Efficient**: Smart buffer management for files of any size (2MB chunks)
- **Network Optimized**: 200 connection pool with intelligent keep-alive
- **Merge Performance**: Size-based strategy selection (sync/async/streaming)
- **Progress Updates**: Optimized to every 50MB vs every 8KB (6000x reduction in overhead)

## 🛠 Installation

### Prerequisites
- **Python 3.8+** (3.9+ recommended for optimal performance)
- **pip package manager**

### Quick Install
```bash
# Clone and install
git clone https://github.com/theny-org/fetchx.git
cd fetchx
pip install -r requirements.txt
pip install -e .

# Verify installation
fetchx --version
```

### Alternative Installation
```bash
# Direct module execution
python -m fetchx_cli.main --version

# Create alias for convenience
echo "alias fx='python -m fetchx_cli.main'" >> ~/.bashrc
source ~/.bashrc
```

## ⚡ Quick Start

### **Instant Download**
```bash
# Basic high-performance download
fetchx download https://example.com/largefile.zip

# Optimized for fast connections
fetchx download https://example.com/file.zip --connections 6 --detailed

# Custom location with progress monitoring
fetchx download https://example.com/file.zip \
  --output ~/Downloads/MyFiles \
  --filename custom_name.zip \
  --connections 8 \
  --detailed
```

### **Queue Management Workflow**
```bash
# Add multiple downloads
fetchx add https://example.com/file1.zip --connections 4
fetchx add https://example.com/file2.mp4 --connections 6
fetchx add https://example.com/file3.pdf --output ~/Documents

# Monitor queue status
fetchx queue --detailed

# Start processing with enhanced monitoring
fetchx start --enhanced

# Manage active downloads
fetchx cancel a1b2c3d4    # Cancel by ID
fetchx remove e5f6g7h8    # Remove from queue
```

## ⚙️ Configuration & Management

### **Smart Configuration System**
```bash
# Interactive configuration view
fetchx config                           # View all settings in tree format
fetchx config --section download        # View specific section
fetchx config --section download --key max_connections  # Get specific setting

# Update settings with validation
fetchx config --section download --key max_connections --value 8
fetchx config --section download --key timeout --value 60
fetchx config --section queue --key max_concurrent_downloads --value 3

# Configuration backup and restore
fetchx config --export my_config.json   # Backup configuration
fetchx config --import-config my_config.json  # Restore configuration
fetchx config --reset                   # Reset to defaults
```

### **Intelligent Cleanup**
```bash
# Smart maintenance
fetchx cleanup --sessions --max-age 30  # Clean old sessions
fetchx cleanup --logs --max-age 7       # Clean old logs
fetchx cleanup --all --max-age 15       # Clean everything
fetchx cleanup --all --dry-run          # Preview cleanup actions
```

### **SQLite Database Benefits**
- **ACID Compliance**: Guaranteed data integrity
- **Concurrent Access**: Multiple process support
- **Efficient Indexing**: Fast queries and lookups
- **Automatic Backup**: Built-in reliability features
- **Cross-Platform**: Works on Windows, macOS, Linux

## 🔍 Complete Configuration Reference

### **Download Settings** (`fetchx config --section download`)
| Setting | Default          | Description | Range |
|---------|------------------|-------------|-------|
| `max_connections` | 8                | Maximum concurrent connections per download | 1-32 |
| `chunk_size` | 2MB              | Download chunk size for optimal performance | 64KB-32MB |
| `timeout` | 30               | Network timeout in seconds | 10-300 |
| `max_retries` | 3                | Maximum retry attempts for failed segments | 1-10 |
| `retry_delay` | 2                | Delay between retries in seconds | 1-30 |
| `user_agent` | FETCHX-IDM/0.1.0 | HTTP User-Agent string | Any string |
| `connect_timeout` | 10               | Connection establishment timeout | 5-60 |
| `read_timeout` | 30               | Data read timeout per chunk | 10-120 |

### **Display Settings** (`fetchx config --section display`)
| Setting | Default | Description |
|---------|---------|-------------|
| `progress_update_interval` | 0.1 | Progress update frequency in seconds |
| `show_speed` | true | Display download speed information |
| `show_eta` | true | Show estimated time remaining |
| `show_percentage` | true | Display progress percentage |

### **Queue Settings** (`fetchx config --section queue`)
| Setting | Default | Description | Range |
|---------|---------|-------------|-------|
| `max_concurrent_downloads` | 3 | Maximum simultaneous downloads | 1-10 |
| `save_interval` | 5 | Queue persistence frequency in seconds | 1-60 |

### **Path Settings** (`fetchx config --section paths`)
| Setting | Default | Description |
|---------|---------|-------------|
| `download_dir` | ~/Downloads/fetchx_idm | Default download directory |
| `session_dir` | ~/.fetchx_idm/sessions | Legacy session storage |
| `log_dir` | ~/.fetchx_idm/logs | Legacy log storage |

## 📊 Performance Optimization Guide

### **Connection Optimization Matrix**

| Internet Speed | Recommended Connections | Use Case | Command |
|----------------|------------------------|----------|---------|
| < 10 Mbps | 1-2 | Slow/Mobile | `fetchx download [URL] --connections 2` |
| 10-50 Mbps | 2-4 | Home/Office | `fetchx download [URL] --connections 4` |
| 50-100 Mbps | 4-6 | Fast Broadband | `fetchx download [URL] --connections 6` |
| 100+ Mbps | 6-8 | High-speed/Fiber | `fetchx download [URL] --connections 8` |
| 1+ Gbps | 8-16 | Enterprise/Datacenter | `fetchx download [URL] --connections 16` |

### **Server-Specific Optimizations**

#### **High-Performance Servers**
```bash
# CDN and enterprise servers
fetchx config --section download --key max_connections --value 8
fetchx config --section download --key timeout --value 30
fetchx config --section queue --key max_concurrent_downloads --value 3
```

#### **Rate-Limited Servers**
```bash
# Social media, file sharing sites
fetchx config --section download --key max_connections --value 2
fetchx config --section download --key timeout --value 60
fetchx config --section download --key retry_delay --value 5
```

#### **Unreliable Servers**
```bash
# Slow or unstable servers
fetchx config --section download --key max_connections --value 1
fetchx config --section download --key max_retries --value 10
fetchx config --section download --key timeout --value 120
```

### **Memory & Disk Optimization**

#### **Large File Downloads (>1GB)**
```bash
# Optimize for large files
fetchx config --section download --key max_connections --value 6
fetchx config --section download --key chunk_size --value 4194304  # 4MB chunks

# Monitor merge performance
fetchx logs --level INFO --module merger
```

#### **Many Small Files**
```bash
# Optimize for multiple small files
fetchx config --section queue --key max_concurrent_downloads --value 5
fetchx config --section download --key max_connections --value 2
```

### **Network Environment Optimization**

#### **Corporate Networks**
```bash
# Behind corporate firewall/proxy
fetchx config --section download --key timeout --value 90
fetchx config --section download --key connect_timeout --value 30
fetchx config --section download --key max_connections --value 4
```

#### **Mobile/Metered Connections**
```bash
# Optimize for mobile data
fetchx config --section download --key max_connections --value 1
fetchx config --section queue --key max_concurrent_downloads --value 1
fetchx config --section download --key timeout --value 60
```

## 🤝 Contributing & Development
If you're interested in contributing, please read the [contribution guidelines](./CONTRIBUTING.md).

## 📄 License & Legal
This project is licensed under the **MIT License** - see the [LICENSE](./LICENSE.md) file for details.

## **Getting Help**
1. **📖 Check Documentation**: This README covers most use cases
2. **🔍 Search Issues**: [GitHub Issues](https://github.com/theany-org/fetchx/issues)
3. **🐛 Report Bugs**: [New Issue](https://github.com/theany-org/fetchx/issues/new?template=bug_report.md)
4. **✨ Feature Issue**: [New Feature](https://github.com/theany-org/fetchx/issues/new?template=feature_request.md)
---

**FETCHX IDM** - Built for speed, reliability, and professional use. 🚀
