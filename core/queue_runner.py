"""Worker dieu phoi cac processor dua tren persistent ProjectQueue."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from core.project_queue import ProjectQueue


@dataclass
class StepResult:
    success: bool
    output_path: str | None = None
    local_video_path: str | None = None
    artifacts: list[tuple[str, str, dict]] = field(default_factory=list)
    error: str | None = None
    requires_review: bool = True


class QueueRunner:
    def __init__(self, queue: ProjectQueue, processors: dict[str, Callable], event_callback=None):
        self.queue = queue
        self.processors = processors
        self.event_callback = event_callback
        self._stop_event = threading.Event()
        self._thread = None
        self._active_job_id = None
        self._cancel_flag = None
        self._cancel_active_on_stop = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, project_id: int | None = None):
        if self.is_running:
            raise RuntimeError("QueueRunner dang chay")
        self._stop_event.clear()
        self.queue.recover_interrupted_jobs()
        self._thread = threading.Thread(
            target=self.run_until_idle, args=(project_id,), daemon=True, name="vietdub-queue"
        )
        self._thread.start()

    def stop(self, *, wait: bool = True, cancel_active: bool = False):
        self._cancel_active_on_stop = cancel_active
        self._stop_event.set()
        with self._lock:
            if self._cancel_flag is not None:
                self._cancel_flag[0] = True
        if wait and self._thread:
            self._thread.join(timeout=10)

    def cancel_job(self, job_id: int):
        with self._lock:
            if self._active_job_id == job_id and self._cancel_flag is not None:
                self._cancel_flag[0] = True
        self.queue.cancel_job(job_id)

    def run_once(self, project_id: int | None = None) -> bool:
        if self._stop_event.is_set():
            return False
        job = self.queue.claim_next_job(project_id)
        if not job:
            return False
        job_id = int(job["id"])
        step = job["current_step"]
        processor = self.processors.get(step)
        if not processor:
            self.queue.fail_job(job_id, f"Chua co processor cho step {step}")
            self._emit("failed", job_id, step, f"Missing processor: {step}")
            return True

        cancel_flag = [False]
        with self._lock:
            self._active_job_id = job_id
            self._cancel_flag = cancel_flag

        def progress(value):
            numeric = _progress_number(value)
            if numeric is not None:
                self.queue.update_progress(job_id, numeric)
            self._emit("progress", job_id, step, value)

        self._emit("started", job_id, step, None)
        try:
            raw_result = processor(job, progress, cancel_flag)
            result = _coerce_result(raw_result)
            if cancel_flag[0] or self._stop_event.is_set():
                current = self.queue.get_job(job_id)
                if current and current["status"] not in {"canceled", "completed"}:
                    if self._stop_event.is_set() and not self._cancel_active_on_stop:
                        self.queue.interrupt_job(job_id)
                        self._emit("interrupted", job_id, step, None)
                    else:
                        self.queue.cancel_job(job_id)
                        self._emit("canceled", job_id, step, None)
                return True
            if not result.success:
                self.queue.fail_job(job_id, result.error or "Processor that bai")
                self._emit("failed", job_id, step, result.error)
                return True
            if result.local_video_path:
                self.queue.set_local_video_path(job_id, result.local_video_path)
            for artifact_type, path, metadata in result.artifacts:
                self.queue.add_artifact(job_id, artifact_type, path, metadata)
            next_status = self.queue.complete_current_step(job_id, result.output_path)
            if next_status == "review" and not result.requires_review:
                self.queue.approve_review(job_id)
                next_status = "pending"
            self._emit("completed_step", job_id, step, next_status)
            return True
        except Exception as error:
            self.queue.fail_job(job_id, str(error))
            self._emit("failed", job_id, step, str(error))
            return True
        finally:
            with self._lock:
                self._active_job_id = None
                self._cancel_flag = None

    def run_until_idle(self, project_id: int | None = None, max_steps: int | None = None):
        completed_steps = 0
        while not self._stop_event.is_set():
            if max_steps is not None and completed_steps >= max_steps:
                break
            if not self.run_once(project_id):
                break
            completed_steps += 1
        self._emit("idle", None, None, completed_steps)
        return completed_steps

    def _emit(self, event, job_id, step, detail):
        if self.event_callback:
            self.event_callback(
                {"event": event, "job_id": job_id, "step": step, "detail": detail}
            )


def _coerce_result(result) -> StepResult:
    if isinstance(result, StepResult):
        return result
    if isinstance(result, dict):
        artifacts = result.get("artifacts", [])
        return StepResult(
            success=bool(result.get("success")),
            output_path=result.get("output_path") or result.get("srt_path") or result.get("filepath"),
            local_video_path=result.get("local_video_path"),
            artifacts=artifacts,
            error=result.get("error"),
            requires_review=bool(result.get("requires_review", True)),
        )
    raise TypeError("Processor phai tra StepResult hoac dict")


def _progress_number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        import re

        match = re.search(r"(\d+(?:\.\d+)?)\s*%", value)
        if match:
            return float(match.group(1))
    return None
