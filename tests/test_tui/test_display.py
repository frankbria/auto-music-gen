"""Tests for Rich-based display helpers."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from auto_music_gen.models.results import AudioResult
from auto_music_gen.tui.display import show_banner, show_error, show_results_table, show_success


def _capture(func, *args, **kwargs) -> str:
    """Run a display function and capture its Rich output as plain text."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    # Temporarily swap the module-level console
    import auto_music_gen.tui.display as display_mod

    original = display_mod.console
    display_mod.console = console
    try:
        func(*args, **kwargs)
    finally:
        display_mod.console = original
    return buf.getvalue()


class TestShowBanner:
    def test_banner_connected(self) -> None:
        output = _capture(show_banner, "http://localhost:8001", True)
        assert "AUTO MUSIC GEN" in output
        assert "v0.1.0" in output
        assert "Connected" in output

    def test_banner_disconnected(self) -> None:
        output = _capture(show_banner, "http://localhost:8001", False)
        assert "Disconnected" in output
        assert "localhost:8001" in output


class TestShowResultsTable:
    def test_renders_table_with_data(self) -> None:
        audios = [
            AudioResult(
                file="song_01.mp3",
                status=1,
                prompt="test",
                metas={"duration": 30.5, "size": 512000},
            ),
            AudioResult(
                file="song_02.mp3",
                status=1,
                prompt="test2",
                metas={"duration": 60.0, "size": 1048576},
            ),
        ]
        output = _capture(show_results_table, audios, "output")
        assert "song_01.mp3" in output
        assert "song_02.mp3" in output
        assert "30.5s" in output
        assert "500.0 KB" in output

    def test_renders_table_with_missing_meta(self) -> None:
        audios = [AudioResult(file="track.wav", status=1)]
        output = _capture(show_results_table, audios, "/tmp/out")
        assert "track.wav" in output
        assert "N/A" in output


class TestShowError:
    def test_renders_error_panel(self) -> None:
        output = _capture(show_error, "Connection Failed", "Could not reach server")
        assert "Connection Failed" in output
        assert "Could not reach server" in output


class TestShowSuccess:
    def test_renders_success_panel(self) -> None:
        output = _capture(show_success, "Files downloaded successfully")
        assert "Files downloaded successfully" in output
        assert "Success" in output
