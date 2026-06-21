from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui.styles import MUTED, PANEL, PRIMARY, SUCCESS, WARNING


class InputTab(ctk.CTkFrame):
    def __init__(self, master, backend, project_id_getter, on_changed, on_start):
        super().__init__(master, fg_color="transparent")
        self.backend = backend
        self.project_id_getter = project_id_getter
        self.on_changed = on_changed
        self.on_start = on_start
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self,
            text="Thêm video cần Việt hóa",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            self,
            text="Dán nhiều link, hoặc chọn file/thư mục. Mỗi dòng có thể chứa một link.",
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        card.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        card.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(
            card,
            height=150,
            corner_radius=8,
            border_width=1,
            border_color="#263247",
        )
        self.input_box.grid(row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=14)

        ctk.CTkButton(
            card, text="+ Thêm link", fg_color=PRIMARY, command=self._add_links
        ).grid(row=1, column=0, padx=(14, 6), pady=(0, 14), sticky="ew")
        ctk.CTkButton(
            card, text="Chọn file", fg_color="#334155", command=self._choose_files
        ).grid(row=1, column=1, padx=6, pady=(0, 14), sticky="ew")
        ctk.CTkButton(
            card, text="Chọn thư mục", fg_color="#334155", command=self._choose_folder
        ).grid(row=1, column=2, padx=(6, 14), pady=(0, 14), sticky="ew")

        summary = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        summary.grid(row=3, column=0, sticky="nsew", padx=20, pady=12)
        summary.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            summary, text="Sẵn sàng xử lý", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        self.summary_label = ctk.CTkLabel(
            summary, text="Chưa có video trong danh sách.", text_color=MUTED, justify="left"
        )
        self.summary_label.grid(row=1, column=0, sticky="nw", padx=16, pady=(0, 12))
        self.message_label = ctk.CTkLabel(summary, text="", text_color=SUCCESS)
        self.message_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 8))
        self.start_button = ctk.CTkButton(
            summary,
            text="Bắt đầu Việt hóa",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.on_start,
        )
        self.start_button.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

    def refresh(self, dashboard=None):
        if not dashboard:
            self.summary_label.configure(text="Ứng dụng chưa sẵn sàng. Hãy khởi động lại.")
            self.start_button.configure(state="disabled")
            return
        counts = dashboard["counts"]
        total = len(dashboard["jobs"])
        review = counts.get("review", 0)
        completed = counts.get("completed", 0)
        self.summary_label.configure(
            text=f"{total} video  •  {completed} hoàn thành  •  {review} cần kiểm tra"
        )
        self.start_button.configure(state="normal" if total else "disabled")

    def set_message(self, text, *, warning=False):
        self.message_label.configure(text=text, text_color=WARNING if warning else SUCCESS)

    def _add_links(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            self.set_message("Chưa có link để thêm.", warning=True)
            return
        self._add_values([text])
        self.input_box.delete("1.0", "end")

    def _choose_files(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Chọn video",
            filetypes=[("Video", "*.mp4 *.mkv *.mov *.avi *.webm")],
        )
        if paths:
            self._add_values(list(paths))

    def _choose_folder(self):
        path = filedialog.askdirectory(parent=self, title="Chọn thư mục video")
        if path:
            self._add_values([path], recursive=True)

    def _add_values(self, values, recursive=False):
        project_id = self.project_id_getter()
        if not project_id:
            self.set_message("Không tìm thấy không gian làm việc. Hãy khởi động lại.", warning=True)
            return
        try:
            result = self.backend.add_inputs(project_id, values, recursive=recursive)
            message = f"Đã thêm {len(result['added'])} video"
            if result["duplicates"]:
                message += f", bỏ qua {len(result['duplicates'])} mục trùng"
            if result["invalid"] or result["errors"]:
                message += f", {len(result['invalid']) + len(result['errors'])} mục không hợp lệ"
            self.set_message(message, warning=bool(result["invalid"] or result["errors"]))
            self.on_changed()
        except Exception as error:
            self.set_message(str(error), warning=True)
