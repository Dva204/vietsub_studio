import tempfile
import unittest
import sqlite3
from pathlib import Path

from utils.db import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        db_path = Path(self.temp_dir.name) / "test.db"
        self.database = Database(db_path)

    def test_initializes_required_tables(self):
        self.database.initialize()

        connection = self.database.connect()
        self.addCleanup(connection.close)

        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {row["name"] for row in rows}

        self.assertIn("projects", table_names)
        self.assertIn("jobs", table_names)
        self.assertIn("job_steps", table_names)

    def test_enables_foreign_keys(self):
        connection = self.database.connect()
        self.addCleanup(connection.close)

        enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        self.assertEqual(enabled, 1)

    def test_uses_row_factory(self):
        connection = self.database.connect()
        self.addCleanup(connection.close)

        row = connection.execute(
            "SELECT 123 AS value"
        ).fetchone()

        self.assertEqual(row["value"], 123)

    def test_migrates_existing_v1_database_without_data_loss(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, output_dir TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, source_type TEXT NOT NULL,
                source_value TEXT NOT NULL, local_video_path TEXT, status TEXT DEFAULT 'pending',
                current_step TEXT DEFAULT 'acquire', progress REAL DEFAULT 0, error TEXT,
                retry_count INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(project_id, source_value)
            );
            CREATE TABLE job_steps (
                id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL, step_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending', progress REAL DEFAULT 0, output_path TEXT,
                error TEXT, attempts INTEGER DEFAULT 0, started_at TEXT, finished_at TEXT,
                UNIQUE(job_id, step_name)
            );
            INSERT INTO projects (id, name, output_dir) VALUES (1, 'Legacy', 'output');
            PRAGMA user_version = 1;
            """
        )
        connection.commit()
        connection.close()

        database = Database(legacy_path)
        database.initialize()
        migrated = database.connect()
        self.addCleanup(migrated.close)
        self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(migrated.execute("SELECT name FROM projects WHERE id = 1").fetchone()[0], "Legacy")
        self.assertIsNotNone(
            migrated.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='glossary_terms'"
            ).fetchone()
        )
        columns = {
            row["name"] for row in migrated.execute("PRAGMA table_info(shop_profiles)")
        }
        self.assertIn("whisper_model", columns)


if __name__ == "__main__":
    unittest.main()
