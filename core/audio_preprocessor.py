"""Prepare speech audio for STT with FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SPEECH_FILTER = "highpass=f=60,lowpass=f=7800,loudnorm=I=-16:TP=-1.5:LRA=11"


def prepare_speech_audio(
    source_path: str | Path,
    output_path: str | Path,
    *,
    timeout_seconds: int = 3600,
) -> dict:
    source = Path(source_path).resolve()
    destination = Path(output_path).resolve()
    if not source.is_file():
        return _error("File audio/video nguon khong ton tai")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return _error("Khong tim thay FFmpeg trong PATH")

    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        SPEECH_FILTER,
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return _error("Tien xu ly audio qua thoi gian cho")
    except OSError as error:
        return _error(f"Khong chay duoc FFmpeg: {error}")

    if result.returncode != 0 or not destination.is_file():
        message = result.stderr.strip() or "FFmpeg khong tao duoc audio"
        return _error(message)
    return {
        "success": True,
        "audio_path": str(destination),
        "sample_rate": 16000,
        "channels": 1,
        "error": None,
    }


def _error(message: str) -> dict:
    return {"success": False, "audio_path": None, "error": message}
