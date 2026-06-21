import customtkinter as ctk

from ui.styles import DANGER, MUTED, PANEL, PRIMARY, SUCCESS, WARNING


class ReviewTab(ctk.CTkFrame):
    def __init__(self, master, backend, project_id_getter, on_continue):
        super().__init__(master, fg_color="transparent")
        self.backend = backend
        self.project_id_getter = project_id_getter
        self.on_continue = on_continue
        self.selected_job_id = None
        self.selected_entry_index = None
        self.workspace = None
        self._job_signature = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header, text="Kiểm tra bản dịch", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        self.job_menu = ctk.CTkOptionMenu(
            header, values=["Không có video cần kiểm tra"], command=self._select_job, width=270
        )
        self.job_menu.grid(row=0, column=1, sticky="e", padx=10)
        self.approve_button = ctk.CTkButton(
            header,
            text="Duyệt & tiếp tục xuất",
            width=180,
            fg_color=SUCCESS,
            command=self._approve,
        )
        self.approve_button.grid(row=0, column=2)

        self.info_label = ctk.CTkLabel(
            self,
            text="Chỉ những câu có nguy cơ sai mới xuất hiện ở đây.",
            text_color=MUTED,
        )
        self.info_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self.issue_list = ctk.CTkScrollableFrame(body, fg_color=PANEL, corner_radius=12)
        self.issue_list.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.issue_list.grid_columnconfigure(0, weight=1)

        editor = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12)
        editor.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(4, weight=1)
        self.entry_title = ctk.CTkLabel(
            editor, text="Chọn một câu cần kiểm tra", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.entry_title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        ctk.CTkLabel(editor, text="Câu gốc", text_color=MUTED).grid(
            row=1, column=0, sticky="w", padx=16
        )
        self.source_box = ctk.CTkTextbox(editor, height=90)
        self.source_box.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 12))
        self.source_box.configure(state="disabled")
        ctk.CTkLabel(editor, text="Bản dịch tiếng Việt", text_color=MUTED).grid(
            row=3, column=0, sticky="w", padx=16
        )
        self.translation_box = ctk.CTkTextbox(editor, height=150)
        self.translation_box.grid(row=4, column=0, sticky="nsew", padx=16, pady=(4, 10))
        self.issue_text = ctk.CTkLabel(
            editor, text="", text_color=WARNING, justify="left", wraplength=520
        )
        self.issue_text.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 8))
        actions = ctk.CTkFrame(editor, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 16))
        actions.grid_columnconfigure((0, 1), weight=1)
        self.save_button = ctk.CTkButton(
            actions, text="Lưu bản sửa", command=self._save, state="disabled"
        )
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.accept_button = ctk.CTkButton(
            actions,
            text="Chấp nhận cảnh báo",
            fg_color="#475569",
            command=self._accept,
            state="disabled",
        )
        self.accept_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def refresh(self, dashboard=None, force=False):
        review_jobs = [
            job for job in (dashboard["jobs"] if dashboard else [])
            if job["status"] in {"review", "completed"}
        ]
        signature = tuple((job["id"], job["updated_at"]) for job in review_jobs)
        if not force and signature == self._job_signature:
            return
        self._job_signature = signature
        self._job_map = {f"#{job['id']} · {_short(job['source_value'])}": job["id"] for job in review_jobs}
        values = list(self._job_map) or ["Không có video cần kiểm tra"]
        self.job_menu.configure(values=values)
        if self.selected_job_id not in self._job_map.values():
            self.selected_job_id = next(iter(self._job_map.values()), None)
        if self.selected_job_id:
            label = next(key for key, value in self._job_map.items() if value == self.selected_job_id)
            self.job_menu.set(label)
            self._load_workspace()
        else:
            self.job_menu.set(values[0])
            self._clear_workspace()

    def select_job(self, job_id):
        self.selected_job_id = job_id
        self._job_signature = None

    def _select_job(self, label):
        job_id = self._job_map.get(label)
        if job_id:
            self.selected_job_id = job_id
            self.selected_entry_index = None
            self._load_workspace()

    def _load_workspace(self):
        self.workspace = self.backend.review_workspace(self.selected_job_id)
        unresolved = [item for item in self.workspace["review_issues"] if not item["resolved"]]
        blocking = [item for item in unresolved if item["severity"] == "error"]
        completed = self.workspace["job"]["status"] == "completed"
        self.info_label.configure(text=f"Còn {len(unresolved)} cảnh báo cần xử lý")
        self.approve_button.configure(
            text="Xu\u1ea5t l\u1ea1i video" if completed else "Duy\u1ec7t & ti\u1ebfp t\u1ee5c xu\u1ea5t",
            state="normal" if not blocking else "disabled",
        )
        for child in self.issue_list.winfo_children():
            child.destroy()
        entries = self.workspace["entries"]
        if not entries:
            ctk.CTkLabel(
                self.issue_list,
                text="Đã xử lý hết cảnh báo.\nBạn có thể duyệt để tiếp tục xuất.",
                text_color=SUCCESS,
                justify="center",
            ).grid(row=0, column=0, pady=30, padx=12)
            self._clear_editor()
            return
        for row, entry in enumerate(entries):
            count = sum(not item["resolved"] for item in entry["issues"])
            text = entry["translated_text"].replace("\n", " ")
            if len(text) > 44:
                text = text[:41] + "..."
            ctk.CTkButton(
                self.issue_list,
                text=f"#{entry['index']}  [{count}]  {text}",
                anchor="w",
                fg_color="#1e293b" if entry["index"] != self.selected_entry_index else PRIMARY,
                command=lambda index=entry["index"]: self._select_entry(index),
            ).grid(row=row, column=0, sticky="ew", padx=8, pady=4)
        if self.selected_entry_index:
            self._show_entry(self.selected_entry_index)

    def _select_entry(self, entry_index):
        self.selected_entry_index = entry_index
        self._load_workspace()

    def _show_entry(self, entry_index):
        entry = next((item for item in self.workspace["entries"] if item["index"] == entry_index), None)
        if not entry:
            self._clear_editor()
            return
        self.entry_title.configure(text=f"Subtitle #{entry_index}")
        self.source_box.configure(state="normal")
        self.source_box.delete("1.0", "end")
        self.source_box.insert("1.0", entry["source_text"])
        self.source_box.configure(state="disabled")
        self.translation_box.delete("1.0", "end")
        self.translation_box.insert("1.0", entry["translated_text"])
        unresolved = [item for item in entry["issues"] if not item["resolved"]]
        self.issue_text.configure(
            text="\n".join(f"• {item['message']}" for item in unresolved)
        )
        self.save_button.configure(state="normal")
        self.accept_button.configure(state="normal" if unresolved else "disabled")

    def _save(self):
        text = self.translation_box.get("1.0", "end").strip()
        if not text:
            self.issue_text.configure(text="Bản dịch không được để trống.", text_color=DANGER)
            return
        self.backend.update_subtitle_text(self.selected_job_id, self.selected_entry_index, text)
        self._load_workspace()

    def _accept(self):
        entry = next(item for item in self.workspace["entries"] if item["index"] == self.selected_entry_index)
        for issue in entry["issues"]:
            if not issue["resolved"]:
                self.backend.resolve_issue(issue["id"])
        self._load_workspace()

    def _approve(self):
        if self.workspace["job"]["status"] == "completed":
            self.backend.reexport_job(self.selected_job_id)
        else:
            self.backend.approve_job(self.selected_job_id)
        project_id = self.project_id_getter()
        self.selected_job_id = None
        self.selected_entry_index = None
        self.on_continue(project_id)

    def _clear_workspace(self):
        self.info_label.configure(text="Không có video cần kiểm tra.")
        self.approve_button.configure(state="disabled")
        for child in self.issue_list.winfo_children():
            child.destroy()
        self._clear_editor()

    def _clear_editor(self):
        self.entry_title.configure(text="Chọn một câu cần kiểm tra")
        for box in (self.source_box, self.translation_box):
            box.configure(state="normal")
            box.delete("1.0", "end")
        self.source_box.configure(state="disabled")
        self.issue_text.configure(text="")
        self.save_button.configure(state="disabled")
        self.accept_button.configure(state="disabled")


def _short(value):
    value = str(value)
    return value if len(value) <= 38 else value[:35] + "..."
