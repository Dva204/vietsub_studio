import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.glossary import GlossaryRepository, ShopProfileRepository
from core.project_queue import InvalidTransitionError, ProjectQueue
from core.review import ReviewService
from core.subtitle import SubtitleDocument
from core.translation_memory import TranslationMemoryRepository
from utils.db import Database


class LocalizationDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.database = Database(root / "data.db")
        self.database.initialize()
        self.profiles = ShopProfileRepository(self.database)
        self.profile_id = self.profiles.create("Shop A")

    def test_glossary_upserts_matches_and_round_trips_csv(self):
        glossary = GlossaryRepository(self.database)
        first_id = glossary.upsert(self.profile_id, "直播间", "phong livestream")
        second_id = glossary.upsert(self.profile_id, "直播间", "phòng livestream")
        self.assertEqual(first_id, second_id)
        self.assertEqual(len(glossary.matching_terms(self.profile_id, "进入直播间", "zh-CN")), 1)

        csv_path = Path(self.temp_dir.name) / "glossary.csv"
        glossary.export_csv(self.profile_id, csv_path)
        other_profile = self.profiles.create("Shop B")
        self.assertEqual(glossary.import_csv(other_profile, csv_path), 1)
        self.assertEqual(glossary.list_terms(other_profile)[0]["target_term"], "phòng livestream")

    def test_translation_memory_uses_normalized_exact_match(self):
        memory = TranslationMemoryRepository(self.database)
        memory.remember(self.profile_id, "  HELLO   World ", "Xin chao")
        match = memory.lookup(self.profile_id, "hello world", source_language="zh-CN")
        self.assertEqual(match["translated_text"], "Xin chao")
        self.assertEqual(match["usage_count"], 1)

    def test_review_detects_persists_and_resolves_issues(self):
        source = SubtitleDocument.from_srt(
            "1\n00:00:00,000 --> 00:00:02,000\n你好\n"
        )
        translated = SubtitleDocument.from_srt(
            "1\n00:00:00,000 --> 00:00:02,000\n你好\n"
        )
        review = ReviewService(self.database)
        issues = review.analyze(translated, source)
        self.assertIn("contains_cjk", {item.code for item in issues})
        self.assertIn("same_as_source", {item.code for item in issues})

        queue = ProjectQueue(self.database)
        project_id = queue.create_project("P", str(Path(self.temp_dir.name) / "out"), self.profile_id)
        job_id = queue.add_job(project_id, "url", "https://example.com/a")
        review.replace_issues(job_id, issues)
        self.assertEqual(len(review.list_issues(job_id, unresolved_only=True)), 2)
        review.resolve_all(job_id)
        self.assertEqual(review.list_issues(job_id, unresolved_only=True), [])

    def test_review_flags_sparse_long_stt_segment(self):
        source = SubtitleDocument.from_srt(
            "1\n00:00:01,000 --> 00:00:09,000\nYou\n"
        )
        translated = SubtitleDocument.from_srt(
            "1\n00:00:01,000 --> 00:00:09,000\nBan\n"
        )

        issues = ReviewService(self.database).analyze(translated, source)

        self.assertIn("suspicious_stt_span", {item.code for item in issues})


if __name__ == "__main__":
    unittest.main()
