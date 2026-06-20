"""Model va cac thao tac chinh sua subtitle SRT dung chung."""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubtitleEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True)
class SubtitleIssue:
    entry_index: int
    code: str
    message: str
    severity: str = "warning"


class SubtitleDocument:
    def __init__(self, entries: list[SubtitleEntry]):
        self.entries = entries

    @classmethod
    def from_srt(cls, content: str) -> "SubtitleDocument":
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return cls([])

        entries = []
        pattern = re.compile(
            r"(?m)^(\d+)\s*\n([^\n]+?)\s*-->\s*([^\n]+?)\s*\n"
            r"(.*?)(?=\n{2,}\d+\s*\n|\Z)",
            re.DOTALL,
        )
        for match in pattern.finditer(normalized):
            entries.append(
                SubtitleEntry(
                    index=int(match.group(1)),
                    start_ms=parse_srt_time(match.group(2)),
                    end_ms=parse_srt_time(match.group(3)),
                    text=match.group(4).strip(),
                )
            )
        return cls(entries)

    @classmethod
    def load(cls, path: str | Path) -> "SubtitleDocument":
        return cls.from_srt(Path(path).read_text(encoding="utf-8-sig"))

    def to_srt(self) -> str:
        chunks = []
        for entry in self.entries:
            chunks.append(
                f"{entry.index}\n"
                f"{format_srt_time(entry.start_ms)} --> {format_srt_time(entry.end_ms)}\n"
                f"{entry.text.strip()}\n"
            )
        return "\n".join(chunks)

    def save(self, path: str | Path):
        Path(path).write_text(self.to_srt(), encoding="utf-8")

    def update_text(self, entry_index: int, text: str):
        entry = self._get_entry(entry_index)
        entry.text = text.strip()

    def replace_text(self, old: str, new: str, *, case_sensitive: bool = False) -> int:
        if not old:
            return 0
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(old), flags)
        replacements = 0
        for entry in self.entries:
            entry.text, count = pattern.subn(new, entry.text)
            replacements += count
        return replacements

    def auto_wrap(self, max_chars: int = 34, max_lines: int = 2):
        for entry in self.entries:
            entry.text = wrap_subtitle_text(entry.text, max_chars, max_lines)

    def validate(
        self,
        *,
        max_chars_per_line: int = 42,
        max_lines: int = 2,
        max_cps: float = 20.0,
        min_duration_ms: int = 300,
    ) -> list[SubtitleIssue]:
        issues = []
        previous = None
        for entry in self.entries:
            if entry.end_ms <= entry.start_ms:
                issues.append(
                    SubtitleIssue(entry.index, "invalid_timing", "Thoi gian ket thuc phai sau bat dau", "error")
                )
                continue
            if entry.duration_ms < min_duration_ms:
                issues.append(
                    SubtitleIssue(entry.index, "too_short", "Subtitle hien thi qua ngan")
                )
            if previous and entry.start_ms < previous.end_ms:
                issues.append(
                    SubtitleIssue(entry.index, "overlap", f"Chong timing voi subtitle {previous.index}", "error")
                )

            lines = entry.text.splitlines() or [""]
            if len(lines) > max_lines:
                issues.append(
                    SubtitleIssue(entry.index, "too_many_lines", f"Vuot qua {max_lines} dong")
                )
            if any(len(line) > max_chars_per_line for line in lines):
                issues.append(
                    SubtitleIssue(entry.index, "line_too_long", f"Co dong dai hon {max_chars_per_line} ky tu")
                )

            visible_chars = len(re.sub(r"\s+", "", entry.text))
            cps = visible_chars / max(entry.duration_ms / 1000, 0.001)
            if cps > max_cps:
                issues.append(
                    SubtitleIssue(entry.index, "reading_too_fast", f"Toc do doc {cps:.1f} ky tu/giay")
                )
            previous = entry
        return issues

    def _get_entry(self, entry_index: int) -> SubtitleEntry:
        for entry in self.entries:
            if entry.index == entry_index:
                return entry
        raise KeyError(f"Khong tim thay subtitle {entry_index}")


def parse_srt_time(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*", value)
    if not match:
        raise ValueError(f"SRT timestamp khong hop le: {value}")
    hours, minutes, seconds, milliseconds = match.groups()
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(milliseconds.ljust(3, "0"))
    )


def format_srt_time(milliseconds: int) -> str:
    if milliseconds < 0:
        raise ValueError("Timestamp khong duoc am")
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def wrap_subtitle_text(text: str, max_chars: int = 34, max_lines: int = 2) -> str:
    if max_chars < 1 or max_lines < 1:
        raise ValueError("max_chars va max_lines phai lon hon 0")
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_chars:
        return normalized

    lines = textwrap.wrap(
        normalized,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(lines) <= max_lines:
        return "\n".join(lines)

    words = normalized.split()
    if len(words) == 1:
        chunk_size = math.ceil(len(normalized) / max_lines)
        return "\n".join(
            normalized[index:index + chunk_size]
            for index in range(0, len(normalized), chunk_size)
        )

    balanced = []
    remaining_words = words
    for line_number in range(max_lines):
        lines_left = max_lines - line_number
        if lines_left == 1:
            balanced.append(" ".join(remaining_words))
            break
        remaining_length = len(" ".join(remaining_words))
        target = math.ceil(remaining_length / lines_left)
        current = []
        while remaining_words:
            candidate = " ".join(current + [remaining_words[0]])
            if current and len(candidate) > target:
                break
            current.append(remaining_words.pop(0))
        balanced.append(" ".join(current))
    return "\n".join(balanced)


def parse_srt_blocks(content: str) -> list[dict]:
    return [
        {
            "index": str(entry.index),
            "time": f"{format_srt_time(entry.start_ms)} --> {format_srt_time(entry.end_ms)}",
            "text": entry.text,
        }
        for entry in SubtitleDocument.from_srt(content).entries
    ]


def blocks_to_srt(blocks: list[dict]) -> str:
    entries = []
    for block in blocks:
        start, end = block["time"].split("-->", 1)
        entries.append(
            SubtitleEntry(
                index=int(block["index"]),
                start_ms=parse_srt_time(start),
                end_ms=parse_srt_time(end),
                text=block["text"],
            )
        )
    return SubtitleDocument(entries).to_srt()
