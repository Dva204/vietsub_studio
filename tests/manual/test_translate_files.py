"""Chay thu translator voi mot hoac nhieu file SRT that."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.translator import translate_srt


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dich mot file, nhieu file, hoac ca thu muc SRT sang tieng Viet."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(PROJECT_ROOT / "downloads")],
        help="File/thu muc SRT. Mac dinh: downloads",
    )
    parser.add_argument(
        "--source",
        "-s",
        default="auto",
        help="Ngon ngu nguon: auto, en, zh-CN, ja, ko... (mac dinh: auto)",
    )
    parser.add_argument(
        "--context",
        "-c",
        type=int,
        default=5,
        help="So subtitle dich chung mot cum (mac dinh: 5)",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Tim SRT trong ca thu muc con",
    )
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Dich lai ca file *.vi.srt",
    )
    return parser


def _collect_srt_files(
    raw_paths: list[str], recursive: bool, include_translated: bool
) -> list[Path]:
    files: set[Path] = set()
    pattern = "**/*.srt" if recursive else "*.srt"

    for raw_path in raw_paths:
        path = Path(raw_path).expanduser()
        if path.is_file() and path.suffix.lower() == ".srt":
            files.add(path.resolve())
        elif path.is_dir():
            files.update(item.resolve() for item in path.glob(pattern) if item.is_file())
        else:
            print(f"CANH BAO: Khong tim thay: {path}")

    if not include_translated:
        files = {path for path in files if not path.name.lower().endswith(".vi.srt")}
    return sorted(files)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _build_parser().parse_args()
    if args.context < 1:
        print("LOI: --context phai lon hon 0")
        return 2

    files = _collect_srt_files(args.paths, args.recursive, args.include_translated)
    if not files:
        print("Khong tim thay file SRT nao de dich.")
        return 2

    print(f"Tim thay {len(files)} file SRT. Ngon ngu nguon: {args.source}\n")
    succeeded = 0
    failed = 0

    for position, path in enumerate(files, start=1):
        print(f"[{position}/{len(files)}] {path}")

        def show_progress(message: str):
            print(f"  {message}")

        result = translate_srt(
            str(path),
            src_lang=args.source,
            context_window=args.context,
            progress_callback=show_progress,
        )
        failed_blocks = int(result.get("failed", 0))
        if result.get("success") and failed_blocks == 0:
            succeeded += 1
            print(f"  OK: {result['output_path']}\n")
        else:
            failed += 1
            error = result.get("error") or f"{failed_blocks} block dich that bai"
            print(f"  LOI: {error}\n")

    print("=" * 50)
    print(f"Hoan tat: {succeeded} thanh cong, {failed} that bai.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
