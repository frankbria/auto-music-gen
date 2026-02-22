"""Tests for RunPodClient -- pod lifecycle + MusicGenClient protocol methods."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from auto_music_gen.client.runpod import RunPodClient
from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import TaskResult, TaskSubmission

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POD_ID = "pod-abc123"
BASE_URL = f"https://{POD_ID}-8001.proxy.runpod.net"


@pytest.fixture()
def client() -> RunPodClient:
    """A RunPodClient with a mocked runpod.api_key, no real API calls."""
    with patch("auto_music_gen.client.runpod.runpod") as _mock:
        c = RunPodClient(api_key="rp_test_key")
    yield c
    c.close()


@pytest.fixture()
def ready_client() -> RunPodClient:
    """A RunPodClient that already has a pod running (base_url set)."""
    with patch("auto_music_gen.client.runpod.runpod"):
        c = RunPodClient(api_key="rp_test_key")
    c._pod_id = POD_ID
    c._base_url = BASE_URL
    yield c
    c.close()


# ---------------------------------------------------------------------------
# __init__ / api_key
# ---------------------------------------------------------------------------


def test_init_sets_api_key() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        RunPodClient(api_key="rp_test_key_123")
    assert mock_runpod.api_key == "rp_test_key_123"


def test_init_defaults() -> None:
    with patch("auto_music_gen.client.runpod.runpod"):
        c = RunPodClient(api_key="k")
    assert c.gpu_type == "NVIDIA GeForce RTX 4090"
    assert c.template_id == ""
    assert c.volume_id == ""
    assert c._pod_id is None
    assert c._base_url is None
    c.close()


# ---------------------------------------------------------------------------
# create_pod
# ---------------------------------------------------------------------------


def test_create_pod_calls_runpod_and_stores_pod_id() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        mock_runpod.create_pod.return_value = {"id": POD_ID}
        c = RunPodClient(api_key="rp_key")
        result = c.create_pod()

    assert result == POD_ID
    assert c._pod_id == POD_ID
    mock_runpod.create_pod.assert_called_once()
    call_kwargs = mock_runpod.create_pod.call_args.kwargs
    assert call_kwargs["gpu_type_id"] == "NVIDIA GeForce RTX 4090"
    assert call_kwargs["ports"] == "8001/http"
    c.close()


def test_create_pod_with_template_and_volume() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        mock_runpod.create_pod.return_value = {"id": POD_ID}
        c = RunPodClient(
            api_key="rp_key", template_id="tpl-xyz", volume_id="vol-789"
        )
        c.create_pod()

    call_kwargs = mock_runpod.create_pod.call_args.kwargs
    assert call_kwargs["template_id"] == "tpl-xyz"
    assert call_kwargs["volume_id"] == "vol-789"
    assert call_kwargs["volume_in_gb"] == 50
    c.close()


def test_create_pod_without_template_or_volume() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        mock_runpod.create_pod.return_value = {"id": POD_ID}
        c = RunPodClient(api_key="rp_key")
        c.create_pod()

    call_kwargs = mock_runpod.create_pod.call_args.kwargs
    assert "template_id" not in call_kwargs
    assert "volume_id" not in call_kwargs
    c.close()


# ---------------------------------------------------------------------------
# wait_for_pod
# ---------------------------------------------------------------------------


def test_wait_for_pod_returns_url_when_running() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        mock_runpod.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"uptimeInSeconds": 10},
        }
        c = RunPodClient(api_key="rp_key")
        c._pod_id = POD_ID

        url = c.wait_for_pod(timeout=10)

    assert url == BASE_URL
    assert c._base_url == BASE_URL
    c.close()


def test_wait_for_pod_raises_timeout() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        mock_runpod.get_pod.return_value = {
            "desiredStatus": "PENDING",
            "runtime": None,
        }
        c = RunPodClient(api_key="rp_key")
        c._pod_id = POD_ID

        with pytest.raises(TimeoutError, match="did not start"):
            c.wait_for_pod(timeout=0.01)
    c.close()


def test_wait_for_pod_raises_when_no_pod_created() -> None:
    with patch("auto_music_gen.client.runpod.runpod"):
        c = RunPodClient(api_key="rp_key")

    with pytest.raises(RuntimeError, match="No pod created"):
        c.wait_for_pod()
    c.close()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@respx.mock
def test_health_check_returns_true_on_200(ready_client: RunPodClient) -> None:
    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    assert ready_client.health_check() is True


@respx.mock
def test_health_check_returns_false_on_connection_error(ready_client: RunPodClient) -> None:
    respx.get(f"{BASE_URL}/health").mock(side_effect=httpx.ConnectError("refused"))
    assert ready_client.health_check() is False


@respx.mock
def test_health_check_returns_false_on_timeout(ready_client: RunPodClient) -> None:
    respx.get(f"{BASE_URL}/health").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    assert ready_client.health_check() is False


def test_health_check_returns_false_when_no_base_url(client: RunPodClient) -> None:
    assert client.health_check() is False


# ---------------------------------------------------------------------------
# submit_task
# ---------------------------------------------------------------------------


@respx.mock
def test_submit_task_sends_payload_and_parses_response(ready_client: RunPodClient) -> None:
    request = GenerationRequest(prompt="upbeat pop song", bpm=120)

    expected_response = {
        "data": {"task_id": "task-001", "status": "queued", "queue_position": 1},
        "code": 200,
        "error": None,
    }
    route = respx.post(f"{BASE_URL}/release_task").mock(
        return_value=httpx.Response(200, json=expected_response)
    )

    result = ready_client.submit_task(request)

    assert isinstance(result, TaskSubmission)
    assert result.task_id == "task-001"
    assert result.status == "queued"
    assert result.queue_position == 1

    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body["prompt"] == "upbeat pop song"
    assert sent_body["bpm"] == 120


def test_submit_task_raises_when_pod_not_ready(client: RunPodClient) -> None:
    request = GenerationRequest(prompt="test")
    with pytest.raises(RuntimeError, match="Pod not ready"):
        client.submit_task(request)


# ---------------------------------------------------------------------------
# poll_result
# ---------------------------------------------------------------------------


@respx.mock
def test_poll_result_parses_double_encoded_json(ready_client: RunPodClient) -> None:
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
                "task_id": "task-001",
                "status": 1,
                "progress_text": "100%",
                "result": inner_result,
            }
        ],
        "code": 200,
        "error": None,
    }
    route = respx.post(f"{BASE_URL}/query_result").mock(
        return_value=httpx.Response(200, json=response_data)
    )

    result = ready_client.poll_result("task-001")

    assert isinstance(result, TaskResult)
    assert result.task_id == "task-001"
    assert result.status == 1
    assert result.is_succeeded is True
    assert len(result.audios) == 1
    assert result.audios[0].file == "/output/song_0.mp3"

    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"task_id_list": ["task-001"]}


def test_poll_result_raises_when_pod_not_ready(client: RunPodClient) -> None:
    with pytest.raises(RuntimeError, match="Pod not ready"):
        client.poll_result("task-001")


# ---------------------------------------------------------------------------
# download_audio
# ---------------------------------------------------------------------------


@respx.mock
def test_download_audio_streams_to_file(
    ready_client: RunPodClient, tmp_path: Path
) -> None:
    audio_bytes = b"\xff\xfb\x90\x00" * 256
    remote_path = "/output/song_0.mp3"
    local_file = tmp_path / "song_0.mp3"

    respx.get(f"{BASE_URL}/v1/audio", params={"path": remote_path}).mock(
        return_value=httpx.Response(200, content=audio_bytes)
    )

    returned_path = ready_client.download_audio(remote_path, local_file)

    assert returned_path == local_file
    assert local_file.exists()
    assert local_file.read_bytes() == audio_bytes


@respx.mock
def test_download_audio_creates_parent_directories(
    ready_client: RunPodClient, tmp_path: Path
) -> None:
    audio_bytes = b"\xff\xfb\x90\x00" * 64
    remote_path = "/output/song_0.mp3"
    local_file = tmp_path / "nested" / "dir" / "song_0.mp3"

    respx.get(f"{BASE_URL}/v1/audio", params={"path": remote_path}).mock(
        return_value=httpx.Response(200, content=audio_bytes)
    )

    returned_path = ready_client.download_audio(remote_path, local_file)

    assert returned_path == local_file
    assert local_file.exists()


def test_download_audio_raises_when_pod_not_ready(
    client: RunPodClient, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="Pod not ready"):
        client.download_audio("/output/song.mp3", tmp_path / "song.mp3")


# ---------------------------------------------------------------------------
# destroy_pod
# ---------------------------------------------------------------------------


def test_destroy_pod_calls_terminate_and_clears_state() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        c = RunPodClient(api_key="rp_key")
        c._pod_id = POD_ID
        c._base_url = BASE_URL

        c.destroy_pod()

    mock_runpod.terminate_pod.assert_called_once_with(POD_ID)
    assert c._pod_id is None
    assert c._base_url is None
    c.close()


def test_destroy_pod_noop_when_no_pod() -> None:
    with patch("auto_music_gen.client.runpod.runpod") as mock_runpod:
        c = RunPodClient(api_key="rp_key")
        c.destroy_pod()

    mock_runpod.terminate_pod.assert_not_called()
    c.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager() -> None:
    with patch("auto_music_gen.client.runpod.runpod"):
        with RunPodClient(api_key="rp_key") as c:
            assert c._http is not None


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_runpod_client_implements_protocol() -> None:
    from auto_music_gen.client.base import MusicGenClient

    with patch("auto_music_gen.client.runpod.runpod"):
        c = RunPodClient(api_key="rp_key")
    assert isinstance(c, MusicGenClient)
    c.close()
