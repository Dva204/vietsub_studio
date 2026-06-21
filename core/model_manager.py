"""Quan ly Faster Whisper model tren may nguoi dung."""

from __future__ import annotations

import shutil
from pathlib import Path


SUPPORTED_MODELS = ("tiny", "base", "small", "large-v3")


class ModelManager:
    def __init__(self, model_root: str | Path):
        self.model_root = Path(model_root).resolve()
        self.model_root.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list[dict]:
        return [self.status(name) for name in SUPPORTED_MODELS]

    def status(self, model_size: str) -> dict:
        self._validate_name(model_size)
        cache_dir = self.model_root / f"models--Systran--faster-whisper-{model_size}"
        snapshots = cache_dir / "snapshots"
        snapshot_dirs = [item for item in snapshots.iterdir() if item.is_dir()] if snapshots.is_dir() else []
        complete = any(_snapshot_complete(item) for item in snapshot_dirs)
        size_bytes = sum(
            item.stat().st_size for item in cache_dir.rglob("*") if item.is_file()
        ) if cache_dir.exists() else 0
        return {
            "model": model_size,
            "downloaded": complete,
            "path": str(cache_dir),
            "size_bytes": size_bytes,
        }

    def download(self, model_size: str, progress_callback=None, cancel_flag=None) -> dict:
        self._validate_name(model_size)
        if cancel_flag and cancel_flag[0]:
            return {"success": False, "error": "Canceled"}
        if progress_callback:
            progress_callback(f"Dang tai Faster Whisper {model_size}...")
        try:
            from huggingface_hub import snapshot_download

            path = snapshot_download(
                repo_id=f"Systran/faster-whisper-{model_size}",
                cache_dir=str(self.model_root),
                local_files_only=False,
            )
            if cancel_flag and cancel_flag[0]:
                return {"success": False, "error": "Canceled"}
            if progress_callback:
                progress_callback("Tai model: 100%")
            return {"success": True, "model": model_size, "path": path, "error": None}
        except Exception as error:
            return {"success": False, "error": f"Khong tai duoc model: {error}"}

    def delete(self, model_size: str) -> bool:
        self._validate_name(model_size)
        path = self.model_root / f"models--Systran--faster-whisper-{model_size}"
        if not path.exists():
            return False
        _ensure_child(path, self.model_root)
        shutil.rmtree(path)
        return True

    def _validate_name(self, model_size):
        if model_size not in SUPPORTED_MODELS:
            raise ValueError(f"Model phai la: {', '.join(SUPPORTED_MODELS)}")


def _snapshot_complete(path: Path) -> bool:
    required = {"config.json", "model.bin", "tokenizer.json"}
    return required.issubset({item.name for item in path.iterdir()})


def _ensure_child(path: Path, root: Path):
    if path.resolve() == root.resolve() or root.resolve() not in path.resolve().parents:
        raise ValueError("Tu choi thao tac ngoai model root")
