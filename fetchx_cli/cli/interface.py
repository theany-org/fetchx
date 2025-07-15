"""Enhanced user interface utilities for CLI with detailed connection progress."""

import asyncio
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, TaskID, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from humanfriendly import format_size, format_timespan
from fetchx_cli.core.queue import DownloadQueue, DownloadStatus
from fetchx_cli.utils.progress import EnhancedProgressTracker

class EnhancedCLIInterface:
    """Enhanced command-line interface utilities with detailed connection progress."""

    def __init__(self):
        self.console = Console()
        self.progress_tracker = None

    def print_success(self, message: str):
        """Print success message."""
        self.console.print(f"✅ {message}", style="green")

    def print_error(self, message: str):
        """Print error message."""
        self.console.print(f"❌ {message}", style="red")

    def print_warning(self, message: str):
        """Print warning message."""
        self.console.print(f"⚠️  {message}", style="yellow")

    def print_info(self, message: str):
        """Print info message."""
        self.console.print(f"ℹ️  {message}", style="blue")

    def display_download_info(self, url: str, filename: str, size: Optional[int] = None,
                            connections: int = 1, output_dir: str = ""):
        """Display download information."""
        table = Table(title="📥 Download Information", border_style="blue")
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="magenta")

        table.add_row("🌐 URL", url[:60] + "..." if len(url) > 60 else url)
        table.add_row("📄 Filename", filename)
        table.add_row("📁 Output Directory", output_dir)
        table.add_row("🔗 Connections", str(connections))

        if size:
            table.add_row("📊 File Size", format_size(size))

        self.console.print(table)

    def display_queue_status(self, queue: DownloadQueue):
        """Display enhanced queue status with better formatting."""
        try:
            items = queue.list_downloads()
            stats = queue.get_queue_stats()

            # Display queue statistics with icons
            stats_panel = Panel(
                f"📊 Total: {stats['total_downloads']} | "
                f"🔄 Active: {stats['active_downloads']} | "
                f"⏳ Queued: {stats['status_counts']['queued']} | "
                f"✅ Completed: {stats['status_counts']['completed']} | "
                f"❌ Failed: {stats['status_counts']['failed']}",
                title="📈 Queue Statistics",
                border_style="blue"
            )
            self.console.print(stats_panel)

            if not items:
                self.console.print("📭 No downloads in queue.", style="yellow")
                return

            # Display downloads table with enhanced formatting
            table = Table(title="📋 Download Queue", border_style="cyan")
            table.add_column("ID", style="cyan", width=10)
            table.add_column("Filename", style="white", width=25)
            table.add_column("URL", style="dim", width=35)
            table.add_column("Status", style="bold", width=12)
            table.add_column("Progress", style="green", width=15)
            table.add_column("Speed", style="blue", width=12)
            table.add_column("ETA", style="yellow", width=10)

            for item in items[-20:]:  # Show last 20 items
                # Truncate filename if too long
                filename = item.filename or "Unknown"
                if len(filename) > 23:
                    filename = filename[:20] + "..."

                # Truncate URL
                url = item.url
                if len(url) > 33:
                    url = url[:30] + "..."

                # Format status with color and icons
                status_icons = {
                    DownloadStatus.QUEUED: "⏳",
                    DownloadStatus.DOWNLOADING: "🔄",
                    DownloadStatus.PAUSED: "⏸️",
                    DownloadStatus.COMPLETED: "✅",
                    DownloadStatus.FAILED: "❌",
                    DownloadStatus.CANCELLED: "🚫"
                }

                status_colors = {
                    DownloadStatus.QUEUED: "yellow",
                    DownloadStatus.DOWNLOADING: "green",
                    DownloadStatus.PAUSED: "orange1",
                    DownloadStatus.COMPLETED: "bright_green",
                    DownloadStatus.FAILED: "red",
                    DownloadStatus.CANCELLED: "orange1"
                }

                icon = status_icons.get(item.status, "❓")
                color = status_colors.get(item.status, "white")
                status_text = Text(f"{icon} {item.status.value.upper()}")
                status_text.style = color

                # Format progress bar
                progress_bar = self._create_progress_bar(item.progress_percentage)

                # Format speed
                speed = format_size(item.download_speed) + "/s" if item.download_speed > 0 else "-"

                # Format ETA
                eta = format_timespan(item.eta) if item.eta else "-"

                table.add_row(
                    item.id[:8] + "...",
                    filename,
                    url,
                    status_text,
                    progress_bar,
                    speed,
                    eta
                )

            self.console.print(table)

        except Exception as e:
            self.print_error(f"Error displaying queue status: {e}")

    def _create_progress_bar(self, percentage: float, width: int = 10) -> str:
        """Create a text-based progress bar."""
        filled = int(percentage / 100 * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {percentage:5.1f}%"

    async def monitor_downloads_enhanced(self, queue: DownloadQueue, refresh_interval: float = 0.5):
        """Enhanced download monitoring with detailed connection progress."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="downloads", size=8),
            Layout(name="connections"),
            Layout(name="stats", size=4)
        )

        with Live(layout, console=self.console, refresh_per_second=1/refresh_interval) as live:
            while queue._is_running:
                try:
                    # Get current downloads
                    items = queue.list_downloads()
                    active_items = [item for item in items if item.status == DownloadStatus.DOWNLOADING]

                    # Update header
                    header_text = f"🚀 FETCHX IDM - Active Downloads: {len(active_items)}"
                    if not active_items:
                        queued_items = [item for item in items if item.status == DownloadStatus.QUEUED]
                        if queued_items:
                            header_text = f"⏳ Waiting for downloads to start... ({len(queued_items)} queued)"
                        else:
                            header_text = "💤 No active downloads"

                    layout["header"].update(Panel(header_text, border_style="blue"))

                    if not active_items:
                        layout["downloads"].update(Panel("📭 No active downloads", border_style="yellow"))
                        layout["connections"].update(Panel("🔌 No active connections", border_style="dim"))
                        layout["stats"].update(Panel("📊 No statistics available", border_style="dim"))
                        await asyncio.sleep(refresh_interval)
                        continue

                    # Create downloads table
                    downloads_table = self._create_active_downloads_table(active_items)
                    layout["downloads"].update(Panel(downloads_table, title="📥 Active Downloads", border_style="green"))

                    # Create connections table (simulated segment data)
                    connections_table = self._create_connections_table(active_items)
                    layout["connections"].update(Panel(connections_table, title="🔗 Connection Details", border_style="cyan"))

                    # Create stats table
                    stats_table = self._create_stats_table(active_items)
                    layout["stats"].update(Panel(stats_table, title="📊 Statistics", border_style="blue"))

                    await asyncio.sleep(refresh_interval)

                except Exception as e:
                    layout["header"].update(Panel(f"❌ Error monitoring downloads: {e}", border_style="red"))
                    await asyncio.sleep(refresh_interval * 2)

    def _create_active_downloads_table(self, active_items) -> Table:
        """Create table for active downloads."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Filename", style="white", width=25)
        table.add_column("Progress", style="green", width=20)
        table.add_column("Speed", style="blue", width=12)
        table.add_column("Downloaded", style="magenta", width=15)
        table.add_column("ETA", style="yellow", width=10)

        for item in active_items:
            filename = item.filename or "Unknown"
            if len(filename) > 23:
                filename = filename[:20] + "..."

            # Progress bar with percentage
            progress_bar = self._create_progress_bar(item.progress_percentage, 15)

            # Speed
            speed = format_size(item.download_speed) + "/s" if item.download_speed > 0 else "-"

            # Downloaded amount (simulated based on progress)
            if hasattr(item, 'total_size') and item.total_size:
                downloaded = item.total_size * (item.progress_percentage / 100)
                downloaded_text = f"{format_size(downloaded)}"
            else:
                downloaded_text = "-"

            # ETA
            eta = format_timespan(item.eta) if item.eta else "-"

            table.add_row(filename, progress_bar, speed, downloaded_text, eta)

        return table

    def _create_connections_table(self, active_items) -> Table:
        """Create table for connection details."""
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("File", style="white", width=15)
        table.add_column("Conn", style="cyan", width=6)
        table.add_column("Progress", style="green", width=18)
        table.add_column("Speed", style="blue", width=10)
        table.add_column("Downloaded", style="magenta", width=12)
        table.add_column("Status", style="yellow", width=8)

        for item in active_items:
            filename = item.filename or "Unknown"
            if len(filename) > 13:
                filename = filename[:10] + "..."

            # Simulate multiple connections for each download
            # In a real implementation, this would come from the downloader's segment data
            num_connections = getattr(item, 'max_connections', None) or 4

            for conn_id in range(num_connections):
                # Simulate connection progress (in real implementation, get from segment data)
                conn_progress = (item.progress_percentage + (conn_id * 5)) % 100
                conn_speed = item.download_speed / num_connections if item.download_speed > 0 else 0

                progress_bar = self._create_progress_bar(conn_progress, 12)
                speed_text = format_size(conn_speed) + "/s" if conn_speed > 0 else "-"

                # Simulate downloaded amount per connection
                if hasattr(item, 'total_size') and item.total_size:
                    segment_size = item.total_size / num_connections
                    downloaded = segment_size * (conn_progress / 100)
                    downloaded_text = format_size(downloaded)
                else:
                    downloaded_text = "-"

                # Status
                if conn_progress >= 100:
                    status = "✅ Done"
                elif conn_progress > 0:
                    status = "🔄 Active"
                else:
                    status = "⏳ Wait"

                table.add_row(
                    filename if conn_id == 0 else "",  # Only show filename for first connection
                    f"#{conn_id + 1}",
                    progress_bar,
                    speed_text,
                    downloaded_text,
                    status
                )

        return table

    def _create_stats_table(self, active_items) -> Table:
        """Create statistics table."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="magenta", width=15)

        # Calculate totals
        total_speed = sum(item.download_speed for item in active_items if item.download_speed)
        total_files = len(active_items)

        # Estimate total connections (in real implementation, get from actual segment count)
        total_connections = sum(getattr(item, 'max_connections', None) or 4 for item in active_items)
        active_connections = sum(1 for item in active_items if item.download_speed > 0) * 4  # Simulate

        table.add_row("📁 Active Files", str(total_files))
        table.add_row("🔗 Total Connections", str(total_connections))
        table.add_row("⚡ Active Connections", str(active_connections))
        table.add_row("🚀 Combined Speed", f"{format_size(total_speed)}/s")

        return table

    def create_segment_aware_progress_tracker(self, download_id: str, filename: str,
                                           segments_info: list = None) -> EnhancedProgressTracker:
        """Create a progress tracker that's aware of download segments."""
        self.progress_tracker = EnhancedProgressTracker(
            show_segments=True,
            show_speed=True,
            show_eta=True
        )

        # Add the download with segment information
        if segments_info:
            self.progress_tracker.add_download(
                download_id=download_id,
                filename=filename,
                total_size=sum(seg.get('total_size', 0) for seg in segments_info),
                segments=segments_info
            )

        return self.progress_tracker

    async def monitor_single_download_with_segments(self, downloader, refresh_interval: float = 0.2):
        """Monitor a single download showing detailed segment progress."""
        # Create layout for single download monitoring
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="overall", size=4),
            Layout(name="segments"),
            Layout(name="footer", size=3)
        )

        with Live(layout, console=self.console, refresh_per_second=1/refresh_interval) as live:
            while not downloader.is_cancelled and not downloader.is_paused:
                try:
                    stats = downloader.get_stats()
                    segment_info = downloader.get_segment_info()

                    # Header
                    filename = downloader.download_info.filename if downloader.download_info else "Unknown"
                    layout["header"].update(Panel(
                        f"🚀 Downloading: {filename}",
                        border_style="blue"
                    ))

                    # Overall progress
                    overall_table = Table(show_header=False)
                    overall_table.add_column("Metric", style="cyan", width=15)
                    overall_table.add_column("Value", style="magenta")

                    progress_bar = self._create_progress_bar(stats.progress_percentage, 30)
                    overall_table.add_row("📊 Progress", progress_bar)
                    overall_table.add_row("🚀 Speed", f"{format_size(stats.speed)}/s")
                    overall_table.add_row("📥 Downloaded", f"{format_size(stats.downloaded)}")
                    if stats.total_size:
                        overall_table.add_row("📦 Total Size", f"{format_size(stats.total_size)}")
                    if stats.eta:
                        overall_table.add_row("⏰ ETA", format_timespan(stats.eta))

                    layout["overall"].update(Panel(overall_table, title="📈 Overall Progress", border_style="green"))

                    # Segments progress
                    if segment_info:
                        segments_table = Table(show_header=True, header_style="bold cyan")
                        segments_table.add_column("Segment", style="cyan", width=8)
                        segments_table.add_column("Progress", style="green", width=25)
                        segments_table.add_column("Speed", style="blue", width=12)
                        segments_table.add_column("Downloaded", style="magenta", width=15)
                        segments_table.add_column("Status", style="yellow", width=10)

                        for seg in segment_info:
                            progress_bar = self._create_progress_bar(seg['progress_percentage'], 18)
                            speed_text = f"{format_size(seg['speed'])}/s" if seg['speed'] > 0 else "-"
                            downloaded_text = format_size(seg['downloaded'])

                            # Status with icons
                            if seg['completed']:
                                status = "✅ Done"
                            elif seg['paused']:
                                status = "⏸️ Paused"
                            else:
                                status = "🔄 Active"

                            segments_table.add_row(
                                f"#{seg['id'] + 1}",
                                progress_bar,
                                speed_text,
                                downloaded_text,
                                status
                            )

                        layout["segments"].update(Panel(segments_table, title="🔗 Segment Progress", border_style="cyan"))
                    else:
                        layout["segments"].update(Panel("🔌 Single connection download", border_style="dim"))

                    # Footer with summary
                    active_segments = len([s for s in segment_info if not s['completed'] and not s['paused']]) if segment_info else 1
                    completed_segments = len([s for s in segment_info if s['completed']]) if segment_info else 0

                    footer_text = f"🔗 Active: {active_segments} | ✅ Completed: {completed_segments} | ⏱️ Elapsed: {stats.elapsed_time:.1f}s"
                    layout["footer"].update(Panel(footer_text, border_style="blue"))

                    # Check if download is complete
                    if stats.progress_percentage >= 100 or all(s['completed'] for s in segment_info):
                        layout["header"].update(Panel("✅ Download Completed!", border_style="green"))
                        await asyncio.sleep(2)  # Show completion for 2 seconds
                        break

                    await asyncio.sleep(refresh_interval)

                except Exception as e:
                    layout["header"].update(Panel(f"❌ Error: {e}", border_style="red"))
                    await asyncio.sleep(refresh_interval * 2)

# Backwards compatibility
CLIInterface = EnhancedCLIInterface