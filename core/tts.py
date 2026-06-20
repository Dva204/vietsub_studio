"""Tao audio long tieng theo timing cua file SRT bang Edge TTS."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path


VOICES = {
    "Nu mien Nam": "vi-VN-HoaiMyNeural",
    "Nam mien Bac": "vi-VN-NamMinhNeural",
}


async def _tts_segment(
    text: str,
    voice: str,
    output_path: str,
    *,
    rate: str,
    volume: str,
    connect_timeout: int,
    receive_timeout: int,
):
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        volume=volume,
        connect_timeout=connect_timeout,
        receive_timeout=receive_timeout,
    )
    await communicate.save(output_path)


def generate_dubbed_audio(
    srt_path: str,
    voice_name: str = "Nu mien Nam",
    output_dir: str | None = None,
    progress_callback=None,
    cancel_flag=None,
    rate: str = "+0%",
    volume: str = "+0%",
    max_retries: int = 3,
    connect_timeout: int = 10,
    receive_timeout: int = 60,
) -> dict:
    """Tao mot file MP3 co cac cau thoai dat dung vi tri tren timeline."""
    source_path = Path(srt_path).resolve()
    if not source_path.is_file():
        return _error_result("File SRT khong ton tai")
    if voice_name not in VOICES:
        return _error_result(f"Giong doc khong hop le: {voice_name}")

    try:
        from pydub import AudioSegment
        from core.subtitle import parse_srt_blocks
    except ImportError as error:
        return _error_result(
            f"Thieu dependency TTS ({error}). Chay: python -m pip install -r requirements.txt"
        )

    try:
        content = source_path.read_text(encoding="utf-8-sig")
        blocks = parse_srt_blocks(content)
    except (OSError, UnicodeError) as error:
        return _error_result(f"Khong doc duoc file SRT: {error}")
    if not blocks:
        return _error_result("File SRT khong co subtitle hop le")

    destination_dir = Path(output_dir).resolve() if output_dir else source_path.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_stem = source_path.name[:-7] if source_path.name.lower().endswith(".vi.srt") else source_path.stem
    output_path = destination_dir / f"{output_stem}_dubbed.mp3"
    temp_dir = Path(tempfile.mkdtemp(prefix="vietdub_tts_", dir=destination_dir))
    segment_files = []
    failures = []

    try:
        for index, block in enumerate(blocks):
            if _is_cancelled(cancel_flag):
                return _error_result("Canceled")

            text = block["text"].strip()
            if not text:
                continue

            segment_path = temp_dir / f"segment_{index:04d}.mp3"
            error = _generate_segment_with_retry(
                text=text,
                voice=VOICES[voice_name],
                output_path=str(segment_path),
                rate=rate,
                volume=volume,
                max_retries=max_retries,
                connect_timeout=connect_timeout,
                receive_timeout=receive_timeout,
                cancel_flag=cancel_flag,
            )
            if error:
                failures.append({"index": block["index"], "error": error})
            else:
                segment_files.append((block["time"], segment_path))

            if progress_callback:
                progress_callback(f"Tao giong: {index + 1} / {len(blocks)}...")

        if _is_cancelled(cancel_flag):
            return _error_result("Canceled")
        if not segment_files:
            return _error_result("Khong tao duoc doan audio nao", failed=len(failures))

        if progress_callback:
            progress_callback("Dang ghep audio theo timing...")

        final_audio = _merge_audio_by_timing(segment_files, blocks, AudioSegment)
        final_audio.export(str(output_path), format="mp3", bitrate="192k")

        if failures:
            return {
                "success": False,
                "audio_path": str(output_path),
                "voice": voice_name,
                "segments": len(segment_files),
                "failed": len(failures),
                "failures": failures,
                "error": f"Co {len(failures)} subtitle khong tao duoc audio",
            }
        return {
            "success": True,
            "audio_path": str(output_path),
            "voice": voice_name,
            "segments": len(segment_files),
            "failed": 0,
            "failures": [],
            "error": None,
        }
    except Exception as error:
        logging.exception("TTS processing failed")
        return _error_result(f"Khong tao duoc audio: {error}", failed=len(failures))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _generate_segment_with_retry(
    *,
    text: str,
    voice: str,
    output_path: str,
    rate: str,
    volume: str,
    max_retries: int,
    connect_timeout: int,
    receive_timeout: int,
    cancel_flag,
) -> str | None:
    attempts = max(1, max_retries)
    last_error = None
    for attempt in range(attempts):
        if _is_cancelled(cancel_flag):
            return "Canceled"
        try:
            asyncio.run(
                _tts_segment(
                    text,
                    voice,
                    output_path,
                    rate=rate,
                    volume=volume,
                    connect_timeout=max(1, connect_timeout),
                    receive_timeout=max(1, receive_timeout),
                )
            )
            if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                return None
            raise RuntimeError("Edge TTS tao file audio rong")
        except Exception as error:
            last_error = error
            logging.warning(
                "TTS that bai lan %s/%s: %s", attempt + 1, attempts, error
            )
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 4))
    return str(last_error)


def _srt_time_to_ms(value: str) -> int:
    normalized = value.strip().replace(".", ",")
    hours, minutes, remainder = normalized.split(":")
    seconds, milliseconds = remainder.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(milliseconds.ljust(3, "0")[:3])
    )


def _merge_audio_by_timing(segment_files, blocks, audio_segment_cls):
    total_ms = max(
        _srt_time_to_ms(block["time"].split("-->", 1)[1]) for block in blocks
    ) + 500
    result = audio_segment_cls.silent(duration=total_ms)

    for time_range, segment_path in segment_files:
        start_time, end_time = time_range.split("-->", 1)
        start_ms = _srt_time_to_ms(start_time)
        end_ms = _srt_time_to_ms(end_time)
        segment = audio_segment_cls.from_mp3(str(segment_path))
        if len(segment) > end_ms - start_ms:
            logging.warning(
                "Audio dai hon subtitle %.2fs; co the chong len cau sau",
                (len(segment) - (end_ms - start_ms)) / 1000,
            )
        result = result.overlay(segment, position=start_ms)
    return result


def _is_cancelled(cancel_flag) -> bool:
    return bool(cancel_flag and cancel_flag[0])


def _error_result(error: str, failed: int = 0) -> dict:
    return {
        "success": False,
        "audio_path": None,
        "segments": 0,
        "failed": failed,
        "failures": [],
        "error": error,
    }
