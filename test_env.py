import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

from utils.device import detect_whisper_config, format_device_summary, get_cuda_device_count

print("=== Kiểm tra môi trường VietDub Studio ===\n")

# Test CustomTkinter
try:
    import customtkinter

    print("✅ CustomTkinter OK")
except Exception:
    print("❌ CustomTkinter FAIL")

# Test Faster Whisper + GPU/CPU auto-detect
try:
    from faster_whisper import WhisperModel

    config = detect_whisper_config()
    cuda_count = get_cuda_device_count()
    if config.using_gpu:
        print(f"✅ Faster Whisper OK | {format_device_summary(config)} | CUDA devices: {cuda_count}")
    else:
        print(f"✅ Faster Whisper OK | {format_device_summary(config)}")
    print(f"   → {config.reason}")
except Exception as exc:
    print(f"❌ Faster Whisper FAIL — {exc}")

# Test yt-dlp
try:
    import yt_dlp

    print("✅ yt-dlp OK")
except Exception:
    print("❌ yt-dlp FAIL")

# Test deep-translator
try:
    from deep_translator import GoogleTranslator

    result = GoogleTranslator(source="en", target="vi").translate("Hello")
    print(f"✅ deep-translator OK | Test dịch: '{result}'")
except Exception:
    print("❌ deep-translator FAIL (kiểm tra kết nối Internet)")

# Test edge-tts
try:
    import edge_tts

    print("✅ edge-tts OK")
except Exception:
    print("❌ edge-tts FAIL")

# Test FFmpeg
ffmpeg = shutil.which("ffmpeg")
if ffmpeg:
    result = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ FFmpeg OK")
    else:
        print("❌ FFmpeg FAIL — kiểm tra lại PATH")
else:
    print("❌ FFmpeg FAIL — cài FFmpeg và thêm vào PATH (winget install Gyan.FFmpeg)")

print("\n=== Hoàn tất ===")
