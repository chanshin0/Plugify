#!/usr/bin/env python3
"""Create a non-destructive illustrated-story-slides project skeleton."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCHEMA = "plugify.illustrated-story-slides/1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New deck directory")
    parser.add_argument("--title", required=True)
    parser.add_argument("--script", required=True, help="Existing source script path")
    parser.add_argument(
        "--coverage-mode",
        choices=("supporting-slides", "full-animatic"),
        default="supporting-slides",
    )
    parser.add_argument(
        "--privacy",
        choices=("public", "internal", "confidential"),
        default="internal",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    script = Path(args.script).expanduser().resolve()
    title = args.title.strip()

    if not script.is_file():
        print(f"ERROR source script does not exist: {script}", file=sys.stderr)
        return 2
    if not title:
        print("ERROR title must not be empty", file=sys.stderr)
        return 2
    if output.exists() and not output.is_dir():
        print(f"ERROR output path exists and is not a directory: {output}", file=sys.stderr)
        return 2
    if output.is_dir() and any(output.iterdir()):
        print(f"ERROR refusing to overwrite non-empty directory: {output}", file=sys.stderr)
        return 2

    output.mkdir(parents=True, exist_ok=True)
    (output / "frames").mkdir(exist_ok=True)

    manifest = {
        "schema": SCHEMA,
        "title": title,
        "production_status": "planning",
        "source": {
            "script_path": str(script),
            "privacy": args.privacy,
            "coverage_mode": args.coverage_mode,
        },
        "canvas": {"width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        "art_direction": {
            "concept": "",
            "medium": "",
            "palette": [],
            "continuity_anchors": [],
            "avoid": [
                "specific artist, studio, program, or episode imitation",
                "logos, watermarks, and generated text",
                "presentation cards, slide numbers, and navigation UI",
                "photoreal fake archival imagery",
                "melodramatic tears and dignity-reducing stereotypes",
            ],
        },
        "characters": [],
        "truth_ledger": [],
        "scenes": [],
    }
    (output / "deck.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    style_bible = f"""# {title} — style bible

## 한 문장 콘셉트

<!-- 이 작품만의 정서와 시각적 중심을 한 문장으로 -->

## 재료와 선

- 재료감:
- 윤곽:
- 채색:
- 피해야 할 생성 이미지 습관:

## 제한 팔레트

- 주조색:
- 보조색 1:
- 보조색 2:
- 강조색:
- 현재/회상/전환/여운의 변화:

## 연속성 앵커

- 반복 인물:
- 반복 장소:
- 반복 소품·빛·색:

## 금지

- 특정 방송·작가·스튜디오·프랜차이즈 이름을 프롬프트에 사용하지 않는다.
- 로고·워터마크·생성 글자·프레젠테이션 UI를 넣지 않는다.
- 대본에 없는 실제 인물·장소·행동을 사실처럼 만들지 않는다.
"""
    (output / "style-bible.md").write_text(style_bible, encoding="utf-8")

    sources = f"""# {title} — sources and provenance

- Source script: `{script}`
- Privacy: `{args.privacy}`
- Coverage mode: `{args.coverage_mode}`

## 참고 자료

<!-- URL, 문서명, 사용 목적. 참고와 최종 사용 자산을 구분한다. -->

## 최종 사용 자산·권리

<!-- 장면 ID / 자산 / source_type / license·permission / tool / human edit -->

## 공개 표기 결정

<!-- AI 생성·기억 기반 삽화·상징적 삽화 표기가 필요한지 기록한다. -->
"""
    (output / "sources.md").write_text(sources, encoding="utf-8")

    print(f"CREATED {output}")
    for name in ("deck.json", "style-bible.md", "sources.md", "frames/"):
        print(f"  {name}")
    print("NEXT fill truth_ledger and scenes, then run validate_deck.py --stage plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
