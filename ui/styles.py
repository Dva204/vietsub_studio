BG = "#0b1120"
PANEL = "#111827"
PANEL_ALT = "#172033"
BORDER = "#263247"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
PRIMARY = "#3b82f6"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#ef4444"

STATUS_LABELS = {
    "pending": ("Chờ xử lý", MUTED),
    "running": ("Đang xử lý", PRIMARY),
    "review": ("Cần kiểm tra", WARNING),
    "completed": ("Hoàn thành", SUCCESS),
    "failed": ("Có lỗi", DANGER),
    "canceled": ("Đã hủy", MUTED),
}

STEP_LABELS = {
    "acquire": "Lấy video",
    "transcribe": "Nhận dạng lời nói",
    "translate": "Dịch subtitle",
    "review": "Kiểm tra",
    "export": "Xuất package",
}
