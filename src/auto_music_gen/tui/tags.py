"""Style tag definitions and selection for music generation prompts."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()

STYLE_TAGS: dict[str, list[str]] = {
    "Genre": [
        "pop", "rock", "hip-hop", "R&B", "electronic", "EDM", "jazz", "classical",
        "country", "folk", "metal", "blues", "reggae", "latin", "funk", "ambient",
        "lo-fi", "indie", "punk", "soul", "disco", "trap", "house", "techno", "K-pop",
    ],
    "Mood": [
        "energetic", "chill", "dark", "happy", "sad", "romantic", "epic", "dreamy",
        "aggressive", "peaceful", "melancholic", "uplifting", "mysterious", "nostalgic",
        "playful", "dramatic",
    ],
    "Instruments": [
        "piano", "acoustic guitar", "electric guitar", "synth", "bass", "strings",
        "brass", "drums", "percussion", "organ", "flute", "violin", "saxophone", "cello",
    ],
    "Vocal Style": [
        "male vocal", "female vocal", "duet", "choir", "raspy", "falsetto",
        "clear vocal", "rap vocal",
    ],
    "Era": ["80s", "90s", "2000s", "modern", "retro", "vintage", "cinematic"],
    "Production": [
        "lo-fi", "acoustic", "orchestral", "minimalist", "atmospheric", "distorted",
        "clean", "reverb-heavy",
    ],
}


def select_tags() -> list[str]:
    """Interactive tag selection across all categories.

    Displays categories with numbered items. User types numbers (comma-separated
    or space-separated) to toggle selections. Type 'd' when done.

    Returns:
        List of selected tag strings.
    """
    selected: list[str] = []

    for category, tags in STYLE_TAGS.items():
        table = Table(title=f"[bold]{category}[/bold]", show_header=False, expand=False)
        table.add_column("Num", style="dim", width=4)
        table.add_column("Tag")

        for idx, tag in enumerate(tags, start=1):
            table.add_row(str(idx), tag)

        console.print(table)
        user_input = console.input(
            f"Select [bold]{category}[/bold] tags (numbers separated by spaces, 'd' to skip): "
        ).strip()

        if user_input.lower() == "d" or not user_input:
            continue

        parts = user_input.replace(",", " ").split()
        for part in parts:
            try:
                num = int(part)
                if 1 <= num <= len(tags):
                    tag_value = tags[num - 1]
                    if tag_value not in selected:
                        selected.append(tag_value)
            except ValueError:
                continue

    if selected:
        console.print(f"\n[bold]Selected tags:[/bold] {', '.join(selected)}")

    return selected


def format_prompt_with_tags(prompt: str, tags: list[str]) -> str:
    """Combine a text prompt with style tags.

    Args:
        prompt: The base music description.
        tags: List of style tag strings to append.

    Returns:
        Combined prompt string. If tags is empty, returns prompt unchanged.
    """
    if not tags:
        return prompt
    return f"{prompt}. {', '.join(tags)}"
