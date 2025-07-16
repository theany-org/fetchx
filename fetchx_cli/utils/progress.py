"""Enhanced progress display utilities with individual segment tracking."""

import time
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.progress import (
    Progress,
    TaskID,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from humanfriendly import format_size, format_timespan


class SegmentProgressTracker:
    """Tracks progress for individual download segments."""

    def __init__(self, segment_id: int, total_size: int, filename: str):
        self.segment_id = segment_id
        self.total_size = total_size
        self.filename = filename
        self.downloaded = 0
        self.speed = 0.0
        self.eta = None
        self.status = "downloading"  # downloading, completed, failed, paused
        self.start_time = time.time()
        self.retry_count = 0

    def update(self, downloaded: int, speed: float = 0.0, eta: Optional[float] = None):
        """Update segment progress."""
        self.downloaded = downloaded
        self.speed = speed
        self.eta = eta

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_size > 0:
            return min((self.downloaded / self.total_size) * 100, 100.0)
        return 0.0

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time."""
        return time.time() - self.start_time


class EnhancedProgressTracker:
    """Enhanced progress tracker with individual segment display."""

    def __init__(
        self, show_segments: bool = True, show_speed: bool = True, show_eta: bool = True
    ):
        self.console = Console()
        self.show_segments = show_segments
        self.show_speed = show_speed
        self.show_eta = show_eta

        self.downloads = {}
        self.segment_trackers: Dict[str, Dict[int, SegmentProgressTracker]] = {}
        self.start_time = time.time()

        # Main progress for overall download
        self.main_progress = self._create_main_progress()

        # Segment progress for individual connections
        self.segment_progress = (
            self._create_segment_progress() if show_segments else None
        )

        self.live = None

    def _create_main_progress(self) -> Progress:
        """Create main progress bar for overall download."""
        columns = [
            TextColumn("[bold blue]{task.fields[filename]}", justify="left"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
        ]

        if self.show_speed:
            columns.append(TransferSpeedColumn())
            columns.append("•")

        if self.show_eta:
            columns.append(TimeRemainingColumn())

        return Progress(*columns, console=self.console)

    def _create_segment_progress(self) -> Progress:
        """Create progress bars for individual segments."""
        return Progress(
            TextColumn(
                "[dim]Conn {task.fields[segment_id]:>2d}", justify="left", width=8
            ),
            BarColumn(bar_width=25),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TextColumn("{task.fields[speed]}", width=10),
            TextColumn("{task.fields[status]}", width=10),
            console=self.console,
        )

    def start(self):
        """Start the progress display."""
        if self.show_segments and self.segment_progress:
            # Create layout with main progress and segment details
            layout = Layout()
            layout.split_column(
                Layout(name="main", size=3), Layout(name="segments", minimum_size=5)
            )

            self.live = Live(layout, console=self.console, refresh_per_second=4)
        else:
            self.live = Live(
                self.main_progress, console=self.console, refresh_per_second=4
            )

        self.live.start()

    def stop(self):
        """Stop the progress display."""
        if self.live:
            self.live.stop()

    def add_download(
        self,
        download_id: str,
        filename: str,
        total_size: Optional[int] = None,
        segments: Optional[List[Dict]] = None,
    ) -> TaskID:
        """Add a new download to track."""
        # Add main download task
        task_id = self.main_progress.add_task(
            description="", filename=filename, total=total_size, start=True
        )

        self.downloads[download_id] = {
            "task_id": task_id,
            "filename": filename,
            "total_size": total_size,
            "downloaded": 0,
            "start_time": time.time(),
            "segments": segments or [],
        }

        # Add segment trackers if segments are provided
        if segments and self.show_segments and self.segment_progress:
            self.segment_trackers[download_id] = {}
            for segment_info in segments:
                segment_id = segment_info["id"]
                segment_size = segment_info.get("total_size", 0)

                # Create segment tracker
                segment_tracker = SegmentProgressTracker(
                    segment_id=segment_id,
                    total_size=segment_size,
                    filename=f"{filename} (part {segment_id})",
                )
                self.segment_trackers[download_id][segment_id] = segment_tracker

                # Add segment task to progress
                segment_tracker.task_id = self.segment_progress.add_task(
                    description=f"Connection {segment_id}",
                    segment_id=segment_id,
                    speed="-",
                    status="starting",
                    total=segment_size,
                    start=True,
                )

        return task_id

    def update_download(
        self, download_id: str, downloaded: int, total: Optional[int] = None
    ):
        """Update overall download progress."""
        if download_id not in self.downloads:
            return

        download_info = self.downloads[download_id]
        download_info["downloaded"] = downloaded

        if total and total != download_info["total_size"]:
            download_info["total_size"] = total

        self.main_progress.update(
            download_info["task_id"],
            completed=downloaded,
            total=download_info["total_size"],
        )

    def update_segment(
        self,
        download_id: str,
        segment_id: int,
        downloaded: int,
        speed: float = 0.0,
        eta: Optional[float] = None,
        status: str = "downloading",
    ):
        """Update individual segment progress."""
        if (
            download_id not in self.segment_trackers
            or segment_id not in self.segment_trackers[download_id]
        ):
            return

        segment_tracker = self.segment_trackers[download_id][segment_id]
        segment_tracker.update(downloaded, speed, eta)
        segment_tracker.status = status

        if self.segment_progress:
            # Format speed
            speed_text = f"{format_size(speed)}/s" if speed > 0 else "-"

            # Format status with color
            status_text = status
            if status == "completed":
                status_text = "[green]done[/green]"
            elif status == "failed":
                status_text = "[red]error[/red]"
            elif status == "paused":
                status_text = "[yellow]paused[/yellow]"
            elif status == "downloading":
                status_text = "[blue]active[/blue]"

            self.segment_progress.update(
                segment_tracker.task_id,
                completed=downloaded,
                speed=speed_text,
                status=status_text,
            )

    def update_with_stats(self, download_id: str, stats):
        """Update progress using DownloadStats object."""
        # Update main progress
        self.update_download(download_id, stats.downloaded, stats.total_size)

        # Update segment progress
        if hasattr(stats, "segments") and stats.segments:
            for segment_id, segment_progress in stats.segments.items():
                self.update_segment(
                    download_id=download_id,
                    segment_id=segment_id,
                    downloaded=segment_progress.downloaded,
                    speed=segment_progress.speed,
                    eta=segment_progress.eta,
                    status=segment_progress.status,
                )

    def complete_download(self, download_id: str):
        """Mark download as completed."""
        if download_id in self.downloads:
            download_info = self.downloads[download_id]
            self.main_progress.update(
                download_info["task_id"], completed=download_info["total_size"]
            )

            # Mark all segments as completed
            if download_id in self.segment_trackers:
                for segment_tracker in self.segment_trackers[download_id].values():
                    segment_tracker.status = "completed"
                    if self.segment_progress:
                        self.segment_progress.update(
                            segment_tracker.task_id,
                            completed=segment_tracker.total_size,
                            status="[green]done[/green]",
                        )

    def remove_download(self, download_id: str):
        """Remove download from tracking."""
        if download_id in self.downloads:
            download_info = self.downloads[download_id]
            self.main_progress.remove_task(download_info["task_id"])
            del self.downloads[download_id]

            # Remove segment trackers
            if download_id in self.segment_trackers:
                for segment_tracker in self.segment_trackers[download_id].values():
                    if self.segment_progress:
                        self.segment_progress.remove_task(segment_tracker.task_id)
                del self.segment_trackers[download_id]

    def _render_layout(self):
        """Render the layout with main and segment progress."""
        if not self.live or not hasattr(self.live, "renderable"):
            return

        layout = self.live.renderable

        # Update main progress
        layout["main"].update(Panel(self.main_progress, title="Overall Progress"))

        # Update segments
        if self.segment_progress and self.segment_trackers:
            # Create segment info
            segment_table = Table(show_header=True, header_style="bold blue")
            segment_table.add_column("Connection", width=10)
            segment_table.add_column("Progress", width=30)
            segment_table.add_column("Speed", width=12)
            segment_table.add_column("Status", width=10)
            segment_table.add_column("Retries", width=8)

            for download_id, segments in self.segment_trackers.items():
                for segment_id, tracker in segments.items():
                    # Progress bar for this segment
                    progress_bar = "█" * int(tracker.progress_percentage / 5) + "░" * (
                        20 - int(tracker.progress_percentage / 5)
                    )
                    progress_text = (
                        f"[{progress_bar}] {tracker.progress_percentage:5.1f}%"
                    )

                    speed_text = (
                        f"{format_size(tracker.speed)}/s" if tracker.speed > 0 else "-"
                    )

                    status_color = {
                        "downloading": "blue",
                        "completed": "green",
                        "failed": "red",
                        "paused": "yellow",
                    }.get(tracker.status, "white")

                    segment_table.add_row(
                        f"#{tracker.segment_id}",
                        progress_text,
                        speed_text,
                        f"[{status_color}]{tracker.status}[/{status_color}]",
                        str(tracker.retry_count) if tracker.retry_count > 0 else "-",
                    )

            layout["segments"].update(Panel(segment_table, title="Connection Details"))

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all downloads."""
        total_downloaded = sum(d["downloaded"] for d in self.downloads.values())
        total_size = sum(d["total_size"] or 0 for d in self.downloads.values())
        active_downloads = len(self.downloads)

        elapsed_time = time.time() - self.start_time
        avg_speed = total_downloaded / elapsed_time if elapsed_time > 0 else 0

        # Segment summary
        total_segments = sum(
            len(segments) for segments in self.segment_trackers.values()
        )
        active_segments = 0
        completed_segments = 0

        for segments in self.segment_trackers.values():
            for tracker in segments.values():
                if tracker.status == "downloading":
                    active_segments += 1
                elif tracker.status == "completed":
                    completed_segments += 1

        return {
            "total_downloaded": total_downloaded,
            "total_size": total_size,
            "active_downloads": active_downloads,
            "elapsed_time": elapsed_time,
            "average_speed": avg_speed,
            "total_segments": total_segments,
            "active_segments": active_segments,
            "completed_segments": completed_segments,
        }

    def display_summary(self):
        """Display summary table."""
        summary = self.get_summary()

        table = Table(title="Download Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Active Downloads", str(summary["active_downloads"]))
        table.add_row("Total Downloaded", format_size(summary["total_downloaded"]))

        if summary["total_size"] > 0:
            table.add_row("Total Size", format_size(summary["total_size"]))

        table.add_row("Average Speed", f"{format_size(summary['average_speed'])}/s")
        table.add_row("Elapsed Time", f"{summary['elapsed_time']:.1f}s")

        if summary["total_segments"] > 0:
            table.add_row("Total Connections", str(summary["total_segments"]))
            table.add_row("Active Connections", str(summary["active_segments"]))
            table.add_row("Completed Connections", str(summary["completed_segments"]))

        self.console.print(table)


# Legacy compatibility
ProgressTracker = EnhancedProgressTracker
