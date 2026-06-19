# ROADMAP.md

# VIETDUB STUDIO

## AI Video Translator & Shorts Factory (Desktop Windows)

**Version:** Business Plan 2.1 — Python Core, Offline-First  
**Author:** An Đỗ Văn  
**Cập nhật:** 2025

---

# 1. TẦM NHÌN

VietDub Studio là phần mềm Desktop Windows giúp người dùng:

- Dịch video Trung Quốc, YouTube, TikTok sang tiếng Việt
- Tạo phụ đề tiếng Việt tự động
- Lồng tiếng AI tiếng Việt
- Xuất video hoàn chỉnh định dạng MP4

**Toàn bộ chạy trên máy người dùng. Không cần server. Không cần trả phí tháng.**

---

# 2. TRIẾT LÝ SẢN PHẨM

| Người Việt thích | Người Việt không thích |
|---|---|
| ✅ Mua 1 lần, dùng mãi | ❌ Trả tiền hàng tháng |
| ✅ Chạy offline | ❌ Upload video lên server |
| ✅ Không cần API riêng | ❌ Mua tool xong phải mua thêm API |

**Mục tiêu V1:** "Không phát sinh chi phí sau khi mua"

---

# 3. KHÁCH HÀNG MỤC TIÊU

| Nhóm | Nhu cầu chính |
|---|---|
| TikTok Creator | Dịch video Trung, tạo content nhanh |
| YouTube Shorts | Tạo Shorts từ video nước ngoài |
| MMO / Affiliate | Kiếm tiền từ video, content số lượng lớn |
| Chủ Shop | Video marketing sản phẩm |

---

# 4. MÔ HÌNH KỸ THUẬT

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

> **Lưu ý:** Không có server render. Edge TTS và dịch thuật cần kết nối Internet. Các bước còn lại hoàn toàn offline.

---

# 5. CÔNG NGHỆ (ĐÃ TỐI ƯU)

| Thành phần | Công nghệ | Lý do chọn |
|---|---|---|
| **UI** | Python + CustomTkinter | Giao diện hiện đại, dark mode, dễ code hơn WPF nhiều |
| **Video processing** | FFmpeg (subprocess) | Không thay thế được, chuẩn công nghiệp |
| **Downloader** | yt-dlp | Hỗ trợ YouTube, TikTok, Bilibili, Douyin |
| **Speech-to-Text** | Faster Whisper | Python native, hỗ trợ Trung/Anh/Nhật/Hàn |
| **Dịch thuật** | deep-translator (Google Translate free) | Trung→Việt chất lượng tốt, không cần API key |
| **TTS** | Edge TTS | Miễn phí, giọng Việt tự nhiên, cần Internet |
| **Database** | SQLite (built-in Python) | Không cài thêm, đủ dùng cho project manager |
| **Packaging** | PyInstaller | Đóng gói thành .exe Windows |
| **License** | HWID hash (tự build) | Offline-friendly, không cần server |

### So sánh với Tech Stack cũ

| | Cũ (C# WPF) | Mới (Python) |
|---|---|---|
| Learning curve | Cao | Thấp |
| AI coding support | Trung bình | Tốt |
| Debug & test | Phải build | Chạy thẳng `python main.py` |
| Community & example | Ít | Nhiều |
| Thời gian ra MVP | Dài hơn | Nhanh hơn |

---

# 6. CẤU TRÚC PROJECT

```
vietdub-studio/
├── main.py                  # Entry point
├── ui/
│   ├── app.py               # Main window (CustomTkinter)
│   ├── tab_downloader.py    # Tab tải video
│   ├── tab_subtitle.py      # Tab subtitle + dịch
│   ├── tab_voice.py         # Tab lồng tiếng
│   └── tab_export.py        # Tab xuất video
├── core/
│   ├── downloader.py        # yt-dlp wrapper
│   ├── transcriber.py       # Faster Whisper wrapper
│   ├── translator.py        # deep-translator wrapper
│   ├── tts.py               # Edge TTS wrapper
│   └── exporter.py          # FFmpeg wrapper
├── utils/
│   ├── db.py                # SQLite helpers
│   ├── license.py           # HWID + key check
│   └── cleaner.py           # Dọn file temp sau render
└── assets/
    └── logo.png
```

> **Tip build:** Mỗi file trong `core/` là 1 module độc lập → dễ prompt AI từng phần, dễ test riêng lẻ.

---

# 7. ROADMAP PHÁT TRIỂN

---

## QUY TẮC XUYÊN SUỐT (Bắt buộc mọi phase)

- **Reliability:** Mọi tác vụ phải có retry, timeout, không treo vô hạn
- **Error log:** Log lỗi rõ ràng, user tự đọc được nguyên nhân
- **Progress bar:** Hiển thị tiến trình + nút hủy cho mọi tác vụ nặng
- **Disk cleanup:** Tự động xóa file temp sau khi render xong
- **License:** Cơ chế activate theo máy, có phương án khôi phục khi đổi máy

---

## ══════════════════════════════════
## PHASE 1 — MVP BÁN ĐƯỢC NGAY
## ══════════════════════════════════

**Mục tiêu:** Có sản phẩm "đáng tiền" để bán, core offline.

**Definition of Done toàn Phase 1:**
- Xuất ra MP4 hoàn chỉnh (có subtitle tiếng Việt)
- Timing subtitle khớp lời ở mức chấp nhận được
- Không crash khi xử lý bộ 10 video test
- Tốc độ: video 5–10 phút xử lý dưới 2 giờ trên máy phổ biến
- Thao tác: tối đa 2 bước từ import → export

---

### V0.1 — Video Downloader

**Chức năng:**
- Tải từ YouTube, TikTok, Douyin, Bilibili
- Dùng yt-dlp

**Chi phí user:** 0đ

**Done khi:**
- Tải được ít nhất YouTube + TikTok ổn định với bộ 10 video test
- Có cơ chế retry + thông báo lỗi rõ ràng
- Không bị kẹt vô hạn khi mất mạng

---

### V0.2 — Import MP4

**Chức năng:**
- Kéo thả file video
- Hỗ trợ các codec phổ biến (H.264, H.265)

**Chi phí user:** 0đ

**Done khi:**
- Import file MP4/MKV/MOV chạy được
- Xử lý lỗi khi file không hợp lệ — user thấy được nguyên nhân

---

### V0.3 — Speech-to-Text

**Chức năng:**
- Nhận diện giọng nói: Trung, Anh, Nhật, Hàn
- Output: file SRT
- Dùng Faster Whisper local

**Chi phí user:** 0đ

**Lưu ý quan trọng:**
- Cần có **Model Manager**: cơ chế cho phép user tự động tải model STT vào ổ cứng dễ dàng
- Cung cấp lựa chọn model size: `tiny` (nhanh) → `base` → `small` (chính xác hơn) để user tự chọn tốc độ vs chất lượng theo cấu hình máy
- Máy không có GPU NVIDIA sẽ chậm hơn đáng kể — cần thông báo rõ ràng

**Done khi:**
- Tự động tải model STT thành công lần đầu
- Tạo được SRT có timing theo audio (không lệch > vài giây)
- Có progress bar + nút hủy

---

### V0.4 — Dịch Subtitle

**Chức năng:**
- Trung → Việt
- Anh → Việt
- Dùng deep-translator (Google Translate free)

**Chi phí user:** 0đ *(cần Internet)*

**Lưu ý:** deep-translator gọi Google Translate miễn phí, không cần API key. Chất lượng Trung→Việt tốt hơn nhiều so với model local. Có giới hạn request nhưng đủ cho user thông thường.

**Done khi:**
- Dịch ra subtitle tiếng Việt đúng với SRT pipeline (giữ timing, số dòng hợp lý)
- Có cache dịch theo đoạn để giảm thời gian khi chạy lại

---

### V0.5 — Voice AI (TTS)

**Chức năng:**
- Giọng nam, giọng nữ tiếng Việt
- Dùng Edge TTS

**Chi phí user:** 0đ *(cần Internet)*

**Lưu ý:** Edge TTS dùng miễn phí nhưng cần kết nối mạng. Phải có tooltip/thông báo rõ ràng khi gọi thất bại do mất mạng.

**Done khi:**
- Có tùy chọn bật/tắt voice khi export
- Ít nhất 3 preset giọng (giọng nam + nữ)
- Ghép voice vào MP4 ổn định

---

### V0.6 — Video Export

**Chức năng:**
- Ghép video + subtitle + voice
- Output: MP4

**Chi phí user:** 0đ

**Done khi:**
- MP4 xuất được với preset cơ bản (giữ âm gốc + subtitle hiển thị rõ)
- Tự động dọn file temp (audio trung gian, frames...) sau render — tránh đầy ổ C
- Có progress bar + log lỗi rõ ràng

---

### 💰 MỐC BÁN ĐẦU TIÊN

> **Giá: 299.000 VNĐ — Lifetime, không phí tháng**

---

## ══════════════════════════════════
## PHASE 2 — TĂNG TỶ LỆ MUA
## ══════════════════════════════════

**Mục tiêu:** Nâng chất lượng output, tăng conversion.

**Definition of Done toàn Phase 2:**
- Subtitle styling đúng layout TikTok/Shorts (line wrap + viền + màu)
- Watermark & preset xuất nhất quán
- Project manager giúp lưu & khôi phục tiến trình

---

### V1.0 — Subtitle Templates

**Kiểu:** TikTok, Podcast, CapCut style  
**Chi phí user:** 0đ

---

### V1.1 — Auto Subtitle Styling

**Tự động:** Căn giữa, viền, màu sắc phù hợp nền tảng  
**Chi phí user:** 0đ

---

### V1.2 — Video Presets

**Xuất tối ưu cho:** TikTok, YouTube Shorts, Instagram Reels  
**Chi phí user:** 0đ

---

### V1.3 — Watermark

**Chức năng:** Thêm logo, tên kênh  
**Chi phí user:** 0đ

---

### V1.4 — Project Manager

**Lưu:** Dự án, video, template, tiến trình xử lý  
**Chi phí user:** 0đ

---

### 💰 MỐC NÂNG GIÁ

> **Giá: 499.000 VNĐ — Lifetime**

---

## ══════════════════════════════════
## PHASE 3 — TĂNG GIÁ TRỊ MẠNH (ADD-ON AI)
## ══════════════════════════════════

**Mục tiêu:** Tính năng AI nâng cao, tùy chọn — yêu cầu user tự cấu hình API Key.

---

### V2.0 — AI Rewrite

**Viết lại nội dung video.**

**Mode A — Gemini API (user tự cấu hình):**
- Chi phí: ~0đ đến vài nghìn đồng/video

**Mode B — OpenAI API (user tự cấu hình):**
- Chi phí: ~100đ – 500đ/video

---

### V2.1 — AI Hook Generator

Sinh hook viral từ nội dung video  
**Chi phí:** API user

### V2.2 — AI Caption Generator

Sinh caption + CTA  
**Chi phí:** API user

### V2.3 — AI Hashtag Generator

**Chi phí:** API user

### V2.4 — AI Title Generator

**Chi phí:** API user

---

### 💰 MỐC NÂNG GIÁ

> **Giá: 699.000 VNĐ — Lifetime**

---

## ══════════════════════════════════
## PHASE 4 — TOOL CHUYÊN NGHIỆP
## ══════════════════════════════════

**Mục tiêu:** Dành cho creator chuyên nghiệp và agency.

---

### V3.0 — Batch Processing

Xử lý 10 / 20 / 50 video cùng lúc  
**Chi phí user:** 0đ *(phụ thuộc API nếu dùng AI)*

### V3.1 — Clip Cutter

Tự cắt clip ngắn từ video dài  
**Chi phí:** 0đ

### V3.2 — Best Moments

Tự động tìm đoạn hay nhất trong video  
**Chi phí:** 0đ

### V3.3 — Auto Zoom

Theo dõi khuôn mặt tự động zoom  
**Chi phí:** 0đ

### V3.4 — Auto Thumbnail

Tự tạo thumbnail  
**Chi phí:** 0đ (hoặc API user)

---

### 💰 MỐC NÂNG GIÁ

> **Giá: 999.000 VNĐ — Lifetime**

---

## ══════════════════════════════════
## PHASE 5 — AGENCY LEVEL
## ══════════════════════════════════

**Mục tiêu:** Phục vụ agency content và team lớn.

---

### V4.0 — Content Factory

1 video → nhiều Shorts tự động

### V4.1 — Channel Builder

Template theo niche (ẩm thực, tài chính, giáo dục...)

### V4.2 — Trend Research

Phân tích chủ đề đang viral *(API user)*

### V4.3 — Content Calendar

Lập lịch nội dung theo nền tảng

---

### 💰 MỐC NÂNG GIÁ

> **Giá: 1.490.000 VNĐ — Lifetime**

---

# 8. CHI PHÍ THỰC TẾ CỦA USER

| Phase | Chi phí AI | Chi phí hàng tháng |
|---|---|---|
| V0 → V1 | 0đ | 0đ |
| V2 (Gemini) | ~0đ – 20.000đ/tháng | Không cố định |
| V2 (OpenAI) | ~20.000đ – 200.000đ/tháng | Không cố định |
| V3 Batch lớn | Phụ thuộc API user | Không cố định |

---

# 9. RỦI RO CẦN XỬ LÝ

| Rủi ro | Mức độ | Giải pháp |
|---|---|---|
| Faster Whisper chậm trên CPU | Cao | Cung cấp 3 model size (tiny/base/small), thông báo thời gian xử lý ước tính |
| Chất lượng dịch thuật kém | Cao | Dùng deep-translator (Google Translate) thay model local |
| Edge TTS mất mạng | Trung | Thông báo lỗi rõ ràng, cho phép export không có voice |
| PyInstaller file size lớn (~300MB) | Thấp | Host file download riêng, document rõ cho user |
| yt-dlp vi phạm ToS nền tảng | Trung | Thêm disclaimer trong app, để user tự chịu trách nhiệm nội dung |
| License bị crack | Trung | HWID binding, cân nhắc obfuscation code sau khi có doanh thu |

---

# 10. CHIẾN LƯỢC BÁN HÀNG

**Thông điệp chính:**
> *"Dịch video Trung Quốc sang tiếng Việt chỉ bằng 1 click."*

**Thông điệp phụ:**
- Không phí tháng
- Không cần server
- Core chạy offline — AI nâng cao tùy chọn, tự cấu hình API
- Mua 1 lần, dùng mãi

**Kênh bán hàng gợi ý:**
- TikTok demo (quay màn hình chạy tool thực tế)
- Facebook group MMO Việt Nam, group TikTok Creator
- Zalo OA thông báo cập nhật version

---

# 11. MỤC TIÊU DÀI HẠN

**Không trở thành:** Tool downloader video đơn thuần

**Trở thành:** Phần mềm dịch và tái sử dụng nội dung video số 1 cho Creator Việt Nam