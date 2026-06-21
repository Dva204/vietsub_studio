import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.project_queue import ProjectQueue
from core.queue_runner import QueueRunner, StepResult
from utils.db import Database


class QueueRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        database = Database(root / "queue.db")
        database.initialize()
        self.queue = ProjectQueue(database)
        self.project_id = self.queue.create_project("Shop", str(root / "output"))
        self.job_id = self.queue.add_job(self.project_id, "url", "https://example.com/a")

    def test_runs_to_review_then_finishes_after_approval(self):
        def successful(job, progress, cancel_flag):
            progress(100)
            return StepResult(True, output_path=f"{job['current_step']}.out")

        runner = QueueRunner(
            self.queue,
            {"acquire": successful, "transcribe": successful, "translate": successful, "export": successful},
        )
        self.assertEqual(runner.run_until_idle(self.project_id), 3)
        self.assertEqual(self.queue.get_job(self.job_id)["status"], "review")

        self.queue.approve_review(self.job_id)
        self.assertEqual(runner.run_until_idle(self.project_id), 1)
        self.assertEqual(self.queue.get_job(self.job_id)["status"], "completed")

    def test_failed_processor_records_error(self):
        runner = QueueRunner(
            self.queue,
            {"acquire": lambda job, progress, cancel: StepResult(False, error="boom")},
        )
        runner.run_once(self.project_id)
        job = self.queue.get_job(self.job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "boom")

    def test_stop_interrupts_job_for_later_resume(self):
        started = threading.Event()

        def slow_processor(job, progress, cancel_flag):
            started.set()
            while not cancel_flag[0]:
                time.sleep(0.01)
            return StepResult(False, error="stopped")

        runner = QueueRunner(self.queue, {"acquire": slow_processor})
        runner.start(self.project_id)
        self.assertTrue(started.wait(timeout=2))
        runner.stop(wait=True)

        job = self.queue.get_job(self.job_id)
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["error"], "Interrupted")


if __name__ == "__main__":
    unittest.main()
