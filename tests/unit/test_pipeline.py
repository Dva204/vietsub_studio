import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.glossary import ShopProfileRepository
from core.pipeline import PipelineConfig, PipelineProcessors
from core.project_queue import ProjectQueue
from core.queue_runner import QueueRunner
from utils.db import Database


class FakeLocalization:
    def localize_srt(self, source_path, **kwargs):
        output = Path(kwargs["output_path"])
        output.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8"
        )
        return {
            "success": True,
            "output_path": str(output),
            "review_issues": 0,
            "memory_hits": 0,
            "requires_review": False,
        }


class PipelineTests(unittest.TestCase):
    def test_passes_model_root_only_to_transcriber(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = Database(root / "app.db")
            database.initialize()
            profile_id = ShopProfileRepository(database).create("Shop")
            queue = ProjectQueue(database)
            project_id = queue.create_project("Project", str(root / "output"), profile_id)
            job_id = queue.add_job(project_id, "url", "https://example.com/video")
            downloaded = root / "downloaded.mp4"
            model_root = root / "models"
            received = {}

            def strict_download(*, url, output_path, progress_callback, cancel_flag):
                downloaded.write_bytes(b"video")
                return {"success": True, "filepath": str(downloaded), "title": "Video"}

            def strict_transcribe(
                *, video_path, language, model_size, progress_callback, cancel_flag, model_dir
            ):
                received["model_dir"] = model_dir
                srt = root / "source.srt"
                srt.write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
                )
                return {"success": True, "srt_path": str(srt), "segment_count": 1}

            processors = PipelineProcessors(
                queue,
                PipelineConfig(model_root=str(model_root)),
                localization_service=FakeLocalization(),
                download_func=strict_download,
                transcribe_func=strict_transcribe,
            )
            runner = QueueRunner(queue, processors.as_dict())
            self.assertTrue(runner.run_once(project_id))
            self.assertTrue(runner.run_once(project_id))
            self.assertEqual(received["model_dir"], str(model_root))
            self.assertEqual(queue.get_job(job_id)["current_step"], "translate")

    def test_file_job_runs_end_to_end_without_ui(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_video = root / "input.mp4"
            source_video.write_bytes(b"fake-video")
            database = Database(root / "app.db")
            database.initialize()
            profile_id = ShopProfileRepository(database).create("Shop")
            queue = ProjectQueue(database)
            project_id = queue.create_project("Project", str(root / "output"), profile_id)
            job_id = queue.add_job(project_id, "file", str(source_video))

            def fake_transcribe(**kwargs):
                srt = Path(kwargs["video_path"]).with_suffix(".srt")
                srt.write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
                )
                return {"success": True, "srt_path": str(srt), "segment_count": 1}

            def fake_render(video, subtitle, output, **kwargs):
                shutil.copy2(video, output)
                return {"success": True, "output_path": output}

            processors = PipelineProcessors(
                queue,
                localization_service=FakeLocalization(),
                transcribe_func=fake_transcribe,
                export_video_func=fake_render,
            )
            runner = QueueRunner(queue, processors.as_dict())

            self.assertEqual(runner.run_until_idle(project_id), 4)
            self.assertEqual(queue.get_job(job_id)["status"], "completed")
            package = [
                item for item in queue.list_artifacts(job_id)
                if item["artifact_type"] == "package"
            ][0]
            self.assertTrue(Path(package["path"]).is_dir())
            self.assertTrue((Path(package["path"]) / "project.json").is_file())


if __name__ == "__main__":
    unittest.main()
