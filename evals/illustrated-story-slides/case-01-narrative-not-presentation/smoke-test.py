#!/usr/bin/env python3
"""Deterministic tool smoke tests for illustrated-story-slides."""

from __future__ import annotations

import binascii
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPTS = REPO / "skills" / "illustrated-story-slides" / "scripts"


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != expect:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise AssertionError(f"expected exit {expect}, got {result.returncode}: {' '.join(args)}")
    return result


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)


def solid_png(path: Path, width: int = 1920, height: int = 1080) -> None:
    row = b"\x00" + (b"\xd9\xc5\x9f" * width)
    raw = row * height
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def valid_scene() -> dict:
    return {
        "id": "01",
        "slug": "yellow-raincoat-button",
        "narration_excerpt": "할머니는 노란 우비의 마지막 단추를 잠가 주셨습니다.",
        "caption": "할머니는 노란 우비의 마지막 단추를 잠가 주셨습니다.",
        "function": "action",
        "truth_mode": "MEMORY",
        "truth_refs": ["T01"],
        "source_basis": "raincoat-script.md paragraphs 1-2; synthetic narrated memory",
        "literal_content": "할머니가 아이의 노란 우비 단추를 잠갔다.",
        "visual_interpretation": "얼굴 대신 두 손과 노란 단추를 가까이 보여 준다.",
        "intentionally_unspecified": ["얼굴", "정확한 연도", "실제 집 구조"],
        "composition": {
            "shot": "close-up",
            "subject": "older hands and a yellow raincoat button",
            "action": "fastening the final button",
            "setting": "quiet entryway on a rainy morning",
            "negative_space": "soft gray doorway fills the right third",
            "anchor_from_previous": "yellow raincoat",
        },
        "continuity_notes": ["yellow raincoat", "navy umbrella handle", "soft gray rain light"],
        "on_screen_text": "",
        "duration_sec": 8,
        "motion": {"type": "slow-push", "purpose": "draw attention to the small act of care"},
        "frame": "frames/01-yellow-raincoat-button.png",
        "alt": "빗빛이 드는 현관에서 나이 든 두 손이 노란 우비의 마지막 단추를 잠근다.",
        "generation_inputs": {"named_styles": [], "reference_images": []},
        "prompt": {
            "positive": "original editorial storybook illustration, 16:9, quiet rainy entryway, older hands fastening one yellow raincoat button, restrained graphite contour, muted gray and yellow palette, no visible face",
            "negative": "text, logo, watermark, presentation UI, fake archival photograph, melodramatic tears",
        },
        "provenance": {
            "source_type": "AI-generated",
            "source_reference": "",
            "license_permission": "evaluation fixture generation",
            "tool": "deterministic smoke-test PNG",
            "prompt_version": "v1",
            "human_edit": "scene selection and crop review",
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="illustrated-story-slides-eval-") as temporary:
        root = Path(temporary)
        source = root / "script.md"
        source.write_text((HERE / "fixture" / "raincoat-script.md").read_text(encoding="utf-8"), encoding="utf-8")
        deck = root / "deck"

        run(
            "python3",
            str(SCRIPTS / "new_deck.py"),
            "--output",
            str(deck),
            "--title",
            "비 오는 날의 우비",
            "--script",
            str(source),
            "--coverage-mode",
            "supporting-slides",
            "--privacy",
            "public",
        )
        assert (deck / "deck.json").is_file()
        assert (deck / "style-bible.md").is_file()
        assert (deck / "sources.md").is_file()
        assert (deck / "frames").is_dir()
        assert json.loads((deck / "deck.json").read_text(encoding="utf-8"))["production_status"] == "planning"
        print("PASS skeleton-created")

        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS empty-plan-fails")

        data = json.loads((deck / "deck.json").read_text(encoding="utf-8"))
        data["art_direction"].update(
            {
                "concept": "A remembered act of care carried forward through one yellow button",
                "medium": "graphite contour with translucent color on visible paper grain",
                "palette": ["rain gray", "warm ivory", "raincoat yellow", "navy blue"],
                "continuity_anchors": ["yellow raincoat", "navy umbrella", "gray rain light"],
            }
        )
        data["truth_ledger"] = [
            {
                "id": "T01",
                "mode": "MEMORY",
                "claim": "할머니가 아이의 우비 마지막 단추를 잠가 주었다.",
                "basis": "evaluation script paragraph 1",
                "visual_handling": "익명의 손과 단추만 보여 실제 기록처럼 보이지 않게 한다.",
            }
        ]
        data["scenes"] = [valid_scene()]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan")
        print("PASS valid-plan")

        data["production_status"] = "visuals-pending"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "build_preview.py"), str(deck), "--storyboard-only")
        assert (deck / "storyboard.md").is_file()
        assert (deck / "captions.vtt").is_file()
        assert not (deck / "preview.html").exists()
        assert "visuals-pending" in (deck / "storyboard.md").read_text(encoding="utf-8")
        print("PASS visuals-pending-storyboard-fallback")
        data["production_status"] = "planning"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "build_preview.py"), str(deck), "--storyboard-only", expect=1)
        print("PASS storyboard-fallback-requires-pending-status")

        data["production_status"] = []
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS invalid-production-status-fails-closed")
        data["production_status"] = "planning"

        data["scenes"][0]["intentionally_unspecified"] = [{}]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS invalid-unspecified-entry-fails-closed")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["continuity_notes"] = [3]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS invalid-continuity-entry-fails-closed")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["generation_inputs"]["reference_images"] = [
            {
                "origin": "self-generated-prior-frame",
                "source_reference": "frames/00-ghost.png",
                "sha256": "0" * 64,
                "permission": "same-deck generated frame",
                "purpose": "character-continuity",
            }
        ]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS undeclared-prior-frame-fails")
        data["scenes"][0] = valid_scene()

        second_scene = valid_scene()
        second_scene.update(
            {
                "id": "02",
                "slug": "yellow-raincoat-door",
                "frame": "frames/02-yellow-raincoat-door.png",
            }
        )
        second_scene["generation_inputs"]["reference_images"] = [
            {
                "origin": "self-generated-prior-frame",
                "source_reference": "frames/01-yellow-raincoat-button.png",
                "sha256": "0" * 64,
                "permission": "same-deck generated frame",
                "purpose": "character-continuity",
            }
        ]
        data["scenes"] = [valid_scene(), second_scene]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan")
        print("PASS declared-prior-frame-passes")
        data["scenes"] = [valid_scene()]

        data["scenes"][0]["prompt"]["positive"] += " in the style of a named living artist"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS named-style-fails")
        data["scenes"][0] = valid_scene()
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for label, wording in (
            ("capitalized-like-artist", "Like the Norman Rockwell illustrations"),
            ("capitalized-after-artist", "After Picasso"),
        ):
            data["scenes"][0]["prompt"]["positive"] += f" {wording}"
            (deck / "deck.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
            print(f"PASS {label}-fails")
            data["scenes"][0] = valid_scene()

        for label, wording in (
            ("korean-program-style", "TV동화 행복한 세상풍"),
            ("korean-comparison", "그 프로그램처럼"),
            ("korean-original-art-style", "원화풍"),
        ):
            data["scenes"][0]["prompt"]["positive"] += f" {wording}"
            (deck / "deck.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
            print(f"PASS {label}-fails")
            data["scenes"][0] = valid_scene()

        data["scenes"][0]["prompt"]["positive"] += " Ghibli-inspired"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS named-studio-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["prompt"]["negative"] += " Ghibli"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS named-studio-in-negative-prompt-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["generation_inputs"]["named_styles"] = ["Named Artist"]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS named-style-list-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["provenance"].update(
            {
                "source_type": "licensed",
                "source_reference": "KBS VOD broadcast still used as a visual reference",
            }
        )
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS broadcast-provenance-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["provenance"].update(
            {
                "source_type": "licensed",
                "source_reference": "TV동화 행복한 세상 캡처",
            }
        )
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS korean-program-capture-provenance-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["generation_inputs"]["reference_images"] = [
            {
                "origin": "licensed-production-asset",
                "source_reference": "KBS VOD episode still",
                "sha256": "0" * 64,
                "permission": "claimed licensed",
                "purpose": "character-continuity",
            }
        ]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS broadcast-generation-reference-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["generation_inputs"]["reference_images"] = [
            {
                "origin": "licensed-production-asset",
                "source_reference": "TV동화 행복한 세상 캡쳐",
                "sha256": "0" * 64,
                "permission": "claimed licensed",
                "purpose": "character-continuity",
            }
        ]
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS korean-program-capture-generation-reference-fails")
        data["scenes"][0] = valid_scene()

        data["scenes"][0]["provenance"].update(
            {
                "source_type": "licensed",
                "source_reference": "licensed screenshot from a reference program",
            }
        )
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS screenshot-provenance-fails")
        data["scenes"][0] = valid_scene()
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        data["scenes"][0]["motion"]["type"] = []
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "plan", expect=1)
        print("PASS invalid-enum-type-fails-closed")
        data["scenes"][0] = valid_scene()
        data["production_status"] = "rendered"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "render", expect=1)
        print("PASS missing-frame-fails")

        frame = deck / data["scenes"][0]["frame"]
        solid_png(frame)
        data["scenes"][0]["truth_mode"] = "UNVERIFIED"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "render", expect=1)
        print("PASS unverified-render-fails")
        data["scenes"][0]["truth_mode"] = "MEMORY"
        (deck / "deck.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "render")
        run("python3", str(SCRIPTS / "build_preview.py"), str(deck))
        for name in ("storyboard.md", "captions.vtt", "preview.html"):
            assert (deck / name).is_file() and (deck / name).stat().st_size > 100
        preview = (deck / "preview.html").read_text(encoding="utf-8")
        assert "prefers-reduced-motion" in preview
        print("PASS valid-render-and-preview")
        assert data["scenes"][0]["prompt"]["positive"] not in preview
        assert data["scenes"][0]["source_basis"] not in preview
        print("PASS preview-excludes-production-metadata")

        shutil.copy2(frame, deck / "frames" / "99-extra.png")
        run("python3", str(SCRIPTS / "validate_deck.py"), str(deck), "--stage", "render", expect=1)
        print("PASS unreferenced-frame-fails")

        run(
            "python3",
            str(SCRIPTS / "new_deck.py"),
            "--output",
            str(deck),
            "--title",
            "덮어쓰기 금지",
            "--script",
            str(source),
            expect=2,
        )
        print("PASS overwrite-refused")

    print("SUMMARY 31/31")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
