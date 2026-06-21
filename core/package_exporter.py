"""Tao editor-compatible output package mot cach atomic."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from core.subtitle import SubtitleDocument


def export_package(
    output_root: str,
    package_name: str,
    *,
    source_video: str,
    translated_srt: str,
    subtitled_video: str | None = None,
    caption: str | None = None,
    metadata: dict | None = None,
    overwrite: bool = True,
) -> dict:
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_name(package_name)
    destination = root / safe_name
    staging = Path(tempfile.mkdtemp(prefix=f".{safe_name}_", dir=root))
    backup = root / f".{safe_name}.backup"

    try:
        source = Path(source_video).resolve()
        subtitle = Path(translated_srt).resolve()
        if not source.is_file() or not subtitle.is_file():
            raise FileNotFoundError("Thieu source video hoac translated SRT")
        source_output = staging / f"source{source.suffix.lower()}"
        shutil.copy2(source, source_output)
        subtitle_output = staging / "subtitle.vi.srt"
        shutil.copy2(subtitle, subtitle_output)

        document = SubtitleDocument.load(subtitle)
        (staging / "transcript.txt").write_text(
            "\n".join(entry.text for entry in document.entries), encoding="utf-8"
        )
        if subtitled_video:
            rendered = Path(subtitled_video).resolve()
            if rendered.is_file():
                shutil.copy2(rendered, staging / "subtitled.mp4")
        if caption is not None:
            (staging / "caption.txt").write_text(caption.strip(), encoding="utf-8")

        files = [path for path in staging.iterdir() if path.is_file()]
        manifest = {
            "package_version": 1,
            "name": safe_name,
            "metadata": metadata or {},
            "files": [
                {"name": path.name, "size": path.stat().st_size, "sha256": _sha256(path)}
                for path in sorted(files)
            ],
        }
        (staging / "project.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if destination.exists():
            if not overwrite:
                raise FileExistsError(f"Package da ton tai: {destination}")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destination, backup)
        os.replace(staging, destination)
        if backup.exists():
            shutil.rmtree(backup)
        return {"success": True, "package_path": str(destination), "manifest": manifest, "error": None}
    except Exception as error:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        return {"success": False, "package_path": None, "manifest": None, "error": str(error)}
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value).strip(" .")
    return cleaned[:100] or "vietdub-package"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
