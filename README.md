# VietDub Studio

**Desktop Windows — AI Video Translator & Shorts Factory**

> Dịch video (Trung/YouTube/TikTok) sang tiếng Việt, tự tạo phụ đề và lồng tiếng AI, xuất MP4 hoàn chỉnh.

## Tính năng chính (V0.1 → V0.6)
- **Video Downloader**: tải video từ YouTube/TikTok/Douyin/Bilibili (dùng `yt-dlp`)
- **Import MP4**: kéo thả file và xử lý các codec phổ biến (H.264/H.265)
- **Speech-to-Text**: Faster Whisper (local) → tạo file **SRT**
- **Dịch subtitle**: Trung → Việt (deep-translator / Google Translate free)
- **Voice AI (TTS)**: Edge TTS → lồng tiếng Việt (cần Internet)
- **Video Export**: ghép video + subtitle + voice (FFmpeg) → **MP4**

## Triết lý sản phẩm
- **Chạy offline trên máy người dùng** (không cần server)
- **Mua 1 lần, dùng mãi** (không phí tháng)
- Core xử lý offline; một số tác vụ cần Internet như **Dịch** và **TTS**

## Kiến trúc tổng quan
```
[User PC]
    ↓
[Video Import / URL Download]
    ↓
[Speech-to-Text — Faster Whisper local]
    ↓
[Dịch thuật — deep-translator (Google Translate free)]
    ↓
[Voice AI — Edge TTS (cần Internet)]
    ↓
[Subtitle Render — FFmpeg]
    ↓
[Export MP4]
```

## Roadmap
Xem chi tiết trong `roadmap.md`.

## Yêu cầu & lưu ý
- **Internet**: cần cho **dịch thuật** (Google Translate) và **Edge TTS**
- **Model STT**: app sẽ cần cơ chế tải/ quản lý model Faster Whisper
- **FFmpeg**: dùng qua subprocess để render đúng chuẩn

## Project structure
- `ui/`: giao diện (CustomTkinter)
- `core/`: các module xử lý chính (downloader/transcriber/translator/tts/exporter)
- `utils/`: helpers như SQLite/cache/cleanup/license
- `assets/`: tài nguyên (logo, v.v.)

## Cài đặt
1) Cài Python
2) Tạo môi trường ảo (khuyến nghị)
3) `pip install -r requirements.txt`

## Bắt đầu
Chạy entry point trong dự án (tùy theo cách bạn cấu hình hiện tại).

## License
Xem phần mô tả trong code `utils/license.py` (HWID binding / activate theo máy).

