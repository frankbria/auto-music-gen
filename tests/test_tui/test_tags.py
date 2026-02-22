"""Tests for TUI tag definitions and selection helpers."""

from __future__ import annotations

import pytest

from auto_music_gen.tui.tags import STYLE_TAGS, format_prompt_with_tags, select_tags

EXPECTED_CATEGORIES = ["Genre", "Mood", "Instruments", "Vocal Style", "Era", "Production"]


class TestStyleTags:
    """Validate the STYLE_TAGS dictionary structure."""

    def test_has_all_expected_categories(self) -> None:
        for category in EXPECTED_CATEGORIES:
            assert category in STYLE_TAGS, f"Missing category: {category}"

    def test_no_unexpected_categories(self) -> None:
        assert set(STYLE_TAGS.keys()) == set(EXPECTED_CATEGORIES)

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_each_category_has_at_least_five_items(self, category: str) -> None:
        assert len(STYLE_TAGS[category]) >= 5, (
            f"Category '{category}' has only {len(STYLE_TAGS[category])} items"
        )

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_no_duplicate_tags_within_category(self, category: str) -> None:
        tags = STYLE_TAGS[category]
        assert len(tags) == len(set(tags)), f"Duplicate tags in '{category}'"


class TestFormatPromptWithTags:
    """Validate prompt + tag formatting."""

    def test_with_tags(self) -> None:
        result = format_prompt_with_tags("upbeat dance track", ["pop", "energetic", "synth"])
        assert result == "upbeat dance track. pop, energetic, synth"

    def test_without_tags(self) -> None:
        result = format_prompt_with_tags("ambient soundscape", [])
        assert result == "ambient soundscape"

    def test_single_tag(self) -> None:
        result = format_prompt_with_tags("chill beat", ["lo-fi"])
        assert result == "chill beat. lo-fi"

    def test_preserves_prompt_exactly(self) -> None:
        prompt = "A cinematic orchestral piece with rising tension"
        result = format_prompt_with_tags(prompt, ["epic"])
        assert result.startswith(prompt)


class TestSelectTags:
    """Validate interactive tag selection."""

    def test_select_tags_skip_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["d"] * len(STYLE_TAGS))
        monkeypatch.setattr("rich.console.Console.input", lambda self, *a, **kw: next(inputs))
        result = select_tags()
        assert result == []

    def test_select_tags_picks_first_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        categories = list(STYLE_TAGS.keys())
        responses = ["1"] + ["d"] * (len(categories) - 1)
        inputs = iter(responses)
        monkeypatch.setattr("rich.console.Console.input", lambda self, *a, **kw: next(inputs))
        result = select_tags()
        assert len(result) == 1
        assert result[0] == STYLE_TAGS[categories[0]][0]
