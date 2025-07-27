"""Complete CLI command definitions with all enhanced commands."""

import asyncio
import json
import os
import sys
from pathlib import Path
import time
from datetime import datetime
from typing import Optional

import click
from humanfriendly import format_size, format_timespan
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from fetchx_cli.cli.interface import EnhancedCLIInterface
from fetchx_cli.cli.validators import Validators
from fetchx_cli.config.settings import get_config
from fetchx_cli.core.database import get_database
from fetchx_cli.core.downloader import EnhancedDownloader
from fetchx_cli.core.queue import DownloadQueue
from fetchx_cli.core.session import SessionManager
from fetchx_cli.utils.exceptions import FetchXIdmException
from fetchx_cli.utils.file_utils import FileManager
from fetchx_cli.utils.logging import get_logger, setup_logging

console = Console()
interface = EnhancedCLIInterface()
logger = get_logger()


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version information")
@click.option(
    "--log-level",
    default=None,
    help="Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). If specified, saves as new default. Use 'fetchx log-level' to manage saved settings.",
)
@click.pass_context
def fetchx(ctx, version, log_level):
    """FETCHX Internet Download Manager - A powerful command-line download manager."""
    # Initialize logging - save to config if user explicitly provided log-level
    setup_logging(log_level, save_if_provided=(log_level is not None))
    logger.info("FETCHX IDM started", "cli")

    if version:
        click.echo("FETCHX IDM v0.1.1")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@fetchx.command()
@click.argument("url")
@click.option("-o", "--output", help="Output directory")
@click.option("-f", "--filename", help="Custom filename")
@click.option(
    "-c", "--connections", default=None, type=int, help="Number of connections (1-32)"
)
@click.option("--header", multiple=True, help='Custom headers (format: "Key: Value")')
@click.option("--no-progress", is_flag=True, help="Disable progress display")
@click.option("--detailed", is_flag=True, help="Show detailed connection progress")
def download(
    url: str,
    output: Optional[str],
    filename: Optional[str],
    connections: Optional[int],
    header: tuple,
    no_progress: bool,
    detailed: bool,
):
    """Download a file from URL with enhanced progress display."""
    try:
        logger.info(
            f"Starting direct download: {url}",
            "cli",
            url=url,
            output=output,
            filename=filename,
        )

        # Validate inputs
        url = Validators.validate_url(url)

        if filename:
            filename = Validators.validate_filename(filename)

        if connections:
            connections = Validators.validate_connections(connections)

        # Parse headers
        headers = {}
        for h in header:
            if ":" not in h:
                raise click.BadParameter(f"Invalid header format: {h}")
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

        # Run download with enhanced progress
        asyncio.run(
            _download_file_enhanced(
                url, output, filename, connections, headers, not no_progress, detailed
            )
        )

        logger.info("Direct download completed successfully", "cli", url=url)

    except FetchXIdmException as e:
        logger.error(f"Download failed: {e}", "cli", url=url)
        interface.print_error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during download: {e}", "cli", url=url)
        interface.print_error(f"Unexpected error: {e}")
        sys.exit(1)


async def _download_file_enhanced(
    url: str,
    output_dir: Optional[str],
    filename: Optional[str],
    connections: Optional[int],
    headers: dict,
    show_progress: bool,
    detailed: bool,
):
    """Enhanced download function with detailed progress tracking."""
    downloader = EnhancedDownloader(url, output_dir, filename, headers)

    # Get download info
    interface.print_info("🔍 Getting file information...")
    download_info = await downloader.get_download_info()

    # Calculate optimal connections
    if connections is None:
        connections = get_config().config.download.max_connections

    # Display download info with enhanced formatting
    interface.display_download_info(
        url=url,
        filename=download_info.filename,
        size=download_info.total_size,
        connections=connections,
        output_dir=download_info.file_path,
    )

    if show_progress:
        if detailed and download_info.supports_ranges and connections > 1:
            # Show detailed segment progress
            interface.print_info(
                "🚀 Starting download with detailed connection tracking..."
            )

            # Add progress callback for stats updates
            def progress_callback(stats):
                pass  # The monitor will handle display updates

            downloader.add_progress_callback(progress_callback)

            # Start download in a separate task
            download_task = asyncio.create_task(downloader.download(connections))

            # Monitor progress with detailed view
            monitor_task = asyncio.create_task(
                interface.monitor_single_download_with_segments(downloader)
            )

            try:
                # Wait for download to complete
                file_path = await download_task

                # Cancel monitoring
                monitor_task.cancel()

                interface.print_success(f"✅ Download completed: {file_path}")

                # Show final summary
                summary = downloader.get_connection_summary()
                interface.print_info(f"📊 Final Summary:")
                interface.print_info(
                    f"   🔗 Total Connections: {summary['total_connections']}"
                )
                interface.print_info(
                    f"   ✅ Completed: {summary['completed_connections']}"
                )
                interface.print_info(
                    f"   📥 Total Downloaded: {format_size(summary['total_downloaded'])}"
                )
                interface.print_info(
                    f"   🚀 Average Speed: {format_size(summary['total_speed'])}/s"
                )

            except Exception as e:
                monitor_task.cancel()
                raise e

        else:
            # Simple progress display
            interface.print_info("🚀 Starting download...")

            # Use simple progress tracker
            progress_tracker = interface.progress_tracker
            if not progress_tracker:
                from fetchx_cli.utils.progress import EnhancedProgressTracker

                progress_tracker = EnhancedProgressTracker(show_segments=False)
                interface.progress_tracker = progress_tracker

            progress_tracker.start()

            download_id = "single_download"
            progress_tracker.add_download(
                download_id, download_info.filename, download_info.total_size
            )

            def progress_callback(stats):
                progress_tracker.update_download(
                    download_id, stats.downloaded, stats.total_size
                )

            downloader.add_progress_callback(progress_callback)

            try:
                # Start download
                file_path = await downloader.download(connections)

                progress_tracker.complete_download(download_id)
                progress_tracker.stop()

                interface.print_success(f"✅ Download completed: {file_path}")

            except Exception as e:
                progress_tracker.stop()
                raise
    else:
        # No progress display
        interface.print_info("🚀 Starting download...")
        file_path = await downloader.download(connections)
        interface.print_success(f"✅ Download completed: {file_path}")


@fetchx.command()
@click.argument("url")
@click.option("-o", "--output", help="Output directory")
@click.option("-f", "--filename", help="Custom filename")
@click.option(
    "-c", "--connections", default=None, type=int, help="Number of connections"
)
@click.option("--header", multiple=True, help="Custom headers")
def add(
    url: str,
    output: Optional[str],
    filename: Optional[str],
    connections: Optional[int],
    header: tuple,
):
    """Add a download to the queue."""
    try:
        logger.info(f"Adding download to queue: {url}", "cli", url=url)

        # Validate inputs
        url = Validators.validate_url(url)

        if filename:
            filename = Validators.validate_filename(filename)

        if connections:
            connections = Validators.validate_connections(connections)

        # Parse headers
        headers = {}
        for h in header:
            if ":" not in h:
                raise click.BadParameter(f"Invalid header format: {h}")
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

        # Add to queue
        interface.print_info("📥 Adding download to queue...")
        queue = DownloadQueue()
        item_id = queue.add_download(url, filename, output, headers, connections)

        interface.print_success(f"✅ Added to queue with ID: {item_id[:8]}")

        # Show current queue status
        items = queue.list_downloads()
        interface.print_info(f"📊 Queue now contains {len(items)} item(s)")

        logger.info(
            f"Download added to queue successfully",
            "cli",
            url=url,
            item_id=item_id,
            queue_size=len(items),
        )

    except FetchXIdmException as e:
        logger.error(f"Failed to add download to queue: {e}", "cli", url=url)
        interface.print_error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error adding to queue: {e}", "cli", url=url)
        interface.print_error(f"Unexpected error: {e}")
        sys.exit(1)


@fetchx.command()
@click.option("--detailed", is_flag=True, help="Show detailed connection information")
def queue(detailed: bool):
    """Show download queue status with enhanced display."""
    try:
        logger.debug("Displaying queue status", "cli")
        queue = DownloadQueue()
        interface.print_info("📊 Loading queue status...")

        if detailed:
            # Show enhanced queue status with connection details
            items = queue.list_downloads()
            stats = queue.get_queue_stats()

            # Enhanced display
            interface.console.print(
                "\n🚀 [bold blue]FETCHX IDM - Queue Status[/bold blue]"
            )

            # Statistics panel
            stats_table = Table(title="📈 Queue Statistics", border_style="blue")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Count", style="magenta")

            stats_table.add_row("📊 Total Downloads", str(stats["total_downloads"]))
            stats_table.add_row("🔄 Active Downloads", str(stats["active_downloads"]))
            stats_table.add_row("⏳ Queued", str(stats["status_counts"]["queued"]))
            stats_table.add_row(
                "✅ Completed", str(stats["status_counts"]["completed"])
            )
            stats_table.add_row("❌ Failed", str(stats["status_counts"]["failed"]))
            stats_table.add_row(
                "🚫 Cancelled", str(stats["status_counts"]["cancelled"])
            )

            interface.console.print(stats_table)

            if items:
                # Detailed downloads table
                detailed_table = Table(title="📋 Detailed Queue", border_style="cyan")
                detailed_table.add_column("ID", style="cyan", width=10)
                detailed_table.add_column("File", style="white", width=20)
                detailed_table.add_column("Status", style="bold", width=12)
                detailed_table.add_column("Progress", style="green", width=20)
                detailed_table.add_column("Speed", style="blue", width=10)
                detailed_table.add_column("Connections", style="yellow", width=11)
                detailed_table.add_column("ETA", style="magenta", width=8)

                for item in items:
                    filename = (
                        (item.filename or "Unknown")[:18] + "..."
                        if len(item.filename or "Unknown") > 18
                        else (item.filename or "Unknown")
                    )

                    # Status with icon
                    status_icons = {
                        "queued": "⏳",
                        "downloading": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                        "cancelled": "🚫",
                        "paused": "⏸️",
                    }

                    icon = status_icons.get(item.status.value, "❓")
                    status_text = f"{icon} {item.status.value.upper()}"

                    # Progress bar
                    progress_bar = interface._create_progress_bar(
                        item.progress_percentage, 15
                    )

                    # Connections info
                    connections = item.max_connections or 1
                    conn_text = f"🔗 {connections}"

                    # Other info
                    speed = (
                        format_size(item.download_speed) + "/s"
                        if item.download_speed > 0
                        else "-"
                    )
                    eta = format_timespan(item.eta) if item.eta else "-"

                    detailed_table.add_row(
                        item.id[:8],
                        filename,
                        status_text,
                        progress_bar,
                        speed,
                        conn_text,
                        eta,
                    )

                interface.console.print(detailed_table)
        else:
            # Standard display
            interface.display_queue_status(queue)

    except Exception as e:
        logger.error(f"Error loading queue: {e}", "cli")
        interface.print_error(f"Error loading queue: {e}")
        sys.exit(1)


@fetchx.command()
@click.option(
    "--enhanced", is_flag=True, help="Use enhanced monitoring with connection details"
)
def start(enhanced: bool):
    """Start processing the download queue with enhanced monitoring."""

    async def _start_queue_enhanced():
        try:
            logger.info("Starting download queue processing", "cli")
            queue = DownloadQueue()

            # Check if there are any downloads to process
            items = queue.list_downloads()
            if not items:
                interface.print_warning("📭 No downloads in queue to process.")
                return

            queued_items = [item for item in items if item.status.value == "queued"]
            if not queued_items:
                interface.print_warning("⏳ No queued downloads to process.")
                return

            interface.print_info(
                f"🚀 Starting download queue with {len(queued_items)} queued download(s)..."
            )
            logger.info(
                f"Queue processing started", "cli", queued_count=len(queued_items)
            )

            # Add progress callback
            queue.add_progress_callback(lambda q: None)  # Placeholder

            await queue.start_queue()

            try:
                # Monitor downloads with enhanced interface
                if enhanced:
                    await interface.monitor_downloads_enhanced(queue)
                else:
                    await interface.monitor_downloads(queue)
            except KeyboardInterrupt:
                interface.print_info("🛑 Stopping download queue...")
                logger.info("Queue processing stopped by user", "cli")
                await queue.stop_queue()

        except Exception as e:
            logger.error(f"Error starting queue: {e}", "cli")
            interface.print_error(f"Error starting queue: {e}")
            raise

    try:
        asyncio.run(_start_queue_enhanced())
    except KeyboardInterrupt:
        interface.print_info("🛑 Queue stopped by user.")
        logger.info("Queue stopped by user interrupt", "cli")
    except Exception as e:
        logger.error(f"Queue error: {e}", "cli")
        interface.print_error(f"Queue error: {e}")
        sys.exit(1)


@fetchx.command()
@click.argument("item_id")
def cancel(item_id: str):
    """Cancel a download."""
    try:
        logger.info(f"Cancelling download: {item_id}", "cli", item_id=item_id)
        queue = DownloadQueue()

        if queue.cancel_download(item_id):
            interface.print_success(f"🚫 Cancelled download: {item_id}")
            logger.info(f"Download cancelled successfully", "cli", item_id=item_id)
        else:
            interface.print_error(f"❌ Download not found: {item_id}")
            logger.warning(
                f"Download not found for cancellation", "cli", item_id=item_id
            )
    except Exception as e:
        logger.error(f"Error cancelling download: {e}", "cli", item_id=item_id)
        interface.print_error(f"Error cancelling download: {e}")
        sys.exit(1)


@fetchx.command()
@click.argument("item_id")
def remove(item_id: str):
    """Remove a download from queue."""
    try:
        logger.info(f"Removing download from queue: {item_id}", "cli", item_id=item_id)
        queue = DownloadQueue()

        if queue.remove_download(item_id):
            interface.print_success(f"🗑️ Removed download: {item_id}")
            logger.info(f"Download removed successfully", "cli", item_id=item_id)
        else:
            interface.print_error(f"❌ Download not found: {item_id}")
            logger.warning(f"Download not found for removal", "cli", item_id=item_id)
    except Exception as e:
        logger.error(f"Error removing download: {e}", "cli", item_id=item_id)
        interface.print_error(f"Error removing download: {e}")
        sys.exit(1)


@fetchx.command()
@click.option("--section", help="Configuration section to display/modify")
@click.option("--key", help="Configuration key to display/modify")
@click.option("--value", help="New value to set (only with --section and --key)")
@click.option("--reset", is_flag=True, help="Reset all settings to defaults")
@click.option("--export", help="Export configuration to file")
@click.option("--import-config", "import_file", help="Import configuration from file")
def config(
    section: Optional[str],
    key: Optional[str],
    value: Optional[str],
    reset: bool,
    export: Optional[str],
    import_file: Optional[str],
):
    """Manage FETCHX configuration."""
    try:
        config_manager = get_config()

        if reset:
            interface.print_info("🔄 Resetting configuration to defaults...")
            config_manager.reset_to_defaults()
            interface.print_success("✅ Configuration reset to defaults")
            return

        if export:
            interface.print_info(f"📤 Exporting configuration to {export}...")
            config_data = config_manager.export_config()
            with open(export, "w") as f:
                json.dump(config_data, f, indent=2)
            interface.print_success(f"✅ Configuration exported to {export}")
            return

        if import_file:
            interface.print_info(f"📥 Importing configuration from {import_file}...")
            with open(import_file, "r") as f:
                config_data = json.load(f)
            config_manager.import_config(config_data)
            interface.print_success(f"✅ Configuration imported from {import_file}")
            return

        if section and key and value is not None:
            # Set specific setting
            interface.print_info(f"🔧 Setting {section}.{key} = {value}")
            config_manager.update_setting(section, key, value)
            interface.print_success(f"✅ Updated {section}.{key}")
            return

        if section and key:
            # Get specific setting
            try:
                current_value = config_manager.get_setting(section, key)
                interface.print_info(f"📋 {section}.{key} = {current_value}")
                return
            except ValueError as e:
                interface.print_error(str(e))
                sys.exit(1)

        # Display configuration
        interface.print_info("📋 FETCHX Configuration")

        all_settings = config_manager.get_all_settings()

        if section:
            # Show specific section
            if section not in all_settings:
                interface.print_error(f"❌ Section '{section}' not found")
                sys.exit(1)

            table = Table(title=f"🔧 {section.upper()} Settings", border_style="blue")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_column("Type", style="yellow")

            for key, value in all_settings[section].items():
                table.add_row(key, str(value), type(value).__name__)

            console.print(table)
        else:
            # Show all sections in a tree
            tree = Tree("⚙️ [bold blue]FETCHX Configuration[/bold blue]")

            for section_name, settings in all_settings.items():
                section_node = tree.add(
                    f"📂 [bold cyan]{section_name.upper()}[/bold cyan]"
                )
                for key, value in settings.items():
                    section_node.add(
                        f"[green]{key}[/green]: [magenta]{value}[/magenta]"
                    )

            console.print(tree)

            # Show path validation
            interface.print_info("\n🔍 Path Validation:")
            path_validation = config_manager.validate_paths()

            path_table = Table(border_style="green")
            path_table.add_column("Path", style="cyan")
            path_table.add_column("Status", style="bold")

            for path_name, is_valid in path_validation.items():
                status = "✅ Valid" if is_valid else "❌ Invalid"
                path_table.add_row(path_name, status)

            console.print(path_table)

    except Exception as e:
        logger.error(f"Configuration error: {e}", "cli")
        interface.print_error(f"Configuration error: {e}")
        sys.exit(1)


@fetchx.command()
@click.option(
    "--level", help="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
)
@click.option("--module", help="Filter by module name")
@click.option("--limit", default=100, type=int, help="Number of log entries to show")
@click.option("--tail", is_flag=True, help="Show most recent logs (like tail -f)")
@click.option("--export", help="Export logs to file")
def logs(
    level: Optional[str],
    module: Optional[str],
    limit: int,
    tail: bool,
    export: Optional[str],
):
    """View and manage FETCHX logs."""
    try:
        logger_instance = get_logger()

        if export:
            interface.print_info(f"📤 Exporting logs to {export}...")
            logs_data = logger_instance.get_logs(level, module, limit=10000)

            with open(export, "w") as f:
                for log_entry in logs_data:
                    timestamp = datetime.fromtimestamp(log_entry["timestamp"])
                    f.write(
                        f"{timestamp} [{log_entry['level']}] {log_entry['module']}: {log_entry['message']}\n"
                    )
                    if log_entry.get("extra_data"):
                        f.write(f"    Extra: {json.dumps(log_entry['extra_data'])}\n")

            interface.print_success(
                f"✅ Exported {len(logs_data)} log entries to {export}"
            )
            return

        if tail:
            interface.print_info("📄 Showing recent logs (Press Ctrl+C to exit)...")
            try:
                while True:
                    logs_data = logger_instance.get_logs(level, module, limit=10)
                    console.clear()

                    if logs_data:
                        table = Table(title="📊 Recent Logs", border_style="blue")
                        table.add_column("Time", style="cyan", width=20)
                        table.add_column("Level", style="bold", width=10)
                        table.add_column("Module", style="yellow", width=15)
                        table.add_column("Message", style="white")

                        for log_entry in logs_data[-10:]:  # Last 10 entries
                            timestamp = datetime.fromtimestamp(log_entry["timestamp"])
                            time_str = timestamp.strftime("%H:%M:%S")

                            # Color by level
                            level_colors = {
                                "DEBUG": "dim",
                                "INFO": "blue",
                                "WARNING": "yellow",
                                "ERROR": "red",
                                "CRITICAL": "bold red",
                            }
                            level_color = level_colors.get(log_entry["level"], "white")

                            table.add_row(
                                time_str,
                                f"[{level_color}]{log_entry['level']}[/{level_color}]",
                                log_entry["module"],
                                (
                                    log_entry["message"][:80] + "..."
                                    if len(log_entry["message"]) > 80
                                    else log_entry["message"]
                                ),
                            )

                        console.print(table)
                    else:
                        console.print("📭 No recent logs found")

                    time.sleep(2)  # Refresh every 2 seconds

            except KeyboardInterrupt:
                interface.print_info("🛑 Stopped log monitoring")
                return

        # Regular log display
        interface.print_info("📄 Loading logs...")
        logs_data = logger_instance.get_logs(level, module, limit)

        if not logs_data:
            interface.print_warning("📭 No logs found matching criteria")
            return

        # Display logs in table
        table = Table(title=f"📊 Logs ({len(logs_data)} entries)", border_style="blue")
        table.add_column("Timestamp", style="cyan", width=20)
        table.add_column("Level", style="bold", width=10)
        table.add_column("Module", style="yellow", width=15)
        table.add_column("Message", style="white")

        for log_entry in logs_data:
            timestamp = datetime.fromtimestamp(log_entry["timestamp"])
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            # Color by level
            level_colors = {
                "DEBUG": "dim",
                "INFO": "blue",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold red",
            }
            level_color = level_colors.get(log_entry["level"], "white")

            # Truncate long messages
            message = log_entry["message"]
            if len(message) > 100:
                message = message[:97] + "..."

            table.add_row(
                time_str,
                f"[{level_color}]{log_entry['level']}[/{level_color}]",
                log_entry["module"],
                message,
            )

        console.print(table)

        # Show log statistics
        stats = logger_instance.get_log_stats()
        if stats:
            interface.print_info("\n📊 Log Statistics:")
            stats_table = Table(border_style="green")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Count", style="magenta")

            stats_table.add_row("Total Logs", str(stats["total_logs"]))
            stats_table.add_row("Recent Errors (24h)", str(stats["recent_errors"]))
            stats_table.add_row("Recent Warnings (24h)", str(stats["recent_warnings"]))

            console.print(stats_table)

    except Exception as e:
        logger.error(f"Error viewing logs: {e}", "cli")
        interface.print_error(f"Error viewing logs: {e}")
        sys.exit(1)


@click.command()
@click.option("--sessions", is_flag=True, help="Clean up old sessions")
@click.option("--logs", is_flag=True, help="Clean up old logs")
@click.option("--temp", is_flag=True, help="Clean up temporary directories")  # NEW
@click.option("--all", "clean_all", is_flag=True, help="Clean up everything")
@click.option("--max-age", default=30, type=int, help="Maximum age in days for cleanup")
@click.option(
    "--temp-age", default=1, type=int, help="Maximum age in days for temp directories"
)  # NEW
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned without actually doing it",
)
@click.option("--force", is_flag=True, help="Force cleanup without confirmation")  # NEW
def cleanup(
    sessions: bool,
    logs: bool,
    temp: bool,
    clean_all: bool,
    max_age: int,
    temp_age: int,
    dry_run: bool,
    force: bool,
):
    """Clean up old files, data, and temporary directories."""
    try:
        interface.print_info("🧹 Starting cleanup process...")

        db = get_database()
        session_manager = SessionManager()
        logger_instance = get_logger()

        cleanup_actions = []
        cleanup_results = {
            "sessions_cleaned": 0,
            "logs_cleaned": 0,
            "temp_cleaned": 0,
            "temp_size_freed": 0,
            "errors": 0,
        }

        # Sessions cleanup
        if clean_all or sessions:
            cutoff_time = time.time() - (max_age * 24 * 60 * 60)
            old_sessions = [
                s
                for s in session_manager.list_sessions()
                if s.status in ["completed", "failed"] and s.updated_at < cutoff_time
            ]

            if old_sessions:
                cleanup_actions.append(
                    f"🗂️ Remove {len(old_sessions)} old sessions (older than {max_age} days)"
                )

        # Logs cleanup
        if clean_all or logs:
            cutoff_time = time.time() - (max_age * 24 * 60 * 60)
            all_logs = logger_instance.get_logs(limit=50000)
            old_logs = [log for log in all_logs if log["timestamp"] < cutoff_time]

            if old_logs:
                cleanup_actions.append(
                    f"📄 Remove {len(old_logs)} old log entries (older than {max_age} days)"
                )

        # NEW: Temporary directories cleanup
        if clean_all or temp:
            temp_info = interface.cleanup_temp_directories(
                max_age_hours=temp_age * 24, dry_run=True  # Always check first
            )

            if temp_info["cleaned"] > 0:
                cleanup_actions.append(
                    f"🗂️ Remove {temp_info['cleaned']} old temporary directories "
                    f"({format_size(temp_info['size_freed'])}) (older than {temp_age} days)"
                )

        if not cleanup_actions:
            interface.print_success("✨ Nothing to clean up!")
            return

        # Show what will be cleaned
        interface.print_info("🔍 Cleanup plan:")
        for action in cleanup_actions:
            console.print(f"  • {action}")

        if dry_run:
            interface.print_info("🔬 Dry run completed - no changes made")
            return

        # Confirm cleanup
        if not force and not click.confirm("\n🤔 Proceed with cleanup?"):
            interface.print_info("❌ Cleanup cancelled")
            return

        # Perform cleanup
        interface.print_info("🚀 Starting cleanup operations...")

        # Clean sessions
        if clean_all or sessions:
            try:
                session_manager.cleanup_old_sessions(max_age)
                cleanup_results["sessions_cleaned"] = len(old_sessions)
                interface.print_success(
                    f"✅ Cleaned {cleanup_results['sessions_cleaned']} old sessions"
                )
            except Exception as e:
                interface.print_error(f"❌ Error cleaning sessions: {e}")
                cleanup_results["errors"] += 1

        # Clean logs
        if clean_all or logs:
            try:
                cleanup_results["logs_cleaned"] = logger_instance.cleanup_old_logs(
                    max_age
                )
                interface.print_success(
                    f"✅ Cleaned {cleanup_results['logs_cleaned']} old log entries"
                )
            except Exception as e:
                interface.print_error(f"❌ Error cleaning logs: {e}")
                cleanup_results["errors"] += 1

        # Clean temporary directories
        if clean_all or temp:
            try:
                temp_results = interface.cleanup_temp_directories(
                    max_age_hours=temp_age * 24, dry_run=False
                )
                cleanup_results["temp_cleaned"] = temp_results["cleaned"]
                cleanup_results["temp_size_freed"] = temp_results["size_freed"]
                cleanup_results["errors"] += temp_results["errors"]

                if temp_results["cleaned"] > 0:
                    interface.print_success(
                        f"✅ Cleaned {temp_results['cleaned']} temporary directories "
                        f"({format_size(temp_results['size_freed'])} freed)"
                    )
                else:
                    interface.print_info("ℹ️ No old temporary directories found")

            except Exception as e:
                interface.print_error(f"❌ Error cleaning temporary directories: {e}")
                cleanup_results["errors"] += 1

        # Show cleanup summary
        interface.print_info("\n📊 Cleanup Summary:")
        summary_table = Table(border_style="green")
        summary_table.add_column("Category", style="cyan")
        summary_table.add_column("Items Cleaned", style="magenta")
        summary_table.add_column("Space Freed", style="yellow")

        if cleanup_results["sessions_cleaned"] > 0:
            summary_table.add_row(
                "Sessions", str(cleanup_results["sessions_cleaned"]), "-"
            )
        if cleanup_results["logs_cleaned"] > 0:
            summary_table.add_row(
                "Log Entries", str(cleanup_results["logs_cleaned"]), "-"
            )
        if cleanup_results["temp_cleaned"] > 0:
            summary_table.add_row(
                "Temp Directories",
                str(cleanup_results["temp_cleaned"]),
                format_size(cleanup_results["temp_size_freed"]),
            )

        if cleanup_results["errors"] > 0:
            summary_table.add_row("Errors", str(cleanup_results["errors"]), "-")

        console.print(summary_table)

        if cleanup_results["errors"] == 0:
            interface.print_success("🎉 Cleanup completed successfully!")
        else:
            interface.print_warning(
                f"⚠️ Cleanup completed with {cleanup_results['errors']} errors"
            )

    except Exception as e:
        logger.error(f"Cleanup error: {e}", "cli")
        interface.print_error(f"Cleanup error: {e}")
        return 1


@fetchx.command()
@click.option("--detailed", is_flag=True, help="Show detailed statistics")
@click.option("--export", help="Export statistics to JSON file")
def stats(detailed: bool, export: Optional[str]):
    """Show FETCHX statistics and performance metrics."""
    try:
        interface.print_info("📊 Gathering statistics...")

        queue = DownloadQueue()
        session_manager = SessionManager()
        logger_instance = get_logger()
        config_manager = get_config()

        # Gather statistics
        queue_stats = queue.get_queue_stats()
        session_stats = session_manager.get_session_stats()
        log_stats = logger_instance.get_log_stats()

        # Calculate additional metrics
        all_downloads = queue.list_downloads()
        completed_downloads = [
            d for d in all_downloads if d.status.value == "completed"
        ]

        # Performance metrics
        total_downloaded = 0
        total_time = 0
        avg_speed = 0

        if completed_downloads:
            for download in completed_downloads:
                if download.completed_at and download.started_at:
                    download_time = download.completed_at - download.started_at
                    total_time += download_time
                    # Estimate size based on typical download speeds (this is approximate)
                    # In a real implementation, you'd store actual download sizes

        stats_data = {
            "queue": queue_stats,
            "sessions": session_stats,
            "logs": log_stats,
            "performance": {
                "total_downloads": len(all_downloads),
                "completed_downloads": len(completed_downloads),
                "success_rate": (
                    (len(completed_downloads) / len(all_downloads) * 100)
                    if all_downloads
                    else 0
                ),
                "average_download_time": (
                    total_time / len(completed_downloads) if completed_downloads else 0
                ),
            },
            "system": {
                "config_sections": len(config_manager.get_all_settings()),
                "storage_path": str(config_manager.config.paths.download_dir),
                "database_size": (
                    os.path.getsize(
                        os.path.join(os.path.expanduser("~/.fetchx_idm"), "fetchx.db")
                    )
                    if os.path.exists(
                        os.path.join(os.path.expanduser("~/.fetchx_idm"), "fetchx.db")
                    )
                    else 0
                ),
            },
        }

        if export:
            interface.print_info(f"📤 Exporting statistics to {export}...")
            with open(export, "w") as f:
                json.dump(stats_data, f, indent=2)
            interface.print_success(f"✅ Statistics exported to {export}")
            return

        # Display statistics
        console.print("\n📊 [bold blue]FETCHX IDM Statistics[/bold blue]")

        # Queue Statistics
        queue_table = Table(title="📥 Queue Statistics", border_style="blue")
        queue_table.add_column("Metric", style="cyan")
        queue_table.add_column("Count", style="magenta")

        queue_table.add_row("Total Downloads", str(queue_stats["total_downloads"]))
        queue_table.add_row("Active Downloads", str(queue_stats["active_downloads"]))
        queue_table.add_row("Queued", str(queue_stats["status_counts"]["queued"]))
        queue_table.add_row("Completed", str(queue_stats["status_counts"]["completed"]))
        queue_table.add_row("Failed", str(queue_stats["status_counts"]["failed"]))
        queue_table.add_row("Cancelled", str(queue_stats["status_counts"]["cancelled"]))

        console.print(queue_table)

        # Performance Statistics
        perf_table = Table(title="🚀 Performance Statistics", border_style="green")
        perf_table.add_column("Metric", style="cyan")
        perf_table.add_column("Value", style="magenta")

        perf_table.add_row(
            "Success Rate", f"{stats_data['performance']['success_rate']:.1f}%"
        )
        perf_table.add_row(
            "Average Download Time",
            f"{stats_data['performance']['average_download_time']:.1f}s",
        )
        perf_table.add_row(
            "Total Completed", str(stats_data["performance"]["completed_downloads"])
        )

        console.print(perf_table)

        if detailed:
            # Session Statistics
            session_table = Table(title="🗂️ Session Statistics", border_style="yellow")
            session_table.add_column("Metric", style="cyan")
            session_table.add_column("Count", style="magenta")

            session_table.add_row(
                "Total Sessions", str(session_stats["total_sessions"])
            )
            session_table.add_row(
                "Active Sessions", str(session_stats["active_sessions"])
            )
            session_table.add_row(
                "Completed Sessions", str(session_stats["completed_sessions"])
            )
            session_table.add_row(
                "Failed Sessions", str(session_stats["failed_sessions"])
            )
            session_table.add_row(
                "Paused Sessions", str(session_stats["paused_sessions"])
            )

            console.print(session_table)

            # System Statistics
            system_table = Table(title="⚙️ System Statistics", border_style="magenta")
            system_table.add_column("Metric", style="cyan")
            system_table.add_column("Value", style="magenta")

            system_table.add_row(
                "Configuration Sections", str(stats_data["system"]["config_sections"])
            )
            system_table.add_row("Storage Path", stats_data["system"]["storage_path"])
            system_table.add_row(
                "Database Size", format_size(stats_data["system"]["database_size"])
            )
            system_table.add_row("Total Log Entries", str(log_stats["total_logs"]))
            system_table.add_row("Recent Errors", str(log_stats["recent_errors"]))
            system_table.add_row("Recent Warnings", str(log_stats["recent_warnings"]))

            console.print(system_table)

            # Disk usage information
            if os.path.exists(config_manager.config.paths.download_dir):
                disk_usage = FileManager.get_available_space(
                    config_manager.config.paths.download_dir
                )
                interface.print_info(
                    f"\n💾 Available disk space: {format_size(disk_usage)}"
                )

    except Exception as e:
        logger.error(f"Error gathering statistics: {e}", "cli")
        interface.print_error(f"Error gathering statistics: {e}")
        sys.exit(1)


@click.command()
@click.option("--detailed", is_flag=True, help="Show detailed information")
def temp_status(detailed: bool):  # ✅ Now accepts the detailed parameter
    """Show status of temporary directories."""
    try:
        interface.print_info("🗂️ Checking temporary directory status...")

        temp_base = os.path.join(Path.home(), ".fetchx_idm", "temp")

        if not os.path.exists(temp_base):
            interface.print_info("📁 No FETCHX temporary directory exists")
            interface.print_info(f"   Expected location: {temp_base}")
            return

        # Show temp directory status
        interface.display_temp_directory_status()

        # Calculate total space used
        total_size = 0
        total_dirs = 0
        total_files = 0

        try:
            temp_dirs = [
                d
                for d in os.listdir(temp_base)
                if os.path.isdir(os.path.join(temp_base, d))
            ]
            total_dirs = len(temp_dirs)

            for temp_dir in temp_dirs:
                temp_path = os.path.join(temp_base, temp_dir)
                try:
                    for root, dirs, files in os.walk(temp_path):
                        total_files += len(files)
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except OSError:
                                pass
                except OSError:
                    pass

        except OSError:
            interface.print_error("Error calculating temporary directory statistics")
            return

        # Summary information
        interface.print_info("\n📊 Summary:")
        summary_table = Table(border_style="blue")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="magenta")

        summary_table.add_row("Base Directory", temp_base)
        summary_table.add_row("Active Temp Directories", str(total_dirs))
        summary_table.add_row("Total Files", str(total_files))
        summary_table.add_row("Total Size", format_size(total_size))

        # Available space
        try:
            import shutil

            free_space = shutil.disk_usage(temp_base).free
            summary_table.add_row("Available Space", format_size(free_space))
        except OSError:
            summary_table.add_row("Available Space", "Unknown")

        console.print(summary_table)

        # NEW: Detailed information when --detailed flag is used
        if detailed:
            interface.print_info("\n🔍 Detailed Directory Information:")

            if total_dirs > 0:
                detailed_table = Table(
                    title="📂 Directory Details", border_style="cyan"
                )
                detailed_table.add_column("Directory Name", style="white", width=30)
                detailed_table.add_column("Size", style="magenta", width=12)
                detailed_table.add_column("Files", style="blue", width=8)
                detailed_table.add_column("Created", style="green", width=15)
                detailed_table.add_column("Last Modified", style="yellow", width=15)
                detailed_table.add_column("Age", style="red", width=10)

                import time
                from datetime import datetime

                for temp_dir in temp_dirs[:20]:  # Show max 20 directories
                    temp_path = os.path.join(temp_base, temp_dir)
                    try:
                        # Calculate directory stats
                        dir_size = 0
                        file_count = 0

                        for root, dirs, files in os.walk(temp_path):
                            file_count += len(files)
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    dir_size += os.path.getsize(file_path)
                                except OSError:
                                    pass

                        # Get timestamps
                        created_time = os.path.getctime(temp_path)
                        modified_time = os.path.getmtime(temp_path)

                        created_str = datetime.fromtimestamp(created_time).strftime(
                            "%H:%M:%S"
                        )
                        modified_str = datetime.fromtimestamp(modified_time).strftime(
                            "%H:%M:%S"
                        )

                        # Calculate age
                        age_hours = (time.time() - created_time) / 3600
                        if age_hours < 1:
                            age_str = f"{int(age_hours * 60)}m"
                        elif age_hours < 24:
                            age_str = f"{int(age_hours)}h"
                        else:
                            age_str = f"{int(age_hours / 24)}d"

                        # Truncate directory name if too long
                        display_name = temp_dir
                        if len(display_name) > 28:
                            display_name = display_name[:25] + "..."

                        detailed_table.add_row(
                            display_name,
                            format_size(dir_size),
                            str(file_count),
                            created_str,
                            modified_str,
                            age_str,
                        )

                    except OSError:
                        detailed_table.add_row(
                            temp_dir[:28], "Error", "Error", "Error", "Error", "Error"
                        )

                console.print(detailed_table)

                # Show file breakdown for detailed mode
                interface.print_info("\n📋 File Type Breakdown:")
                file_types = {}
                total_analyzed = 0

                for temp_dir in temp_dirs:
                    temp_path = os.path.join(temp_base, temp_dir)
                    try:
                        for root, dirs, files in os.walk(temp_path):
                            for file in files:
                                total_analyzed += 1
                                ext = os.path.splitext(file)[1].lower()
                                if not ext:
                                    ext = "(no extension)"
                                file_types[ext] = file_types.get(ext, 0) + 1
                    except OSError:
                        continue

                if file_types:
                    types_table = Table(border_style="green")
                    types_table.add_column("File Type", style="cyan")
                    types_table.add_column("Count", style="magenta")
                    types_table.add_column("Percentage", style="yellow")

                    # Sort by count and show top 10
                    sorted_types = sorted(
                        file_types.items(), key=lambda x: x[1], reverse=True
                    )[:10]

                    for ext, count in sorted_types:
                        percentage = (
                            (count / total_analyzed) * 100 if total_analyzed > 0 else 0
                        )
                        types_table.add_row(ext, str(count), f"{percentage:.1f}%")

                    console.print(types_table)

        # Recommendations
        if total_size > 1024 * 1024 * 1024:  # > 1GB
            interface.print_warning(
                f"⚠️ Temporary directories are using {format_size(total_size)}. "
                "Consider running 'fetchx cleanup --temp' to free space."
            )
        elif total_dirs > 10:
            interface.print_info(
                f"ℹ️ Found {total_dirs} temporary directories. "
                "Old directories can be cleaned with 'fetchx cleanup --temp'."
            )
        else:
            interface.print_success("✅ Temporary directory usage looks healthy")

    except Exception as e:
        logger.error(f"Error checking temp status: {e}", "cli")
        interface.print_error(f"Error checking temp status: {e}")
        return 1


# Create temp command group
@fetchx.group()
def temp():
    """Manage temporary directories."""
    pass


# Add temp_status as a subcommand of temp
temp.add_command(temp_status, name="status")

# Register the cleanup command with main fetchx group
fetchx.add_command(cleanup)


@fetchx.command()
@click.argument('level', required=False, type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False))
def log_level(level):
    """View or set the persistent log level configuration."""
    from fetchx_cli.config.settings import get_config
    
    config = get_config()
    
    if level is None:
        # Show current setting
        try:
            current_level = config.get_setting("logging", "log_level")
            console.print(f"\n[green]Current saved log level:[/green] {current_level}")
            console.print(f"[dim]This level will be used when no --log-level is specified[/dim]")
        except Exception as e:
            console.print(f"[red]Error reading log level from config:[/red] {e}")
            console.print(f"[yellow]Using default: INFO[/yellow]")
        
        console.print(f"\n[yellow]To change the saved log level:[/yellow]")
        console.print(f"  fetchx log-level DEBUG    # Set to DEBUG")
        console.print(f"  fetchx log-level INFO     # Set to INFO")
        console.print(f"  fetchx log-level WARNING  # Set to WARNING")
        console.print(f"  fetchx log-level ERROR    # Set to ERROR")
        console.print(f"  fetchx log-level CRITICAL # Set to CRITICAL")
    else:
        # Set new level
        try:
            config.update_setting("logging", "log_level", level.upper())
            console.print(f"[green]✅ Log level saved to:[/green] {level.upper()}")
            console.print(f"[dim]This will be used for future fetchx commands (when --log-level is not specified)[/dim]")
            
            # Also update the current session
            logger.set_log_level(level.upper(), save_to_config=False)  # Don't save again
            console.print(f"[green]✅ Current session log level updated to:[/green] {level.upper()}")
            
        except Exception as e:
            console.print(f"[red]Error saving log level:[/red] {e}")
            return
        

# Entry point for setuptools
def main():
    """Main entry point."""
    try:
        fetchx()
    except Exception as e:
        console.print(f"[red]💥 Fatal error: {e}[/red]")
        logger.critical(f"Fatal error: {e}", "cli")
        sys.exit(1)
