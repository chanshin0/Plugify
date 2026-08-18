#!/usr/bin/env python3
"""Crop and resize an image to an exact 16:9 PNG using Pillow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - environment guidance
    print(
        "ERROR Pillow is required. Run with: uv run --with pillow python normalize_frame.py ...",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--center-x", type=float, default=0.5)
    parser.add_argument("--center-y", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    target = Path(args.output).expanduser().resolve()
    if not source.is_file():
        print(f"ERROR input image does not exist: {source}", file=sys.stderr)
        return 2
    if target.exists() and not args.overwrite:
        print(f"ERROR refusing to overwrite: {target}; pass --overwrite explicitly", file=sys.stderr)
        return 2
    if args.width < 1 or args.height < 1:
        print("ERROR width and height must be positive", file=sys.stderr)
        return 2
    if not 0 <= args.center_x <= 1 or not 0 <= args.center_y <= 1:
        print("ERROR center-x and center-y must be between 0 and 1", file=sys.stderr)
        return 2

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        fitted = ImageOps.fit(
            image,
            (args.width, args.height),
            method=Image.Resampling.LANCZOS,
            centering=(args.center_x, args.center_y),
        )
        fitted.save(target, format="PNG", optimize=True)
    print(f"WROTE {target} {args.width}x{args.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
