import tempfile
import unittest
from pathlib import Path

from utils.db import Database
from core.project_queue import DuplicateJobError, ProjectQueue


class ProjectQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        root = Path(self.temp_dir.name)

        self.database = Database(root / "test.db")
        self.database.initialize()

        self.queue = ProjectQueue(self.database)
        self.output_dir = root / "output"

    def test_creates_and_reads_project(self):
        project_id = self.queue.create_project(
            name="Shop thoi trang",
            output_dir=str(self.output_dir),
        )

        project = self.queue.get_project(project_id)

        self.assertIsNotNone(project)
        self.assertEqual(project["id"], project_id)
        self.assertEqual(project["name"], "Shop thoi trang")
        self.assertEqual(project["output_dir"], str(self.output_dir))
        self.assertEqual(project["status"], "active")

    def test_returns_none_for_missing_project(self):
        project = self.queue.get_project(999)

        self.assertIsNone(project)

    def test_lists_newest_projects_first(self):
        first_id = self.queue.create_project(
            name="Project 1",
            output_dir=str(self.output_dir / "one"),
        )
        second_id = self.queue.create_project(
            name="Project 2",
            output_dir=str(self.output_dir / "two"),
        )

        projects = self.queue.list_projects()

        self.assertEqual(
            [project["id"] for project in projects],
            [second_id, first_id],
        )

    def test_rejects_empty_project_name(self):
        with self.assertRaises(ValueError):
            self.queue.create_project(
                name="   ",
                output_dir=str(self.output_dir),
            )

    def test_adds_job_steps_and_rejects_duplicate(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/video")

        self.assertEqual(len(self.queue.get_job_steps(job_id)), 5)
        self.assertEqual(self.queue.get_job(job_id)["current_step"], "acquire")
        with self.assertRaises(DuplicateJobError):
            self.queue.add_job(project_id, "url", "https://example.com/video")

    def test_lists_newest_jobs_first(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        first_id = self.queue.add_job(project_id, "url", "https://example.com/first")
        second_id = self.queue.add_job(project_id, "url", "https://example.com/second")

        jobs = self.queue.list_jobs(project_id)

        self.assertEqual([job["id"] for job in jobs], [second_id, first_id])

    def test_claim_fail_and_retry_job(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/video")

        claimed = self.queue.claim_next_job(project_id)
        self.assertEqual(claimed["id"], job_id)
        self.queue.fail_job(job_id, "network")
        self.assertEqual(self.queue.get_job(job_id)["status"], "failed")

        self.queue.retry_job(job_id)
        retried = self.queue.get_job(job_id)
        self.assertEqual(retried["status"], "pending")
        self.assertEqual(retried["retry_count"], 1)

    def test_recovers_interrupted_job(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/video")
        self.queue.claim_next_job(project_id)

        self.assertEqual(self.queue.recover_interrupted_jobs(), 1)
        self.assertEqual(self.queue.get_job(job_id)["status"], "pending")

    def test_reprocesses_completed_job_from_stt_and_keeps_source_video(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/video")
        video = self.output_dir / "source.mp4"
        source_srt = self.output_dir / "source.srt"
        self.queue.add_artifact(job_id, "source_video", str(video))
        self.queue.add_artifact(job_id, "source_srt", str(source_srt))
        self.queue.add_artifact(job_id, "package", str(self.output_dir / "package"))
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'completed', current_step = 'export', progress = 100 WHERE id = ?",
                (job_id,),
            )
            connection.execute(
                "UPDATE job_steps SET status = 'completed', progress = 100 WHERE job_id = ?",
                (job_id,),
            )

        self.queue.reprocess_job(job_id)

        job = self.queue.get_job(job_id)
        artifacts = self.queue.list_artifacts(job_id)
        steps = {item["step_name"]: item for item in self.queue.get_job_steps(job_id)}
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["current_step"], "transcribe")
        self.assertEqual([item["artifact_type"] for item in artifacts], ["source_video"])
        self.assertEqual(steps["acquire"]["status"], "completed")
        self.assertEqual(steps["transcribe"]["status"], "pending")

    def test_reexports_completed_job_without_removing_edited_subtitle(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/video")
        paths = {
            "source_video": self.output_dir / "source.mp4",
            "source_srt": self.output_dir / "source.srt",
            "translated_srt": self.output_dir / "subtitle.vi.srt",
            "subtitled_video": self.output_dir / "subtitled.mp4",
            "package": self.output_dir / "package",
        }
        for artifact_type, path in paths.items():
            self.queue.add_artifact(job_id, artifact_type, str(path))
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'completed', current_step = 'export', progress = 100 WHERE id = ?",
                (job_id,),
            )
            connection.execute(
                "UPDATE job_steps SET status = 'completed', progress = 100 WHERE job_id = ?",
                (job_id,),
            )

        self.queue.reprocess_job(job_id, from_step="export")

        artifact_types = {
            item["artifact_type"] for item in self.queue.list_artifacts(job_id)
        }
        self.assertEqual(self.queue.get_job(job_id)["current_step"], "export")
        self.assertIn("translated_srt", artifact_types)
        self.assertNotIn("subtitled_video", artifact_types)
        self.assertNotIn("package", artifact_types)

    def test_reprocesses_review_job_from_stt(self):
        project_id = self.queue.create_project("Shop", str(self.output_dir))
        job_id = self.queue.add_job(project_id, "url", "https://example.com/review")
        self.queue.add_artifact(job_id, "source_video", str(self.output_dir / "source.mp4"))
        self.queue.add_artifact(job_id, "source_srt", str(self.output_dir / "wrong.srt"))
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'review', current_step = 'review', progress = 60 WHERE id = ?",
                (job_id,),
            )

        self.queue.reprocess_job(job_id, from_step="transcribe")

        job = self.queue.get_job(job_id)
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["current_step"], "transcribe")
        self.assertEqual(
            [item["artifact_type"] for item in self.queue.list_artifacts(job_id)],
            ["source_video"],
        )


if __name__ == "__main__":
    unittest.main()
