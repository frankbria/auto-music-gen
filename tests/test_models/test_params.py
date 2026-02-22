"""Tests for GenerationRequest validation."""

import pytest
from pydantic import ValidationError

from auto_music_gen.models.params import (
    BPM_MAX,
    BPM_MIN,
    DURATION_MAX,
    DURATION_MIN,
    MAX_BATCH_SIZE,
    MAX_PROMPT_LENGTH,
    GenerationRequest,
)


class TestGenerationRequestDefaults:
    def test_defaults(self):
        req = GenerationRequest()
        assert req.prompt == ""
        assert req.lyrics == ""
        assert req.bpm is None
        assert req.batch_size == 2
        assert req.audio_format == "mp3"
        assert req.task_type == "text2music"

    def test_basic_prompt(self):
        req = GenerationRequest(prompt="A chill lo-fi beat")
        assert req.prompt == "A chill lo-fi beat"


class TestPromptValidation:
    def test_max_length(self):
        req = GenerationRequest(prompt="x" * MAX_PROMPT_LENGTH)
        assert len(req.prompt) == MAX_PROMPT_LENGTH

    def test_over_max_length_raises(self):
        with pytest.raises(ValidationError, match="Prompt must be under"):
            GenerationRequest(prompt="x" * (MAX_PROMPT_LENGTH + 1))


class TestLyricsValidation:
    def test_lyrics_accepted(self):
        req = GenerationRequest(lyrics="La la la\nDo re mi")
        assert "La la la" in req.lyrics

    def test_over_max_raises(self):
        with pytest.raises(ValidationError, match="Lyrics must be under"):
            GenerationRequest(lyrics="x" * 4097)


class TestBPMValidation:
    def test_none_allowed(self):
        req = GenerationRequest(bpm=None)
        assert req.bpm is None

    def test_valid_bpm(self):
        req = GenerationRequest(bpm=120)
        assert req.bpm == 120

    def test_min_boundary(self):
        req = GenerationRequest(bpm=BPM_MIN)
        assert req.bpm == BPM_MIN

    def test_max_boundary(self):
        req = GenerationRequest(bpm=BPM_MAX)
        assert req.bpm == BPM_MAX

    def test_below_min_raises(self):
        with pytest.raises(ValidationError, match="BPM must be between"):
            GenerationRequest(bpm=BPM_MIN - 1)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError, match="BPM must be between"):
            GenerationRequest(bpm=BPM_MAX + 1)


class TestDurationValidation:
    def test_none_allowed(self):
        req = GenerationRequest(audio_duration=None)
        assert req.audio_duration is None

    def test_valid_duration(self):
        req = GenerationRequest(audio_duration=120.0)
        assert req.audio_duration == 120.0

    def test_below_min_raises(self):
        with pytest.raises(ValidationError, match="Duration must be between"):
            GenerationRequest(audio_duration=DURATION_MIN - 1)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError, match="Duration must be between"):
            GenerationRequest(audio_duration=DURATION_MAX + 1)


class TestTimeSignatureValidation:
    def test_empty_allowed(self):
        req = GenerationRequest(time_signature="")
        assert req.time_signature == ""

    @pytest.mark.parametrize("ts", ["2", "3", "4", "6"])
    def test_valid_signatures(self, ts: str):
        req = GenerationRequest(time_signature=ts)
        assert req.time_signature == ts

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Time signature must be one of"):
            GenerationRequest(time_signature="5")


class TestBatchSizeValidation:
    def test_valid(self):
        req = GenerationRequest(batch_size=4)
        assert req.batch_size == 4

    def test_too_large_raises(self):
        with pytest.raises(ValidationError, match="Batch size must be between"):
            GenerationRequest(batch_size=MAX_BATCH_SIZE + 1)

    def test_zero_raises(self):
        with pytest.raises(ValidationError, match="Batch size must be between"):
            GenerationRequest(batch_size=0)


class TestKeyScaleValidation:
    def test_empty_allowed(self):
        req = GenerationRequest(key_scale="")
        assert req.key_scale == ""

    @pytest.mark.parametrize("ks", ["C major", "F# minor", "Bb major", "A minor"])
    def test_valid_scales(self, ks: str):
        req = GenerationRequest(key_scale=ks)
        assert req.key_scale == ks

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Invalid key scale"):
            GenerationRequest(key_scale="Z# major")


class TestAudioFormatValidation:
    @pytest.mark.parametrize("fmt", ["mp3", "wav", "flac", "opus", "aac", "wav32"])
    def test_valid_formats(self, fmt: str):
        req = GenerationRequest(audio_format=fmt)
        assert req.audio_format == fmt

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Format must be one of"):
            GenerationRequest(audio_format="ogg")


class TestVocalLanguageValidation:
    def test_default_en(self):
        req = GenerationRequest()
        assert req.vocal_language == "en"

    @pytest.mark.parametrize("lang", ["en", "zh", "ja", "ko", "unknown"])
    def test_valid_languages(self, lang: str):
        req = GenerationRequest(vocal_language=lang)
        assert req.vocal_language == lang

    def test_invalid_raises(self):
        with pytest.raises(ValidationError, match="Unsupported language"):
            GenerationRequest(vocal_language="xx")


class TestToApiDict:
    def test_omits_none(self):
        req = GenerationRequest(prompt="test", bpm=None, audio_duration=None)
        d = req.to_api_dict()
        assert "bpm" not in d
        assert "audio_duration" not in d

    def test_omits_empty_strings(self):
        req = GenerationRequest(prompt="test", key_scale="", time_signature="")
        d = req.to_api_dict()
        assert "key_scale" not in d
        assert "time_signature" not in d

    def test_includes_values(self):
        req = GenerationRequest(prompt="test", bpm=120, batch_size=4)
        d = req.to_api_dict()
        assert d["prompt"] == "test"
        assert d["bpm"] == 120
        assert d["batch_size"] == 4
