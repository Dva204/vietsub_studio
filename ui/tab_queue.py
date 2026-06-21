import os
import threading
from pathlib import Path

import customtkinter as ctk

from ui.styles import DANGER, MUTED, PANEL, PANEL_ALT, PRIMARY, STATUS_LABELS, STEP_LABELS


class QueueTab(ctk.CTkFrame):
    def __init__(self, master, backend, project_id_getter, on_start, on_review):
        super().__init__(master, fg_color="transparent")
        self.backend = backend
        self.project_id_getter = project_id_getter
        self.on_start = on_start
        self.on_review = on_review
        self._signature = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Hàng đợi xử lý", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        self.start_button = ctk.CTkButton(
            header, text="Chạy hàng đợi", width=140, command=self.on_start
        )
        self.start_button.grid(row=0, column=1, padx=(8, 0))
        self.stop_button = ctk.CTkButton(
            header,
            text="Dừng",
            width=90,
            fg_color="#334155",
            command=self._stop,
        )
        self.stop_button.grid(row=0, column=2, padx=(8, 0))

        self.summary_label = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.summary_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        self.jobs_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.jobs_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.jobs_frame.grid_columnconfigure(0, weight=1)

    def refresh(self, dashboard=None):
        jobs = dashboard["jobs"] if dashboard else []
        signature = tuple(
            (job["id"], job["status"], job["current_step"], round(job["progress"], 1), job["error"])
            for job in jobs
        )
        processing = self.backend.is_processing()
        self.start_button.configure(state="disabled" if processing or not jobs else "normal")
        self.stop_button.configure(state="normal" if processing else "disabled")
        if dashboard:
            counts = dashboard["counts"]
            self.summary_label.configure(
                text=(
                    f"Tổng {len(jobs)}  •  Đang chạy {counts.get('running', 0)}  •  "
                    f"Cần kiểm tra {counts.get('review', 0)}  •  Hoàn thành {counts.get('completed', 0)}"
                )
            )
        if signature == self._signature:
            return
        self._signature = signature
        for child in self.jobs_frame.winfo_children():
            child.destroy()
        if not jobs:
            ctk.CTkLabel(
                self.jobs_frame,
                text="Chưa có video. Hãy thêm video ở bước 1.",
                text_color=MUTED,
            ).grid(row=0, column=0, pady=30)
            return
        for row, job in enumerate(jobs):
            self._build_job_card(row, job)

    def _build_job_card(self, row, job):
        card = ctk.CTkFrame(self.jobs_frame, fg_color=PANEL, corner_radius=10)
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=5)
        card.grid_columnconfigure(0, weight=1)
        if job.get("local_video_path"):
            name = Path(job["local_video_path"]).stem
        else:
            name = Path(job["source_value"]).name if job["source_type"] == "file" else job["source_value"]
        if len(name) > 78:
            name = name[:75] + "..."
        ctk.CTkLabel(
            card, text=f"#{job['id']}  {name}", font=ctk.CTkFont(weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 3))
        status_text, status_color = STATUS_LABELS.get(job["status"], (job["status"], MUTED))
        ctk.CTkLabel(card, text=status_text, text_color=status_color).grid(
            row=0, column=1, padx=12, pady=(12, 3)
        )
        step = STEP_LABELS.get(job["current_step"], job["current_step"])
        detail = step if not job["error"] else f"{step} • {job['error']}"
        ctk.CTkLabel(card, text=detail, text_color=MUTED, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 5)
        )
        progress = ctk.CTkProgressBar(card, height=7)
        progress.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        progress.set(min(1, max(0, job["progress"] / 100)))
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.grid(row=1, column=1, rowspan=2, padx=10, pady=(0, 8))
        if job["status"] == "failed":
            ctk.CTkButton(
                action_frame,
                text="Thử lại",
                width=80,
                command=lambda job_id=job["id"]: self._retry(job_id),
            ).pack()
        elif job["status"] == "review":
            ctk.CTkButton(
                action_frame,
                text="Kiểm tra",
                width=80,
                fg_color="#d97706",
                command=lambda job_id=job["id"]: self.on_review(job_id),
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                action_frame,
                text="L\u00e0m l\u1ea1i",
                width=70,
                command=lambda job_id=job["id"]: self._reprocess(job_id),
            ).pack(side="left")
        elif job["status"] in {"pending", "running"}:
            ctk.CTkButton(
                action_frame,
                text="Hủy",
                width=80,
                fg_color=DANGER,
                command=lambda job_id=job["id"]: self._cancel(job_id),
            ).pack()
        elif job["status"] == "completed":
            ctk.CTkButton(
                action_frame,
                text="Mở",
                width=80,
                fg_color="#334155",
                command=lambda job_id=job["id"]: self._open_video(job_id),
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                action_frame,
                text="S\u1eeda sub",
                width=70,
                fg_color="#475569",
                command=lambda job_id=job["id"]: self.on_review(job_id),
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                action_frame,
                text="Th\u01b0 m\u1ee5c",
                width=70,
                fg_color="#475569",
                command=lambda job_id=job["id"]: self._open_output(job_id),
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                action_frame,
                text="L\u00e0m l\u1ea1i",
                width=70,
                command=lambda job_id=job["id"]: self._reprocess(job_id),
            ).pack(side="left")

    def _retry(self, job_id):
        self.backend.retry_job(job_id)
        self._signature = None
        self.on_start()

    def _reprocess(self, job_id):
        self.backend.reprocess_job(job_id)
        self._signature = None
        self.on_start()

    def _cancel(self, job_id):
        try:
            self.backend.cancel_job(job_id)
        finally:
            self._signature = None

    def _stop(self):
        self.stop_button.configure(state="disabled", text="Đang dừng...")

        def run():
            self.backend.stop_project()
            self.after(0, lambda: self.stop_button.configure(text="Dừng"))
            self._signature = None

        threading.Thread(target=run, daemon=True).start()

    def _open_output(self, job_id):
        detail = self.backend.job_detail(job_id)
        packages = [item for item in detail["artifacts"] if item["artifact_type"] == "package"]
        if packages and hasattr(os, "startfile"):
            os.startfile(packages[-1]["path"])

    def _open_video(self, job_id):
        detail = self.backend.job_detail(job_id)
        artifacts = detail["artifacts"]
        videos = [item for item in artifacts if item["artifact_type"] == "subtitled_video"]
        path = videos[-1]["path"] if videos else detail["job"].get("local_video_path")
        if path and Path(path).is_file() and hasattr(os, "startfile"):
            os.startfile(path)
