"""TOML-based application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_CONFIG_PATHS = [
    Path("config.toml"),
    Path.home() / ".config" / "auto-music-gen" / "config.toml",
]


class ServerConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8001"
    api_key: str = ""


class AceStepConfig(BaseModel):
    install_dir: str = ""
    port: int = 8001


class GenerationDefaults(BaseModel):
    audio_format: str = "mp3"
    batch_size: int = 1
    inference_steps: int = 8
    guidance_scale: float = 7.0
    audio_duration: int = 120


class OutputConfig(BaseModel):
    output_dir: str = "output"


class RunPodConfig(BaseModel):
    api_key: str = ""
    gpu_type: str = "NVIDIA RTX 4090"
    template_id: str = ""
    volume_id: str = ""
    auto_destroy: bool = True


class AppConfig(BaseModel):
    """Top-level application configuration."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    acestep: AceStepConfig = Field(default_factory=AceStepConfig)
    generation: GenerationDefaults = Field(default_factory=GenerationDefaults)
    output: OutputConfig = Field(default_factory=OutputConfig)
    runpod: RunPodConfig = Field(default_factory=RunPodConfig)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load config from TOML file, falling back to defaults.

    Resolution order for secrets (env vars):
    1. .env file in current directory (loaded first)
    2. Explicit environment variables (override .env)
    3. config.toml values (lowest priority for secrets)

    Resolution order for config file:
    1. Explicit path argument
    2. config.toml in current directory
    3. ~/.config/auto-music-gen/config.toml
    4. All defaults
    """
    _load_dotenv()

    if path and path.exists():
        return _parse_toml(path)

    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate.exists():
            return _parse_toml(candidate)

    return _apply_env_overrides(AppConfig())


def _load_dotenv() -> None:
    """Load .env file from current directory if it exists.

    We parse it manually (KEY=VALUE lines) to avoid adding a dependency.
    Existing environment variables are NOT overwritten.
    """
    env_path = Path(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        # Don't overwrite existing env vars
        if key not in os.environ:
            os.environ[key] = value


def _parse_toml(path: Path) -> AppConfig:
    """Parse a TOML file into AppConfig."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    config = AppConfig.model_validate(data)
    return _apply_env_overrides(config)


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Override config values with environment variables."""
    if api_key := os.environ.get("ACESTEP_API_KEY"):
        config.server.api_key = api_key
    if runpod_key := os.environ.get("RUNPOD_API_KEY"):
        config.runpod.api_key = runpod_key
    if install_dir := os.environ.get("ACESTEP_INSTALL_DIR"):
        config.acestep.install_dir = install_dir
    return config
