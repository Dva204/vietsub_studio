import sys
from pathlib import Path

# Ensure we can import project modules when running from anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.transcriber import transcribe_video


def show(msg: str):
    print(f"  >> {msg}")


# Use absolute path so tests don't break due to working directory
VIDEO = PROJECT_ROOT / "downloads" / "vd.mp4"

result = transcribe_video(
    video_path=str(VIDEO),
    language="Tieng Anh",  # Test voi tieng Anh truoc cho de kiem tra
    model_size="base",
    progress_callback=show,
)

if result.get("success"):
    print(f'OK  SRT: {result["srt_path"]}')
    print(f'    So doan: {result["segment_count"]}')
    print(f'    Chay tren: {result["device_used"]}')

    # Hien thi 3 dong dau cua SRT de kiem tra
    with open(result["srt_path"], encoding="utf-8") as f:
        print("\n--- 10 dong dau SRT ---")
        print("".join(f.readlines()[:10]))
else:
    print(f'LOI: {result.get("error")}')

