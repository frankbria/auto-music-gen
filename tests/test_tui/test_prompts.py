"""Tests for Rich-based input helpers."""

from __future__ import annotations

import pytest

from auto_music_gen.tui.prompts import confirm_action, get_lyrics, get_prompt


class TestGetPrompt:
    def test_returns_user_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rich.prompt.Prompt.ask",
            lambda *args, **kwargs: "a chill lo-fi beat",
        )
        result = get_prompt()
        assert result == "a chill lo-fi beat"

    def test_returns_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: "")
        result = get_prompt()
        assert result == ""


class TestGetLyrics:
    def test_instrumental_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rich.prompt.IntPrompt.ask",
            lambda *args, **kwargs: 3,
        )
        result = get_lyrics()
        assert result == "[Instrumental]"

    def test_type_lyrics_option(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rich.prompt.IntPrompt.ask",
            lambda *args, **kwargs: 1,
        )
        lines = iter(["Hello world", "Second line", "", ""])
        monkeypatch.setattr(
            "rich.console.Console.input",
            lambda self, *a, **kw: next(lines),
        )
        result = get_lyrics()
        assert "Hello world" in result
        assert "Second line" in result

    def test_load_from_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
    ) -> None:
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Verse 1\nChorus\nVerse 2", encoding="utf-8")

        monkeypatch.setattr(
            "rich.prompt.IntPrompt.ask",
            lambda *args, **kwargs: 2,
        )
        monkeypatch.setattr(
            "rich.prompt.Prompt.ask",
            lambda *args, **kwargs: str(lyrics_file),
        )
        result = get_lyrics()
        assert "Verse 1" in result
        assert "Chorus" in result


class TestConfirmAction:
    def test_confirm_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: True)
        assert confirm_action("Proceed?") is True

    def test_confirm_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: False)
        assert confirm_action("Proceed?") is False
