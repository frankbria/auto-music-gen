"""Protocol interface for music generation API clients."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import TaskResult, TaskSubmission


@runtime_checkable
class MusicGenClient(Protocol):
    """Protocol defining the interface for music generation API clients.

    Implementations must support health checking, task submission,
    result polling, and audio file download.
    """

    def health_check(self) -> bool: ...

    def submit_task(self, request: GenerationRequest) -> TaskSubmission: ...

    def poll_result(self, task_id: str) -> TaskResult: ...

    def download_audio(self, remote_path: str, local_path: Path) -> Path: ...
