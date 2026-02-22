"""Tests for LocalClient using respx to mock httpx requests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from auto_music_gen.client.local import LocalClient
from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import TaskResult, TaskSubmission

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_url() -> str:
    return "http://127.0.0.1:8001"


@pytest.fixture()
def client(base_url: str) -> LocalClient:
    c = LocalClient(base_url=base_url)
    yield c
    c.close()


@pytest.fixture()
def auth_client(base_url: str) -> LocalClient:
    c = LocalClient(base_url=base_url, api_key="test-secret-key")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@respx.mock
def test_health_check_returns_true_on_200(client: LocalClient, base_url: str) -> None:
    respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    assert client.health_check() is True


@respx.mock
def test_health_check_returns_false_on_connection_error(
    client: LocalClient, base_url: str
) -> None:
    respx.get(f"{base_url}/health").mock(side_effect=httpx.ConnectError("refused"))
    assert client.health_check() is False


# ---------------------------------------------------------------------------
# submit_task
# ---------------------------------------------------------------------------


@respx.mock
def test_submit_task_sends_payload_and_parses_response(
    client: LocalClient, base_url: str
) -> None:
    request = GenerationRequest(prompt="upbeat pop song", bpm=120)

    expected_response = {
        "data": {"task_id": "abc-123", "status": "queued", "queue_position": 1},
        "code": 200,
        "error": None,
    }

    route = respx.post(f"{base_url}/release_task").mock(
        return_value=httpx.Response(200, json=expected_response)
    )

    result = client.submit_task(request)

    assert isinstance(result, TaskSubmission)
    assert result.task_id == "abc-123"
    assert result.status == "queued"
    assert result.queue_position == 1

    # Verify the payload sent to the API
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body["prompt"] == "upbeat pop song"
    assert sent_body["bpm"] == 120


# ---------------------------------------------------------------------------
# poll_result
# ---------------------------------------------------------------------------


@respx.mock
def test_poll_result_handles_double_encoded_json(client: LocalClient, base_url: str) -> None:
    # The result field is a JSON string inside the JSON response
    inner_result = json.dumps([
        {
            "file": "/output/song_0.mp3",
            "status": 1,
            "prompt": "upbeat pop song",
            "lyrics": "",
            "metas": {},
        }
    ])

    response_data = {
        "data": [
            {
                "task_id": "abc-123",
                "status": 1,
                "progress_text": "100%",
                "result": inner_result,
            }
        ],
        "code": 200,
        "error": None,
    }

    route = respx.post(f"{base_url}/query_result").mock(
        return_value=httpx.Response(200, json=response_data)
    )

    result = client.poll_result("abc-123")

    assert isinstance(result, TaskResult)
    assert result.task_id == "abc-123"
    assert result.status == 1
    assert result.is_succeeded is True
    assert len(result.audios) == 1
    assert result.audios[0].file == "/output/song_0.mp3"

    # Verify the request payload
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"task_id_list": ["abc-123"]}


# ---------------------------------------------------------------------------
# download_audio
# ---------------------------------------------------------------------------


@respx.mock
def test_download_audio_streams_to_file(
    client: LocalClient, base_url: str, tmp_path: Path
) -> None:
    audio_bytes = b"\xff\xfb\x90\x00" * 256  # fake MP3 data
    remote_path = "/output/song_0.mp3"
    local_file = tmp_path / "song_0.mp3"

    respx.get(f"{base_url}/v1/audio", params={"path": remote_path}).mock(
        return_value=httpx.Response(200, content=audio_bytes)
    )

    returned_path = client.download_audio(remote_path, local_file)

    assert returned_path == local_file
    assert local_file.exists()
    assert local_file.read_bytes() == audio_bytes


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


@respx.mock
def test_auth_header_included_when_api_key_set(auth_client: LocalClient, base_url: str) -> None:
    route = respx.get(f"{base_url}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )

    auth_client.health_check()

    auth_header = route.calls[0].request.headers.get("authorization")
    assert auth_header == "Bearer test-secret-key"


@respx.mock
def test_auth_header_absent_when_api_key_empty(client: LocalClient, base_url: str) -> None:
    route = respx.get(f"{base_url}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )

    client.health_check()

    auth_header = route.calls[0].request.headers.get("authorization")
    assert auth_header is None


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@respx.mock
def test_context_manager(base_url: str) -> None:
    respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "ok"}))

    with LocalClient(base_url=base_url) as client:
        assert client.health_check() is True


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_local_client_implements_protocol() -> None:
    from auto_music_gen.client.base import MusicGenClient

    assert isinstance(LocalClient(base_url="http://localhost:8001"), MusicGenClient)
