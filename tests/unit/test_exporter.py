import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.exporter import (
    SubtitleStyle,
    _build_subtitle_filter,
    _parse_progress,
    export_subtitled_video,
    get_subtitle_style,
)


class ExporterTests(unittest.TestCase):
    def test_builds_safe_subtitle_style(self):
        subtitle_filter = _build_subtitle_filter(
            SubtitleStyle(font_name="Arial,'Bad", font_size=22, margin_vertical=50)
        )
        self.assertIn("FontName=ArialBad", subtitle_filter)
        self.assertIn("FontSize=22", subtitle_filter)
        self.assertIn("MarginV=50", subtitle_filter)

    def test_parses_ffmpeg_progress(self):
        self.assertEqual(_parse_progress("out_time_us=5000000", 10), 50.0)
        self.assertEqual(_parse_progress("out_time=00:00:02.500000", 10), 25.0)
        self.assertIsNone(_parse_progress("speed=2x", 10))

    def test_provides_three_commercial_presets(self):
        self.assertGreater(get_subtitle_style("shorts").font_size, get_subtitle_style("compact").font_size)
        with self.assertRaises(ValueError):
            get_subtitle_style("unknown")

    def test_rejects_missing_video(self):
        result = export_subtitled_video("missing.mp4", "missing.srt")
        self.assertFalse(result["success"])
        self.assertIn("video khong ton tai", result["error"])

    def test_rejects_non_srt_subtitle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "video.mp4"
            subtitle = Path(temp_dir) / "subtitle.txt"
            video.touch()
            subtitle.touch()
            result = export_subtitled_video(str(video), str(subtitle))
        self.assertFalse(result["success"])
        self.assertIn(".srt", result["error"])


if __name__ == "__main__":
    unittest.main()
