import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.backend import VietDubBackend, _whisper_language_name


class BackendTests(unittest.TestCase):
    def test_maps_shop_language_to_whisper_language(self):
        self.assertEqual(_whisper_language_name("auto"), "Tu dong")
        self.assertEqual(_whisper_language_name("en"), "Tieng Anh")
        self.assertEqual(_whisper_language_name("zh-CN"), "Tieng Trung")
        self.assertEqual(_whisper_language_name("ja"), "Tieng Nhat")
        self.assertEqual(_whisper_language_name("ko"), "Tieng Han")

    def test_facade_creates_shop_project_and_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "video.mp4"
            video.touch()
            backend = VietDubBackend(root / "data")
            startup = backend.initialize()
            shop_id = backend.create_shop("Shop")
            self.assertEqual(backend.shops.get(shop_id)["whisper_model"], "small")
            project_id = backend.create_project("Project", shop_id)
            result = backend.add_inputs(project_id, [str(video), str(video), "invalid"])
            dashboard = backend.project_dashboard(project_id)

            self.assertEqual(startup["recovered_jobs"], 0)
            self.assertEqual(len(result["added"]), 1)
            self.assertEqual(len(dashboard["jobs"]), 1)
            self.assertEqual(result["invalid"], ["invalid"])


if __name__ == "__main__":
    unittest.main()
