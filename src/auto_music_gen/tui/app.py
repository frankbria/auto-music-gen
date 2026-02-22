"""Main wizard orchestrator -- ties all TUI components together."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from auto_music_gen.client.local import LocalClient
from auto_music_gen.config import AppConfig
from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.output.manager import OutputManager
from auto_music_gen.server.launcher import ServerLauncher
from auto_music_gen.tui.display import show_banner, show_error, show_results_table, show_success
from auto_music_gen.tui.progress import poll_with_progress
from auto_music_gen.tui.prompts import (
    confirm_action,
    get_execution_mode,
    get_lyrics,
    get_prompt,
    get_settings,
)
from auto_music_gen.tui.tags import format_prompt_with_tags, select_tags

console = Console()


def run(config: AppConfig) -> None:
    """Run the step-by-step music generation wizard."""
    launcher: ServerLauncher | None = None
    client: LocalClient | None = None

    try:
        # Step 0: Choose execution mode
        mode = get_execution_mode()

        if mode == "runpod":
            client, base_url = _setup_runpod(config)
        else:
            client, launcher, base_url = _setup_local(config)

        # Show banner with connection status
        connected = client.health_check()
        show_banner(base_url, connected)

        if not connected:
            show_error("Connection Failed", f"Cannot reach server at {base_url}")
            return

        # Main generation loop
        while True:
            result = _generation_wizard(client, config)
            if result == "quit":
                break

    finally:
        # Cleanup
        if client:
            client.close()
        if launcher and launcher.is_launched:
            if confirm_action("Stop the ACE-Step server?"):
                launcher.shutdown()
                console.print("[dim]Server stopped.[/dim]")


def _setup_local(config: AppConfig) -> tuple:
    """Set up local mode -- auto-launch server if needed."""
    base_url = config.server.base_url
    client = LocalClient(base_url=base_url, api_key=config.server.api_key)
    launcher = None

    if not client.health_check():
        console.print(f"\n[yellow]ACE-Step server not detected at {base_url}[/yellow]")

        acestep_dir = _resolve_acestep_dir(config.acestep.install_dir)

        if acestep_dir and confirm_action("Launch ACE-Step server now?"):
            launcher = ServerLauncher(
                acestep_dir=acestep_dir, port=config.acestep.port
            )
            launcher.launch()

            console.print("[dim]Starting ACE-Step server... (this may take a minute)[/dim]")
            if not launcher.wait_until_ready(base_url):
                show_error(
                    "Server Timeout",
                    "Server didn't start in time. Check GPU/memory.",
                )
                raise SystemExit(1)
            show_success("Server ready!")
        elif not acestep_dir:
            console.print(
                "[dim]Could not find ACE-Step installation.[/dim]"
            )
            console.print(
                "[dim]Set acestep.install_dir in config.toml or "
                "ACESTEP_INSTALL_DIR env var.[/dim]"
            )

    return client, launcher, base_url


# Common locations to search for ACE-Step installation
_ACESTEP_SEARCH_PATHS = [
    Path.home() / "projects" / "ACE-Step-1.5",
    Path.home() / "ACE-Step-1.5",
    Path.cwd().parent / "ACE-Step-1.5",
    Path.cwd() / "ACE-Step-1.5",
]


def _resolve_acestep_dir(configured: str) -> Path | None:
    """Find the ACE-Step installation directory.

    Resolution order:
    1. Explicit config value (acestep.install_dir or ACESTEP_INSTALL_DIR)
    2. Auto-detect from common locations
    """
    if configured:
        p = Path(configured).expanduser()
        if p.is_dir():
            return p

    for candidate in _ACESTEP_SEARCH_PATHS:
        if candidate.is_dir() and (candidate / "pyproject.toml").exists():
            return candidate

    return None


def _setup_runpod(config: AppConfig) -> tuple:
    """Set up RunPod mode -- create and wait for pod."""
    from auto_music_gen.client.runpod import GPU_OPTIONS, RunPodClient

    api_key = config.runpod.api_key
    if not api_key:
        from rich.prompt import Prompt

        api_key = Prompt.ask("RunPod API key")

    # GPU selection
    console.print("\n[bold]GPU Type:[/bold]")
    gpu_list = list(GPU_OPTIONS.items())
    for i, (name, info) in enumerate(gpu_list, 1):
        console.print(f"  [{i}] {name} (${info['price_hr']:.2f}/hr)")

    from rich.prompt import IntPrompt

    choice = IntPrompt.ask("Select GPU", default=1)
    choice = max(1, min(choice, len(gpu_list)))
    gpu_name, gpu_info = gpu_list[choice - 1]

    console.print(f"\n[dim]Estimated cost: ~${gpu_info['price_hr']:.2f}/hr[/dim]")
    if not confirm_action("Proceed with RunPod?"):
        raise SystemExit(0)

    rp_client = RunPodClient(
        api_key=api_key,
        gpu_type=gpu_info["id"],
        template_id=config.runpod.template_id,
        volume_id=config.runpod.volume_id,
    )

    console.print("[dim]Creating RunPod instance...[/dim]")
    rp_client.create_pod()

    console.print("[dim]Waiting for pod to start... (may take 1-3 minutes)[/dim]")
    base_url = rp_client.wait_for_pod()

    console.print("[dim]Waiting for ACE-Step server to initialize...[/dim]")
    if not rp_client.wait_for_server():
        show_error("Server Timeout", "ACE-Step server on RunPod didn't start in time.")
        rp_client.destroy_pod()
        raise SystemExit(1)

    show_success("RunPod ready!")

    # Wrap RunPodClient to match LocalClient interface for the wizard
    return rp_client, base_url


def _generation_wizard(client, config: AppConfig) -> str:
    """Run one generation cycle. Returns 'quit', 'new', or 'again'."""
    output_mgr = OutputManager(config.output.output_dir)

    # Step 1: Music description
    console.print("\n[bold cyan]Step 1: Music Description[/bold cyan]")
    prompt = get_prompt()
    if not prompt:
        return "quit"

    # Step 2: Style tags
    console.print("\n[bold cyan]Step 2: Style Tags (optional)[/bold cyan]")
    tags = select_tags()
    full_prompt = format_prompt_with_tags(prompt, tags)
    if tags:
        console.print(f"[dim]Final prompt: {full_prompt}[/dim]")

    # Step 3: Lyrics
    console.print("\n[bold cyan]Step 3: Lyrics[/bold cyan]")
    lyrics = get_lyrics()

    # Step 4: Settings
    console.print("\n[bold cyan]Step 4: Settings[/bold cyan]")
    settings = get_settings(config.generation)

    # Build request
    request = GenerationRequest(
        prompt=full_prompt,
        lyrics=lyrics,
        **settings,
    )

    # Step 5: Generate!
    console.print("\n[bold cyan]Step 5: Generate![/bold cyan]")
    try:
        submission = client.submit_task(request)
        console.print(f"[dim]Task submitted: {submission.task_id}[/dim]")

        result = poll_with_progress(client, submission.task_id)

        if result.is_failed:
            show_error("Generation Failed", result.error or "Unknown error")
        elif result.is_succeeded:
            # Download and save audio files
            output_dir = output_mgr.create_output_dir(prompt)
            for i, audio in enumerate(result.audios, 1):
                if audio.file:
                    ext = config.generation.audio_format
                    filename = f"sample_{i}.{ext}"
                    local_path = output_dir / filename
                    client.download_audio(audio.file, local_path)

            # Save metadata
            output_mgr.save_metadata(request, result, output_dir)

            show_success(f"{len(result.audios)} samples generated!")
            show_results_table(result.audios, str(output_dir))

    except TimeoutError:
        show_error("Timeout", "Generation took too long. Check the server.")
    except Exception as e:
        show_error("Error", str(e))

    # Post-generation menu
    console.print("\n[dim][g] Generate again  [n] New prompt  [q] Quit[/dim]")
    from rich.prompt import Prompt

    choice = Prompt.ask("", choices=["g", "n", "q"], default="q")
    return {"g": "again", "n": "new", "q": "quit"}.get(choice, "quit")
