"""Test thu cong: burn subtitle tieng Viet vao video mau."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.exporter import SUBTITLE_PRESETS, export_subtitled_video, get_subtitle_style


def main() -> int:
    parser = argparse.ArgumentParser(description="Burn SRT vao MP4 bang FFmpeg.")
    parser.add_argument("video", nargs="?", default=str(PROJECT_ROOT / "downloads" / "vd.mp4"))
    parser.add_argument("subtitle", nargs="?", default=str(PROJECT_ROOT / "downloads" / "vd.vi.srt"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "downloads" / "vd_subtitled.mp4"))
    parser.add_argument("--preset", choices=sorted(SUBTITLE_PRESETS), default="shorts")
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--margin", type=int)
    args = parser.parse_args()

    style = get_subtitle_style(args.preset)
    if args.font_size is not None:
        style = replace(style, font_size=args.font_size)
    if args.margin is not None:
        style = replace(style, margin_vertical=args.margin)

    result = export_subtitled_video(
        args.video,
        args.subtitle,
        args.output,
        style=style,
        progress_callback=print,
    )
    print("\n=== KET QUA ===")
    print(result)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
