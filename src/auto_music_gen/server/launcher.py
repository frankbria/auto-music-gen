"""ACE-Step server subprocess launcher and lifecycle management."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class ServerLauncher:
    """Manage launching and monitoring an ACE-Step API server subprocess."""

    def __init__(self, acestep_dir: Path, port: int = 8001) -> None:
        self.acestep_dir = acestep_dir
        self.port = port
        self._process: subprocess.Popen | None = None

    @property
    def is_launched(self) -> bool:
        """Whether we launched and manage a running subprocess."""
        return self._process is not None and self._process.poll() is None

    def is_running(self, base_url: str) -> bool:
        """Check if ACE-Step server is accessible via health check.

        Args:
            base_url: Root URL of the server (e.g. ``http://127.0.0.1:8001``).

        Returns:
            ``True`` if the health endpoint responds, ``False`` on any
            connection error.
        """
        try:
            response = httpx.get(f"{base_url}/health", timeout=5.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def launch(self) -> None:
        """Launch ACE-Step server as a subprocess.

        Runs ``uv run acestep-api`` inside *acestep_dir*.  Standard output
        and standard error are redirected to ``subprocess.DEVNULL`` so they
        do not clutter the parent process output.
        """
        self._process = subprocess.Popen(
            ["uv", "run", "acestep-api"],
            cwd=self.acestep_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Launched ACE-Step server (pid=%s)", self._process.pid)

    def wait_until_ready(self, base_url: str, timeout: float = 120) -> bool:
        """Poll the health endpoint every 2 seconds until the server is ready.

        Args:
            base_url: Root URL of the server.
            timeout: Maximum seconds to wait before giving up.

        Returns:
            ``True`` if the server became ready within *timeout*, ``False``
            otherwise.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_running(base_url):
                return True
            time.sleep(2)
        return False

    def shutdown(self) -> None:
        """Gracefully stop the server subprocess.

        Sends ``SIGTERM`` and waits up to 10 seconds.  If the process does
        not exit in time it is killed with ``SIGKILL``.
        """
        if self._process is None:
            return

        logger.info("Shutting down ACE-Step server (pid=%s)", self._process.pid)
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Server did not stop in time, sending SIGKILL")
            self._process.kill()
            self._process.wait()

        self._process = None
