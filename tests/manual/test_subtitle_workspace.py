"""Test thu cong: validate va auto-wrap mot file SRT."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.subtitle import SubtitleDocument


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiem tra va xuong dong subtitle.")
    parser.add_argument("srt", nargs="?", default=str(PROJECT_ROOT / "downloads" / "vd.vi.srt"))
    parser.add_argument("--max-chars", type=int, default=34)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args()

    source = Path(args.srt).resolve()
    output = Path(args.output).resolve() if args.output else source.with_name(f"{source.stem}.edited.srt")
    document = SubtitleDocument.load(source)
    issues_before = document.validate()
    document.auto_wrap(args.max_chars, args.max_lines)
    document.save(output)
    issues_after = document.validate()

    print(f"Subtitle: {len(document.entries)}")
    print(f"Canh bao truoc/sau: {len(issues_before)} / {len(issues_after)}")
    for issue in issues_after:
        print(f"  [{issue.severity}] #{issue.entry_index} {issue.code}: {issue.message}")
    print(f"Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
