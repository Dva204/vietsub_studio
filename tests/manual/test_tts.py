"""Test thu cong: tao audio long tieng tu mot file SRT tieng Viet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.tts import VOICES, generate_dubbed_audio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tao MP3 long tieng tu file SRT.")
    parser.add_argument(
        "srt",
        nargs="?",
        default=str(PROJECT_ROOT / "downloads" / "vd.vi.srt"),
        help="File SRT dau vao (mac dinh: downloads/vd.vi.srt)",
    )
    parser.add_argument(
        "--voice",
        choices=list(VOICES),
        default="Nu mien Nam",
        help="Giong doc Edge TTS",
    )
    parser.add_argument("--output-dir", help="Thu muc luu MP3")
    parser.add_argument(
        "--rate",
        default="+0%",
        help="Toc do Edge TTS, vi du: +10%% hoac -10%%",
    )
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _build_parser().parse_args()

    print(f"SRT: {Path(args.srt).resolve()}")
    print(f"Giong: {args.voice} | Toc do: {args.rate}\n")
    result = generate_dubbed_audio(
        srt_path=args.srt,
        voice_name=args.voice,
        output_dir=args.output_dir,
        rate=args.rate,
        progress_callback=lambda message: print(f"  {message}"),
    )

    print("\n=== KET QUA ===")
    if result["success"]:
        print(f"OK: {result['audio_path']}")
        print(f"So doan audio: {result['segments']}")
        return 0

    print(f"LOI: {result['error']}")
    if result.get("audio_path"):
        print(f"Audio mot phan: {result['audio_path']}")
    for failure in result.get("failures", []):
        print(f"  Subtitle {failure['index']}: {failure['error']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
