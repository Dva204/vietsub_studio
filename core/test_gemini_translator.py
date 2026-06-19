import json
import os
import unittest
from unittest.mock import patch

from core.gemini_translator import translate_blocks


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


class GeminiTranslatorTests(unittest.TestCase):
    def test_translates_and_preserves_ids(self):
        response = json.dumps(
            [
                {"id": 1, "text": "Bạn uống cà phê thế nào?"},
                {"id": 2, "text": "Cho sữa và một viên đường."},
            ],
            ensure_ascii=False,
        )
        client = FakeClient([response])

        result = translate_blocks(
            [
                {"id": 1, "text": "How do you take it?"},
                {"id": 2, "text": "White with one sugar."},
            ],
            client=client,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["translated"], 2)
        self.assertEqual(result["blocks"][1]["text"], "Cho sữa và một viên đường.")

    def test_rejects_missing_ids(self):
        response = json.dumps([{"id": 1, "text": "Xin chào"}])
        client = FakeClient([response])

        with self.assertLogs(level="WARNING"):
            result = translate_blocks(
                [{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}],
                client=client,
                max_retries=1,
            )

        self.assertFalse(result["success"])
        self.assertIn("subtitle ID", result["error"])

    def test_retries_transient_error(self):
        response = json.dumps([{"id": "a", "text": "Xin chào"}])
        client = FakeClient([RuntimeError("temporary"), response])

        with self.assertLogs(level="WARNING"):
            result = translate_blocks(
                [{"id": "a", "text": "Hello"}],
                client=client,
                max_retries=2,
                retry_delay=0,
            )

        self.assertTrue(result["success"])
        self.assertEqual(len(client.models.calls), 2)

    def test_splits_large_input_into_batches(self):
        first = json.dumps([{"id": 1, "text": "Một"}, {"id": 2, "text": "Hai"}])
        second = json.dumps([{"id": 3, "text": "Ba"}])
        client = FakeClient([first, second])

        result = translate_blocks(
            [
                {"id": 1, "text": "One"},
                {"id": 2, "text": "Two"},
                {"id": 3, "text": "Three"},
            ],
            client=client,
            batch_size=2,
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(client.models.calls), 2)

    def test_requires_api_key_without_injected_client(self):
        with patch.dict(os.environ, {}, clear=True):
            result = translate_blocks([{"id": 1, "text": "Hello"}], api_key="")
        self.assertFalse(result["success"])
        self.assertIn("API key", result["error"])


if __name__ == "__main__":
    unittest.main()
