"""Orchestrate translation, glossary, memory va exception review."""

from __future__ import annotations

from pathlib import Path

from core.gemini_translator import translate_blocks as gemini_translate_blocks
from core.glossary import GlossaryRepository
from core.review import ReviewService
from core.subtitle import SubtitleDocument
from core.translation_memory import TranslationMemoryRepository
from core.translator import translate_srt as google_translate_srt


class LocalizationService:
    def __init__(
        self,
        glossary: GlossaryRepository,
        memory: TranslationMemoryRepository,
        review: ReviewService,
        *,
        google_func=google_translate_srt,
        gemini_func=gemini_translate_blocks,
    ):
        self.glossary = glossary
        self.memory = memory
        self.review = review
        self.google_func = google_func
        self.gemini_func = gemini_func

    def localize_srt(
        self,
        source_path: str,
        *,
        shop_profile_id: int,
        job_id: int,
        mode: str = "google",
        source_language: str = "zh-CN",
        output_path: str | None = None,
        api_key: str | None = None,
        progress_callback=None,
        cancel_flag=None,
    ) -> dict:
        source = SubtitleDocument.load(source_path)
        if not source.entries:
            return {"success": False, "error": "SRT nguon khong co subtitle"}
        destination = Path(output_path) if output_path else Path(source_path).with_suffix(".vi.srt")

        memory_hits = {}
        for entry in source.entries:
            match = self.memory.lookup(
                shop_profile_id,
                entry.text,
                source_language=source_language,
            )
            if match:
                memory_hits[entry.index] = match["translated_text"]

        if mode == "google":
            result = self.google_func(
                source_path,
                src_lang=source_language,
                progress_callback=progress_callback,
                cancel_flag=cancel_flag,
            )
            if not result.get("success"):
                return result
            translated = SubtitleDocument.load(result["output_path"])
        elif mode == "gemini":
            blocks = [{"id": item.index, "text": item.text} for item in source.entries]
            glossary_context = self.glossary.prompt_context(
                shop_profile_id, [item.text for item in source.entries], source_language
            )
            result = self.gemini_func(
                blocks,
                api_key=api_key,
                source_language=source_language,
                progress_callback=progress_callback,
                cancel_flag=cancel_flag,
                glossary_context=glossary_context,
            )
            if not result.get("success"):
                return result
            translated = SubtitleDocument.from_srt(source.to_srt())
            translated_by_id = {int(item["id"]): item["text"] for item in result["blocks"]}
            for entry in translated.entries:
                entry.text = translated_by_id[entry.index]
        else:
            return {"success": False, "error": "Translation mode khong hop le"}

        for entry in translated.entries:
            if entry.index in memory_hits:
                entry.text = memory_hits[entry.index]
        translated.auto_wrap(max_chars=34, max_lines=2)
        destination.parent.mkdir(parents=True, exist_ok=True)
        translated.save(destination)

        issues = self.review.analyze(translated, source)
        self.review.replace_issues(job_id, issues)
        return {
            "success": True,
            "output_path": str(destination.resolve()),
            "total": len(translated.entries),
            "memory_hits": len(memory_hits),
            "review_issues": len(issues),
            "requires_review": any(item.severity == "error" for item in issues),
            "error": None,
        }

    def remember_approved_document(
        self,
        source_path: str,
        translated_path: str,
        *,
        shop_profile_id: int,
        source_language: str,
    ) -> int:
        source = SubtitleDocument.load(source_path)
        translated = SubtitleDocument.load(translated_path)
        translated_by_id = {item.index: item for item in translated.entries}
        count = 0
        for source_entry in source.entries:
            target = translated_by_id.get(source_entry.index)
            if target and target.text.strip():
                self.memory.remember(
                    shop_profile_id,
                    source_entry.text,
                    target.text,
                    source_language=source_language,
                    approved=True,
                )
                count += 1
        return count
