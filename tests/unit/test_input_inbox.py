import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.input_inbox import collect_inputs


class InputInboxTests(unittest.TestCase):
    def test_extracts_and_deduplicates_urls(self):
        result = collect_inputs(
            "Xem https://youtube.com/watch?v=abc&si=one va "
            "https://youtube.com/watch?v=abc&si=two"
        )
        self.assertEqual(len(result["items"]), 1)
        self.assertNotIn("si=", result["items"][0].source_value)

    def test_expands_video_directory_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.mp4").touch()
            (root / "b.mov").touch()
            (root / "note.txt").touch()
            result = collect_inputs(str(root))
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(item.source_type == "file" for item in result["items"]))

    def test_reports_invalid_input(self):
        result = collect_inputs("not a url or file")
        self.assertEqual(result["invalid"], ["not a url or file"])


if __name__ == "__main__":
    unittest.main()
