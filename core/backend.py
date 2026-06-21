"""Facade duy nhat ma UI VietDub Studio can su dung."""

from __future__ import annotations

import os
from pathlib import Path

from core.glossary import GlossaryRepository, ShopProfileRepository
from core.input_inbox import collect_inputs
from core.model_manager import ModelManager
from core.pipeline import PipelineConfig, PipelineProcessors
from core.project_queue import ProjectQueue
from core.queue_runner import QueueRunner
from core.review import ReviewService
from core.subtitle import SubtitleDocument
from core.translation_memory import TranslationMemoryRepository
from utils.cleaner import WorkspaceCleaner
from utils.db import Database
from utils.secrets import SecretStore


WHISPER_LANGUAGE_BY_SOURCE = {
    "auto": "Tu dong",
    "zh-CN": "Tieng Trung",
    "en": "Tieng Anh",
    "ja": "Tieng Nhat",
    "ko": "Tieng Han",
}


class VietDubBackend:
    def __init__(self, data_root: str | Path | None = None):
        self.data_root = Path(data_root or _default_data_root()).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.database = Database(self.data_root / "vietdub.db")
        self.queue = ProjectQueue(self.database)
        self.shops = ShopProfileRepository(self.database)
        self.glossary = GlossaryRepository(self.database)
        self.memory = TranslationMemoryRepository(self.database)
        self.review = ReviewService(self.database)
        self.secrets = SecretStore(self.database)
        self.cleaner = WorkspaceCleaner([self.data_root])
        self.models = ModelManager(self.data_root / "models")
        self._runner = None

    def initialize(self) -> dict:
        self.database.initialize()
        recovered = self.queue.recover_interrupted_jobs()
        removed = self.cleaner.cleanup_stale_workdirs(
            protected_paths=self._protected_workdirs()
        )
        return {"recovered_jobs": recovered, "removed_temp": removed}

    def create_shop(self, name: str, **options) -> int:
        return self.shops.create(name, **options)

    def list_shops(self) -> list[dict]:
        return self.shops.list_all()

    def update_shop(self, shop_profile_id: int, **changes):
        self.shops.update(shop_profile_id, **changes)

    def list_projects(self, shop_profile_id: int | None = None) -> list[dict]:
        return self.queue.list_projects(shop_profile_id)

    def create_project(
        self, name: str, shop_profile_id: int, output_dir: str | None = None
    ) -> int:
        if not self.shops.get(shop_profile_id):
            raise KeyError(f"Khong tim thay shop profile {shop_profile_id}")
        destination = Path(output_dir) if output_dir else self.data_root / "projects" / name
        destination.mkdir(parents=True, exist_ok=True)
        return self.queue.create_project(name, str(destination.resolve()), shop_profile_id)

    def add_inputs(self, project_id: int, values, *, recursive: bool = False) -> dict:
        collected = collect_inputs(values, recursive=recursive)
        sources = [(item.source_type, item.source_value) for item in collected["items"]]
        result = self.queue.add_jobs(project_id, sources)
        result["invalid"] = collected["invalid"]
        return result

    def run_project_sync(
        self,
        project_id: int,
        *,
        event_callback=None,
        max_steps: int | None = None,
        processor_overrides: dict | None = None,
    ) -> int:
        runner = self._build_runner(project_id, event_callback, processor_overrides)
        return runner.run_until_idle(project_id, max_steps=max_steps)

    def start_project(self, project_id: int, *, event_callback=None):
        if self._runner and self._runner.is_running:
            raise RuntimeError("Dang co project khac duoc xu ly")
        self._runner = self._build_runner(project_id, event_callback)
        self._runner.start(project_id)

    def stop_project(self):
        if self._runner:
            self._runner.stop(wait=True)

    def is_processing(self) -> bool:
        return bool(self._runner and self._runner.is_running)

    def cancel_job(self, job_id: int):
        if self._runner and self._runner.is_running:
            self._runner.cancel_job(job_id)
        else:
            self.queue.cancel_job(job_id)

    def retry_job(self, job_id: int):
        self.queue.retry_job(job_id)

    def reprocess_job(self, job_id: int):
        self.queue.reprocess_job(job_id, from_step="transcribe")

    def reexport_job(self, job_id: int):
        self.queue.reprocess_job(job_id, from_step="export")

    def project_dashboard(self, project_id: int) -> dict:
        project = self.queue.get_project(project_id)
        if not project:
            raise KeyError(f"Khong tim thay project {project_id}")
        jobs = self.queue.list_jobs(project_id)
        counts = {}
        for job in jobs:
            counts[job["status"]] = counts.get(job["status"], 0) + 1
        return {"project": project, "jobs": jobs, "counts": counts}

    def job_detail(self, job_id: int) -> dict:
        job = self.queue.get_job(job_id)
        if not job:
            raise KeyError(f"Khong tim thay job {job_id}")
        return {
            "job": job,
            "steps": self.queue.get_job_steps(job_id),
            "artifacts": self.queue.list_artifacts(job_id),
            "review_issues": self.review.list_issues(job_id),
        }

    def review_workspace(self, job_id: int) -> dict:
        detail = self.job_detail(job_id)
        artifacts = {item["artifact_type"]: item["path"] for item in detail["artifacts"]}
        source_path = artifacts.get("source_srt")
        translated_path = artifacts.get("translated_srt")
        source = _load_subtitle_if_present(source_path)
        translated = _load_subtitle_if_present(translated_path)
        source_by_id = {entry.index: entry.text for entry in source.entries}
        issues_by_id = {}
        for issue in detail["review_issues"]:
            issues_by_id.setdefault(issue["entry_index"], []).append(issue)
        entries = [
            {
                "index": entry.index,
                "start_ms": entry.start_ms,
                "end_ms": entry.end_ms,
                "source_text": source_by_id.get(entry.index, ""),
                "translated_text": entry.text,
                "issues": issues_by_id.get(entry.index, []),
            }
            for entry in translated.entries
        ]
        return {
            **detail,
            "entries": entries,
            "editable": bool(translated_path and Path(translated_path).is_file()),
        }

    def can_edit_subtitles(self, job_id: int) -> bool:
        detail = self.job_detail(job_id)
        return any(
            item["artifact_type"] == "translated_srt" and Path(item["path"]).is_file()
            for item in detail["artifacts"]
        )

    def model_status(self) -> list[dict]:
        return self.models.list_models()

    def download_model(self, model_size: str, progress_callback=None, cancel_flag=None):
        return self.models.download(model_size, progress_callback, cancel_flag)

    def update_subtitle_text(self, job_id: int, entry_index: int, text: str):
        detail = self.job_detail(job_id)
        artifacts = {item["artifact_type"]: item["path"] for item in detail["artifacts"]}
        translated_path = artifacts.get("translated_srt")
        source_path = artifacts.get("source_srt")
        if not translated_path or not Path(translated_path).is_file():
            raise RuntimeError("File subtitle cua job khong con ton tai")
        translated = SubtitleDocument.load(translated_path)
        translated.update_text(entry_index, text)
        translated.save(translated_path)
        source = _load_subtitle_if_present(source_path) if source_path else None
        issues = self.review.analyze(translated, source)
        self.review.replace_issues(job_id, issues)
        return {"issues": self.review.list_issues(job_id), "path": translated_path}

    def resolve_issue(self, issue_id: int):
        self.review.resolve(issue_id)

    def approve_job(self, job_id: int) -> int:
        detail = self.job_detail(job_id)
        unresolved = [
            item for item in detail["review_issues"]
            if not item["resolved"] and item["severity"] == "error"
        ]
        if unresolved:
            raise RuntimeError(f"Con {len(unresolved)} review issue chua xu ly")
        artifacts = {item["artifact_type"]: item["path"] for item in detail["artifacts"]}
        source_path = artifacts.get("source_srt")
        translated_path = artifacts.get("translated_srt")
        if not source_path or not translated_path:
            raise RuntimeError("Job chua co du SRT de approve")
        remembered = self._localization_service().remember_approved_document(
            source_path,
            translated_path,
            shop_profile_id=detail["job"]["shop_profile_id"],
            source_language=self._profile_for_project(detail["job"])["source_language"],
        )
        self.queue.approve_review(job_id)
        return remembered

    def set_gemini_api_key(self, api_key: str):
        if not api_key.strip():
            self.secrets.delete("gemini_api_key")
        else:
            self.secrets.set("gemini_api_key", api_key.strip())

    def has_gemini_api_key(self) -> bool:
        return bool(self.secrets.get("gemini_api_key"))

    def add_glossary_term(self, shop_profile_id: int, source_term: str, target_term: str):
        profile = self.shops.get(shop_profile_id)
        if not profile:
            raise KeyError(f"Khong tim thay shop profile {shop_profile_id}")
        return self.glossary.upsert(
            shop_profile_id,
            source_term,
            target_term,
            source_language=profile["source_language"],
        )

    def list_glossary_terms(self, shop_profile_id: int):
        return self.glossary.list_terms(shop_profile_id)

    def delete_glossary_term(self, term_id: int):
        self.glossary.delete(term_id)

    def _build_runner(self, project_id, event_callback, overrides=None):
        project = self.queue.get_project(project_id)
        if not project:
            raise KeyError(f"Khong tim thay project {project_id}")
        profile = self._profile_for_project(project)
        api_key = self.secrets.get("gemini_api_key") if profile["translation_mode"] == "gemini" else None
        config = PipelineConfig(
            source_language=profile["source_language"],
            translation_mode=profile["translation_mode"],
            gemini_api_key=api_key,
            subtitle_preset=profile["export_preset"],
            whisper_language_name=_whisper_language_name(profile["source_language"]),
            whisper_model=profile.get("whisper_model", "small"),
            model_root=str(self.models.model_root),
        )
        processors = PipelineProcessors(
            self.queue, config, localization_service=self._localization_service()
        ).as_dict()
        processors.update(overrides or {})
        return QueueRunner(self.queue, processors, event_callback)

    def _profile_for_project(self, project_or_job):
        profile_id = project_or_job.get("shop_profile_id")
        profile = self.shops.get(profile_id) if profile_id else None
        if not profile:
            raise RuntimeError("Project chua gan shop profile")
        return profile

    def _localization_service(self):
        from core.localization import LocalizationService

        return LocalizationService(self.glossary, self.memory, self.review)

    def _protected_workdirs(self):
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT jobs.id, projects.output_dir
                FROM jobs JOIN projects ON projects.id = jobs.project_id
                WHERE jobs.status NOT IN ('completed', 'canceled')
                """
            ).fetchall()
            return [
                Path(row["output_dir"]) / ".work" / f"job_{row['id']}"
                for row in rows
            ]
        finally:
            connection.close()


def _default_data_root():
    base = os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    return Path(base) / "VietDubStudio"


def _load_subtitle_if_present(path: str | None) -> SubtitleDocument:
    if not path or not Path(path).is_file():
        return SubtitleDocument([])
    try:
        return SubtitleDocument.load(path)
    except (OSError, UnicodeError, ValueError):
        return SubtitleDocument([])


def _whisper_language_name(source_language: str) -> str:
    try:
        return WHISPER_LANGUAGE_BY_SOURCE[source_language]
    except KeyError as error:
        raise ValueError(f"Ngon ngu nguon khong ho tro STT: {source_language}") from error
