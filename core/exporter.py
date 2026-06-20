"""Xuat MP4 co subtitle burn-in bang FFmpeg."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubtitleStyle:
    font_name: str = "Arial"
    font_size: int = 20
    primary_colour: str = "&H00FFFFFF"
    outline_colour: str = "&H00000000"
    outline: int = 3
    shadow: int = 1
    alignment: int = 2
    margin_vertical: int = 42


DEFAULT_STYLE = SubtitleStyle()
SUBTITLE_PRESETS = {
    "shorts": DEFAULT_STYLE,
    "classic": SubtitleStyle(font_size=16, outline=2, shadow=1, margin_vertical=32),
    "compact": SubtitleStyle(font_size=13, outline=2, shadow=0, margin_vertical=24),
}


def export_subtitled_video(
    video_path: str,
    subtitle_path: str,
    output_path: str | None = None,
    *,
    style: SubtitleStyle | None = None,
    subtitle_preset: str = "shorts",
    crf: int = 20,
    preset: str = "medium",
    progress_callback=None,
    cancel_flag=None,
    timeout_seconds: int = 7200,
    overwrite: bool = True,
) -> dict:
    """Burn subtitle vao video va giu audio goc trong file MP4."""
    video = Path(video_path).resolve()
    subtitle = Path(subtitle_path).resolve()
    validation_error = _validate_inputs(video, subtitle, crf, timeout_seconds)
    if validation_error:
        return _error_result(validation_error)

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return _error_result("Khong tim thay FFmpeg/ffprobe trong PATH")
    try:
        style = style or get_subtitle_style(subtitle_preset)
    except ValueError as error:
        return _error_result(str(error))

    destination = (
        Path(output_path).resolve()
        if output_path
        else video.with_name(f"{video.stem}_subtitled.mp4")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        return _error_result(f"File output da ton tai: {destination}")

    try:
        duration = _probe_duration(ffprobe, video)
    except Exception as error:
        return _error_result(f"Khong doc duoc thoi luong video: {error}")

    temp_dir = Path(tempfile.mkdtemp(prefix="vietdub_export_", dir=destination.parent))
    temp_subtitle = temp_dir / "subtitle.srt"
    temp_output = temp_dir / "render.mp4"
    shutil.copy2(subtitle, temp_subtitle)

    command = _build_ffmpeg_command(
        ffmpeg=ffmpeg,
        video=video,
        output=temp_output,
        style=style,
        crf=crf,
        preset=preset,
    )
    process = None
    started_at = time.monotonic()
    last_progress = -1.0
    log_tail: list[str] = []

    try:
        process = subprocess.Popen(
            command,
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if process.stdout is None:
            raise RuntimeError("Khong doc duoc output FFmpeg")

        for raw_line in process.stdout:
            line = raw_line.strip()
            if line:
                log_tail.append(line)
                log_tail = log_tail[-30:]

            if _is_cancelled(cancel_flag):
                _stop_process(process)
                return _error_result("Canceled")
            if time.monotonic() - started_at > timeout_seconds:
                _stop_process(process)
                return _error_result(f"FFmpeg vuot timeout {timeout_seconds} giay")

            progress = _parse_progress(line, duration)
            if (
                progress is not None
                and progress_callback
                and (progress - last_progress >= 0.5 or progress >= 100)
            ):
                progress_callback(f"Render: {progress:.1f}%")
                last_progress = progress

        return_code = process.wait()
        if return_code != 0 or not temp_output.is_file():
            details = "\n".join(log_tail[-8:])
            return _error_result(f"FFmpeg render that bai\n{details}".strip())

        os.replace(temp_output, destination)
        if progress_callback:
            progress_callback("Render: 100.0%")
        return {
            "success": True,
            "output_path": str(destination),
            "duration": duration,
            "error": None,
        }
    except Exception as error:
        if process and process.poll() is None:
            _stop_process(process)
        logging.exception("Video export failed")
        return _error_result(f"Khong xuat duoc video: {error}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _build_ffmpeg_command(
    *, ffmpeg: str, video: Path, output: Path, style: SubtitleStyle, crf: int, preset: str
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        str(video),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        _build_subtitle_filter(style),
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]


def _build_subtitle_filter(style: SubtitleStyle) -> str:
    font_name = style.font_name.replace("'", "").replace(",", "").strip() or "Arial"
    force_style = ",".join(
        [
            f"FontName={font_name}",
            f"FontSize={max(8, style.font_size)}",
            f"PrimaryColour={style.primary_colour}",
            f"OutlineColour={style.outline_colour}",
            "BorderStyle=1",
            f"Outline={max(0, style.outline)}",
            f"Shadow={max(0, style.shadow)}",
            f"Alignment={style.alignment}",
            f"MarginV={max(0, style.margin_vertical)}",
        ]
    )
    return f"subtitles=filename=subtitle.srt:charenc=UTF-8:force_style='{force_style}'"


def get_subtitle_style(preset_name: str) -> SubtitleStyle:
    try:
        return SUBTITLE_PRESETS[preset_name.lower()]
    except KeyError as error:
        choices = ", ".join(sorted(SUBTITLE_PRESETS))
        raise ValueError(f"Preset subtitle khong hop le. Chon: {choices}") from error


def _probe_duration(ffprobe: str, video: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe that bai")
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise RuntimeError("Thoi luong video khong hop le")
    return duration


def _parse_progress(line: str, duration: float) -> float | None:
    if duration <= 0 or "=" not in line:
        return None
    key, value = line.split("=", 1)
    try:
        if key in {"out_time_us", "out_time_ms"}:
            seconds = int(value) / 1_000_000
        elif key == "out_time":
            hours, minutes, seconds_text = value.split(":")
            seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds_text)
        else:
            return None
        return min(100.0, max(0.0, seconds / duration * 100))
    except (TypeError, ValueError):
        return None


def _validate_inputs(video: Path, subtitle: Path, crf: int, timeout_seconds: int):
    if not video.is_file():
        return "File video khong ton tai"
    if not subtitle.is_file():
        return "File subtitle khong ton tai"
    if subtitle.suffix.lower() != ".srt":
        return "Subtitle phai co dinh dang .srt"
    if not 0 <= crf <= 51:
        return "CRF phai nam trong khoang 0-51"
    if timeout_seconds < 1:
        return "timeout_seconds phai lon hon 0"
    return None


def _stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _is_cancelled(cancel_flag) -> bool:
    return bool(cancel_flag and cancel_flag[0])


def _error_result(error: str) -> dict:
    return {"success": False, "output_path": None, "duration": 0, "error": error}
