import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.subtitle import SubtitleDocument, format_srt_time, parse_srt_time, wrap_subtitle_text


SRT = """1\r
00:00:00,000 --> 00:00:02,000\r
Day la mot cau subtitle kha dai can xuong dong\r
\r
2\r
00:00:01,900 --> 00:00:02,100\r
Nhanh\r
"""


class SubtitleTests(unittest.TestCase):
    def test_parses_and_serializes_crlf_srt(self):
        document = SubtitleDocument.from_srt(SRT)
        self.assertEqual(len(document.entries), 2)
        self.assertEqual(document.entries[0].start_ms, 0)
        self.assertIn("00:00:00,000 --> 00:00:02,000", document.to_srt())

    def test_updates_replaces_and_saves_text(self):
        document = SubtitleDocument.from_srt(SRT)
        document.update_text(1, "Xin chao ban")
        self.assertEqual(document.replace_text("ban", "Bạn"), 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "edited.srt"
            document.save(output)
            loaded = SubtitleDocument.load(output)
        self.assertEqual(loaded.entries[0].text, "Xin chao Bạn")

    def test_wraps_text_to_two_balanced_lines(self):
        wrapped = wrap_subtitle_text("Mot cau rat dai can duoc chia thanh hai dong de doc", 24, 2)
        self.assertEqual(len(wrapped.splitlines()), 2)

    def test_reports_overlap_speed_and_short_duration(self):
        issues = SubtitleDocument.from_srt(SRT).validate(max_chars_per_line=20)
        codes = {issue.code for issue in issues}
        self.assertIn("overlap", codes)
        self.assertIn("too_short", codes)
        self.assertIn("reading_too_fast", codes)
        self.assertIn("line_too_long", codes)

    def test_timestamp_round_trip(self):
        self.assertEqual(parse_srt_time("00:01:23,456"), 83_456)
        self.assertEqual(format_srt_time(83_456), "00:01:23,456")


if __name__ == "__main__":
    unittest.main()
