import threading

import customtkinter as ctk

from ui.styles import DANGER, MUTED, PANEL, PRIMARY, SUCCESS


LANGUAGE_OPTIONS = {
    "T\u1ef1 \u0111\u1ed9ng (khuy\u1ebfn ngh\u1ecb)": "auto",
    "Ti\u1ebfng Anh": "en",
    "Ti\u1ebfng Trung": "zh-CN",
    "Ti\u1ebfng Nh\u1eadt": "ja",
    "Ti\u1ebfng H\u00e0n": "ko",
}
LANGUAGE_LABELS = {value: label for label, value in LANGUAGE_OPTIONS.items()}
QUALITY_OPTIONS = {
    "Nhanh (base)": "base",
    "C\u00e2n b\u1eb1ng (small)": "small",
    "T\u1ed1t nh\u1ea5t (large-v3)": "large-v3",
}
QUALITY_LABELS = {value: label for label, value in QUALITY_OPTIONS.items()}


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, backend, shop_id_getter, on_shop_saved):
        super().__init__(master, fg_color="transparent")
        self.backend = backend
        self.shop_id_getter = shop_id_getter
        self.on_shop_saved = on_shop_saved
        self._profile_id = None
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Cài đặt", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(18, 10))

        left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(14, 6), pady=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        right = ctk.CTkScrollableFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 14), pady=(0, 14))
        right.grid_columnconfigure(0, weight=1)

        profile = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=12)
        profile.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        profile.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            profile, text="Cấu hình xử lý", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))
        self.shop_name = ctk.CTkEntry(profile, placeholder_text="Tên shop")
        self.language_menu = ctk.CTkOptionMenu(profile, values=list(LANGUAGE_OPTIONS))
        self.language_menu.grid(row=1, column=0, sticky="ew", padx=14, pady=5)
        self.translation_menu = ctk.CTkOptionMenu(profile, values=["google", "gemini"])
        self.translation_menu.grid(row=2, column=0, sticky="ew", padx=14, pady=5)
        self.preset_menu = ctk.CTkOptionMenu(profile, values=["shorts", "classic", "compact"])
        self.preset_menu.grid(row=3, column=0, sticky="ew", padx=14, pady=5)
        self.quality_menu = ctk.CTkOptionMenu(profile, values=list(QUALITY_OPTIONS))
        self.quality_menu.grid(row=4, column=0, sticky="ew", padx=14, pady=5)
        ctk.CTkButton(profile, text="Lưu cài đặt", command=self._save_profile).grid(
            row=5, column=0, sticky="ew", padx=14, pady=(8, 14)
        )

        api = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=12)
        api.grid(row=1, column=0, sticky="ew", pady=10)
        api.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(api, text="Gemini API", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 3)
        )
        self.api_status = ctk.CTkLabel(api, text="", text_color=MUTED)
        self.api_status.grid(row=1, column=0, sticky="w", padx=14)
        self.api_entry = ctk.CTkEntry(api, placeholder_text="Dán API key mới", show="•")
        self.api_entry.grid(row=2, column=0, sticky="ew", padx=14, pady=8)
        api_actions = ctk.CTkFrame(api, fg_color="transparent")
        api_actions.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(api_actions, text="Lưu key", command=self._save_api_key).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ctk.CTkButton(
            api_actions, text="Xóa key", fg_color="#475569", command=self._delete_api_key
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        models = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=12)
        models.grid(row=2, column=0, sticky="ew", pady=10)
        models.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            models, text="Model nhận dạng", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))
        self.model_frame = ctk.CTkFrame(models, fg_color="transparent")
        self.model_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 12))
        self.model_frame.grid_columnconfigure(0, weight=1)

        glossary = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=12)
        glossary.grid(row=0, column=0, sticky="nsew")
        glossary.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            glossary, text="Từ điển riêng", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 3))
        ctk.CTkLabel(
            glossary,
            text="Giữ tên sản phẩm và cách xưng hô nhất quán.",
            text_color=MUTED,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 8))
        self.source_term = ctk.CTkEntry(glossary, placeholder_text="Từ gốc")
        self.source_term.grid(row=2, column=0, sticky="ew", padx=(14, 4), pady=5)
        self.target_term = ctk.CTkEntry(glossary, placeholder_text="Cách dịch")
        self.target_term.grid(row=2, column=1, sticky="ew", padx=(4, 14), pady=5)
        ctk.CTkButton(glossary, text="+ Thêm thuật ngữ", command=self._add_term).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10)
        )
        self.glossary_frame = ctk.CTkFrame(glossary, fg_color="transparent")
        self.glossary_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 12))
        self.glossary_frame.grid_columnconfigure(0, weight=1)

    def refresh(self):
        profile_id = self.shop_id_getter()
        if not profile_id:
            return
        profile = self.backend.shops.get(profile_id)
        if not profile:
            return
        if profile_id != self._profile_id:
            self._profile_id = profile_id
            self.shop_name.delete(0, "end")
            self.shop_name.insert(0, profile["name"])
            self.language_menu.set(
                LANGUAGE_LABELS.get(profile["source_language"], next(iter(LANGUAGE_OPTIONS)))
            )
            self.translation_menu.set(profile["translation_mode"])
            self.preset_menu.set(profile["export_preset"])
            self.quality_menu.set(
                QUALITY_LABELS.get(
                    profile.get("whisper_model", "small"),
                    QUALITY_LABELS["small"],
                )
            )
        self.api_status.configure(
            text="Đã lưu key an toàn bằng Windows DPAPI" if self.backend.has_gemini_api_key()
            else "Chưa cấu hình Gemini API key",
            text_color=SUCCESS if self.backend.has_gemini_api_key() else MUTED,
        )
        self._refresh_models()
        self._refresh_glossary()

    def _save_profile(self):
        self.backend.update_shop(
            self._profile_id,
            name=self.shop_name.get().strip(),
            source_language=LANGUAGE_OPTIONS[self.language_menu.get()],
            translation_mode=self.translation_menu.get(),
            export_preset=self.preset_menu.get(),
            whisper_model=QUALITY_OPTIONS[self.quality_menu.get()],
        )
        self.on_shop_saved()

    def _save_api_key(self):
        key = self.api_entry.get().strip()
        if key:
            self.backend.set_gemini_api_key(key)
            self.api_entry.delete(0, "end")
            self.refresh()

    def _delete_api_key(self):
        self.backend.set_gemini_api_key("")
        self.refresh()

    def _refresh_models(self):
        for child in self.model_frame.winfo_children():
            child.destroy()
        for row, model in enumerate(self.backend.model_status()):
            size_mb = model["size_bytes"] / 1024 / 1024
            status = f"Đã tải · {size_mb:.0f} MB" if model["downloaded"] else "Chưa tải"
            ctk.CTkLabel(self.model_frame, text=f"{model['model']}  —  {status}", anchor="w").grid(
                row=row, column=0, sticky="ew", padx=4, pady=4
            )
            if not model["downloaded"]:
                ctk.CTkButton(
                    self.model_frame,
                    text="Tải",
                    width=65,
                    command=lambda name=model["model"]: self._download_model(name),
                ).grid(row=row, column=1, padx=4, pady=4)

    def _download_model(self, model_name):
        def run():
            result = self.backend.download_model(
                model_name,
                progress_callback=lambda text: self.after(
                    0, lambda value=text: self.api_status.configure(text=value, text_color=PRIMARY)
                ),
            )
            self.after(
                0,
                lambda: self.api_status.configure(
                    text="Tải model thành công" if result["success"] else result["error"],
                    text_color=SUCCESS if result["success"] else DANGER,
                ),
            )
            self.after(0, self._refresh_models)

        threading.Thread(target=run, daemon=True).start()

    def _add_term(self):
        source, target = self.source_term.get().strip(), self.target_term.get().strip()
        if not source or not target:
            return
        self.backend.add_glossary_term(self._profile_id, source, target)
        self.source_term.delete(0, "end")
        self.target_term.delete(0, "end")
        self._refresh_glossary()

    def _refresh_glossary(self):
        for child in self.glossary_frame.winfo_children():
            child.destroy()
        terms = self.backend.list_glossary_terms(self._profile_id)
        if not terms:
            ctk.CTkLabel(
                self.glossary_frame, text="Chưa có thuật ngữ.", text_color=MUTED
            ).grid(row=0, column=0, pady=20)
            return
        for row, term in enumerate(terms):
            ctk.CTkLabel(
                self.glossary_frame,
                text=f"{term['source_term']}  →  {term['target_term']}",
                anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=4, pady=4)
            ctk.CTkButton(
                self.glossary_frame,
                text="Xóa",
                width=55,
                fg_color="#475569",
                command=lambda term_id=term["id"]: self._delete_term(term_id),
            ).grid(row=row, column=1, padx=4, pady=4)

    def _delete_term(self, term_id):
        self.backend.delete_glossary_term(term_id)
        self._refresh_glossary()
