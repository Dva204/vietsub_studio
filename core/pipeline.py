"""Production processor adapters cho ProjectQueue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.glossary import GlossaryRepository
from core.localization import LocalizationService
from core.package_exporter import export_package
from core.project_queue import ProjectQueue
from core.queue_runner import StepResult
from core.review import ReviewService
from core.translation_memory import TranslationMemoryRepository


@dataclass
class PipelineConfig:
    source_language: str = "auto"
    translation_mode: str = "google"
    gemini_api_key: str | None = None
    subtitle_preset: str = "shorts"
    whisper_model: str = "base"
    whisper_language_name: str = "Tu dong"
    burn_subtitles: bool = True
    model_root: str | None = None


class PipelineProcessors:
    def __init__(
        self,
        queue: ProjectQueue,
        config: PipelineConfig | None = None,
        *,
        localization_service=None,
        download_func=None,
        transcribe_func=None,
        export_video_func=None,
        package_func=export_package,
    ):
        self.queue = queue
        self.config = config or PipelineConfig()
        self.localization = localization_service or LocalizationService(
            GlossaryRepository(queue.database),
            TranslationMemoryRepository(queue.database),
            ReviewService(queue.database),
        )
        self.download_func = download_func
        self.transcribe_func = transcribe_func
        self.export_video_func = export_video_func
        self.package_func = package_func

    def as_dict(self):
        return {
            "acquire": self.acquire,
            "transcribe": self.transcribe,
            "translate": self.translate,
            "export": self.export,
        }

    def acquire(self, job, progress, cancel_flag):
        work_dir = self._work_dir(job)
        if job["source_type"] == "file":
            source = Path(job["source_value"])
            if not source.is_file():
                return StepResult(False, error="File video nguon khong ton tai")
            path = str(source.resolve())
            return StepResult(
                True,
                output_path=path,
                local_video_path=path,
                artifacts=[("source_video", path, {"source_type": "file"})],
            )

        if self.download_func is None:
            from core.downloader import download_video

            self.download_func = download_video
        result = self.download_func(
            url=job["source_value"],
            output_path=str(work_dir),
            progress_callback=progress,
            cancel_flag=cancel_flag,
        )
        if not result.get("success"):
            return StepResult(False, error=result.get("error") or "Download that bai")
        path = result["filepath"]
        return StepResult(
            True,
            output_path=path,
            local_video_path=path,
            artifacts=[("source_video", path, {"source_type": "url", "title": result.get("title")})],
        )

    def transcribe(self, job, progress, cancel_flag):
        video = self._artifact(job["id"], "source_video") or job.get("local_video_path")
        if not video:
            return StepResult(False, error="Khong tim thay source video")
        if self.transcribe_func is None:
            from core.transcriber import transcribe_video

            self.transcribe_func = transcribe_video
        result = self.transcribe_func(
            video_path=video,
            language=self.config.whisper_language_name,
            model_size=self.config.whisper_model,
            progress_callback=progress,
            cancel_flag=cancel_flag,
            model_dir=self.config.model_root,
        )
        if not result.get("success"):
            return StepResult(False, error=result.get("error") or "STT that bai")
        path = result["srt_path"]
        return StepResult(
            True,
            output_path=path,
            artifacts=[
                (
                    "source_srt",
                    path,
                    {
                        "segments": result.get("segment_count"),
                        "rescued_segments": result.get("rescued_segments", 0),
                        "detected_language": result.get("detected_language"),
                    },
                )
            ],
        )

    def translate(self, job, progress, cancel_flag):
        source_srt = self._artifact(job["id"], "source_srt")
        if not source_srt:
            return StepResult(False, error="Khong tim thay source SRT")
        if not job.get("shop_profile_id"):
            return StepResult(False, error="Project chua gan shop profile")
        output = self._work_dir(job) / "subtitle.vi.srt"
        result = self.localization.localize_srt(
            source_srt,
            shop_profile_id=job["shop_profile_id"],
            job_id=job["id"],
            mode=self.config.translation_mode,
            source_language=self.config.source_language,
            output_path=str(output),
            api_key=self.config.gemini_api_key,
            progress_callback=progress,
            cancel_flag=cancel_flag,
        )
        if not result.get("success"):
            return StepResult(False, error=result.get("error") or "Dich that bai")
        return StepResult(
            True,
            output_path=result["output_path"],
            artifacts=[
                (
                    "translated_srt",
                    result["output_path"],
                    {"review_issues": result["review_issues"], "memory_hits": result["memory_hits"]},
                )
            ],
            requires_review=result["requires_review"],
        )

    def export(self, job, progress, cancel_flag):
        source_video = self._artifact(job["id"], "source_video")
        translated_srt = self._artifact(job["id"], "translated_srt")
        if not source_video or not translated_srt:
            return StepResult(False, error="Thieu source video hoac translated SRT")
        work_dir = self._work_dir(job)
        rendered_path = None

        if self.config.burn_subtitles:
            if self.export_video_func is None:
                from core.exporter import export_subtitled_video

                self.export_video_func = export_subtitled_video
            rendered_path = str(work_dir / "subtitled.mp4")
            rendered = self.export_video_func(
                source_video,
                translated_srt,
                rendered_path,
                subtitle_preset=self.config.subtitle_preset,
                progress_callback=progress,
                cancel_flag=cancel_flag,
            )
            if not rendered.get("success"):
                return StepResult(False, error=rendered.get("error") or "Render that bai")

        package_name = Path(source_video).stem
        packaged = self.package_func(
            job["output_dir"],
            package_name,
            source_video=source_video,
            translated_srt=translated_srt,
            subtitled_video=rendered_path,
            metadata={"job_id": job["id"], "source": job["source_value"]},
        )
        if not packaged.get("success"):
            return StepResult(False, error=packaged.get("error") or "Package export that bai")
        artifacts = [("package", packaged["package_path"], {})]
        if rendered_path:
            artifacts.append(("subtitled_video", rendered_path, {}))
        return StepResult(True, output_path=packaged["package_path"], artifacts=artifacts)

    def _work_dir(self, job):
        path = Path(job["output_dir"]) / ".work" / f"job_{job['id']}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _artifact(self, job_id, artifact_type):
        matches = [
            item for item in self.queue.list_artifacts(job_id)
            if item["artifact_type"] == artifact_type
        ]
        return matches[-1]["path"] if matches else None
