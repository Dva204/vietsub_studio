"""Persistent project/job queue va state machine."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from utils.db import Database


JOB_STEPS = ("acquire", "transcribe", "translate", "review", "export")
SOURCE_TYPES = {"url", "file"}


class DuplicateJobError(ValueError):
    pass


class InvalidTransitionError(RuntimeError):
    pass


class ProjectQueue:
    def __init__(self, database: Database):
        self.database = database

    def create_project(self, name: str, output_dir: str, shop_profile_id=None) -> int:
        name = name.strip()
        output_dir = output_dir.strip()
        if not name:
            raise ValueError("Ten project khong duoc de trong")
        if not output_dir:
            raise ValueError("Thu muc output khong duoc de trong")
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (name, output_dir, shop_profile_id)
                VALUES (?, ?, ?)
                """,
                (name, output_dir, shop_profile_id),
            )
            return int(cursor.lastrowid)

    def get_project(self, project_id: int):
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list_projects(self, shop_profile_id: int | None = None) -> list[dict]:
        connection = self.database.connect()
        try:
            if shop_profile_id is None:
                rows = connection.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM projects WHERE shop_profile_id = ? ORDER BY id DESC",
                    (shop_profile_id,),
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def set_project_status(self, project_id: int, status: str):
        if status not in {"active", "paused", "completed", "archived"}:
            raise ValueError("Trang thai project khong hop le")
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, project_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Khong tim thay project {project_id}")

    def delete_project(self, project_id: int):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def add_job(self, project_id: int, source_type: str, source_value: str) -> int:
        source_type = source_type.strip().lower()
        source_value = source_value.strip()
        if source_type not in SOURCE_TYPES:
            raise ValueError("source_type phai la url hoac file")
        if not source_value:
            raise ValueError("Nguon video khong duoc de trong")
        if source_type == "file":
            source_value = str(Path(source_value).resolve())

        try:
            with self.database.transaction() as connection:
                project = connection.execute(
                    "SELECT status FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if not project:
                    raise KeyError(f"Khong tim thay project {project_id}")
                if project["status"] != "active":
                    raise InvalidTransitionError("Chi them job vao project dang active")
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (project_id, source_type, source_value)
                    VALUES (?, ?, ?)
                    """,
                    (project_id, source_type, source_value),
                )
                job_id = int(cursor.lastrowid)
                connection.executemany(
                    "INSERT INTO job_steps (job_id, step_name) VALUES (?, ?)",
                    [(job_id, step) for step in JOB_STEPS],
                )
                return job_id
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error).upper():
                raise DuplicateJobError("Nguon nay da co trong project") from error
            raise

    def add_jobs(self, project_id: int, sources: list[tuple[str, str]]) -> dict:
        added, duplicates, errors = [], [], []
        for source_type, source_value in sources:
            try:
                added.append(self.add_job(project_id, source_type, source_value))
            except DuplicateJobError:
                duplicates.append(source_value)
            except Exception as error:
                errors.append({"source": source_value, "error": str(error)})
        return {"added": added, "duplicates": duplicates, "errors": errors}

    def get_job(self, job_id: int):
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT jobs.*, projects.output_dir, projects.shop_profile_id
                FROM jobs JOIN projects ON projects.id = jobs.project_id
                WHERE jobs.id = ?
                """,
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list_jobs(self, project_id: int, status: str | None = None) -> list[dict]:
        connection = self.database.connect()
        try:
            if status:
                rows = connection.execute(
                    "SELECT * FROM jobs WHERE project_id = ? AND status = ? ORDER BY id DESC",
                    (project_id, status),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM jobs WHERE project_id = ? ORDER BY id DESC", (project_id,)
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def get_job_steps(self, job_id: int) -> list[dict]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM job_steps WHERE job_id = ?
                ORDER BY CASE step_name
                    WHEN 'acquire' THEN 1 WHEN 'transcribe' THEN 2
                    WHEN 'translate' THEN 3 WHEN 'review' THEN 4 ELSE 5 END
                """,
                (job_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def claim_next_job(self, project_id: int | None = None):
        with self.database.transaction(immediate=True) as connection:
            params = []
            project_clause = ""
            if project_id is not None:
                project_clause = "AND jobs.project_id = ?"
                params.append(project_id)
            row = connection.execute(
                f"""
                SELECT jobs.id FROM jobs
                JOIN projects ON projects.id = jobs.project_id
                WHERE jobs.status = 'pending' AND projects.status = 'active'
                  AND jobs.current_step != 'review' {project_clause}
                ORDER BY jobs.id LIMIT 1
                """,
                params,
            ).fetchone()
            if not row:
                return None
            job_id = int(row["id"])
            connection.execute(
                """
                UPDATE jobs SET status = 'running', error = NULL,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (job_id,),
            )
            connection.execute(
                """
                UPDATE job_steps SET status = 'running', attempts = attempts + 1,
                    error = NULL, started_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND step_name = (SELECT current_step FROM jobs WHERE id = ?)
                """,
                (job_id, job_id),
            )
            job = connection.execute(
                """
                SELECT jobs.*, projects.output_dir, projects.shop_profile_id
                FROM jobs JOIN projects ON projects.id = jobs.project_id
                WHERE jobs.id = ?
                """,
                (job_id,),
            ).fetchone()
            return dict(job)

    def update_progress(self, job_id: int, step_progress: float):
        step_progress = min(100.0, max(0.0, float(step_progress)))
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            step_index = JOB_STEPS.index(job["current_step"])
            overall = (step_index + step_progress / 100) / len(JOB_STEPS) * 100
            connection.execute(
                "UPDATE job_steps SET progress = ? WHERE job_id = ? AND step_name = ?",
                (step_progress, job_id, job["current_step"]),
            )
            connection.execute(
                "UPDATE jobs SET progress = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (overall, job_id),
            )

    def complete_current_step(self, job_id: int, output_path: str | None = None):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] != "running":
                raise InvalidTransitionError("Chi complete job dang running")
            current = job["current_step"]
            connection.execute(
                """
                UPDATE job_steps SET status = 'completed', progress = 100,
                    output_path = ?, finished_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND step_name = ?
                """,
                (output_path, job_id, current),
            )
            index = JOB_STEPS.index(current)
            if index == len(JOB_STEPS) - 1:
                connection.execute(
                    """
                    UPDATE jobs SET status = 'completed', progress = 100,
                        error = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                    """,
                    (job_id,),
                )
                return "completed"
            next_step = JOB_STEPS[index + 1]
            next_status = "review" if next_step == "review" else "pending"
            connection.execute(
                """
                UPDATE jobs SET status = ?, current_step = ?, error = NULL,
                    progress = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (next_status, next_step, (index + 1) / len(JOB_STEPS) * 100, job_id),
            )
            return next_status

    def approve_review(self, job_id: int):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] != "review" or job["current_step"] != "review":
                raise InvalidTransitionError("Job khong o buoc review")
            unresolved = connection.execute(
                """
                SELECT COUNT(*) FROM review_issues
                WHERE job_id = ? AND resolved = 0 AND severity = 'error'
                """,
                (job_id,),
            ).fetchone()[0]
            if unresolved:
                raise InvalidTransitionError(f"Con {unresolved} review issue chua xu ly")
            connection.execute(
                """
                UPDATE job_steps SET status = 'completed', progress = 100,
                    finished_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND step_name = 'review'
                """,
                (job_id,),
            )
            connection.execute(
                """
                UPDATE jobs SET status = 'pending', current_step = 'export', progress = 80,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (job_id,),
            )

    def fail_job(self, job_id: int, error: str):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            connection.execute(
                """
                UPDATE job_steps SET status = 'failed', error = ?,
                    finished_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND step_name = ?
                """,
                (error, job_id, job["current_step"]),
            )
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', error = ?,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (error, job_id),
            )

    def retry_job(self, job_id: int):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] != "failed":
                raise InvalidTransitionError("Chi retry job failed")
            connection.execute(
                """
                UPDATE job_steps SET status = 'pending', progress = 0, error = NULL,
                    started_at = NULL, finished_at = NULL
                WHERE job_id = ? AND step_name = ?
                """,
                (job_id, job["current_step"]),
            )
            connection.execute(
                """
                UPDATE jobs SET status = 'pending', error = NULL,
                    retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (job_id,),
            )

    def reprocess_job(self, job_id: int, *, from_step: str = "transcribe"):
        """Run a completed job again while preserving its downloaded video."""
        if from_step not in JOB_STEPS or from_step == "acquire":
            raise ValueError("from_step phai la mot buoc sau acquire")
        step_index = JOB_STEPS.index(from_step)
        downstream_steps = JOB_STEPS[step_index:]
        placeholders = ", ".join("?" for _ in downstream_steps)
        removable_artifacts = {
            "transcribe": ("source_srt", "translated_srt", "subtitled_video", "package"),
            "translate": ("translated_srt", "subtitled_video", "package"),
            "review": ("subtitled_video", "package"),
            "export": ("subtitled_video", "package"),
        }[from_step]

        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] not in {"completed", "review"}:
                raise InvalidTransitionError("Chi xu ly lai job da hoan thanh hoac dang review")
            connection.execute(
                f"""
                UPDATE job_steps SET status = 'pending', progress = 0, error = NULL,
                    output_path = NULL, started_at = NULL, finished_at = NULL
                WHERE job_id = ? AND step_name IN ({placeholders})
                """,
                (job_id, *downstream_steps),
            )
            artifact_placeholders = ", ".join("?" for _ in removable_artifacts)
            connection.execute(
                f"DELETE FROM artifacts WHERE job_id = ? AND artifact_type IN ({artifact_placeholders})",
                (job_id, *removable_artifacts),
            )
            connection.execute("DELETE FROM review_issues WHERE job_id = ?", (job_id,))
            connection.execute(
                """
                UPDATE jobs SET status = 'pending', current_step = ?, progress = ?,
                    error = NULL, retry_count = retry_count + 1,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (from_step, step_index / len(JOB_STEPS) * 100, job_id),
            )

    def cancel_job(self, job_id: int):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] in {"completed", "canceled"}:
                raise InvalidTransitionError("Khong the cancel job da ket thuc")
            connection.execute(
                "UPDATE jobs SET status = 'canceled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,),
            )
            connection.execute(
                """
                UPDATE job_steps SET status = 'canceled', finished_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND step_name = ? AND status IN ('pending', 'running')
                """,
                (job_id, job["current_step"]),
            )

    def recover_interrupted_jobs(self) -> int:
        with self.database.transaction(immediate=True) as connection:
            rows = connection.execute(
                "SELECT id, current_step FROM jobs WHERE status = 'running'"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE job_steps SET status = 'pending', progress = 0,
                        error = 'Interrupted', started_at = NULL
                    WHERE job_id = ? AND step_name = ?
                    """,
                    (row["id"], row["current_step"]),
                )
                connection.execute(
                    """
                    UPDATE jobs SET status = 'pending', error = 'Interrupted',
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?
                    """,
                    (row["id"],),
                )
            return len(rows)

    def interrupt_job(self, job_id: int):
        with self.database.transaction() as connection:
            job = _require_job(connection, job_id)
            if job["status"] != "running":
                return
            connection.execute(
                """
                UPDATE job_steps SET status = 'pending', progress = 0,
                    error = 'Interrupted', started_at = NULL
                WHERE job_id = ? AND step_name = ?
                """,
                (job_id, job["current_step"]),
            )
            connection.execute(
                """
                UPDATE jobs SET status = 'pending', error = 'Interrupted',
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (job_id,),
            )

    def set_local_video_path(self, job_id: int, path: str):
        with self.database.transaction() as connection:
            _require_job(connection, job_id)
            connection.execute(
                "UPDATE jobs SET local_video_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(Path(path).resolve()), job_id),
            )

    def add_artifact(self, job_id: int, artifact_type: str, path: str, metadata=None):
        with self.database.transaction() as connection:
            _require_job(connection, job_id)
            connection.execute(
                """
                INSERT OR REPLACE INTO artifacts
                    (job_id, artifact_type, path, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, artifact_type, str(Path(path).resolve()), json.dumps(metadata or {})),
            )

    def list_artifacts(self, job_id: int) -> list[dict]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM artifacts WHERE job_id = ? ORDER BY id", (job_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()


def _require_job(connection, job_id: int):
    row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise KeyError(f"Khong tim thay job {job_id}")
    return row
