import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.package_exporter import export_package


class PackageExporterTests(unittest.TestCase):
    def test_exports_complete_atomic_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "source.mp4"
            video.write_bytes(b"video")
            subtitle = root / "translated.srt"
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8"
            )
            result = export_package(
                root / "output",
                "San pham: A?",
                source_video=video,
                translated_srt=subtitle,
                caption="Caption mau",
                metadata={"job_id": 1},
            )
            package = Path(result["package_path"])
            manifest = json.loads((package / "project.json").read_text(encoding="utf-8"))

            self.assertTrue(result["success"])
            self.assertTrue((package / "subtitle.vi.srt").is_file())
            self.assertTrue((package / "transcript.txt").is_file())
            self.assertTrue((package / "caption.txt").is_file())
            self.assertEqual(manifest["metadata"]["job_id"], 1)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["files"]))


if __name__ == "__main__":
    unittest.main()
