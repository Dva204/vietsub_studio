import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.backend import VietDubBackend
from core.subtitle import SubtitleIssue


class UiContractTests(unittest.TestCase):
    def test_review_edit_and_approve_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend = VietDubBackend(root / "data")
            backend.initialize()
            shop_id = backend.create_shop("Shop", source_language="en")
            project_id = backend.create_project("Project", shop_id)
            video = root / "video.mp4"
            video.touch()
            job_id = backend.queue.add_job(project_id, "file", str(video))

            source_srt = root / "source.srt"
            source_srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
            )
            translated_srt = root / "translated.srt"
            translated_srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
            )

            backend.queue.claim_next_job(project_id)
            backend.queue.complete_current_step(job_id, str(video))
            backend.queue.claim_next_job(project_id)
            backend.queue.add_artifact(job_id, "source_srt", str(source_srt))
            backend.queue.complete_current_step(job_id, str(source_srt))
            backend.queue.claim_next_job(project_id)
            backend.queue.add_artifact(job_id, "translated_srt", str(translated_srt))
            backend.review.replace_issues(
                job_id,
                [SubtitleIssue(1, "same_as_source", "Ban dich giong cau nguon")],
            )
            backend.queue.complete_current_step(job_id, str(translated_srt))

            workspace = backend.review_workspace(job_id)
            self.assertEqual(workspace["entries"][0]["source_text"], "Hello")
            self.assertEqual(len(workspace["review_issues"]), 1)

            updated = backend.update_subtitle_text(job_id, 1, "Xin chao")
            self.assertEqual(updated["issues"], [])
            remembered = backend.approve_job(job_id)

            self.assertEqual(remembered, 1)
            self.assertEqual(backend.queue.get_job(job_id)["current_step"], "export")
            self.assertEqual(backend.queue.get_job(job_id)["status"], "pending")


if __name__ == "__main__":
    unittest.main()
