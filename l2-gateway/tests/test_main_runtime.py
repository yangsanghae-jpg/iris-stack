import os
import unittest
from unittest.mock import patch

os.environ["IRIS_RUNTIME_PROFILE"] = "m2"
os.environ["IRIS_DEFAULT_MODEL"] = "qwen3.5:4b"
os.environ["IRIS_ALLOWED_MODELS"] = "qwen3.5:4b"
os.environ["IRIS_MODEL_NUM_CTX"] = "8192"
os.environ["IRIS_MODEL_NUM_PREDICT"] = "1024"
os.environ["IRIS_SEARCH_ENABLED"] = "false"
os.environ["IRIS_MEMORY_ENABLED"] = "false"
os.environ["IRIS_MEMORY_PROFILE_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app import main


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class MainRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def test_disallowed_model_is_rejected_before_ollama_call(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "qwen3:30b",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not allowed", response.json()["detail"])

    def test_ready_requires_configured_default_model(self):
        with patch.object(
            main.requests,
            "get",
            return_value=FakeResponse(
                {"models": [{"name": "qwen3.5:4b"}, {"name": "qwen3:30b"}]}
            ),
        ):
            response = self.client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available_models"], ["qwen3.5:4b"])

    def test_completion_payload_is_capped_by_m2_policy(self):
        with patch.object(
            main.requests,
            "post",
            return_value=FakeResponse(
                {"message": {"content": "ok"}, "done_reason": "stop"}
            ),
        ) as post, patch.object(main, "call_memory_writeback") as writeback:
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "qwen3.5:4b",
                    "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 4096,
                    "options": {"num_ctx": 32768},
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3.5:4b")
        self.assertEqual(payload["options"]["num_ctx"], 8192)
        self.assertEqual(payload["options"]["num_predict"], 1024)
        writeback.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
