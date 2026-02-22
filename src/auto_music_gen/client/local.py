"""Local HTTP client for ACE-Step API using httpx."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import TaskResult, TaskSubmission


class LocalClient:
    """Synchronous HTTP client for a local ACE-Step API server.

    Implements the MusicGenClient protocol using httpx.Client.
    All API responses are expected in the envelope format:
        {"data": ..., "code": 200, "error": null}
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8001", api_key: str = "") -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(base_url=base_url, headers=headers)

    def health_check(self) -> bool:
        """GET /health -- returns True on 200, False on connection error."""
        try:
            resp = self._client.get("/health")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    def submit_task(self, request: GenerationRequest) -> TaskSubmission:
        """POST /release_task with generation parameters.

        Returns a TaskSubmission parsed from the response envelope's ``data`` field.
        """
        resp = self._client.post("/release_task", json=request.to_api_dict())
        resp.raise_for_status()
        data = self._unwrap(resp)
        return TaskSubmission.model_validate(data)

    def poll_result(self, task_id: str) -> TaskResult:
        """POST /query_result to check task progress.

        The response ``data`` is a list; we take the first item and parse it
        via ``TaskResult.from_api_response`` which handles the double-encoded
        ``result`` field.
        """
        resp = self._client.post("/query_result", json={"task_id_list": [task_id]})
        resp.raise_for_status()
        data = self._unwrap(resp)
        item = data[0]
        return TaskResult.from_api_response(item)

    def download_audio(self, remote_path: str, local_path: Path) -> Path:
        """GET /v1/audio?path=<encoded> with streaming, writing chunks to *local_path*.

        Returns the resolved *local_path*.
        """
        encoded = quote(remote_path, safe="")
        with self._client.stream("GET", f"/v1/audio?path={encoded}") as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        return local_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unwrap(resp: httpx.Response) -> Any:
        """Extract the ``data`` field from the API response envelope."""
        envelope = resp.json()
        return envelope["data"]

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def __enter__(self) -> LocalClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
