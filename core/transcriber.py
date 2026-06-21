"""Faster Whisper wrapper tao SRT atomic."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from core.audio_preprocessor import prepare_speech_audio
from utils.device import load_whisper_model


MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
SUPPORTED_MODELS = {"tiny", "base", "small", "large-v3"}
LANGUAGE_MAP = {
    "Tu dong": None,
    "Tieng Trung": "zh",
    "Tieng Anh": "en",
    "Tieng Nhat": "ja",
    "Tieng Han": "ko",
}


@dataclass(frozen=True)
class RecognizedSegment:
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_probability: float | None = None


def transcribe_video(
    video_path: str,
    language: str = "Tieng Trung",
    model_size: str = "base",
    progress_callback=None,
    cancel_flag=None,
    prefer_gpu: bool = True,
    model_dir: str | None = None,
) -> dict:
    source = Path(video_path).resolve()
    if not source.is_file():
        return _error("File video khong ton tai")
    if model_size not in SUPPORTED_MODELS:
        return _error(f"Model phai la: {', '.join(sorted(SUPPORTED_MODELS))}")
    if language not in LANGUAGE_MAP:
        return _error("Ngon ngu STT khong hop le")
    if _is_cancelled(cancel_flag):
        return _error("Canceled")

    audio_path = source.with_name(f"{source.stem}.stt.wav")
    prepared = prepare_speech_audio(source, audio_path)
    if not prepared.get("success"):
        return _error(f"Tien xu ly audio that bai: {prepared.get('error')}")

    try:
        if progress_callback:
            progress_callback(f"Dang tai model {model_size}...")
        model, device_config = load_whisper_model(
            model_size,
            download_root=str(Path(model_dir).resolve()) if model_dir else str(MODEL_DIR),
            prefer_gpu=prefer_gpu,
        )
    except Exception as error:
        logging.exception("Could not load Whisper model")
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Khong xoa duoc audio STT temp: %s", audio_path)
        return _error(f"Khong tai duoc Faster Whisper: {error}")

    final_path = source.with_suffix(".srt")
    temp_path = source.with_suffix(".srt.tmp")
    try:
        if progress_callback:
            progress_callback("STT luot 1: dang nhan dien...")
        language_code = LANGUAGE_MAP[language]
        segments, info = _transcribe_pass(
            model,
            audio_path,
            language_code=language_code,
            use_vad=True,
            cancel_flag=cancel_flag,
            progress_callback=progress_callback,
            progress_label="STT luot 1",
        )
        duration = max(float(getattr(info, "duration", 0) or 0), 0.001)
        if not segments:
            return _error("Khong nhan dien duoc cau noi nao")

        rescue_ranges = _find_rescue_ranges(segments, duration)
        rescued_count = 0
        if rescue_ranges and model_size in {"small", "large-v3"}:
            if progress_callback:
                progress_callback(f"STT luot 2: kiem tra lai {len(rescue_ranges)} vung...")
            rescue_segments, _ = _transcribe_pass(
                model,
                audio_path,
                language_code=getattr(info, "language", None) or language_code,
                use_vad=False,
                cancel_flag=cancel_flag,
                progress_callback=None,
                progress_label="STT luot 2",
            )
            segments, rescued_count = _merge_rescue_segments(
                segments, rescue_segments, rescue_ranges
            )

        _write_srt(temp_path, segments)
        os.replace(temp_path, final_path)
        if progress_callback:
            progress_callback("STT: 100.0%")
        device_name = "GPU" if device_config.using_gpu else "CPU"
        return {
            "success": True,
            "srt_path": str(final_path),
            "segment_count": len(segments),
            "rescued_segments": rescued_count,
            "device_used": device_name,
            "device_config": device_config,
            "detected_language": getattr(info, "language", None) or language_code,
            "error": None,
        }
    except _TranscriptionCancelled:
        return _error("Canceled")
    except Exception as error:
        logging.exception("Speech-to-text failed")
        return _error(f"STT that bai: {error}")
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logging.warning("Khong xoa duoc SRT temp: %s", temp_path)
        if audio_path.exists():
            try:
                audio_path.unlink()
            except OSError:
                logging.warning("Khong xoa duoc audio STT temp: %s", audio_path)


class _TranscriptionCancelled(RuntimeError):
    pass


def _transcribe_pass(
    model,
    audio_path: Path,
    *,
    language_code: str | None,
    use_vad: bool,
    cancel_flag,
    progress_callback,
    progress_label: str,
):
    options = {
        "beam_size": 5,
        "patience": 1.2,
        "temperature": 0.0,
        "vad_filter": use_vad,
        "word_timestamps": True,
        "condition_on_previous_text": use_vad,
    }
    if use_vad:
        options["vad_parameters"] = {
            "min_silence_duration_ms": 300,
            "speech_pad_ms": 200,
        }
    if language_code:
        options["language"] = language_code

    raw_segments, info = model.transcribe(str(audio_path), **options)
    duration = max(float(getattr(info, "duration", 0) or 0), 0.001)
    segments = []
    for raw in raw_segments:
        if _is_cancelled(cancel_flag):
            raise _TranscriptionCancelled()
        text = str(getattr(raw, "text", "")).strip()
        start = max(0.0, float(getattr(raw, "start", 0) or 0))
        end = max(start, float(getattr(raw, "end", start) or start))
        if text and end > start:
            segments.append(
                RecognizedSegment(
                    start=start,
                    end=end,
                    text=text,
                    avg_logprob=_optional_float(getattr(raw, "avg_logprob", None)),
                    no_speech_probability=_optional_float(
                        getattr(raw, "no_speech_prob", None)
                    ),
                )
            )
        if progress_callback:
            percent = min(99.0, max(0.0, end / duration * 100))
            progress_callback(f"{progress_label}: {percent:.1f}%")
    return segments, info


def _find_rescue_ranges(
    segments: list[RecognizedSegment],
    duration: float,
) -> list[tuple[float, float]]:
    ranges = []
    for segment in segments:
        visible_chars = len("".join(segment.text.split()))
        sparse_long = segment.end - segment.start >= 4.0 and visible_chars <= 8
        low_confidence = (
            segment.avg_logprob is not None and segment.avg_logprob < -0.75
        )
        if sparse_long or low_confidence:
            ranges.append((max(0.0, segment.start - 0.35), min(duration, segment.end + 0.35)))

    previous_end = 0.0
    for segment in segments:
        gap = segment.start - previous_end
        if 0.65 <= gap <= 4.0:
            ranges.append((max(0.0, previous_end - 0.2), min(duration, segment.start + 0.2)))
        previous_end = max(previous_end, segment.end)
    tail_gap = duration - previous_end
    if 0.65 <= tail_gap <= 4.0:
        ranges.append((max(0.0, previous_end - 0.2), duration))
    return _merge_ranges(ranges)


def _merge_rescue_segments(
    primary: list[RecognizedSegment],
    rescue: list[RecognizedSegment],
    ranges: list[tuple[float, float]],
) -> tuple[list[RecognizedSegment], int]:
    accepted_rescue = [
        segment for segment in rescue
        if _segment_is_usable(segment) and any(_midpoint_in(segment, item) for item in ranges)
    ]
    active_ranges = [
        item for item in ranges
        if any(_midpoint_in(segment, item) for segment in accepted_rescue)
    ]
    if not active_ranges:
        return primary, 0

    kept_primary = [
        segment for segment in primary
        if not any(_midpoint_in(segment, item) for item in active_ranges)
    ]
    merged = _normalize_timeline([*kept_primary, *accepted_rescue])
    return merged, len(accepted_rescue)


def _segment_is_usable(segment: RecognizedSegment) -> bool:
    if not segment.text.strip() or segment.end <= segment.start:
        return False
    if segment.avg_logprob is not None and segment.avg_logprob < -0.9:
        return False
    if (
        segment.no_speech_probability is not None
        and segment.no_speech_probability > 0.65
    ):
        return False
    return True


def _normalize_timeline(segments: list[RecognizedSegment]) -> list[RecognizedSegment]:
    result = []
    for segment in sorted(segments, key=lambda item: (item.start, item.end)):
        if result and segment.text.casefold() == result[-1].text.casefold():
            if segment.start <= result[-1].end + 0.25:
                continue
        start = max(segment.start, result[-1].end if result else 0.0)
        if segment.end - start < 0.08:
            continue
        result.append(
            RecognizedSegment(
                start=start,
                end=segment.end,
                text=segment.text,
                avg_logprob=segment.avg_logprob,
                no_speech_probability=segment.no_speech_probability,
            )
        )
    return result


def _merge_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _midpoint_in(segment: RecognizedSegment, interval: tuple[float, float]) -> bool:
    midpoint = (segment.start + segment.end) / 2
    return interval[0] <= midpoint <= interval[1]


def _write_srt(path: Path, segments: list[RecognizedSegment]):
    with path.open("w", encoding="utf-8") as file:
        for index, segment in enumerate(segments, start=1):
            file.write(
                f"{index}\n{_seconds_to_srt_time(segment.start)} --> "
                f"{_seconds_to_srt_time(segment.end)}\n{segment.text.strip()}\n\n"
            )


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _seconds_to_srt_time(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _is_cancelled(cancel_flag):
    return bool(cancel_flag and cancel_flag[0])


def _error(message):
    return {
        "success": False,
        "srt_path": None,
        "segment_count": 0,
        "device_used": None,
        "error": message,
    }
