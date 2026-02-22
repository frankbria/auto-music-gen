"""Tests for application configuration."""

from pathlib import Path

import pytest

from auto_music_gen.config import AppConfig, load_config


class TestAppConfigDefaults:
    def test_defaults(self):
        config = AppConfig()
        assert config.server.base_url == "http://127.0.0.1:8001"
        assert config.server.api_key == ""
        assert config.generation.batch_size == 1
        assert config.generation.audio_duration == 120
        assert config.generation.audio_format == "mp3"
        assert config.output.output_dir == "output"
        assert config.runpod.auto_destroy is True


class TestLoadConfig:
    def test_loads_from_toml(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[server]\nbase_url = "http://10.0.0.1:9000"\napi_key = "test-key"\n'
            "[generation]\nbatch_size = 4\n"
        )
        config = load_config(cfg_file)
        assert config.server.base_url == "http://10.0.0.1:9000"
        assert config.server.api_key == "test-key"
        assert config.generation.batch_size == 4

    def test_falls_back_to_defaults(self, tmp_path: Path):
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.server.base_url == "http://127.0.0.1:8001"

    def test_env_overrides(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setenv("ACESTEP_API_KEY", "env-key")
        monkeypatch.setenv("RUNPOD_API_KEY", "rp-key")
        monkeypatch.setenv("ACESTEP_INSTALL_DIR", "/opt/acestep")

        config = load_config(tmp_path / "nonexistent.toml")
        assert config.server.api_key == "env-key"
        assert config.runpod.api_key == "rp-key"
        assert config.acestep.install_dir == "/opt/acestep"

    def test_env_overrides_toml_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[server]\napi_key = "toml-key"\n')
        monkeypatch.setenv("ACESTEP_API_KEY", "env-key")

        config = load_config(cfg_file)
        assert config.server.api_key == "env-key"
