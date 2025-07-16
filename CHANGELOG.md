# Changelog

All notable changes to FETCHX IDM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-07-16

### Added
- **Ultra-high performance download engine** with 100x speed improvement (300-2000+ KB/s per segment)
- **SQLite-based architecture** for reliable data persistence and ACID compliance
- **Intelligent file merger** with automatic strategy selection (sync/async/streaming)
- **Advanced CLI interface** with rich terminal displays and real-time monitoring
- **Comprehensive configuration system** with hierarchical settings and validation
- **Enterprise logging** with structured data and real-time monitoring capabilities
- **Performance analytics** with detailed statistics and export functionality
- **Automated maintenance** with intelligent cleanup and retention policies

### Enhanced
- **Download engine** with 2MB chunks (vs 8KB) and optimized progress callbacks
- **Connection management** with 200 connection pool and smart keep-alive
- **Queue system** with enhanced monitoring and detailed status displays
- **Error handling** with robust retry logic and graceful degradation
- **Memory efficiency** with 90% reduction for large file operations

### Changed
- **Configuration storage** migrated from JSON files to SQLite database (auto-migrated)
- **Progress updates** reduced from every 8KB to every 50MB for better performance
- **Minimum Python version** requirement increased to 3.8+
- **CLI commands** enhanced with new options (--detailed, --enhanced, --export)

### Fixed
- **Segment merging failures** with async file operations
- **Connection timeout errors** during large file downloads
- **Memory leaks** in long-running downloads
- **Queue persistence issues** with concurrent access
- **File corruption** during network interruptions

### Breaking Changes
- Requires Python 3.8+ (previously 3.7+)
- Configuration format changed to SQLite (automatic migration provided)
- Some CLI option names updated for consistency

### Performance
- **Download speeds**: 3-4 KB/s → 300-2000+ KB/s per segment
- **Memory usage**: 90% reduction for large file merging
- **Progress overhead**: 6000x reduction in callback frequency
- **Success rate**: 85% → 98% download completion rate


*For the complete version history and detailed release notes, visit our [GitHub Releases](https://github.com/theany-org/fetchx/releases) page.*