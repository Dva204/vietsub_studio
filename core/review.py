"""Phat hien va luu cac subtitle can nguoi dung kiem tra."""

from __future__ import annotations

import re

from core.subtitle import SubtitleDocument, SubtitleIssue
from core.translation_memory import normalize_source
from utils.db import Database


CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


class ReviewService:
    def __init__(self, database: Database):
        self.database = database

    def analyze(
        self,
        translated: SubtitleDocument,
        source: SubtitleDocument | None = None,
    ) -> list[SubtitleIssue]:
        issues = list(translated.validate())
        source_by_index = {entry.index: entry for entry in source.entries} if source else {}
        existing = {(issue.entry_index, issue.code) for issue in issues}

        for entry in translated.entries:
            candidates = []
            if not entry.text.strip():
                candidates.append(SubtitleIssue(entry.index, "empty_translation", "Ban dich dang trong", "error"))
            if CJK_PATTERN.search(entry.text):
                candidates.append(SubtitleIssue(entry.index, "contains_cjk", "Ban dich van con ky tu Trung"))
            source_entry = source_by_index.get(entry.index)
            if source_entry and normalize_source(source_entry.text) == normalize_source(entry.text):
                candidates.append(SubtitleIssue(entry.index, "same_as_source", "Ban dich giong het cau nguon"))
            if source_entry:
                visible_source = len(re.sub(r"\s+", "", source_entry.text))
                if source_entry.duration_ms >= 6_000 and visible_source <= 15:
                    candidates.append(
                        SubtitleIssue(
                            entry.index,
                            "suspicious_stt_span",
                            "Doan nhan dang keo dai bat thuong; nen nghe lai audio",
                        )
                    )
            for issue in candidates:
                if (issue.entry_index, issue.code) not in existing:
                    issues.append(issue)
                    existing.add((issue.entry_index, issue.code))
        return issues

    def replace_issues(self, job_id: int, issues: list[SubtitleIssue]):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM review_issues WHERE job_id = ?", (job_id,))
            connection.executemany(
                """
                INSERT INTO review_issues
                    (job_id, entry_index, code, severity, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (job_id, item.entry_index, item.code, item.severity, item.message)
                    for item in issues
                ],
            )

    def list_issues(self, job_id: int, *, unresolved_only: bool = False) -> list[dict]:
        connection = self.database.connect()
        try:
            clause = "AND resolved = 0" if unresolved_only else ""
            rows = connection.execute(
                f"""
                SELECT * FROM review_issues WHERE job_id = ? {clause}
                ORDER BY CASE severity WHEN 'error' THEN 1 ELSE 2 END, entry_index
                """,
                (job_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def resolve(self, issue_id: int, resolved: bool = True):
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE review_issues SET resolved = ?,
                    resolved_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE id = ?
                """,
                (int(resolved), int(resolved), issue_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Khong tim thay review issue {issue_id}")

    def resolve_all(self, job_id: int):
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE review_issues SET resolved = 1, resolved_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND resolved = 0
                """,
                (job_id,),
            )
