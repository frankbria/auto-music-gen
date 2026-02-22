"""CLI entry point for auto-music-gen."""

from __future__ import annotations

import sys
from pathlib import Path

from auto_music_gen.config import load_config
from auto_music_gen.tui.app import run


def main() -> None:
    """Parse args, load config, launch TUI."""
    config_path = None

    # Simple arg parsing -- just --config for now
    args = sys.argv[1:]
    if "--config" in args:
        idx = args.index("--config")
        if idx + 1 < len(args):
            config_path = Path(args[idx + 1])
        else:
            print("Error: --config requires a path argument")
            sys.exit(1)

    config = load_config(config_path)

    try:
        run(config)
    except KeyboardInterrupt:
        print("\nBye!")
        sys.exit(0)
