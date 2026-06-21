"""Exact-match translation memory theo shop."""

from __future__ import annotations

import re
import unicodedata

from utils.db import Database


class TranslationMemoryRepository:
    def __init__(self, database: Database):
        self.database = database

    def remember(
        self,
        shop_profile_id: int,
        source_text: str,
        translated_text: str,
        *,
        source_language: str = "zh-CN",
        target_language: str = "vi",
        approved: bool = True,
    ) -> int:
        source_text, translated_text = source_text.strip(), translated_text.strip()
        if not source_text or not translated_text:
            raise ValueError("Cau nguon va ban dich khong duoc de trong")
        normalized = normalize_source(source_text)
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO translation_memory
                    (shop_profile_id, source_language, target_language, source_text,
                     normalized_source, translated_text, approved)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(shop_profile_id, source_language, target_language, normalized_source)
                DO UPDATE SET source_text = excluded.source_text,
                    translated_text = excluded.translated_text,
                    approved = excluded.approved,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    shop_profile_id, source_language, target_language, source_text,
                    normalized, translated_text, int(approved),
                ),
            )
            row = connection.execute(
                """
                SELECT id FROM translation_memory
                WHERE shop_profile_id = ? AND source_language = ?
                  AND target_language = ? AND normalized_source = ?
                """,
                (shop_profile_id, source_language, target_language, normalized),
            ).fetchone()
            return int(row["id"])

    def lookup(
        self,
        shop_profile_id: int,
        source_text: str,
        *,
        source_language: str = "zh-CN",
        target_language: str = "vi",
    ):
        normalized = normalize_source(source_text)
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM translation_memory
                WHERE shop_profile_id = ? AND source_language = ?
                  AND target_language = ? AND normalized_source = ? AND approved = 1
                """,
                (shop_profile_id, source_language, target_language, normalized),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE translation_memory SET usage_count = usage_count + 1 WHERE id = ?",
                (row["id"],),
            )
            result = dict(row)
            result["usage_count"] += 1
            return result

    def list_all(self, shop_profile_id: int) -> list[dict]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM translation_memory WHERE shop_profile_id = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (shop_profile_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def delete(self, memory_id: int):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM translation_memory WHERE id = ?", (memory_id,))


def normalize_source(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().strip()
    return re.sub(r"\s+", " ", text)
