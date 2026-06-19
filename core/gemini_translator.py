"""Dich subtitle theo ngu canh bang Gemini API."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_BATCH_SIZE = 25


def translate_blocks(
    blocks: list[dict],
    api_key: str | None = None,
    source_language: str = "auto",
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = 3,
    timeout_seconds: int = 60,
    progress_callback=None,
    cancel_flag=None,
    client=None,
    retry_delay: float = 1.0,
) -> dict:
    """Dich cac block ``{id, text}`` va giu nguyen thu tu cung ID.

    ``client`` chi danh cho dependency injection khi test. Khi chay that,
    module tu tao Google Gen AI client tu ``api_key`` hoac GEMINI_API_KEY.
    """
    validation_error = _validate_input(blocks, batch_size)
    if validation_error:
        return _error_result(validation_error)

    if _is_cancelled(cancel_flag):
        return _error_result("Canceled")

    if client is None:
        api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not api_key:
            return _error_result("Chua cau hinh Gemini API key")
        try:
            client = _create_client(api_key, timeout_seconds)
        except ImportError:
            return _error_result(
                "Thieu google-genai. Chay: python -m pip install google-genai"
            )
        except Exception as error:
            return _error_result(f"Khong khoi tao duoc Gemini client: {error}")

    output = [dict(block) for block in blocks]
    translated_indexes = [
        index for index, block in enumerate(output) if str(block["text"]).strip()
    ]
    completed = 0

    for start in range(0, len(translated_indexes), batch_size):
        if _is_cancelled(cancel_flag):
            return _error_result("Canceled", blocks=output, translated=completed)

        indexes = translated_indexes[start:start + batch_size]
        batch = [{"id": output[index]["id"], "text": output[index]["text"]} for index in indexes]

        try:
            translated_batch = _request_translation(
                client=client,
                blocks=batch,
                source_language=source_language,
                model=model,
                max_retries=max_retries,
                cancel_flag=cancel_flag,
                retry_delay=retry_delay,
            )
        except Exception as error:
            logging.error("Gemini translation failed: %s", error)
            return _error_result(
                str(error), blocks=output, translated=completed
            )

        by_id = {str(item["id"]): item["text"] for item in translated_batch}
        for index in indexes:
            output[index]["text"] = _polish_vietnamese(by_id[str(output[index]["id"])])

        completed += len(indexes)
        if progress_callback:
            progress_callback(f"Gemini: {completed} / {len(translated_indexes)} doan...")

    return {
        "success": True,
        "blocks": output,
        "translated": completed,
        "failed": 0,
        "model": model,
        "error": None,
    }


def _create_client(api_key: str, timeout_seconds: int):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=max(1, timeout_seconds) * 1000),
    )


def _request_translation(
    *,
    client,
    blocks: list[dict],
    source_language: str,
    model: str,
    max_retries: int,
    cancel_flag,
    retry_delay: float,
) -> list[dict]:
    prompt = _build_prompt(blocks, source_language)
    attempts = max(1, max_retries)
    last_error: Exception | None = None

    for attempt in range(attempts):
        if _is_cancelled(cancel_flag):
            raise RuntimeError("Canceled")
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                },
            )
            response_text = getattr(response, "text", None)
            if not response_text:
                raise ValueError("Gemini tra ve noi dung rong")
            parsed = _parse_response(response_text)
            return _validate_output(parsed, blocks)
        except Exception as error:
            last_error = error
            logging.warning(
                "Gemini that bai lan %s/%s: %s", attempt + 1, attempts, error
            )
            if attempt + 1 < attempts:
                time.sleep(max(0.0, retry_delay) * min(2 ** attempt, 4))

    raise RuntimeError(f"Gemini that bai sau {attempts} lan: {last_error}")


def _build_prompt(blocks: list[dict], source_language: str) -> str:
    source = "tu dong nhan dien" if source_language == "auto" else source_language
    payload = json.dumps(blocks, ensure_ascii=False)
    return f"""Ban la bien dich phu de video chuyen nghiep.
Ngon ngu nguon: {source}. Ngon ngu dich: tieng Viet.

Yeu cau:
- Doc toan bo cac cau de hieu ngu canh truoc khi dich.
- Dich tu nhien nhu nguoi Viet noi, khong dich may tung tu.
- Giu dung y nghia, ten rieng, tieng long va cach xung ho nhat quan.
- Cau dich ngan gon, phu hop de hien thi lam subtitle.
- Giu nguyen ID, thu tu va so luong phan tu.
- Khong gop, tach, them hoac bo subtitle.
- Chi tra ve JSON array theo mau [{{"id": 1, "text": "Ban dich"}}].
- Khong markdown, khong giai thich.

Du lieu:
{payload}
"""


def _parse_response(response_text: str) -> list[dict]:
    cleaned = response_text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"Gemini tra ve JSON khong hop le: {error}") from error

    if isinstance(data, dict):
        data = data.get("translations")
    if not isinstance(data, list):
        raise ValueError("Gemini phai tra ve mot JSON array")
    return data


def _validate_output(translated: list[dict], source: list[dict]) -> list[dict]:
    expected_ids = [str(block["id"]) for block in source]
    actual_ids = []

    for item in translated:
        if not isinstance(item, dict) or "id" not in item or "text" not in item:
            raise ValueError("Moi ban dich phai co id va text")
        if not isinstance(item["text"], str) or not item["text"].strip():
            raise ValueError(f"Ban dich ID {item['id']} bi trong")
        actual_ids.append(str(item["id"]))

    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("Gemini tra ve ID trung lap")
    if actual_ids != expected_ids:
        raise ValueError("Gemini tra ve thieu, du hoac sai thu tu subtitle ID")
    return translated


def _validate_input(blocks: Any, batch_size: int) -> str | None:
    if not isinstance(blocks, list) or not blocks:
        return "Danh sach subtitle dang trong"
    if batch_size < 1:
        return "batch_size phai lon hon 0"

    ids = []
    for block in blocks:
        if not isinstance(block, dict) or "id" not in block or "text" not in block:
            return "Moi subtitle phai co id va text"
        if not isinstance(block["text"], str):
            return f"Text cua subtitle ID {block['id']} phai la chuoi"
        ids.append(str(block["id"]))
    if len(ids) != len(set(ids)):
        return "Subtitle ID khong duoc trung lap"
    return None


def _polish_vietnamese(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _is_cancelled(cancel_flag) -> bool:
    return bool(cancel_flag and cancel_flag[0])


def _error_result(error: str, blocks=None, translated: int = 0) -> dict:
    return {
        "success": False,
        "blocks": blocks or [],
        "translated": translated,
        "failed": 0 if error == "Canceled" else 1,
        "model": None,
        "error": error,
    }
