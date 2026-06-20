import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.tts import _srt_time_to_ms, generate_dubbed_audio


class TtsTests(unittest.TestCase):
    def test_converts_srt_time_to_milliseconds(self):
        self.assertEqual(_srt_time_to_ms("00:01:23,456"), 83_456)
        self.assertEqual(_srt_time_to_ms("00:00:01.5"), 1_500)

    def test_rejects_missing_srt(self):
        result = generate_dubbed_audio("missing.srt")
        self.assertFalse(result["success"])
        self.assertIn("khong ton tai", result["error"])

    def test_rejects_unknown_voice_before_loading_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            srt_path = Path(temp_dir) / "sample.srt"
            srt_path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nXin chao\n",
                encoding="utf-8",
            )
            result = generate_dubbed_audio(str(srt_path), voice_name="Unknown")

        self.assertFalse(result["success"])
        self.assertIn("khong hop le", result["error"])


if __name__ == "__main__":
    unittest.main()
