"""Polling progress display for long-running generation tasks."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

if TYPE_CHECKING:
    from auto_music_gen.models.results import TaskResult

console = Console()

POLL_INTERVAL = 2.0
DEFAULT_TIMEOUT = 1800.0


@runtime_checkable
class Pollable(Protocol):
    """Protocol for clients that support polling for task results."""

    def poll_result(self, task_id: str) -> TaskResult: ...


def poll_with_progress(
    client: Pollable,
    task_id: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> TaskResult:
    """Poll for task completion with a live spinner display.

    Uses Rich Live to show a spinner and progress text while repeatedly
    polling the client for results.

    Args:
        client: Any object implementing the Pollable protocol (has poll_result).
        task_id: The task ID to poll.
        timeout: Maximum seconds to wait before raising TimeoutError.

    Returns:
        The final TaskResult when status != 0 (succeeded or failed).

    Raises:
        TimeoutError: If the task does not complete within the timeout.
    """
    start = time.monotonic()

    with Live(console=console, refresh_per_second=4) as live:
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError(
                    f"Task {task_id} did not complete within {timeout:.0f}s"
                )

            result = client.poll_result(task_id)

            if not result.is_running:
                return result

            progress_msg = result.progress_text or "Generating..."
            elapsed_display = f"{elapsed:.0f}s"

            spinner = Spinner("dots", text=Text.from_markup(
                f"[cyan]{progress_msg}[/cyan]  [dim]({elapsed_display})[/dim]"
            ))
            live.update(spinner)

            time.sleep(POLL_INTERVAL)
