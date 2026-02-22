"""Generation request parameters -- mirrors ACE-Step's GenerateMusicRequest."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Validation constants from ACE-Step (acestep/constants.py)
BPM_MIN = 30
BPM_MAX = 300
DURATION_MIN = 10
DURATION_MAX = 600
VALID_TIME_SIGNATURES = [2, 3, 4, 6]
MAX_PROMPT_LENGTH = 1024
MAX_LYRICS_LENGTH = 4096
MAX_BATCH_SIZE = 8
VALID_AUDIO_FORMATS = ("mp3", "wav", "flac", "wav32", "opus", "aac")

VALID_LANGUAGES = [
    "ar", "az", "bg", "bn", "ca", "cs", "da", "de", "el", "en",
    "es", "fa", "fi", "fr", "he", "hi", "hr", "ht", "hu", "id",
    "is", "it", "ja", "ko", "la", "lt", "ms", "ne", "nl", "no",
    "pa", "pl", "pt", "ro", "ru", "sa", "sk", "sr", "sv", "sw",
    "ta", "te", "th", "tl", "tr", "uk", "ur", "vi", "yue", "zh",
    "unknown",
]

KEYSCALE_NOTES = ["A", "B", "C", "D", "E", "F", "G"]
KEYSCALE_ACCIDENTALS = ["", "#", "b", "\u266f", "\u266d"]
KEYSCALE_MODES = ["major", "minor"]

VALID_KEYSCALES: set[str] = set()
for _note in KEYSCALE_NOTES:
    for _acc in KEYSCALE_ACCIDENTALS:
        for _mode in KEYSCALE_MODES:
            VALID_KEYSCALES.add(f"{_note}{_acc} {_mode}")


class GenerationRequest(BaseModel):
    """Parameters for a text2music generation request.

    This model validates user input before sending to the ACE-Step API.
    Field names match the API's GenerateMusicRequest schema.
    """

    prompt: str = Field(default="", description="Text prompt describing the desired music")
    lyrics: str = Field(default="", description="Lyrics text, or empty for instrumental")

    # Music metadata
    bpm: Optional[int] = Field(default=None, description="Beats per minute (30-300), None for auto")
    key_scale: str = Field(default="", description="Musical key, e.g. 'C major', 'F# minor'")
    time_signature: str = Field(default="", description="Time signature: 2, 3, 4, or 6")
    vocal_language: str = Field(default="en", description="Language code for vocals")
    audio_duration: Optional[float] = Field(
        default=None, description="Target duration in seconds (10-600), None for auto"
    )

    # Generation settings
    batch_size: Optional[int] = Field(default=2, description="Number of samples to generate (1-8)")
    inference_steps: int = Field(default=8, description="Diffusion steps (8 for turbo)")
    guidance_scale: float = Field(default=7.0, description="CFG scale")
    seed: int = Field(default=-1, description="Seed (-1 for random)")
    audio_format: str = Field(default="mp3", description="Output format")

    # Task type (v1: text2music only)
    task_type: str = Field(default="text2music")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt must be under {MAX_PROMPT_LENGTH} characters (got {len(v)})")
        return v

    @field_validator("lyrics")
    @classmethod
    def validate_lyrics(cls, v: str) -> str:
        if len(v) > MAX_LYRICS_LENGTH:
            raise ValueError(
                f"Lyrics must be under {MAX_LYRICS_LENGTH} characters (got {len(v)})"
            )
        return v

    @field_validator("bpm")
    @classmethod
    def validate_bpm(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (BPM_MIN <= v <= BPM_MAX):
            raise ValueError(f"BPM must be between {BPM_MIN} and {BPM_MAX} (got {v})")
        return v

    @field_validator("audio_duration")
    @classmethod
    def validate_duration(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (DURATION_MIN <= v <= DURATION_MAX):
            raise ValueError(
                f"Duration must be between {DURATION_MIN}s and {DURATION_MAX}s (got {v})"
            )
        return v

    @field_validator("time_signature")
    @classmethod
    def validate_time_signature(cls, v: str) -> str:
        if v and v not in [str(ts) for ts in VALID_TIME_SIGNATURES]:
            raise ValueError(
                f"Time signature must be one of {VALID_TIME_SIGNATURES} (got '{v}')"
            )
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= MAX_BATCH_SIZE):
            raise ValueError(f"Batch size must be between 1 and {MAX_BATCH_SIZE} (got {v})")
        return v

    @field_validator("key_scale")
    @classmethod
    def validate_key_scale(cls, v: str) -> str:
        if v and v not in VALID_KEYSCALES:
            raise ValueError(f"Invalid key scale '{v}'. Examples: 'C major', 'F# minor'")
        return v

    @field_validator("vocal_language")
    @classmethod
    def validate_vocal_language(cls, v: str) -> str:
        if v and v not in VALID_LANGUAGES:
            raise ValueError(f"Unsupported language '{v}'")
        return v

    @field_validator("audio_format")
    @classmethod
    def validate_audio_format(cls, v: str) -> str:
        if v not in VALID_AUDIO_FORMATS:
            raise ValueError(f"Format must be one of {VALID_AUDIO_FORMATS} (got '{v}')")
        return v

    def to_api_dict(self) -> dict:
        """Convert to dict for the ACE-Step API, omitting None values."""
        d = self.model_dump(exclude_none=True)
        # Remove empty strings so the API uses its defaults
        return {k: v for k, v in d.items() if v != ""}
