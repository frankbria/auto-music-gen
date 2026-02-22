"""Rich-based display helpers for the TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from auto_music_gen.models.results import AudioResult

console = Console()

VERSION = "0.1.0"


def show_banner(base_url: str, connected: bool) -> None:
    """Display the application banner with server status."""
    status = "[green]Connected[/green]" if connected else "[red]Disconnected[/red]"
    content = (
        f"[bold cyan]AUTO MUSIC GEN[/bold cyan] v{VERSION}\n"
        f"Server: {base_url} [{status}]"
    )
    panel = Panel(content, border_style="cyan", expand=False)
    console.print(panel)


def show_results_table(audios: list[AudioResult], output_dir: str) -> None:
    """Display a table of generated audio results."""
    table = Table(title=f"Generated Audio ({output_dir})")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Size", justify="right")

    for idx, audio in enumerate(audios, start=1):
        duration = audio.metas.get("duration", "N/A")
        if isinstance(duration, (int, float)):
            duration = f"{duration:.1f}s"
        size = audio.metas.get("size", "N/A")
        if isinstance(size, (int, float)):
            size = _format_bytes(size)
        table.add_row(str(idx), audio.file, str(duration), str(size))

    console.print(table)


def show_error(title: str, message: str) -> None:
    """Display an error panel with red border."""
    panel = Panel(
        f"[red]{message}[/red]",
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
    )
    console.print(panel)


def show_success(message: str) -> None:
    """Display a success panel with green border."""
    panel = Panel(
        f"[green]{message}[/green]",
        title="[bold green]Success[/bold green]",
        border_style="green",
    )
    console.print(panel)


def _format_bytes(num_bytes: int | float) -> str:
    """Format a byte count into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
