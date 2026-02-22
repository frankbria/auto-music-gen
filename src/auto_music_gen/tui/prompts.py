"""Rich-based input helpers for user interaction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

if TYPE_CHECKING:
    from auto_music_gen.config import GenerationDefaults

console = Console()


def get_prompt() -> str:
    """Ask the user for a music description.

    Returns:
        The user-provided prompt string.
    """
    return Prompt.ask("[bold cyan]Describe the music you want to generate[/bold cyan]")


def get_lyrics() -> str:
    """Present a menu for lyrics input.

    Options:
        1. Type lyrics directly
        2. Load lyrics from a file
        3. Instrumental (no lyrics)

    Returns:
        The lyrics string, or '[Instrumental]' for instrumental tracks.
    """
    console.print("\n[bold]Lyrics Options:[/bold]")
    console.print("  [1] Type lyrics")
    console.print("  [2] Load from file")
    console.print("  [3] Instrumental (no lyrics)")

    choice = IntPrompt.ask("Select option", choices=["1", "2", "3"], default=3)

    if choice == 1:
        console.print("[dim]Enter lyrics (press Enter twice to finish):[/dim]")
        lines: list[str] = []
        while True:
            line = console.input("")
            if line == "" and lines and lines[-1] == "":
                lines.pop()
                break
            lines.append(line)
        return "\n".join(lines)

    if choice == 2:
        file_path = Prompt.ask("Path to lyrics file")
        path = Path(file_path).expanduser()
        if not path.exists():
            console.print(f"[red]File not found: {path}[/red]")
            return get_lyrics()
        return path.read_text(encoding="utf-8")

    return "[Instrumental]"


def get_settings(defaults: GenerationDefaults) -> dict:
    """Show current generation defaults and allow customization.

    Args:
        defaults: The current GenerationDefaults instance.

    Returns:
        Dict of settings (matching GenerationDefaults fields).
    """
    table = Table(title="Generation Settings")
    table.add_column("Setting", style="bold")
    table.add_column("Current Value", style="green")

    table.add_row("Audio Format", defaults.audio_format)
    table.add_row("Batch Size", str(defaults.batch_size))
    table.add_row("Inference Steps", str(defaults.inference_steps))
    table.add_row("Guidance Scale", str(defaults.guidance_scale))

    console.print(table)

    if not Confirm.ask("Customize settings?", default=False):
        return {
            "audio_format": defaults.audio_format,
            "batch_size": defaults.batch_size,
            "inference_steps": defaults.inference_steps,
            "guidance_scale": defaults.guidance_scale,
        }

    audio_format = Prompt.ask("Audio format", default=defaults.audio_format, choices=["mp3", "wav"])
    batch_size = IntPrompt.ask("Batch size (1-8)", default=defaults.batch_size)
    batch_size = max(1, min(8, batch_size))
    inference_steps = IntPrompt.ask("Inference steps", default=defaults.inference_steps)
    guidance_scale_str = Prompt.ask("Guidance scale", default=str(defaults.guidance_scale))

    try:
        guidance_scale = float(guidance_scale_str)
    except ValueError:
        guidance_scale = defaults.guidance_scale

    return {
        "audio_format": audio_format,
        "batch_size": batch_size,
        "inference_steps": inference_steps,
        "guidance_scale": guidance_scale,
    }


def get_execution_mode() -> str:
    """Ask the user to choose between local and RunPod execution.

    Returns:
        'local' or 'runpod'.
    """
    console.print("\n[bold]Execution Mode:[/bold]")
    console.print("  [1] Local server")
    console.print("  [2] RunPod (cloud GPU)")

    choice = IntPrompt.ask("Select mode", choices=["1", "2"], default=1)
    return "local" if choice == 1 else "runpod"


def confirm_action(message: str) -> bool:
    """Ask for a yes/no confirmation.

    Args:
        message: The confirmation prompt to display.

    Returns:
        True if confirmed, False otherwise.
    """
    return Confirm.ask(message)
