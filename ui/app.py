"""VietDub Studio desktop application shell."""

from __future__ import annotations

import sys
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.backend import VietDubBackend
from ui.styles import BG, BORDER, MUTED, PANEL, PRIMARY, SUCCESS, WARNING
from ui.tab_input import InputTab
from ui.tab_queue import QueueTab
from ui.tab_review import ReviewTab
from ui.tab_settings import SettingsTab


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self, backend=None):
        super().__init__(fg_color=BG)
        self.backend = backend or VietDubBackend()
        self.backend.initialize()
        self.title("VietDub Studio")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._shop_map = {}
        self._project_map = {}
        self._selected_shop_id = None
        self._selected_project_id = None
        self._ensure_onboarding()
        self._build_ui()
        self._refresh_selectors()
        self._refresh_all(force=True)
        self.after(1200, self._tick)

    def _ensure_onboarding(self):
        shops = self.backend.list_shops()
        if not shops:
            shop_id = self.backend.create_shop("Shop mặc định")
            self.backend.create_project("Dự án đầu tiên", shop_id)
            shops = self.backend.list_shops()
        self._selected_shop_id = shops[0]["id"]
        projects = self.backend.list_projects(self._selected_shop_id)
        if not projects:
            self._selected_project_id = self.backend.create_project(
                "Dự án đầu tiên", self._selected_shop_id
            )
        else:
            self._selected_project_id = projects[0]["id"]

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            self, height=76, fg_color=PANEL, corner_radius=0, border_width=0
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text="VIETDUB",
            text_color=PRIMARY,
            font=ctk.CTkFont(size=23, weight="bold"),
        ).grid(row=0, column=0, padx=(20, 14), pady=18)
        self.global_status = ctk.CTkLabel(header, text="Sẵn sàng", text_color=MUTED)
        self.global_status.grid(row=0, column=1, sticky="e", padx=14)
        ctk.CTkButton(
            header,
            text="+ Thêm video",
            width=110,
            command=lambda: self.tabview.set("1. Thêm video"),
        ).grid(row=0, column=2, padx=(5, 20))

        self.tabview = ctk.CTkTabview(
            self,
            fg_color=BG,
            segmented_button_fg_color=PANEL,
            segmented_button_selected_color=PRIMARY,
            segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color="#1e293b",
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        for name in ("1. Thêm video", "2. Hàng đợi", "3. Kiểm tra", "4. Cài đặt"):
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self.input_tab = InputTab(
            self.tabview.tab("1. Thêm video"),
            self.backend,
            self.get_project_id,
            lambda: self._refresh_all(force=True),
            self._start_processing,
        )
        self.input_tab.grid(row=0, column=0, sticky="nsew")
        self.queue_tab = QueueTab(
            self.tabview.tab("2. Hàng đợi"),
            self.backend,
            self.get_project_id,
            self._start_processing,
            self._open_review,
        )
        self.queue_tab.grid(row=0, column=0, sticky="nsew")
        self.review_tab = ReviewTab(
            self.tabview.tab("3. Kiểm tra"),
            self.backend,
            self.get_project_id,
            self._continue_after_review,
        )
        self.review_tab.grid(row=0, column=0, sticky="nsew")
        self.settings_tab = SettingsTab(
            self.tabview.tab("4. Cài đặt"),
            self.backend,
            self.get_shop_id,
            self._shop_saved,
        )
        self.settings_tab.grid(row=0, column=0, sticky="nsew")

    def get_shop_id(self):
        return self._selected_shop_id

    def get_project_id(self):
        return self._selected_project_id

    def _refresh_selectors(self):
        shops = self.backend.list_shops()
        self._shop_map = {f"{item['name']}": item["id"] for item in shops}
        if self._selected_shop_id not in self._shop_map.values():
            self._selected_shop_id = next(iter(self._shop_map.values()), None)

        projects = self.backend.list_projects(self._selected_shop_id)
        self._project_map = {f"#{item['id']} · {item['name']}": item["id"] for item in projects}
        if self._selected_project_id not in self._project_map.values():
            self._selected_project_id = next(iter(self._project_map.values()), None)

    def _refresh_all(self, force=False):
        dashboard = None
        if self._selected_project_id:
            try:
                dashboard = self.backend.project_dashboard(self._selected_project_id)
            except KeyError:
                self._selected_project_id = None
        self.input_tab.refresh(dashboard)
        self.queue_tab.refresh(dashboard)
        self.review_tab.refresh(dashboard, force=force)
        if self.tabview.get() == "4. Cài đặt":
            self.settings_tab.refresh()

    def _tick(self):
        try:
            self._refresh_all()
        finally:
            if self.winfo_exists():
                self.after(1200, self._tick)

    def _start_processing(self):
        project_id = self.get_project_id()
        if not project_id:
            return
        if self.backend.is_processing():
            self.tabview.set("2. Hàng đợi")
            return
        try:
            self.backend.start_project(project_id, event_callback=self._queue_event)
            self.global_status.configure(text="Đang xử lý...", text_color=PRIMARY)
            self.tabview.set("2. Hàng đợi")
            self._refresh_all(force=True)
        except Exception as error:
            messagebox.showerror("Không thể chạy", str(error), parent=self)

    def _queue_event(self, event):
        try:
            self.after(0, lambda value=event: self._handle_queue_event(value))
        except RuntimeError:
            pass

    def _handle_queue_event(self, event):
        event_name = event["event"]
        if event_name == "progress":
            self.global_status.configure(text=str(event["detail"]), text_color=PRIMARY)
        elif event_name == "failed":
            self.global_status.configure(text="Có job bị lỗi", text_color="#ef4444")
        elif event_name == "idle":
            self.global_status.configure(text="Đã xử lý xong hàng đợi", text_color=SUCCESS)
        elif event_name == "interrupted":
            self.global_status.configure(text="Đã tạm dừng", text_color=WARNING)
        self._refresh_all(force=True)

    def _open_review(self, job_id):
        self.review_tab.select_job(job_id)
        self.tabview.set("3. Kiểm tra")
        self._refresh_all(force=True)

    def _continue_after_review(self, project_id):
        self._refresh_all(force=True)
        self._start_processing()

    def _on_shop_selected(self, label):
        self._selected_shop_id = self._shop_map.get(label)
        self._selected_project_id = None
        self._refresh_selectors()
        self._refresh_all(force=True)

    def _on_project_selected(self, label):
        self._selected_project_id = self._project_map.get(label)
        self._refresh_all(force=True)

    def _new_shop(self):
        dialog = ctk.CTkInputDialog(text="Tên shop hoặc khách hàng:", title="Tạo shop")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        try:
            shop_id = self.backend.create_shop(name.strip())
            project_id = self.backend.create_project("Dự án đầu tiên", shop_id)
            self._selected_shop_id = shop_id
            self._selected_project_id = project_id
            self._refresh_selectors()
            self._refresh_all(force=True)
        except Exception as error:
            messagebox.showerror("Không tạo được shop", str(error), parent=self)

    def _new_project(self):
        if not self._selected_shop_id:
            return
        dialog = ctk.CTkInputDialog(text="Tên dự án:", title="Tạo dự án")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        output_dir = filedialog.askdirectory(
            parent=self,
            title="Chọn thư mục xuất (Cancel để dùng mặc định)",
        )
        try:
            project_id = self.backend.create_project(
                name.strip(), self._selected_shop_id, output_dir or None
            )
            self._selected_project_id = project_id
            self._refresh_selectors()
            self._refresh_all(force=True)
        except Exception as error:
            messagebox.showerror("Không tạo được dự án", str(error), parent=self)

    def _shop_saved(self):
        self._refresh_selectors()
        self._refresh_all(force=True)
        self.global_status.configure(text="Đã lưu cài đặt", text_color=SUCCESS)

    def _on_close(self):
        try:
            self.backend.stop_project()
        finally:
            self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
