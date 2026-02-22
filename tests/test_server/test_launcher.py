"""Tests for server launcher lifecycle management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from auto_music_gen.server.launcher import ServerLauncher

BASE_URL = "http://127.0.0.1:8001"


@pytest.fixture()
def launcher(tmp_path: Path) -> ServerLauncher:
    """Return a ServerLauncher pointed at a temporary directory."""
    return ServerLauncher(acestep_dir=tmp_path, port=8001)


class TestIsRunning:
    def test_returns_false_on_connect_error(self, launcher: ServerLauncher):
        with patch.object(httpx, "get", side_effect=httpx.ConnectError("refused")):
            assert launcher.is_running(BASE_URL) is False

    def test_returns_true_on_200(self, launcher: ServerLauncher):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(httpx, "get", return_value=mock_response) as mock_get:
            assert launcher.is_running(BASE_URL) is True
            mock_get.assert_called_once_with(f"{BASE_URL}/health", timeout=5.0)

    def test_returns_false_on_non_200(self, launcher: ServerLauncher):
        mock_response = MagicMock()
        mock_response.status_code = 503
        with patch.object(httpx, "get", return_value=mock_response):
            assert launcher.is_running(BASE_URL) is False


class TestLaunch:
    @patch("auto_music_gen.server.launcher.subprocess.Popen")
    def test_calls_popen_with_correct_args(
        self, mock_popen: MagicMock, launcher: ServerLauncher
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        launcher.launch()

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["uv", "run", "acestep-api"]
        assert call_args[1]["cwd"] == launcher.acestep_dir

    @patch("auto_music_gen.server.launcher.subprocess.Popen")
    def test_stores_process_reference(
        self, mock_popen: MagicMock, launcher: ServerLauncher
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        launcher.launch()

        assert launcher._process is mock_proc


class TestWaitUntilReady:
    @patch("auto_music_gen.server.launcher.time.sleep")
    def test_succeeds_when_health_check_passes(
        self, mock_sleep: MagicMock, launcher: ServerLauncher
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(httpx, "get", return_value=mock_response):
            assert launcher.wait_until_ready(BASE_URL, timeout=10) is True
        mock_sleep.assert_not_called()

    @patch("auto_music_gen.server.launcher.time.sleep")
    @patch("auto_music_gen.server.launcher.time.monotonic")
    def test_returns_false_on_timeout(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
        launcher: ServerLauncher,
    ):
        # Simulate: first call sets deadline, subsequent calls exceed it
        mock_monotonic.side_effect = [0.0, 0.0, 3.0, 6.0, 11.0]
        with patch.object(httpx, "get", side_effect=httpx.ConnectError("refused")):
            assert launcher.wait_until_ready(BASE_URL, timeout=10) is False

    @patch("auto_music_gen.server.launcher.time.sleep")
    @patch("auto_music_gen.server.launcher.time.monotonic")
    def test_retries_before_success(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
        launcher: ServerLauncher,
    ):
        # Time sequence: deadline calc, first loop check, second loop check
        mock_monotonic.side_effect = [0.0, 0.0, 3.0]
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch.object(
            httpx,
            "get",
            side_effect=[httpx.ConnectError("refused"), mock_response],
        ):
            assert launcher.wait_until_ready(BASE_URL, timeout=10) is True
        assert mock_sleep.call_count == 1


class TestShutdown:
    def test_terminates_running_process(self, launcher: ServerLauncher):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        launcher._process = mock_proc

        launcher.shutdown()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=10)
        assert launcher._process is None

    def test_kills_on_timeout(self, launcher: ServerLauncher):
        import subprocess

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 10), None]
        launcher._process = mock_proc

        launcher.shutdown()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert launcher._process is None

    def test_noop_when_no_process(self, launcher: ServerLauncher):
        launcher.shutdown()  # Should not raise


class TestIsLaunched:
    def test_false_when_no_process(self, launcher: ServerLauncher):
        assert launcher.is_launched is False

    def test_true_when_process_running(self, launcher: ServerLauncher):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still running
        launcher._process = mock_proc

        assert launcher.is_launched is True

    def test_false_when_process_exited(self, launcher: ServerLauncher):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # Exited
        launcher._process = mock_proc

        assert launcher.is_launched is False
