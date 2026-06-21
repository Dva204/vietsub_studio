"""Chuan hoa link, file va thu muc thanh danh sach input cho project queue."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
URL_PATTERN = re.compile(r"https?://[^\s\u4e00-\u9fff]+", re.IGNORECASE)
TRACKING_PARAMS = {
    "si", "sender_device", "share_app_id", "share_link_id", "share_source",
    "is_from_webapp", "refer", "referer_url", "timestamp",
}


@dataclass(frozen=True)
class InputItem:
    source_type: str
    source_value: str
    display_name: str
    canonical_key: str


def collect_inputs(values: list[str] | str, *, recursive: bool = False) -> dict:
    if isinstance(values, str):
        values = [values]
    items, invalid = [], []
    seen = set()

    for raw in values:
        raw = str(raw).strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            _add_file(path, items, invalid, seen)
            continue
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in sorted(path.glob(pattern)):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    _add_file(candidate, items, invalid, seen)
            continue

        urls = URL_PATTERN.findall(raw)
        if urls:
            for url in urls:
                cleaned = _clean_url(url.rstrip(".,;:!?)】』\"'"))
                key = f"url:{cleaned.casefold()}"
                if key not in seen:
                    seen.add(key)
                    items.append(InputItem("url", cleaned, _url_display_name(cleaned), key))
        else:
            invalid.append(raw)

    return {"items": items, "invalid": invalid}


def _add_file(path: Path, items, invalid, seen):
    if path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        invalid.append(str(path))
        return
    resolved = path.resolve()
    key = f"file:{str(resolved).casefold()}"
    if key not in seen:
        seen.add(key)
        items.append(InputItem("file", str(resolved), resolved.name, key))


def _clean_url(url: str) -> str:
    parsed = urlsplit(url)
    kept_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in TRACKING_PARAMS or key.casefold().startswith("utm_"):
            continue
        kept_query.append((key, value))
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(kept_query), "")
    )


def _url_display_name(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc}{parsed.path}" or url
