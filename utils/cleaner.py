"""Don file temp voi gioi han thu muc an toan."""

from __future__ import annotations

import shutil
import time
from pathlib import Path


class WorkspaceCleaner:
    def __init__(self, allowed_roots):
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]

    def remove(self, path: str | Path) -> bool:
        target = Path(path).resolve()
        self._validate(target)
        if not target.exists():
            return False
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return True

    def cleanup_stale_workdirs(
        self,
        max_age_hours: float = 24,
        *,
        protected_paths=(),
    ) -> list[str]:
        cutoff = time.time() - max_age_hours * 3600
        protected = {Path(path).resolve() for path in protected_paths}
        removed = []
        for root in self.allowed_roots:
            if not root.exists():
                continue
            candidates = list(root.glob("**/.work/job_*"))
            candidates += list(root.glob("**/vietdub_export_*"))
            candidates += list(root.glob("**/vietdub_tts_*"))
            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                    if any(
                        resolved == item or resolved in item.parents or item in resolved.parents
                        for item in protected
                    ):
                        continue
                    if candidate.stat().st_mtime < cutoff and self.remove(candidate):
                        removed.append(str(candidate))
                except FileNotFoundError:
                    continue
        return removed

    def _validate(self, target: Path):
        for root in self.allowed_roots:
            if target != root and root in target.parents:
                return
        raise ValueError(f"Tu choi xoa ngoai workspace: {target}")
