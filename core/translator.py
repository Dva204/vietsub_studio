import json
import logging
import os
import re
import time
from pathlib import Path

from core.subtitle import blocks_to_srt, parse_srt_blocks

CACHE_FILE = Path(__file__).resolve().parent.parent / "cache" / "translate_cache.json"
MARKER_TEMPLATE = "[[VDS_{index:04d}]]"


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logging.warning("Khong doc duoc translation cache", exc_info=True)
        return {}


def _save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CACHE_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)
    os.replace(temp_file, CACHE_FILE)


def translate_srt(
    srt_path: str,
    src_lang: str = "zh-CN",
    progress_callback=None,
    cancel_flag=None,
    context_window: int = 5,
    max_retries: int = 3,
    translator=None,
) -> dict:
    """Dich SRT sang tieng Viet va giu nguyen timing tung block."""
    if not os.path.isfile(srt_path):
        return {"success": False, "error": "File SRT khong ton tai"}
    if context_window < 1:
        return {"success": False, "error": "context_window phai lon hon 0"}

    try:
        with open(srt_path, "r", encoding="utf-8-sig") as file:
            blocks = _parse_srt(file.read())
    except (OSError, UnicodeError) as error:
        return {"success": False, "error": f"Khong doc duoc file SRT: {error}"}

    if not blocks:
        return {"success": False, "error": "File SRT khong co subtitle hop le"}

    if translator is None:
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            return {
                "success": False,
                "error": "Thieu deep-translator. Hay cai dependencies cua du an.",
            }
        translator = GoogleTranslator(source=src_lang, target="vi")
    cache = _load_cache()
    translated_count = 0
    failed_count = 0

    for start in range(0, len(blocks), context_window):
        if _is_cancelled(cancel_flag):
            return {"success": False, "error": "Canceled"}

        chunk = blocks[start:start + context_window]
        source_texts = [block["text"].strip() for block in chunk]
        translated_texts, request_count, failures = _translate_chunk(
            source_texts,
            src_lang=src_lang,
            translator=translator,
            cache=cache,
            max_retries=max_retries,
            cancel_flag=cancel_flag,
        )
        translated_count += request_count
        failed_count += failures

        for block, translated_text in zip(chunk, translated_texts):
            if translated_text:
                block["text"] = _polish_vietnamese(translated_text)

        if progress_callback:
            done = min(start + len(chunk), len(blocks))
            progress_callback(f"Dich: {done} / {len(blocks)} doan...")

    try:
        _save_cache(cache)
        output_path = str(Path(srt_path).with_suffix(".vi.srt"))
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(_blocks_to_srt(blocks))
    except OSError as error:
        return {"success": False, "error": f"Khong luu duoc ban dich: {error}"}

    return {
        "success": True,
        "output_path": output_path,
        "total": len(blocks),
        "translated": translated_count,
        "failed": failed_count,
        "error": None,
    }


def _translate_chunk(
    texts: list[str],
    *,
    src_lang: str,
    translator,
    cache: dict,
    max_retries: int,
    cancel_flag,
) -> tuple[list[str], int, int]:
    """Translate each cue independently so Google cannot blend nearby dialogue.

    Batch markers preserve timing, but machine translation may still rewrite the
    contents of several short cues as one conversation.  That produced valid SRT
    with repeated, incorrect sentences.  Context-aware batching belongs to the
    Gemini translator, which has an explicit structured-output contract.
    """
    non_empty = [(index, text) for index, text in enumerate(texts) if text]
    if not non_empty:
        return texts, 0, 0

    result = list(texts)
    request_count = 0
    failures = 0
    for index, text in non_empty:
        if _is_cancelled(cancel_flag):
            break
        item_key = f"v3::{src_lang}::item::{text}"
        translated = cache.get(item_key)
        if not translated:
            translated = _translate_with_retry(
                translator, text, max_retries, cancel_flag
            )
            request_count += 1
            if translated:
                cache[item_key] = translated
        if translated:
            result[index] = translated
        else:
            failures += 1
    return result, request_count, failures


def _translate_with_retry(translator, text, max_retries, cancel_flag):
    for attempt in range(max(1, max_retries)):
        if _is_cancelled(cancel_flag):
            return None
        try:
            return translator.translate(text) or None
        except Exception as error:
            logging.warning(
                "Dich that bai lan %s/%s: %s", attempt + 1, max_retries, error
            )
            if attempt + 1 < max_retries:
                time.sleep(min(2 ** attempt, 4))
    return None


def _split_marked_translation(text: str, expected_count: int):
    marker_pattern = re.compile(r"\[\[\s*VDS_(\d{4})\s*\]\]", re.IGNORECASE)
    matches = list(marker_pattern.finditer(text))
    if not matches:
        return None

    result = [""] * expected_count
    seen = set()
    for position, match in enumerate(matches):
        index = int(match.group(1))
        if index >= expected_count or index in seen:
            return None
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        result[index] = text[match.end():end].strip()
        seen.add(index)

    if seen != set(range(expected_count)) or any(not item for item in result):
        return None
    return result


def _polish_vietnamese(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]
    return text


def _is_cancelled(cancel_flag) -> bool:
    return bool(cancel_flag and cancel_flag[0])


def _parse_srt(content: str) -> list[dict]:
    return parse_srt_blocks(content)


def _blocks_to_srt(blocks: list[dict]) -> str:
    return blocks_to_srt(blocks)
