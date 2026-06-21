import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.audio_preprocessor import SPEECH_FILTER, prepare_speech_audio


class AudioPreprocessorTests(unittest.TestCase):
    def test_builds_normalized_mono_16khz_wav(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "video.mp4"
            output = Path(temp_dir) / "speech.wav"
            source.touch()

            def fake_run(command, **kwargs):
                Path(command[-1]).touch()
                return SimpleNamespace(returncode=0, stderr="")

            with patch("core.audio_preprocessor.shutil.which", return_value="ffmpeg"):
                with patch("core.audio_preprocessor.subprocess.run", side_effect=fake_run) as run:
                    result = prepare_speech_audio(source, output)

        self.assertTrue(result["success"])
        command = run.call_args.args[0]
        self.assertIn("16000", command)
        self.assertIn(SPEECH_FILTER, command)
        self.assertEqual(command[-1], str(output.resolve()))

    def test_reports_missing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "video.mp4"
            source.touch()
            with patch("core.audio_preprocessor.shutil.which", return_value=None):
                result = prepare_speech_audio(source, Path(temp_dir) / "speech.wav")

        self.assertFalse(result["success"])
        self.assertIn("FFmpeg", result["error"])


if __name__ == "__main__":
    unittest.main()
