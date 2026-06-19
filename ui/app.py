"""
VietSub Studio - Main UI
"""
import os
import sys
import threading
import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from downloader import download_video, is_bilibili_url
from bilibili_auth import (
    show_login_window,
    has_login_session,
    prepare_bilibili_session,
    LOGIN_COOKIE_FILE,
    GUEST_COOKIE_FILE,
)

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'downloads')


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('VietSub Studio')
        self.geometry('720x520')
        self.minsize(600, 420)

        self._build_ui()
        self._update_bilibili_status()

    def _build_ui(self):
        pad = {'padx': 16, 'pady': 8}

        ctk.CTkLabel(
            self, text='VietSub Studio', font=ctk.CTkFont(size=22, weight='bold'),
        ).pack(anchor='w', **pad)

        ctk.CTkLabel(self, text='URL video (YouTube / TikTok / Douyin / Bilibili):').pack(
            anchor='w', padx=16,
        )
        self.url_entry = ctk.CTkEntry(self, placeholder_text='Dan link hoac text share...')
        self.url_entry.pack(fill='x', **pad)

        quality_frame = ctk.CTkFrame(self, fg_color='transparent')
        quality_frame.pack(fill='x', **pad)

        ctk.CTkLabel(quality_frame, text='Bilibili:').pack(side='left')
        self.bili_quality = ctk.StringVar(value='guest')
        ctk.CTkRadioButton(
            quality_frame, text='720p (tu dong)', variable=self.bili_quality, value='guest',
        ).pack(side='left', padx=(8, 16))
        ctk.CTkRadioButton(
            quality_frame, text='1080p (can dang nhap)', variable=self.bili_quality, value='hd',
        ).pack(side='left')

        bili_frame = ctk.CTkFrame(self, fg_color='transparent')
        bili_frame.pack(fill='x', **pad)

        self.bili_status = ctk.CTkLabel(bili_frame, text='', text_color='gray')
        self.bili_status.pack(side='left')

        ctk.CTkButton(
            bili_frame,
            text='Ket noi Bilibili',
            width=140,
            command=self._on_bilibili_login,
        ).pack(side='right')

        self.progress_label = ctk.CTkLabel(self, text='San sang')
        self.progress_label.pack(anchor='w', **pad)

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill='x', padx=16, pady=(0, 8))
        self.progress_bar.set(0)

        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(fill='x', **pad)

        self.download_btn = ctk.CTkButton(
            btn_frame, text='Tai video', command=self._on_download,
        )
        self.download_btn.pack(side='left')

        self.log_box = ctk.CTkTextbox(self, height=160, state='disabled')
        self.log_box.pack(fill='both', expand=True, **pad)

    def _log(self, message: str):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', message + '\n')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def _update_bilibili_status(self):
        if has_login_session():
            self.bili_status.configure(
                text='Bilibili: da dang nhap (1080p)', text_color='#4ade80',
            )
        elif GUEST_COOKIE_FILE.is_file():
            self.bili_status.configure(
                text='Bilibili: session tu dong (720p)', text_color='gray',
            )
        else:
            self.bili_status.configure(
                text='Bilibili: chua ket noi (tu dong khi tai)', text_color='gray',
            )

    def _on_bilibili_login(self):
        self._log('Mo cua so dang nhap Bilibili...')
        self.bili_status.configure(text='Dang cho dang nhap...', text_color='#fbbf24')
        path = show_login_window()
        self._on_login_done(path)

    def _on_login_done(self, path):
        if path and os.path.isfile(path):
            self._log('Dang nhap Bilibili thanh cong!')
            self.bili_quality.set('hd')
        else:
            self._log('Chua luu duoc session dang nhap.')
        self._update_bilibili_status()

    def _on_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log('Vui long nhap URL.')
            return

        quality = self.bili_quality.get() if is_bilibili_url(url) else 'guest'
        cookies_file = None

        if is_bilibili_url(url):
            self._log('Chuan bi session Bilibili...')
            self.progress_label.configure(text='Dang ket noi Bilibili...')
            self.update_idletasks()
            cookie_path = prepare_bilibili_session(quality=quality, video_url=url)
            if not cookie_path:
                self._log('Khong lay duoc session Bilibili.')
                if quality == 'hd':
                    self._log('Nhan "Ket noi Bilibili" de dang nhap 1080p.')
                return
            cookies_file = str(cookie_path)
            self._update_bilibili_status()

        self.download_btn.configure(state='disabled')
        self.progress_bar.set(0.1)
        self.progress_label.configure(text='Dang tai...')

        def run():
            def progress(msg):
                self.after(0, lambda: self.progress_label.configure(text=msg))

            result = download_video(
                url=url,
                output_path=OUTPUT_DIR,
                progress_callback=progress,
                bilibili_quality=quality,
                cookies_file=cookies_file,
            )
            self.after(0, lambda: self._on_download_done(result))

        threading.Thread(target=run, daemon=True).start()

    def _on_download_done(self, result):
        self.download_btn.configure(state='normal')
        self.progress_bar.set(1.0 if result['success'] else 0)

        if result['success']:
            self.progress_label.configure(text='Tai xong!')
            self._log(f"OK: {result['title']}")
            self._log(f"File: {result['filepath']}")
        else:
            self.progress_label.configure(text='Loi')
            self._log(f"LOI: {result['error']}")
            if result.get('needs_bilibili_login'):
                self._log('-> Nhan "Ket noi Bilibili" de tai 1080p.')

        self._update_bilibili_status()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
