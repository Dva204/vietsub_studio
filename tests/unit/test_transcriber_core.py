import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.transcriber import (
    RecognizedSegment,
    _find_rescue_ranges,
    _merge_rescue_segments,
    _seconds_to_srt_time,
    transcribe_video,
)


class TranscriberCoreTests(unittest.TestCase):
    def test_formats_timestamp_with_rounding(self):
        self.assertEqual(_seconds_to_srt_time(125.4), "00:02:05,400")
        self.assertEqual(_seconds_to_srt_time(0.9996), "00:00:01,000")

    def test_rejects_missing_video_before_loading_model(self):
        result = transcribe_video("missing.mp4")
        self.assertFalse(result["success"])
        self.assertIn("khong ton tai", result["error"])

    def test_auto_language_uses_whisper_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "video.mp4"
            video.touch()
            model = SimpleNamespace()
            calls = []

            def transcribe(path, **options):
                calls.append(options)
                segment = SimpleNamespace(start=0.0, end=1.0, text="Hello")
                info = SimpleNamespace(duration=1.0, language="en")
                return [segment], info

            model.transcribe = transcribe
            config = SimpleNamespace(using_gpu=False)
            with patch("core.transcriber.prepare_speech_audio", return_value={"success": True}):
                with patch("core.transcriber.load_whisper_model", return_value=(model, config)):
                    result = transcribe_video(str(video), language="Tu dong")

        self.assertTrue(result["success"])
        self.assertEqual(result["detected_language"], "en")
        self.assertNotIn("language", calls[0])
        self.assertTrue(calls[0]["word_timestamps"])

    def test_rescue_replaces_low_confidence_segment(self):
        primary = [RecognizedSegment(0.0, 5.0, "wrong", -1.1, 0.1)]
        rescue = [RecognizedSegment(0.0, 5.0, "correct sentence", -0.2, 0.1)]
        ranges = _find_rescue_ranges(primary, 5.0)

        merged, rescued = _merge_rescue_segments(primary, rescue, ranges)

        self.assertEqual(rescued, 1)
        self.assertEqual([item.text for item in merged], ["correct sentence"])

    def test_keeps_primary_when_rescue_confidence_is_too_low(self):
        primary = [RecognizedSegment(0.0, 5.0, "original", -1.1, 0.1)]
        rescue = [RecognizedSegment(0.0, 5.0, "hallucination", -1.5, 0.1)]

        merged, rescued = _merge_rescue_segments(primary, rescue, [(0.0, 5.0)])

        self.assertEqual(rescued, 0)
        self.assertEqual([item.text for item in merged], ["original"])

    def test_transcribe_video_runs_rescue_pass_for_suspicious_segment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "video.mp4"
            video.touch()
            calls = []

            class FakeModel:
                def transcribe(self, path, **options):
                    calls.append(options)
                    info = SimpleNamespace(duration=5.0, language="zh")
                    if options["vad_filter"]:
                        segment = SimpleNamespace(
                            start=0.0,
                            end=5.0,
                            text="wrong",
                            avg_logprob=-1.2,
                            no_speech_prob=0.1,
                        )
                    else:
                        segment = SimpleNamespace(
                            start=0.0,
                            end=5.0,
                            text="correct sentence",
                            avg_logprob=-0.2,
                            no_speech_prob=0.1,
                        )
                    return [segment], info

            config = SimpleNamespace(using_gpu=False)
            with patch("core.transcriber.prepare_speech_audio", return_value={"success": True}):
                with patch(
                    "core.transcriber.load_whisper_model",
                    return_value=(FakeModel(), config),
                ):
                    result = transcribe_video(str(video), language="Tu dong", model_size="small")

            output = Path(result["srt_path"]).read_text(encoding="utf-8")

        self.assertTrue(result["success"])
        self.assertEqual(result["rescued_segments"], 1)
        self.assertEqual([item["vad_filter"] for item in calls], [True, False])
        self.assertIn("correct sentence", output)


if __name__ == "__main__":
    unittest.main()
