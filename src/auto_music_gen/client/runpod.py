"""RunPod GPU orchestration client for ACE-Step music generation."""

from __future__ import annotations

import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import runpod

from auto_music_gen.models.params import GenerationRequest
from auto_music_gen.models.results import TaskResult, TaskSubmission

GPU_OPTIONS: dict[str, dict[str, Any]] = {
    "RTX 4090": {"id": "NVIDIA GeForce RTX 4090", "price_hr": 0.69},
    "A100 80GB": {"id": "NVIDIA A100 80GB PCIe", "price_hr": 1.64},
    "H100": {"id": "NVIDIA H100 80GB HBM3", "price_hr": 3.89},
}


class RunPodClient:
    """Client that provisions a RunPod GPU pod and talks to the ACE-Step API on it.

    Implements the MusicGenClient protocol (health_check, submit_task,
    poll_result, download_audio) plus pod lifecycle methods (create_pod,
    wait_for_pod, wait_for_server, destroy_pod).
    """

    def __init__(
        self,
        api_key: str,
        gpu_type: str = "NVIDIA GeForce RTX 4090",
        template_id: str = "",
        volume_id: str = "",
    ) -> None:
        runpod.api_key = api_key
        self.gpu_type = gpu_type
        self.template_id = template_id
        self.volume_id = volume_id
        self._pod_id: str | None = None
        self._base_url: str | None = None
        self._http: httpx.Client = httpx.Client(timeout=30)

    # ------------------------------------------------------------------
    # Pod lifecycle
    # ------------------------------------------------------------------

    def create_pod(self) -> str:
        """Create a RunPod GPU pod. Returns pod_id."""
        pod_config: dict[str, Any] = {
            "name": "acestep-musicgen",
            "image_name": "acestep/acestep:latest",
            "gpu_type_id": self.gpu_type,
            "cloud_type": "SECURE",
            "ports": "8001/http",
            "container_disk_in_gb": 20,
        }
        if self.template_id:
            pod_config["template_id"] = self.template_id
        if self.volume_id:
            pod_config["volume_id"] = self.volume_id
            pod_config["volume_in_gb"] = 50

        pod = runpod.create_pod(**pod_config)
        self._pod_id = pod["id"]
        return self._pod_id

    def wait_for_pod(self, timeout: float = 300) -> str:
        """Wait for pod to reach RUNNING state. Returns the pod's base URL.

        Raises TimeoutError if the pod does not start within *timeout* seconds.
        """
        if not self._pod_id:
            raise RuntimeError("No pod created. Call create_pod first.")

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            pod = runpod.get_pod(self._pod_id)
            status = pod.get("desiredStatus", "")
            runtime = pod.get("runtime") or {}

            if status == "RUNNING" and runtime.get("uptimeInSeconds", 0) > 0:
                self._base_url = f"https://{self._pod_id}-8001.proxy.runpod.net"
                return self._base_url

            time.sleep(5)

        raise TimeoutError(f"Pod {self._pod_id} did not start within {timeout}s")

    def wait_for_server(self, timeout: float = 180) -> bool:
        """Wait for the ACE-Step HTTP server inside the pod to become ready."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.health_check():
                return True
            time.sleep(3)
        return False

    def destroy_pod(self) -> None:
        """Terminate and destroy the RunPod pod."""
        if self._pod_id:
            runpod.terminate_pod(self._pod_id)
            self._pod_id = None
            self._base_url = None

    # ------------------------------------------------------------------
    # MusicGenClient protocol methods
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """GET /health -- returns True on 200, False on connection/timeout error."""
        if not self._base_url:
            return False
        try:
            resp = self._http.get(f"{self._base_url}/health")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def submit_task(self, request: GenerationRequest) -> TaskSubmission:
        """POST /release_task with generation parameters.

        Returns a TaskSubmission parsed from the response envelope's ``data`` field.
        """
        if not self._base_url:
            raise RuntimeError("Pod not ready. Call create_pod + wait_for_pod first.")
        resp = self._http.post(
            f"{self._base_url}/release_task",
            json=request.to_api_dict(),
        )
        resp.raise_for_status()
        data = self._unwrap(resp)
        return TaskSubmission.model_validate(data)

    def poll_result(self, task_id: str) -> TaskResult:
        """POST /query_result to check task progress.

        The response ``data`` is a list; we take the first item and parse it
        via ``TaskResult.from_api_response`` which handles the double-encoded
        ``result`` field.
        """
        if not self._base_url:
            raise RuntimeError("Pod not ready.")
        resp = self._http.post(
            f"{self._base_url}/query_result",
            json={"task_id_list": [task_id]},
        )
        resp.raise_for_status()
        data = self._unwrap(resp)
        return TaskResult.from_api_response(data[0])

    def download_audio(self, remote_path: str, local_path: Path) -> Path:
        """GET /v1/audio?path=<encoded> with streaming, writing chunks to *local_path*.

        Returns the resolved *local_path*.
        """
        if not self._base_url:
            raise RuntimeError("Pod not ready.")
        encoded = urllib.parse.quote(remote_path, safe="")
        with self._http.stream("GET", f"{self._base_url}/v1/audio?path={encoded}") as resp:
            resp.raise_for_status()
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
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
        self._http.close()

    def __enter__(self) -> RunPodClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
