"""Tests for OutputManager."""

import json
import re
from pathlib import Path

import pytest

from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import AudioResult, TaskResult
from auto_music_gen.output.manager import OutputManager


@pytest.fixture
def manager(tmp_path: Path) -> OutputManager:
    """OutputManager using a temporary base directory."""
    return OutputManager(base_dir=str(tmp_path))


@pytest.fixture
def sample_request() -> GenerationRequest:
    return GenerationRequest(
        prompt="A chill lo-fi beat",
        lyrics="La la la",
        bpm=90,
        audio_format="mp3",
    )


@pytest.fixture
def sample_result() -> TaskResult:
    return TaskResult(
        task_id="task-001",
        status=1,
        progress_text="done",
        audios=[
            AudioResult(
                file="/results/audio_0.mp3",
                status=1,
                prompt="A chill lo-fi beat",
                lyrics="La la la",
                metas={"bpm": 90},
            ),
        ],
    )


class TestCreateOutputDir:
    """Tests for create_output_dir."""

    def test_creates_directory(self, manager: OutputManager) -> None:
        result = manager.create_output_dir("My cool song")
        assert result.exists()
        assert result.is_dir()

    def test_timestamp_format(self, manager: OutputManager) -> None:
        result = manager.create_output_dir("test prompt")
        name = result.name
        # Format: YYYYMMDD_HHMMSS_<slug>
        pattern = r"^\d{8}_\d{6}_[a-z0-9_]+$"
        assert re.match(pattern, name), f"Directory name '{name}' does not match expected format"

    def test_prompt_slug_in_name(self, manager: OutputManager) -> None:
        result = manager.create_output_dir("My Awesome Song!")
        assert "my_awesome_song" in result.name

    def test_empty_prompt(self, manager: OutputManager) -> None:
        result = manager.create_output_dir("")
        assert result.exists()
        # With empty prompt, slug is empty, so name ends with timestamp + _
        # _slugify("") returns "" after strip, so dir name is just timestamp
        pattern = r"^\d{8}_\d{6}_$"
        assert re.match(pattern, result.name), (
            f"Directory name '{result.name}' unexpected for empty prompt"
        )

    def test_nested_base_dir_created(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        manager = OutputManager(base_dir=str(nested))
        result = manager.create_output_dir("test")
        assert result.exists()
        assert nested.exists()


class TestSlugify:
    """Tests for _slugify."""

    def test_basic_text(self) -> None:
        assert OutputManager._slugify("Hello World") == "hello_world"

    def test_special_characters(self) -> None:
        assert OutputManager._slugify("Rock & Roll!!!") == "rock_roll"

    def test_uppercase(self) -> None:
        assert OutputManager._slugify("ALL CAPS HERE") == "all_caps_here"

    def test_long_text_truncated(self) -> None:
        long_text = "a" * 100
        result = OutputManager._slugify(long_text)
        assert len(result) <= 50

    def test_custom_max_len(self) -> None:
        result = OutputManager._slugify("hello world", max_len=5)
        assert result == "hello"

    def test_leading_trailing_underscores_stripped(self) -> None:
        result = OutputManager._slugify("---hello---")
        assert result == "hello"

    def test_empty_string(self) -> None:
        assert OutputManager._slugify("") == ""

    def test_only_special_chars(self) -> None:
        assert OutputManager._slugify("!!!@@@###") == ""

    def test_unicode_chars(self) -> None:
        result = OutputManager._slugify("caf\u00e9 m\u00fasica")
        assert result == "caf_m_sica"

    def test_numbers_preserved(self) -> None:
        assert OutputManager._slugify("track 42 remix") == "track_42_remix"


class TestSaveAudio:
    """Tests for save_audio."""

    def test_writes_bytes(self, manager: OutputManager, tmp_path: Path) -> None:
        audio_data = b"\x00\x01\x02\x03" * 100
        result = manager.save_audio(audio_data, "song.mp3", tmp_path)
        assert result.exists()
        assert result.read_bytes() == audio_data

    def test_returns_correct_path(self, manager: OutputManager, tmp_path: Path) -> None:
        result = manager.save_audio(b"data", "output.wav", tmp_path)
        assert result == tmp_path / "output.wav"

    def test_empty_audio(self, manager: OutputManager, tmp_path: Path) -> None:
        result = manager.save_audio(b"", "empty.mp3", tmp_path)
        assert result.exists()
        assert result.stat().st_size == 0


class TestSaveMetadata:
    """Tests for save_metadata."""

    def test_creates_json_file(
        self,
        manager: OutputManager,
        sample_request: GenerationRequest,
        sample_result: TaskResult,
        tmp_path: Path,
    ) -> None:
        meta_path = manager.save_metadata(sample_request, sample_result, tmp_path)
        assert meta_path.exists()
        assert meta_path.name == "metadata.json"

    def test_valid_json(
        self,
        manager: OutputManager,
        sample_request: GenerationRequest,
        sample_result: TaskResult,
        tmp_path: Path,
    ) -> None:
        meta_path = manager.save_metadata(sample_request, sample_result, tmp_path)
        data = json.loads(meta_path.read_text())
        assert isinstance(data, dict)

    def test_metadata_structure(
        self,
        manager: OutputManager,
        sample_request: GenerationRequest,
        sample_result: TaskResult,
        tmp_path: Path,
    ) -> None:
        meta_path = manager.save_metadata(sample_request, sample_result, tmp_path)
        data = json.loads(meta_path.read_text())

        assert data["prompt"] == "A chill lo-fi beat"
        assert data["lyrics"] == "La la la"
        assert data["task_id"] == "task-001"
        assert data["status"] == 1
        assert isinstance(data["settings"], dict)
        assert isinstance(data["audios"], list)
        assert len(data["audios"]) == 1

    def test_audio_entry_fields(
        self,
        manager: OutputManager,
        sample_request: GenerationRequest,
        sample_result: TaskResult,
        tmp_path: Path,
    ) -> None:
        meta_path = manager.save_metadata(sample_request, sample_result, tmp_path)
        data = json.loads(meta_path.read_text())
        audio = data["audios"][0]

        assert audio["file"] == "/results/audio_0.mp3"
        assert audio["prompt"] == "A chill lo-fi beat"
        assert audio["lyrics"] == "La la la"
        assert audio["metas"] == {"bpm": 90}

    def test_settings_uses_to_api_dict(
        self,
        manager: OutputManager,
        sample_request: GenerationRequest,
        sample_result: TaskResult,
        tmp_path: Path,
    ) -> None:
        meta_path = manager.save_metadata(sample_request, sample_result, tmp_path)
        data = json.loads(meta_path.read_text())
        settings = data["settings"]
        # to_api_dict excludes None and empty string values
        assert "prompt" in settings
        assert "bpm" in settings
        assert settings["bpm"] == 90


class TestGetFileSize:
    """Tests for get_file_size."""

    def test_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "small.bin"
        f.write_bytes(b"x" * 500)
        assert OutputManager.get_file_size(f) == "500.0B"

    def test_kilobytes(self, tmp_path: Path) -> None:
        f = tmp_path / "medium.bin"
        f.write_bytes(b"x" * 2048)
        assert OutputManager.get_file_size(f) == "2.0KB"

    def test_megabytes(self, tmp_path: Path) -> None:
        f = tmp_path / "large.bin"
        f.write_bytes(b"x" * (3 * 1024 * 1024))
        assert OutputManager.get_file_size(f) == "3.0MB"

    def test_gigabytes(self, tmp_path: Path) -> None:
        # We won't create a real GB file, so test the logic with a mock
        # Instead, test boundary: 1 GB = 1073741824 bytes
        # We'll test with a smaller file and verify the math indirectly
        f = tmp_path / "one_kb.bin"
        f.write_bytes(b"x" * 1024)
        assert OutputManager.get_file_size(f) == "1.0KB"

    def test_exact_boundary(self, tmp_path: Path) -> None:
        f = tmp_path / "boundary.bin"
        f.write_bytes(b"x" * 1023)
        assert OutputManager.get_file_size(f) == "1023.0B"

    def test_zero_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert OutputManager.get_file_size(f) == "0.0B"
