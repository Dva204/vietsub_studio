import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.model_manager import ModelManager
from utils.cleaner import WorkspaceCleaner
from utils.db import Database
from utils.secrets import SecretStore


class OperationsTests(unittest.TestCase):
    def test_model_manager_detects_and_deletes_complete_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(temp_dir)
            snapshot = (
                Path(temp_dir)
                / "models--Systran--faster-whisper-base"
                / "snapshots"
                / "hash"
            )
            snapshot.mkdir(parents=True)
            for name in ("config.json", "model.bin", "tokenizer.json"):
                (snapshot / name).write_bytes(b"x")
            self.assertTrue(manager.status("base")["downloaded"])
            self.assertTrue(manager.delete("base"))
            self.assertFalse(manager.status("base")["downloaded"])

    def test_cleaner_only_removes_stale_owned_workdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = root / ".work" / "job_1"
            work.mkdir(parents=True)
            (work / "temp.txt").write_text("x")
            old = time.time() - 48 * 3600
            os.utime(work, (old, old))
            cleaner = WorkspaceCleaner([root])
            removed = cleaner.cleanup_stale_workdirs(max_age_hours=24)
            self.assertIn(str(work), removed)
            self.assertFalse(work.exists())
            with self.assertRaises(ValueError):
                cleaner.remove(root)

    def test_cleaner_preserves_protected_review_workdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = root / ".work" / "job_3"
            work.mkdir(parents=True)
            old = time.time() - 48 * 3600
            os.utime(work, (old, old))

            removed = WorkspaceCleaner([root]).cleanup_stale_workdirs(
                max_age_hours=24,
                protected_paths=[work],
            )

            self.assertEqual(removed, [])
            self.assertTrue(work.exists())

    @unittest.skipUnless(os.name == "nt", "DPAPI chi co tren Windows")
    def test_secret_store_round_trip_uses_dpapi(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "secrets.db")
            database.initialize()
            store = SecretStore(database)
            store.set("gemini_api_key", "secret-value")
            self.assertEqual(store.get("gemini_api_key"), "secret-value")
            connection = database.connect()
            try:
                raw = connection.execute(
                    "SELECT value FROM settings WHERE key = 'gemini_api_key'"
                ).fetchone()["value"]
            finally:
                connection.close()
            self.assertNotIn("secret-value", raw)
            store.delete("gemini_api_key")
            self.assertIsNone(store.get("gemini_api_key"))


if __name__ == "__main__":
    unittest.main()
