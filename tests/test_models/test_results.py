"""Tests for API result models."""

import json

from auto_music_gen.models.results import AudioResult, TaskResult, TaskSubmission


class TestTaskSubmission:
    def test_basic(self):
        sub = TaskSubmission(task_id="abc-123", status="queued", queue_position=1)
        assert sub.task_id == "abc-123"
        assert sub.status == "queued"
        assert sub.queue_position == 1

    def test_defaults(self):
        sub = TaskSubmission(task_id="abc-123")
        assert sub.status == "queued"
        assert sub.queue_position == 0


class TestAudioResult:
    def test_basic(self):
        ar = AudioResult(file="/audio/sample_1.mp3", status=1)
        assert ar.file == "/audio/sample_1.mp3"
        assert ar.status == 1


class TestTaskResult:
    def test_status_properties(self):
        assert TaskResult(task_id="t1", status=0).is_running
        assert TaskResult(task_id="t1", status=1).is_succeeded
        assert TaskResult(task_id="t1", status=2).is_failed

    def test_from_api_response_succeeded(self):
        result_data = [
            {
                "file": "/outputs/sample_1.mp3",
                "wave": "",
                "status": 1,
                "create_time": 1700000000,
                "prompt": "A chill beat",
                "lyrics": "",
                "metas": {"bpm": 90, "duration": 120.0},
            }
        ]
        item = {
            "task_id": "task-001",
            "result": json.dumps(result_data),
            "status": 1,
            "progress_text": "",
        }
        tr = TaskResult.from_api_response(item)
        assert tr.task_id == "task-001"
        assert tr.is_succeeded
        assert len(tr.audios) == 1
        assert tr.audios[0].file == "/outputs/sample_1.mp3"
        assert tr.audios[0].metas["bpm"] == 90

    def test_from_api_response_running(self):
        item = {
            "task_id": "task-002",
            "result": json.dumps([{"file": "", "status": 0, "create_time": 1700000000}]),
            "status": 0,
            "progress_text": "Inference step 3/8",
        }
        tr = TaskResult.from_api_response(item)
        assert tr.is_running
        assert tr.progress_text == "Inference step 3/8"

    def test_from_api_response_failed_with_error(self):
        item = {
            "task_id": "task-003",
            "result": json.dumps([{"file": "", "status": 2, "error": "OOM"}]),
            "status": 2,
        }
        tr = TaskResult.from_api_response(item)
        assert tr.is_failed
        assert tr.error == "OOM"

    def test_from_api_response_empty_result(self):
        item = {"task_id": "task-004", "result": "[]", "status": 0}
        tr = TaskResult.from_api_response(item)
        assert tr.is_running
        assert len(tr.audios) == 0

    def test_from_api_response_malformed_result(self):
        item = {"task_id": "task-005", "result": "not-json", "status": 0}
        tr = TaskResult.from_api_response(item)
        assert len(tr.audios) == 0

    def test_multiple_audios(self):
        result_data = [
            {"file": "/out/s1.mp3", "status": 1, "prompt": "test", "lyrics": "", "metas": {}},
            {"file": "/out/s2.mp3", "status": 1, "prompt": "test", "lyrics": "", "metas": {}},
        ]
        item = {
            "task_id": "task-006",
            "result": json.dumps(result_data),
            "status": 1,
        }
        tr = TaskResult.from_api_response(item)
        assert len(tr.audios) == 2
        assert tr.audios[0].file == "/out/s1.mp3"
        assert tr.audios[1].file == "/out/s2.mp3"
