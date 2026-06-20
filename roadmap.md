# VIETDUB STUDIO

## Batch Video Localization for Vietnamese Shops

**Version:** Product Roadmap 3.0

**Nền tảng:** Desktop Windows, Python Core, Local-First

**Khách hàng chính:** Shop và agency Việt hóa video sản phẩm Trung Quốc
**Cập nhật:** 2026

---

# 1. ĐỊNH VỊ SẢN PHẨM

VietDub Studio không cạnh tranh với CapCut, Premiere hoặc các trình chỉnh sửa video lớn.

VietDub là công cụ **chuẩn bị và Việt hóa nội dung hàng loạt** trước khi người dùng đưa tài nguyên sang editor họ đã quen dùng.

> **Thông điệp chính:** Biến một thư mục hoặc danh sách link video sản phẩm Trung Quốc thành bộ nội dung tiếng Việt có thể sử dụng ngay.

Giá trị cốt lõi:

- Xử lý 10–50 video theo hàng đợi thay vì làm thủ công từng video.
- Dịch nhất quán theo thuật ngữ và cách xưng hô riêng của từng shop.
- Chỉ yêu cầu người dùng kiểm tra những câu có nguy cơ sai.
- Xuất tài nguyên chuẩn, không khóa người dùng vào VietDub.
- Video và model STT được xử lý trên máy người dùng.

---

# 2. KHÁCH HÀNG MỤC TIÊU

## Khách hàng ưu tiên

| Nhóm | Công việc cần giải quyết |
|---|---|
| Shop nhập hàng Trung Quốc | Việt hóa video sản phẩm từ nhà cung cấp |
| Agency marketing | Xử lý nhiều video cho nhiều shop mỗi ngày |
| Nhân viên content | Tạo subtitle, transcript và caption nhanh |
| Creator chuyên review sản phẩm | Dịch và tái biên tập video được cấp quyền sử dụng |

## Không ưu tiên trong MVP

- Người dùng cần một video editor hoàn chỉnh.
- Studio cần lip-sync hoặc voice cloning chuyên nghiệp.
- Người chỉ cần tải một video đơn lẻ.
- Nhu cầu tạo hiệu ứng, transition hoặc chỉnh màu chuyên sâu.

---

# 3. WORKFLOW SẢN PHẨM

```text
[Dán nhiều link / Import file / Import thư mục]
                    ↓
             [Project Queue]
                    ↓
       [Faster Whisper nhận dạng local]
                    ↓
  [Google Translate hoặc Gemini API của user]
                    ↓
      [Glossary + Translation Memory]
                    ↓
             [Exception Review]
                    ↓
             [Package Export]
```

Package đầu ra tiêu chuẩn:

```text
ten-video/
├── source.mp4
├── subtitle.vi.srt
├── subtitled.mp4
├── transcript.txt
├── caption.txt
└── project.json
```

Người dùng có thể tiếp tục chỉnh sửa bằng CapCut, Premiere hoặc công cụ khác.

---

# 4. NGUYÊN TẮC XUYÊN SUỐT

- **Local-first:** Video, model STT, cache và project nằm trên máy người dùng.
- **Internet minh bạch:** Downloader, Google Translate, Gemini và Edge TTS cần Internet.
- **BYOK:** Gemini là tùy chọn; người dùng tự cung cấp API key.
- **Không lưu API key plaintext:** Dùng Windows Credential Manager hoặc DPAPI.
- **Reliability:** Tác vụ nặng có retry, timeout, progress, cancel và resume.
- **Không mất dữ liệu:** Ghi file tạm rồi replace; project được lưu sau mỗi bước.
- **Human-in-the-loop:** AI hỗ trợ, người dùng duyệt các trường hợp có nguy cơ sai.
- **Editor-compatible:** Ưu tiên SRT, MP4, TXT, JSON và cấu trúc file chuẩn.
- **Quyền nội dung:** App hiển thị cảnh báo chỉ sử dụng video người dùng có quyền khai thác.

---

# 5. CÔNG NGHỆ

| Thành phần | Công nghệ |
|---|---|
| Desktop UI | Python + CustomTkinter |
| Video processing | FFmpeg / ffprobe |
| Link input | yt-dlp |
| Speech-to-Text | Faster Whisper local |
| Dịch nhanh | deep-translator / Google Translate |
| Dịch thông minh | Gemini API, user tự nhập key |
| Subtitle workspace | SRT parser + validation riêng |
| Database | SQLite |
| Packaging | PyInstaller |
| Secret storage | Windows Credential Manager / DPAPI |
| License | Perpetual version license, machine activation |

---

# 6. TRẠNG THÁI CORE HIỆN TẠI

| Module | Trạng thái | Ghi chú |
|---|---|---|
| Downloader | Đang phát triển | Có YouTube, TikTok, Douyin, Bilibili |
| Import/video info | Prototype | Có ffprobe validation |
| Faster Whisper | Prototype | Có CPU/GPU fallback, cần Model Manager |
| Google Translator | Prototype | Có cache, retry và giữ timing |
| Gemini Translator | Core hoàn thành | Có batch, retry và kiểm tra ID |
| Subtitle Workspace | Core hoàn thành | Parse, edit, wrap và quality warning |
| Subtitle Export | Core hoàn thành | Có preset Shorts, Classic, Compact |
| TTS | Beta | Không nằm trong luồng bán hàng chính |
| Project Queue | Chưa làm | Ưu tiên cao nhất tiếp theo |
| Glossary/Memory | Chưa làm | Lợi thế cạnh tranh chính |
| Exception Review UI | Chưa làm | Lợi thế cạnh tranh chính |
| Package Export | Chưa hoàn thiện | Đã có MP4/SRT, thiếu manifest/text |

---

# 7. ROADMAP PHÁT TRIỂN

## PHASE 1 — COMMERCIAL MVP

**Mục tiêu:** Một shop có thể đưa 10 video vào app, xử lý theo hàng đợi, chỉ sửa các câu đáng ngờ và nhận đủ package đầu ra.

### V0.1 — Input Inbox

- Dán một hoặc nhiều link.
- Import MP4/MKV/MOV.
- Import cả thư mục.
- Phát hiện link/file trùng.
- Cảnh báo quyền sử dụng nội dung.

**Done khi:** 20 input hỗn hợp được đưa vào cùng một project mà UI không treo.

### V0.2 — Persistent Project Queue

- SQLite lưu project, job và trạng thái từng bước.
- Trạng thái: pending, running, review, completed, failed, canceled.
- Retry từng job.
- Resume sau khi đóng app hoặc mất điện.
- Giới hạn concurrency để không làm đầy RAM/GPU.

**Done khi:** Đóng app giữa batch 10 video, mở lại và tiếp tục đúng bước chưa hoàn thành.

### V0.3 — STT Model Manager

- Model tiny, base và small.
- Hiển thị dung lượng, trạng thái tải và thư mục lưu.
- CPU/GPU auto-detect.
- Ước lượng tốc độ theo cấu hình máy.
- Progress và cancel khi tải model/STT.

**Done khi:** Máy mới có thể tải model và tạo SRT mà không thao tác terminal.

### V0.4 — Translation Engines

- Fast Mode: Google Translate, không cần API key.
- Smart Mode: Gemini, người dùng tự nhập API key.
- Kiểm tra API key và thông báo quota/lỗi mạng.
- Gemini lỗi thì cho phép fallback Google.
- Không gửi video; chỉ gửi nội dung subtitle.

**Done khi:** Không mất ID/timing và không âm thầm báo thành công khi có câu dịch thất bại.

### V0.5 — Shop Glossary

- Glossary theo shop/project.
- Tên thương hiệu, tên sản phẩm, đơn vị, CTA và cách xưng hô.
- Import/export CSV hoặc JSON.
- Preview các thay đổi trước khi áp dụng.

Ví dụ:

```text
直播间 → phòng livestream
到手价 → giá sau ưu đãi
宝贝 → sản phẩm
姐妹们 → các chị em
```

**Done khi:** Thuật ngữ đã cấu hình xuất hiện nhất quán trong toàn bộ batch.

### V0.6 — Translation Memory

- Lưu câu nguồn, câu máy dịch và bản người dùng sửa.
- Tái sử dụng bản dịch đã duyệt cho video sau.
- Match chính xác trước; fuzzy match để Phase 2.
- Cho phép xóa và export dữ liệu.

**Done khi:** Câu đã sửa được tự động tái sử dụng và có nhãn cho người dùng biết nguồn.

### V0.7 — Exception Review

Chỉ đưa vào danh sách cần kiểm tra các subtitle:

- STT confidence thấp.
- Còn ký tự Trung sau khi dịch.
- Câu quá dài hoặc quá nhiều dòng.
- Tốc độ đọc quá nhanh.
- Timing bị chồng.
- Gemini trả thiếu/sai ID.
- Dịch thất bại hoặc fallback về câu nguồn.

**Done khi:** Người dùng có thể duyệt lỗi bằng bàn phím, sửa và chuyển nhanh sang câu tiếp theo.

### V0.8 — Package Export

- SRT tiếng Việt.
- MP4 burn subtitle tùy chọn.
- Transcript TXT.
- Caption/CTA tùy chọn bằng Gemini BYOK.
- Manifest JSON chứa trạng thái và metadata.
- Preset Shorts, Classic, Compact.

**Done khi:** Package mở được bằng công cụ phổ biến và có cấu trúc tên file nhất quán.

### Definition of Done Phase 1

- Batch 10 video chạy hết mà không crash.
- Có thể resume project sau khi đóng app.
- Không có job treo vô hạn.
- Mọi lỗi có nguyên nhân và nút retry.
- Người dùng không cần terminal.
- Ít nhất 5 shop pilot dùng dữ liệu thật.
- Ít nhất 3 shop đồng ý trả tiền hoặc đặt cọc.

---

## PHASE 2 — SELLABLE PRODUCT

**Chỉ bắt đầu khi Phase 1 đạt cổng pilot trả tiền.**

### V1.0 — One-Screen Workflow

- Inbox, Queue, Review và Export trong một luồng rõ ràng.
- Không xây timeline video editor.
- Hiển thị disk usage và thời gian ước tính.

### V1.1 — Shop Profiles

- Mỗi shop có glossary, cách xưng hô, preset và thư mục export riêng.
- Clone cấu hình shop.

### V1.2 — Batch Operations

- Retry, cancel, export và áp preset cho nhiều job.
- Filter theo trạng thái/lỗi.
- Xử lý 10/20/50 video theo giới hạn máy.

### V1.3 — Packaging & Update

- PyInstaller Windows.
- Kiểm tra FFmpeg/model khi khởi động.
- Migration SQLite an toàn.
- Crash log dễ gửi hỗ trợ.
- Cơ chế cập nhật phiên bản có kiểm soát.

### V1.4 — License

- Mua một lần, dùng vĩnh viễn phiên bản đã mua.
- Bao gồm 12 tháng cập nhật.
- Hết thời hạn vẫn dùng được; chỉ trả phí khi muốn nâng cấp.
- Có cơ chế chuyển máy và khôi phục license.

---

## PHASE 3 — AGENCY PRO

**Chỉ phát triển theo nhu cầu đã trả tiền.**

- Fuzzy Translation Memory.
- Báo cáo thời gian và tỷ lệ lỗi theo batch.
- Nhiều output variant cho cùng một video.
- Queue ưu tiên và lịch chạy ngoài giờ.
- Template caption theo shop/ngành hàng.
- Export/import project để bàn giao.
- Preset riêng cho từng khách hàng agency.

---

# 8. TTS VÀ DUBBING

TTS không phải tính năng bán hàng chính của MVP.

## Narration Beta

- Gom nhiều subtitle thành đoạn thuyết minh liên tục.
- Duck âm thanh gốc khi narration phát.
- Không cam kết lip-sync.

## Dubbing Sync — Deferred

Chỉ nghiên cứu sau khi có khách hàng yêu cầu và trả tiền:

```text
Gom câu theo hội thoại
→ Tạo audio
→ Đo duration
→ Viết ngắn nếu quá dài
→ FFmpeg atempo nếu lệch nhẹ
→ Collision resolver
→ Mix với âm thanh gốc
```

Không overlay audio từng subtitle một cách mù quáng.

---

# 9. NHỮNG THỨ KHÔNG XÂY

- Video timeline editor hoàn chỉnh.
- Kho transition/effect cạnh tranh CapCut.
- Chỉnh màu chuyên nghiệp.
- Lip-sync và voice cloning trong MVP.
- Social scheduler.
- Trend research trước khi có khách trả tiền.
- Auto zoom, thumbnail hoặc clip cutter nếu chưa có nhu cầu pilot rõ ràng.

---

# 10. MÔ HÌNH THƯƠNG MẠI

Giá dưới đây là giả thuyết cần kiểm chứng, không phải cam kết:

| Gói | Đối tượng | Giá thử nghiệm |
|---|---|---|
| Founder | Nhóm pilot đầu tiên | 299.000 VNĐ |
| Standard | Shop xử lý batch nhỏ | 499.000 VNĐ |
| Pro | Shop lớn/agency | 799.000–999.000 VNĐ |

Nguyên tắc:

- Không thu phí theo số video ở bản desktop.
- Gemini dùng API key của khách.
- License vĩnh viễn cho version đã mua, không hứa cập nhật miễn phí trọn đời.
- Chỉ chốt bảng giá sau khi có ít nhất 5 cuộc thử nghiệm với dữ liệu thật.

---

# 11. CỔNG KIỂM CHỨNG SẢN PHẨM

Trước khi mở rộng tính năng, cần đo:

- Thời gian xử lý và review trung bình mỗi video.
- Tỷ lệ subtitle không cần người dùng sửa.
- Số lỗi được Exception Review phát hiện đúng.
- Số video trung bình mỗi shop xử lý mỗi tuần.
- Có ít nhất 3 khách hàng trả tiền hoặc đặt cọc.

Nếu khách hàng không trả tiền cho Batch + Glossary + Review, dừng mở rộng sản phẩm và phỏng vấn lại nhu cầu. Không dùng thêm tính năng để che giấu việc chưa có product-market fit.

---

# 12. MỤC TIÊU DÀI HẠN

**Không trở thành:** downloader hoặc video editor tổng quát.

**Trở thành:** công cụ desktop Việt hóa video sản phẩm Trung Quốc nhanh và nhất quán nhất cho shop và agency Việt Nam.
