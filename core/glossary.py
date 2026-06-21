"""Shop profile va glossary persistence."""

from __future__ import annotations

import csv
from pathlib import Path

from utils.db import Database


class ShopProfileRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(
        self,
        name: str,
        *,
        source_language: str = "auto",
        translation_mode: str = "google",
        export_preset: str = "shorts",
        whisper_model: str = "small",
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Ten shop khong duoc de trong")
        if translation_mode not in {"google", "gemini"}:
            raise ValueError("translation_mode khong hop le")
        if whisper_model not in {"base", "small", "large-v3"}:
            raise ValueError("whisper_model khong hop le")
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO shop_profiles
                    (name, source_language, translation_mode, export_preset, whisper_model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, source_language, translation_mode, export_preset, whisper_model),
            )
            return int(cursor.lastrowid)

    def get(self, profile_id: int):
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM shop_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list_all(self) -> list[dict]:
        connection = self.database.connect()
        try:
            rows = connection.execute("SELECT * FROM shop_profiles ORDER BY name").fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def update(self, profile_id: int, **changes):
        allowed = {"name", "source_language", "translation_mode", "export_preset", "whisper_model"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return
        if "name" in values and not str(values["name"]).strip():
            raise ValueError("Ten shop khong duoc de trong")
        if values.get("translation_mode") not in {None, "google", "gemini"}:
            raise ValueError("translation_mode khong hop le")
        if values.get("whisper_model") not in {None, "base", "small", "large-v3"}:
            raise ValueError("whisper_model khong hop le")
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                f"""
                UPDATE shop_profiles SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [*values.values(), profile_id],
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Khong tim thay shop profile {profile_id}")


class GlossaryRepository:
    def __init__(self, database: Database):
        self.database = database

    def upsert(
        self,
        shop_profile_id: int,
        source_term: str,
        target_term: str,
        *,
        source_language: str = "zh-CN",
        target_language: str = "vi",
        case_sensitive: bool = False,
    ) -> int:
        source_term, target_term = source_term.strip(), target_term.strip()
        if not source_term or not target_term:
            raise ValueError("Thuat ngu nguon va dich khong duoc de trong")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO glossary_terms
                    (shop_profile_id, source_language, target_language,
                     source_term, target_term, case_sensitive)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(shop_profile_id, source_language, target_language, source_term)
                DO UPDATE SET target_term = excluded.target_term,
                    case_sensitive = excluded.case_sensitive,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    shop_profile_id, source_language, target_language,
                    source_term, target_term, int(case_sensitive),
                ),
            )
            row = connection.execute(
                """
                SELECT id FROM glossary_terms
                WHERE shop_profile_id = ? AND source_language = ?
                  AND target_language = ? AND source_term = ?
                """,
                (shop_profile_id, source_language, target_language, source_term),
            ).fetchone()
            return int(row["id"])

    def list_terms(
        self, shop_profile_id: int, source_language: str | None = None
    ) -> list[dict]:
        connection = self.database.connect()
        try:
            if source_language:
                rows = connection.execute(
                    """
                    SELECT * FROM glossary_terms
                    WHERE shop_profile_id = ? AND source_language = ?
                    ORDER BY LENGTH(source_term) DESC, source_term
                    """,
                    (shop_profile_id, source_language),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM glossary_terms WHERE shop_profile_id = ?
                    ORDER BY LENGTH(source_term) DESC, source_term
                    """,
                    (shop_profile_id,),
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def delete(self, term_id: int):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))

    def matching_terms(self, shop_profile_id: int, text: str, source_language: str):
        matches = []
        for term in self.list_terms(shop_profile_id, source_language):
            haystack = text if term["case_sensitive"] else text.casefold()
            needle = term["source_term"] if term["case_sensitive"] else term["source_term"].casefold()
            if needle in haystack:
                matches.append(term)
        return matches

    def prompt_context(self, shop_profile_id: int, texts: list[str], source_language: str):
        combined = "\n".join(texts)
        matches = self.matching_terms(shop_profile_id, combined, source_language)
        return "\n".join(f"{item['source_term']} => {item['target_term']}" for item in matches)

    def export_csv(self, shop_profile_id: int, output_path: str):
        fields = [
            "source_language", "target_language", "source_term",
            "target_term", "case_sensitive",
        ]
        with Path(output_path).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for term in self.list_terms(shop_profile_id):
                writer.writerow({field: term[field] for field in fields})

    def import_csv(self, shop_profile_id: int, input_path: str) -> int:
        count = 0
        with Path(input_path).open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                self.upsert(
                    shop_profile_id,
                    row["source_term"],
                    row["target_term"],
                    source_language=row.get("source_language") or "zh-CN",
                    target_language=row.get("target_language") or "vi",
                    case_sensitive=str(row.get("case_sensitive", "0")).lower() in {"1", "true", "yes"},
                )
                count += 1
        return count
