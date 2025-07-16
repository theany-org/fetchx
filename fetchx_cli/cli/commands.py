"""Updated CLI command definitions with enhanced progress display."""

import asyncio
import sys
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from fetchx_cli.core.downloader import EnhancedDownloader
from fetchx_cli.core.queue import DownloadQueue
from fetchx_cli.cli.interface import EnhancedCLIInterface
from fetchx_cli.cli.validators import Validators
from fetchx_cli.config.settings import get_config
from fetchx_cli.utils.exceptions import FetchXIdmException
from fetchx_cli.utils.logging import get_logger, setup_logging
from humanfriendly import format_size
import time

console = Console()
interface = EnhancedCLIInterface()
logger = get_logger()


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version information")
@click.option(
    "--log-level",
    default="INFO",
    help="Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.pass_context
def fetchx(ctx, version, log_level):
    """FETCHX Internet Download Manager - A powerful command-line download manager."""
    # Initialize logging
    setup_logging(log_level)
    logger.info("FETCHX IDM started", "cli")

    if version:
        click.echo("FETCHX IDM v0.1.0")
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


# Add the remaining commands with similar enhancements...
# (config, logs, cleanup, stats commands remain the same as in original)


# Entry point for setuptools
def main():
    """Main entry point."""
    try:
        fetchx()
    except Exception as e:
        console.print(f"[red]💥 Fatal error: {e}[/red]")
        logger.critical(f"Fatal error: {e}", "cli")
        sys.exit(1)
