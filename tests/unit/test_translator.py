import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core import translator as translator_module

SRT_CONTENT = """1\r
00:00:00,000 --> 00:00:01,000\r
你好\r
\r
2\r
00:00:01,000 --> 00:00:02,000\r
世界\r
"""


class FakeTranslator:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class TranslatorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.old_cache_file = translator_module.CACHE_FILE
        translator_module.CACHE_FILE = Path(self.temp_dir.name) / "cache.json"
        self.addCleanup(setattr, translator_module, "CACHE_FILE", self.old_cache_file)

    def _write_srt(self):
        path = Path(self.temp_dir.name) / "input.srt"
        path.write_text(SRT_CONTENT, encoding="utf-8")
        return path

    def test_translates_blocks_individually_to_avoid_context_bleeding(self):
        fake = FakeTranslator(["Xin chao", "The gioi"])

        result = translator_module.translate_srt(
            str(self._write_srt()), translator=fake, context_window=2
        )

        self.assertTrue(result["success"])
        output = Path(result["output_path"]).read_text(encoding="utf-8")
        self.assertIn("Xin chao", output)
        self.assertIn("The gioi", output)
        self.assertEqual(len(fake.calls), 2)
        self.assertNotIn("[[VDS_", fake.calls[0])

    def test_keeps_individual_results_in_their_original_timing(self):
        fake = FakeTranslator(["Xin chao", "The gioi"])

        result = translator_module.translate_srt(
            str(self._write_srt()), translator=fake, context_window=2
        )

        self.assertTrue(result["success"])
        output = Path(result["output_path"]).read_text(encoding="utf-8")
        self.assertIn("1\n00:00:00,000 --> 00:00:01,000\nXin chao", output)
        self.assertIn("2\n00:00:01,000 --> 00:00:02,000\nThe gioi", output)
        self.assertEqual(fake.calls, ["\u4f60\u597d", "\u4e16\u754c"])

    def test_retries_transient_errors(self):
        fake = FakeTranslator([
            RuntimeError("temporary"),
            "Xin chao",
            "The gioi",
        ])

        with self.assertLogs(level="WARNING") as logs:
            result = translator_module.translate_srt(
                str(self._write_srt()), translator=fake, context_window=2, max_retries=2
            )

        self.assertTrue(result["success"])
        self.assertEqual(len(fake.calls), 3)
        self.assertIn("temporary", logs.output[0])


if __name__ == "__main__":
    unittest.main()
