"""Response models for ACE-Step API results."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskSubmission(BaseModel):
    """Response from POST /release_task."""

    task_id: str
    status: str = "queued"
    queue_position: int = 0


class AudioResult(BaseModel):
    """A single audio file from a completed generation."""

    file: str = Field(description="Remote path to the audio file on the server")
    status: int = Field(description="0=running, 1=succeeded, 2=failed")
    prompt: str = ""
    lyrics: str = ""
    metas: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Parsed result from POST /query_result for a single task."""

    task_id: str
    status: int = Field(description="0=running, 1=succeeded, 2=failed")
    progress_text: str = ""
    audios: list[AudioResult] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self.status == 0

    @property
    def is_succeeded(self) -> bool:
        return self.status == 1

    @property
    def is_failed(self) -> bool:
        return self.status == 2

    @classmethod
    def from_api_response(cls, item: dict[str, Any]) -> TaskResult:
        """Parse a single item from the /query_result response.

        The `result` field is double-encoded JSON -- a JSON string inside the
        response JSON. We parse it here into AudioResult objects.
        """
        task_id = item["task_id"]
        status = item.get("status", 0)
        progress_text = item.get("progress_text", "") or ""

        result_raw = item.get("result", "[]")
        if isinstance(result_raw, str):
            try:
                result_data = json.loads(result_raw)
            except (json.JSONDecodeError, TypeError):
                result_data = []
        else:
            result_data = result_raw if isinstance(result_raw, list) else []

        audios = []
        error = None
        for entry in result_data:
            if isinstance(entry, dict):
                if entry.get("error"):
                    error = entry["error"]
                audios.append(
                    AudioResult(
                        file=entry.get("file", ""),
                        status=entry.get("status", status),
                        prompt=entry.get("prompt", ""),
                        lyrics=entry.get("lyrics", ""),
                        metas=entry.get("metas", {}),
                    )
                )

        return cls(
            task_id=task_id,
            status=status,
            progress_text=progress_text,
            audios=audios,
            error=error,
        )
