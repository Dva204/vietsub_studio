"""SQLite connection va migration cho VietDub Studio."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


LATEST_SCHEMA_VERSION = 3


class Database:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self):
        connection = self.connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > LATEST_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database version {version} moi hon app ho tro {LATEST_SCHEMA_VERSION}"
                )
            if version < 1:
                _migration_v1(connection)
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
                version = 1
            if version < 2:
                _migration_v2(connection)
                connection.execute("PRAGMA user_version = 2")
                connection.commit()
                version = 2
            if version < 3:
                _migration_v3(connection)
                connection.execute("PRAGMA user_version = 3")
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _migration_v1(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            output_dir TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            source_value TEXT NOT NULL,
            local_video_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT NOT NULL DEFAULT 'acquire',
            progress REAL NOT NULL DEFAULT 0,
            error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, source_value)
        );

        CREATE TABLE IF NOT EXISTS job_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            progress REAL NOT NULL DEFAULT 0,
            output_path TEXT,
            error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(job_id, step_name)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
        """
    )


def _migration_v2(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS shop_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source_language TEXT NOT NULL DEFAULT 'auto',
            translation_mode TEXT NOT NULL DEFAULT 'google',
            export_preset TEXT NOT NULL DEFAULT 'shorts',
            whisper_model TEXT NOT NULL DEFAULT 'small',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,
            path TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(job_id, artifact_type, path)
        );

        CREATE TABLE IF NOT EXISTS glossary_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_profile_id INTEGER NOT NULL,
            source_language TEXT NOT NULL,
            target_language TEXT NOT NULL DEFAULT 'vi',
            source_term TEXT NOT NULL,
            target_term TEXT NOT NULL,
            case_sensitive INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_profile_id) REFERENCES shop_profiles(id) ON DELETE CASCADE,
            UNIQUE(shop_profile_id, source_language, target_language, source_term)
        );

        CREATE TABLE IF NOT EXISTS translation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_profile_id INTEGER NOT NULL,
            source_language TEXT NOT NULL,
            target_language TEXT NOT NULL DEFAULT 'vi',
            source_text TEXT NOT NULL,
            normalized_source TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 1,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_profile_id) REFERENCES shop_profiles(id) ON DELETE CASCADE,
            UNIQUE(shop_profile_id, source_language, target_language, normalized_source)
        );

        CREATE TABLE IF NOT EXISTS review_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            entry_index INTEGER NOT NULL,
            code TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            message TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(job_id, entry_index, code)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_steps_job_status ON job_steps(job_id, status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);
        CREATE INDEX IF NOT EXISTS idx_glossary_shop ON glossary_terms(shop_profile_id);
        CREATE INDEX IF NOT EXISTS idx_memory_lookup
            ON translation_memory(shop_profile_id, source_language, target_language, normalized_source);
        CREATE INDEX IF NOT EXISTS idx_review_job_resolved ON review_issues(job_id, resolved);
        """
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "shop_profile_id" not in columns:
        connection.execute(
            "ALTER TABLE projects ADD COLUMN shop_profile_id INTEGER REFERENCES shop_profiles(id)"
        )


def _migration_v3(connection):
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(shop_profiles)").fetchall()
    }
    if "whisper_model" not in columns:
        connection.execute(
            "ALTER TABLE shop_profiles ADD COLUMN whisper_model TEXT NOT NULL DEFAULT 'small'"
        )
