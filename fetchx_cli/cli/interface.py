"""Enhanced user interface utilities for CLI with detailed connection progress."""

import asyncio
import os
from pathlib import Path
import shutil
from datetime import datetime
from typing import Dict, Optional

from humanfriendly import format_size, format_timespan
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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

    def display_download_info(
        self,
        url: str,
        filename: str,
        size: Optional[int] = None,
        connections: int = 1,
        output_dir: str = "",
        temp_dir: str = "",  # NEW: Show temp directory
    ):
        """Display download information with temp directory."""
        table = Table(title="📥 Download Information", border_style="blue")
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="magenta")

        table.add_row("🌐 URL", url[:60] + "..." if len(url) > 60 else url)
        table.add_row("📄 Filename", filename)
        table.add_row("📁 Output Directory", output_dir)
        table.add_row(
            "🗂️ Temp Directory", temp_dir if temp_dir else "Auto-generated"
        )  # NEW
        table.add_row("🔗 Connections", str(connections))

        if size:
            table.add_row("📊 File Size", format_size(size))

        self.console.print(table)

    def display_temp_directory_status(self):
        """Display status of temporary directories."""
        temp_base = os.path.join(Path.home(), ".fetchx_idm", "temp")

        if not os.path.exists(temp_base):
            self.print_info("🗂️ No temporary directories found")
            return

        try:
            temp_dirs = [
                d
                for d in os.listdir(temp_base)
                if os.path.isdir(os.path.join(temp_base, d))
            ]

            if not temp_dirs:
                self.print_info("🗂️ No active temporary directories")
                return

            table = Table(title="🗂️ Temporary Directories", border_style="yellow")
            table.add_column("Directory", style="cyan", width=40)
            table.add_column("Size", style="magenta", width=15)
            table.add_column("Files", style="blue", width=10)
            table.add_column("Modified", style="green", width=20)

            total_size = 0
            for temp_dir in temp_dirs:
                temp_path = os.path.join(temp_base, temp_dir)
                try:
                    # Calculate directory size and file count
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

                    total_size += dir_size

                    # Get modification time
                    mod_time = os.path.getmtime(temp_path)
                    mod_time_str = format_timespan(os.path.getctime(temp_path))

                    table.add_row(
                        temp_dir[:37] + "..." if len(temp_dir) > 37 else temp_dir,
                        format_size(dir_size),
                        str(file_count),
                        mod_time_str + " ago",
                    )

                except OSError:
                    table.add_row(temp_dir, "Error", "Error", "Error")

            self.console.print(table)
            self.print_info(
                f"📊 Total temporary storage used: {format_size(total_size)}"
            )

        except OSError as e:
            self.print_error(f"Error reading temporary directories: {e}")

    def cleanup_temp_directories(
        self, max_age_hours: int = 24, dry_run: bool = False
    ) -> Dict[str, int]:
        """Clean up old temporary directories."""
        temp_base = os.path.join(Path.home(), ".fetchx_idm", "temp")

        if not os.path.exists(temp_base):
            return {"cleaned": 0, "size_freed": 0, "errors": 0}

        import time

        cutoff_time = time.time() - (max_age_hours * 3600)

        cleaned_count = 0
        size_freed = 0
        error_count = 0

        try:
            temp_dirs = [
                d
                for d in os.listdir(temp_base)
                if os.path.isdir(os.path.join(temp_base, d))
            ]

            for temp_dir in temp_dirs:
                temp_path = os.path.join(temp_base, temp_dir)
                try:
                    # Check if directory is old enough
                    if os.path.getmtime(temp_path) < cutoff_time:
                        # Calculate size before deletion
                        dir_size = 0
                        for root, dirs, files in os.walk(temp_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    dir_size += os.path.getsize(file_path)
                                except OSError:
                                    pass

                        if not dry_run:
                            shutil.rmtree(temp_path)
                            self.print_info(f"🗑️ Cleaned temp directory: {temp_dir}")
                        else:
                            self.print_info(
                                f"🔍 Would clean temp directory: {temp_dir} ({format_size(dir_size)})"
                            )

                        cleaned_count += 1
                        size_freed += dir_size

                except OSError as e:
                    self.print_warning(f"⚠️ Error cleaning {temp_dir}: {e}")
                    error_count += 1

        except OSError as e:
            self.print_error(f"Error accessing temporary directories: {e}")
            error_count += 1

        return {
            "cleaned": cleaned_count,
            "size_freed": size_freed,
            "errors": error_count,
        }

    def display_queue_status(self, queue: DownloadQueue):
        """Display queue status with enhanced pause/resume support."""
        items = queue.list_downloads()
        stats = queue.get_queue_stats()

        if not items:
            self.print_info("📭 Download queue is empty")
            return

        # Enhanced status with pause support
        self.console.print("\n🚀 [bold blue]FETCHX IDM - Download Queue[/bold blue]")

        # Summary table
        summary_table = Table(title="📊 Queue Summary", border_style="blue")
        summary_table.add_column("Status", style="cyan")
        summary_table.add_column("Count", style="magenta")

        summary_table.add_row("📊 Total Downloads", str(stats["total_downloads"]))
        summary_table.add_row("🔄 Active Downloads", str(stats["active_downloads"]))
        summary_table.add_row("⏳ Queued", str(stats["status_counts"]["queued"]))
        summary_table.add_row("⏸️ Paused", str(stats["status_counts"]["paused"]))
        summary_table.add_row("✅ Completed", str(stats["status_counts"]["completed"]))
        summary_table.add_row("❌ Failed", str(stats["status_counts"]["failed"]))
        summary_table.add_row("🚫 Cancelled", str(stats["status_counts"]["cancelled"]))

        self.console.print(summary_table)

        # Downloads table with pause/resume status
        downloads_table = Table(title="📋 Downloads", border_style="cyan")
        downloads_table.add_column("ID", style="cyan", width=10)
        downloads_table.add_column("File", style="white", width=25)
        downloads_table.add_column("Status", style="bold", width=12)
        downloads_table.add_column("Progress", style="green", width=15)
        downloads_table.add_column("Speed", style="blue", width=10)
        downloads_table.add_column("ETA", style="magenta", width=8)

        # Status icons with pause support
        status_icons = {
            "queued": "⏳",
            "downloading": "🔄",
            "paused": "⏸️",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫",
        }

        for item in items:
            filename = (
                (item.filename or "Unknown")[:22] + "..."
                if len(item.filename or "Unknown") > 22
                else (item.filename or "Unknown")
            )

            icon = status_icons.get(item.status.value, "❓")
            status_text = f"{icon} {item.status.value.upper()}"

            # Enhanced progress bar
            progress_bar = self._create_progress_bar(item.progress_percentage, 12)

            speed = (
                format_size(item.download_speed) + "/s"
                if item.download_speed > 0
                else "-"
            )
            eta = format_timespan(item.eta) if item.eta else "-"

            downloads_table.add_row(
                item.id[:8],
                filename,
                status_text,
                progress_bar,
                speed,
                eta,
            )

        self.console.print(downloads_table)

        # Show helpful commands for pause/resume
        self.console.print("\n💡 [dim]Available commands:[/dim]")
        self.console.print("   [yellow]fetchx pause <id>[/yellow]   - Pause a download")
        self.console.print("   [yellow]fetchx resume <id>[/yellow]  - Resume a paused download")
        self.console.print("   [yellow]fetchx cancel <id>[/yellow]  - Cancel a download")
        self.console.print("   [yellow]fetchx resume-session --list[/yellow] - List resumable sessions")

    def _create_progress_bar(self, percentage: float, width: int = 10) -> str:
        """Create a text-based progress bar."""
        filled = int(percentage / 100 * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {percentage:5.1f}%"

    async def monitor_downloads_enhanced(
        self, queue: DownloadQueue, refresh_interval: float = 0.5
    ):
        """Enhanced download monitoring with temp directory tracking."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="downloads", size=8),
            Layout(name="connections"),
            Layout(name="storage", size=4),  # NEW: Storage info
            Layout(name="stats", size=4),
        )

        with Live(
            layout, console=self.console, refresh_per_second=1 / refresh_interval
        ) as live:
            while queue._is_running:
                try:
                    # Get current downloads
                    items = queue.list_downloads()
                    active_items = [
                        item
                        for item in items
                        if item.status == DownloadStatus.DOWNLOADING
                    ]

                    # Update header
                    header_text = (
                        f"🚀 FETCHX IDM - Active Downloads: {len(active_items)}"
                    )
                    if not active_items:
                        queued_items = [
                            item
                            for item in items
                            if item.status == DownloadStatus.QUEUED
                        ]
                        if queued_items:
                            header_text = f"⏳ Waiting for downloads to start... ({len(queued_items)} queued)"
                        else:
                            header_text = "💤 No active downloads"

                    layout["header"].update(Panel(header_text, border_style="blue"))

                    if not active_items:
                        layout["downloads"].update(
                            Panel("📭 No active downloads", border_style="yellow")
                        )
                        layout["connections"].update(
                            Panel("🔌 No active connections", border_style="dim")
                        )
                        layout["storage"].update(
                            Panel("🗂️ No active temporary storage", border_style="dim")
                        )
                        layout["stats"].update(
                            Panel("📊 No statistics available", border_style="dim")
                        )
                        await asyncio.sleep(refresh_interval)
                        continue

                    # Create downloads table
                    downloads_table = self._create_active_downloads_table(active_items)
                    layout["downloads"].update(
                        Panel(
                            downloads_table,
                            title="📥 Active Downloads",
                            border_style="green",
                        )
                    )

                    # Create connections table (simulated segment data)
                    connections_table = self._create_connections_table(active_items)
                    layout["connections"].update(
                        Panel(
                            connections_table,
                            title="🔗 Connection Details",
                            border_style="cyan",
                        )
                    )

                    # NEW: Create storage info table
                    storage_table = self._create_storage_table()
                    layout["storage"].update(
                        Panel(
                            storage_table,
                            title="🗂️ Storage Info",
                            border_style="magenta",
                        )
                    )

                    # Create stats table
                    stats_table = self._create_stats_table(active_items)
                    layout["stats"].update(
                        Panel(stats_table, title="📊 Statistics", border_style="blue")
                    )

                    await asyncio.sleep(refresh_interval)

                except Exception as e:
                    layout["header"].update(
                        Panel(f"❌ Error monitoring downloads: {e}", border_style="red")
                    )
                    await asyncio.sleep(refresh_interval * 2)

    async def monitor_downloads(
            self, queue: DownloadQueue, refresh_interval: float = 1.0
    ):
        """Basic download monitoring with simple display."""
        try:
            self.print_info("🚀 Starting download queue monitoring...")
            self.print_info("Press Ctrl+C to stop monitoring")

            while queue._is_running:
                try:
                    # Clear screen for clean display
                    import os
                    os.system('clear' if os.name == 'posix' else 'cls')

                    # Get current downloads
                    items = queue.list_downloads()
                    active_items = [
                        item
                        for item in items
                        if item.status == DownloadStatus.DOWNLOADING
                    ]

                    # Header
                    self.console.print("\n🚀 [bold blue]FETCHX IDM - Download Monitor[/bold blue]")
                    self.console.print(f"⏰ Last updated: {datetime.now().strftime('%H:%M:%S')}")

                    if not active_items:
                        queued_items = [
                            item
                            for item in items
                            if item.status == DownloadStatus.QUEUED
                        ]

                        if queued_items:
                            self.console.print(f"\n⏳ Waiting for downloads to start... ({len(queued_items)} queued)")
                        else:
                            self.console.print("\n💤 No active downloads")

                        # Show queue summary
                        stats = queue.get_queue_stats()
                        summary_text = (
                            f"📊 Queue Summary: {stats['total_downloads']} total, "
                            f"{stats['status_counts']['completed']} completed, "
                            f"{stats['status_counts']['failed']} failed"
                        )
                        self.console.print(summary_text)

                        await asyncio.sleep(refresh_interval)
                        continue

                    # Active downloads table
                    table = Table(title="📥 Active Downloads", border_style="green")
                    table.add_column("ID", style="cyan", width=10)
                    table.add_column("Filename", style="white", width=25)
                    table.add_column("Progress", style="green", width=20)
                    table.add_column("Speed", style="blue", width=12)
                    table.add_column("ETA", style="yellow", width=10)
                    table.add_column("Connections", style="magenta", width=11)

                    for item in active_items:
                        # Truncate filename if too long
                        filename = item.filename or "Unknown"
                        if len(filename) > 23:
                            filename = filename[:20] + "..."

                        # Progress bar with percentage
                        progress_bar = self._create_progress_bar(item.progress_percentage, 15)

                        # Speed
                        speed = (
                            format_size(item.download_speed) + "/s"
                            if item.download_speed > 0
                            else "-"
                        )

                        # ETA
                        eta = format_timespan(item.eta) if item.eta else "-"

                        # Connections
                        connections = item.max_connections or 1
                        conn_text = f"🔗 {connections}"

                        table.add_row(
                            item.id[:8] + "...",
                            filename,
                            progress_bar,
                            speed,
                            eta,
                            conn_text,
                        )

                    self.console.print(table)

                    # Summary statistics
                    total_speed = sum(
                        item.download_speed for item in active_items if item.download_speed
                    )

                    summary_table = Table(border_style="blue")
                    summary_table.add_column("Metric", style="cyan")
                    summary_table.add_column("Value", style="magenta")

                    summary_table.add_row("📁 Active Downloads", str(len(active_items)))
                    summary_table.add_row("🚀 Combined Speed", f"{format_size(total_speed)}/s")

                    # Calculate total connections
                    total_connections = sum(
                        getattr(item, "max_connections", None) or 1 for item in active_items
                    )
                    summary_table.add_row("🔗 Total Connections", str(total_connections))

                    self.console.print(summary_table)

                    # Instructions
                    self.console.print("\n💡 Press Ctrl+C to stop monitoring")

                    await asyncio.sleep(refresh_interval)

                except KeyboardInterrupt:
                    self.print_info("🛑 Monitoring stopped by user")
                    break
                except Exception as e:
                    self.print_error(f"❌ Error during monitoring: {e}")
                    await asyncio.sleep(refresh_interval * 2)

        except Exception as e:
            self.print_error(f"❌ Failed to start monitoring: {e}")
            raise

    def _create_storage_table(self) -> Table:
        """Create table for storage information."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Storage Type", style="cyan", width=15)
        table.add_column("Location", style="white", width=30)
        table.add_column("Usage", style="yellow", width=15)

        # Temp directory info
        temp_base = os.path.join(Path.home(), ".fetchx_idm", "temp")
        temp_usage = 0

        if os.path.exists(temp_base):
            try:
                for root, dirs, files in os.walk(temp_base):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            temp_usage += os.path.getsize(file_path)
                        except OSError:
                            pass
            except OSError:
                pass

        table.add_row(
            "🗂️ Temporary",
            temp_base[:28] + "..." if len(temp_base) > 28 else temp_base,
            format_size(temp_usage),
        )

        # Download directory info
        from fetchx_cli.config.settings import get_config

        config = get_config()
        download_dir = config.config.paths.download_dir

        try:
            download_usage = 0
            if os.path.exists(download_dir):
                for root, dirs, files in os.walk(download_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            download_usage += os.path.getsize(file_path)
                        except OSError:
                            pass

            table.add_row(
                "📁 Downloads",
                download_dir[:28] + "..." if len(download_dir) > 28 else download_dir,
                format_size(download_usage),
            )
        except OSError:
            table.add_row("📁 Downloads", download_dir, "Error")

        return table

    def _create_active_downloads_table(self, active_items) -> Table:
        """Create table for active downloads."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Filename", style="white", width=25)
        table.add_column("Progress", style="green", width=20)
        table.add_column("Speed", style="blue", width=12)
        table.add_column("Downloaded", style="magenta", width=15)
        table.add_column("ETA", style="yellow", width=10)
        table.add_column("Storage", style="cyan", width=8)  # NEW

        for item in active_items:
            filename = item.filename or "Unknown"
            if len(filename) > 23:
                filename = filename[:20] + "..."

            # Progress bar with percentage
            progress_bar = self._create_progress_bar(item.progress_percentage, 15)

            # Speed
            speed = (
                format_size(item.download_speed) + "/s"
                if item.download_speed > 0
                else "-"
            )

            # Downloaded amount (simulated based on progress)
            if hasattr(item, "total_size") and item.total_size:
                downloaded = item.total_size * (item.progress_percentage / 100)
                downloaded_text = f"{format_size(downloaded)}"
            else:
                downloaded_text = "-"

            # ETA
            eta = format_timespan(item.eta) if item.eta else "-"

            # Storage type
            storage = "🗂️ Temp"

            table.add_row(filename, progress_bar, speed, downloaded_text, eta, storage)

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
            num_connections = getattr(item, "max_connections", None) or 4

            for conn_id in range(num_connections):
                # Simulate connection progress
                conn_progress = (item.progress_percentage + (conn_id * 5)) % 100
                conn_speed = (
                    item.download_speed / num_connections
                    if item.download_speed > 0
                    else 0
                )

                progress_bar = self._create_progress_bar(conn_progress, 12)
                speed_text = format_size(conn_speed) + "/s" if conn_speed > 0 else "-"

                # Simulate downloaded amount per connection
                if hasattr(item, "total_size") and item.total_size:
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
                    filename if conn_id == 0 else "",
                    f"#{conn_id + 1}",
                    progress_bar,
                    speed_text,
                    downloaded_text,
                    status,
                )

        return table

    def _create_stats_table(self, active_items) -> Table:
        """Create statistics table."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="magenta", width=15)

        # Calculate totals
        total_speed = sum(
            item.download_speed for item in active_items if item.download_speed
        )
        total_files = len(active_items)

        # Estimate total connections
        total_connections = sum(
            getattr(item, "max_connections", None) or 4 for item in active_items
        )
        active_connections = (
            sum(1 for item in active_items if item.download_speed > 0) * 4
        )

        table.add_row("📁 Active Files", str(total_files))
        table.add_row("🔗 Total Connections", str(total_connections))
        table.add_row("⚡ Active Connections", str(active_connections))
        table.add_row("🚀 Combined Speed", f"{format_size(total_speed)}/s")

        return table

    def create_segment_aware_progress_tracker(
        self, download_id: str, filename: str, segments_info: list = None
    ) -> EnhancedProgressTracker:
        """Create a progress tracker that's aware of download segments."""
        self.progress_tracker = EnhancedProgressTracker(
            show_segments=True, show_speed=True, show_eta=True
        )

        # Add the download with segment information
        if segments_info:
            self.progress_tracker.add_download(
                download_id=download_id,
                filename=filename,
                total_size=sum(seg.get("total_size", 0) for seg in segments_info),
                segments=segments_info,
            )

        return self.progress_tracker

    async def monitor_single_download_with_segments(
        self, downloader, refresh_interval: float = 0.2
    ):
        """Monitor a single download showing detailed segment progress."""
        # Create layout for single download monitoring
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="overall", size=4),
            Layout(name="segments"),
            Layout(name="footer", size=3),
        )

        with Live(
            layout, console=self.console, refresh_per_second=1 / refresh_interval
        ) as live:
            while not downloader.is_cancelled and not downloader.is_paused:
                try:
                    stats = downloader.get_stats()
                    segment_info = downloader.get_segment_info()

                    # Header
                    filename = (
                        downloader.download_info.filename
                        if downloader.download_info
                        else "Unknown"
                    )
                    layout["header"].update(
                        Panel(f"🚀 Downloading: {filename}", border_style="blue")
                    )

                    # Overall progress
                    overall_table = Table(show_header=False)
                    overall_table.add_column("Metric", style="cyan", width=15)
                    overall_table.add_column("Value", style="magenta")

                    progress_bar = self._create_progress_bar(
                        stats.progress_percentage, 30
                    )
                    overall_table.add_row("📊 Progress", progress_bar)
                    overall_table.add_row("🚀 Speed", f"{format_size(stats.speed)}/s")
                    overall_table.add_row(
                        "📥 Downloaded", f"{format_size(stats.downloaded)}"
                    )
                    if stats.total_size:
                        overall_table.add_row(
                            "📦 Total Size", f"{format_size(stats.total_size)}"
                        )
                    if stats.eta:
                        overall_table.add_row("⏰ ETA", format_timespan(stats.eta))

                    layout["overall"].update(
                        Panel(
                            overall_table,
                            title="📈 Overall Progress",
                            border_style="green",
                        )
                    )

                    # Segments progress
                    if segment_info:
                        segments_table = Table(
                            show_header=True, header_style="bold cyan"
                        )
                        segments_table.add_column("Segment", style="cyan", width=8)
                        segments_table.add_column("Progress", style="green", width=25)
                        segments_table.add_column("Speed", style="blue", width=12)
                        segments_table.add_column(
                            "Downloaded", style="magenta", width=15
                        )
                        segments_table.add_column("Status", style="yellow", width=10)

                        for seg in segment_info:
                            progress_bar = self._create_progress_bar(
                                seg["progress_percentage"], 18
                            )
                            speed_text = (
                                f"{format_size(seg['speed'])}/s"
                                if seg["speed"] > 0
                                else "-"
                            )
                            downloaded_text = format_size(seg["downloaded"])

                            # Status with icons
                            if seg["completed"]:
                                status = "✅ Done"
                            elif seg["paused"]:
                                status = "⏸️ Paused"
                            else:
                                status = "🔄 Active"

                            segments_table.add_row(
                                f"#{seg['id'] + 1}",
                                progress_bar,
                                speed_text,
                                downloaded_text,
                                status,
                            )

                        layout["segments"].update(
                            Panel(
                                segments_table,
                                title="🔗 Segment Progress",
                                border_style="cyan",
                            )
                        )
                    else:
                        layout["segments"].update(
                            Panel("🔌 Single connection download", border_style="dim")
                        )

                    # Footer with summary
                    active_segments = (
                        len(
                            [
                                s
                                for s in segment_info
                                if not s["completed"] and not s["paused"]
                            ]
                        )
                        if segment_info
                        else 1
                    )
                    completed_segments = (
                        len([s for s in segment_info if s["completed"]])
                        if segment_info
                        else 0
                    )

                    footer_text = f"🔗 Active: {active_segments} | ✅ Completed: {completed_segments} | ⏱️ Elapsed: {stats.elapsed_time:.1f}s"
                    layout["footer"].update(Panel(footer_text, border_style="blue"))

                    # Check if download is complete
                    if stats.progress_percentage >= 100 or all(
                        s["completed"] for s in segment_info
                    ):
                        layout["header"].update(
                            Panel("✅ Download Completed!", border_style="green")
                        )
                        await asyncio.sleep(2)  # Show completion for 2 seconds
                        break

                    await asyncio.sleep(refresh_interval)

                except Exception as e:
                    layout["header"].update(Panel(f"❌ Error: {e}", border_style="red"))
                    await asyncio.sleep(refresh_interval * 2)


# Backwards compatibility
CLIInterface = EnhancedCLIInterface
