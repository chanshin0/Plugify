#!/usr/bin/env python3
"""Fail-closed validation for illustrated-story-slides deck.json and frames."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any


SCHEMA = "plugify.illustrated-story-slides/1"
TRUTH_MODES = {"FACT", "MEMORY", "SYMBOLIC", "UNVERIFIED"}
FUNCTIONS = {"setting", "absence", "action", "turn", "reflection", "afterglow"}
MOTIONS = {"none", "slow-push", "slow-pan-left", "slow-pan-right"}
PRIVACY = {"public", "internal", "confidential"}
COVERAGE = {"supporting-slides", "full-animatic"}
PRODUCTION_STATUSES = {"planning", "visuals-pending", "rendered"}
SOURCE_TYPES = {"AI-generated", "licensed", "original", "mixed"}
REFERENCE_ORIGINS = {
    "self-generated-prior-frame",
    "user-owned-photo",
    "licensed-production-asset",
}
REFERENCE_PURPOSES = {"character-continuity", "location-continuity", "fact-anchoring"}
FRAME_RE = re.compile(r"^frames/(?P<id>\d{2})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.png$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HANGUL_OR_CJK_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
PROMPT_REFERENCE_PATTERNS = (
    re.compile(r"\bstyle\b", re.IGNORECASE),
    re.compile(r"\b(?:inspired\s+by|reminiscent\s+of|similar\s+to|as\s+seen\s+in)\b", re.IGNORECASE),
    re.compile(r"\b(?:frame|still|art|illustration|painting|drawing)\s+(?:from|by)\b", re.IGNORECASE),
    re.compile(r"\b(?:imitate|imitation|replicate|copy)\b", re.IGNORECASE),
    re.compile(r"\b(?:kbs|ebs|ghibli|pixar|disney|dreamworks|netflix|marvel)\b", re.IGNORECASE),
    re.compile(r"https?://|www\.", re.IGNORECASE),
    re.compile(r"\blike\s+the\b", re.IGNORECASE),
    re.compile(r"\b(?i:like|after)\s+[A-Z][A-Za-z'’-]+"),
    re.compile(r"\b[A-Z][A-Za-z'’-]+-(?i:like|inspired|style)\b"),
)
BROADCAST_REFERENCE_RE = re.compile(
    r"\b(?:kbs|ebs|vod|broadcast|episode|tv\s*(?:show|program)|broadcast\s*still|"
    r"capture|screenshot|screen\s*grab)\b|"
    r"방송|스틸|원화|에피소드|다시보기|프로그램|캡처|캡쳐|스크린샷|화면\s*갈무리|"
    r"tv\s*동화\s*행복한\s*세상|감성애니\s*하루",
    re.IGNORECASE,
)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG")
        length = struct.unpack(">I", handle.read(4))[0]
        chunk = handle.read(4)
        if chunk != b"IHDR" or length < 8:
            raise ValueError("missing PNG IHDR")
        width, height = struct.unpack(">II", handle.read(8))
        return width, height


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def prompt_policy_errors(value: Any) -> list[str]:
    if not _text(value):
        return ["required"]
    text = str(value)
    failures: list[str] = []
    if HANGUL_OR_CJK_RE.search(text):
        failures.append("use English observable attributes; Korean/CJK named-style wording is forbidden")
    for pattern in PROMPT_REFERENCE_PATTERNS:
        if pattern.search(text):
            failures.append(f"named/comparative reference marker matched {pattern.pattern!r}")
    return failures


def validate(root: Path, stage: str) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "deck.json"
    if not manifest_path.is_file():
        return ["deck.json: missing"]
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"deck.json: cannot parse: {exc}"]

    if data.get("schema") != SCHEMA:
        errors.append(f"schema: expected {SCHEMA}")
    if not _text(data.get("title")):
        errors.append("title: required non-empty string")
    production_status = data.get("production_status")
    if not isinstance(production_status, str) or production_status not in PRODUCTION_STATUSES:
        errors.append("production_status: expected planning|visuals-pending|rendered")
    elif stage == "render" and production_status != "rendered":
        errors.append("production_status: render stage requires rendered")

    source = _dict(data.get("source"))
    if not isinstance(source.get("privacy"), str) or source.get("privacy") not in PRIVACY:
        errors.append("source.privacy: expected public|internal|confidential")
    if not isinstance(source.get("coverage_mode"), str) or source.get("coverage_mode") not in COVERAGE:
        errors.append("source.coverage_mode: expected supporting-slides|full-animatic")
    if not _text(source.get("script_path")):
        errors.append("source.script_path: required")
    else:
        script_path = Path(source["script_path"]).expanduser()
        if not script_path.is_absolute() or not script_path.is_file():
            errors.append("source.script_path: expected an existing absolute file")

    for required_file in ("style-bible.md", "sources.md"):
        file_path = root / required_file
        if not file_path.is_file() or file_path.stat().st_size == 0:
            errors.append(f"{required_file}: missing or empty")

    canvas = _dict(data.get("canvas"))
    width, height = canvas.get("width"), canvas.get("height")
    if width != 1920 or height != 1080 or canvas.get("aspect_ratio") != "16:9":
        errors.append("canvas: expected width=1920 height=1080 aspect_ratio=16:9")

    art = _dict(data.get("art_direction"))
    for key in ("concept", "medium"):
        if not _text(art.get(key)):
            errors.append(f"art_direction.{key}: required")
    palette = _list(art.get("palette"))
    if not 3 <= len(palette) <= 4 or any(not _text(item) for item in palette):
        errors.append("art_direction.palette: require 3-4 named or hex colors")
    continuity_anchors = art.get("continuity_anchors")
    if (
        not isinstance(continuity_anchors, list)
        or not continuity_anchors
        or any(not _text(item) for item in continuity_anchors)
    ):
        errors.append("art_direction.continuity_anchors: require non-empty string anchors")
    avoid = art.get("avoid")
    if not isinstance(avoid, list) or not avoid or any(not _text(item) for item in avoid):
        errors.append("art_direction.avoid: require non-empty string rules")

    ledger = _list(data.get("truth_ledger"))
    if not ledger:
        errors.append("truth_ledger: require at least one entry")
    ledger_ids: set[str] = set()
    for index, entry in enumerate(ledger, 1):
        item = _dict(entry)
        prefix = f"truth_ledger[{index}]"
        entry_id = item.get("id")
        if not _text(entry_id):
            errors.append(f"{prefix}.id: required")
        elif entry_id in ledger_ids:
            errors.append(f"{prefix}.id: duplicate {entry_id}")
        else:
            ledger_ids.add(entry_id)
        if not isinstance(item.get("mode"), str) or item.get("mode") not in TRUTH_MODES:
            errors.append(f"{prefix}.mode: invalid")
        for key in ("claim", "basis", "visual_handling"):
            if not _text(item.get(key)):
                errors.append(f"{prefix}.{key}: required")

    scenes = _list(data.get("scenes"))
    if not scenes:
        errors.append("scenes: require at least one scene")
        return errors

    seen_frames: set[str] = set()
    expected_frame_paths: set[Path] = set()
    for index, entry in enumerate(scenes, 1):
        scene = _dict(entry)
        expected_id = f"{index:02d}"
        prefix = f"scenes[{index}]"
        if scene.get("id") != expected_id:
            errors.append(f"{prefix}.id: expected {expected_id}")
        slug = scene.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
            errors.append(f"{prefix}.slug: expected lowercase kebab-case")
        for key in (
            "narration_excerpt",
            "caption",
            "source_basis",
            "literal_content",
            "visual_interpretation",
            "alt",
        ):
            if not _text(scene.get(key)):
                errors.append(f"{prefix}.{key}: required")
        caption = scene.get("caption")
        if isinstance(caption, str) and "-->" in caption:
            errors.append(f"{prefix}.caption: VTT timing marker is forbidden")
        if not isinstance(scene.get("function"), str) or scene.get("function") not in FUNCTIONS:
            errors.append(f"{prefix}.function: invalid")
        if not isinstance(scene.get("truth_mode"), str) or scene.get("truth_mode") not in TRUTH_MODES:
            errors.append(f"{prefix}.truth_mode: invalid")
        elif stage == "render" and scene.get("truth_mode") == "UNVERIFIED":
            errors.append(f"{prefix}.truth_mode: UNVERIFIED cannot be rendered")
        truth_refs = scene.get("truth_refs")
        if not isinstance(truth_refs, list) or not truth_refs or any(not _text(item) for item in truth_refs):
            errors.append(f"{prefix}.truth_refs: require non-empty list")
        else:
            missing_refs = [item for item in truth_refs if item not in ledger_ids]
            if missing_refs:
                errors.append(f"{prefix}.truth_refs: unknown ledger IDs {missing_refs}")
        unspecified = scene.get("intentionally_unspecified")
        if (
            not isinstance(unspecified, list)
            or not unspecified
            or any(not _text(item) for item in unspecified)
        ):
            errors.append(f"{prefix}.intentionally_unspecified: require non-empty string list")

        composition = _dict(scene.get("composition"))
        for key in ("shot", "subject", "action", "setting", "negative_space", "anchor_from_previous"):
            if not _text(composition.get(key)):
                errors.append(f"{prefix}.composition.{key}: required")
        continuity = scene.get("continuity_notes")
        if (
            not isinstance(continuity, list)
            or not continuity
            or any(not _text(item) for item in continuity)
        ):
            errors.append(f"{prefix}.continuity_notes: require non-empty string list")

        on_screen = scene.get("on_screen_text")
        if not isinstance(on_screen, str):
            errors.append(f"{prefix}.on_screen_text: expected string")
        elif len(on_screen.replace("\n", "")) > 40 or on_screen.count("\n") > 1:
            errors.append(f"{prefix}.on_screen_text: maximum 40 characters and 2 lines")

        duration = scene.get("duration_sec")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not 1 <= duration <= 60:
            errors.append(f"{prefix}.duration_sec: expected 1..60 seconds")

        motion = _dict(scene.get("motion"))
        if not isinstance(motion.get("type"), str) or motion.get("type") not in MOTIONS:
            errors.append(f"{prefix}.motion.type: invalid")
        if motion.get("type") != "none" and not _text(motion.get("purpose")):
            errors.append(f"{prefix}.motion.purpose: required for moving scene")

        frame = scene.get("frame")
        match = FRAME_RE.fullmatch(frame) if isinstance(frame, str) else None
        if not match or match.group("id") != expected_id or match.group("slug") != slug:
            errors.append(f"{prefix}.frame: expected frames/{expected_id}-{slug or '<slug>'}.png")
        elif frame in seen_frames:
            errors.append(f"{prefix}.frame: duplicate {frame}")
        else:
            seen_frames.add(frame)
            frame_path = root / frame
            expected_frame_paths.add(frame_path.resolve())
            if not _inside(root, frame_path):
                errors.append(f"{prefix}.frame: escapes deck root")
            elif stage == "render":
                if not frame_path.is_file():
                    errors.append(f"{prefix}.frame: missing file {frame}")
                else:
                    try:
                        image_width, image_height = png_dimensions(frame_path)
                    except (OSError, ValueError, struct.error) as exc:
                        errors.append(f"{prefix}.frame: invalid PNG: {exc}")
                    else:
                        if (image_width, image_height) != (width, height):
                            errors.append(
                                f"{prefix}.frame: expected {width}x{height}, got {image_width}x{image_height}"
                            )

        prompt = _dict(scene.get("prompt"))
        for prompt_key in ("positive", "negative"):
            for detail in prompt_policy_errors(prompt.get(prompt_key)):
                errors.append(f"{prefix}.prompt.{prompt_key}: {detail}")

        generation_inputs = _dict(scene.get("generation_inputs"))
        named_styles = generation_inputs.get("named_styles")
        if not isinstance(named_styles, list) or named_styles:
            errors.append(f"{prefix}.generation_inputs.named_styles: expected empty list")
        reference_images = generation_inputs.get("reference_images")
        if not isinstance(reference_images, list):
            errors.append(f"{prefix}.generation_inputs.reference_images: expected list")
            reference_images = []
        for ref_index, raw_reference in enumerate(reference_images, 1):
            reference = _dict(raw_reference)
            ref_prefix = f"{prefix}.generation_inputs.reference_images[{ref_index}]"
            origin = reference.get("origin")
            if not isinstance(origin, str) or origin not in REFERENCE_ORIGINS:
                errors.append(f"{ref_prefix}.origin: invalid")
            source_reference = reference.get("source_reference")
            if not _text(source_reference):
                errors.append(f"{ref_prefix}.source_reference: required")
            elif BROADCAST_REFERENCE_RE.search(str(source_reference)):
                errors.append(f"{ref_prefix}.source_reference: broadcast/program artwork is forbidden")
            digest = reference.get("sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"{ref_prefix}.sha256: expected lowercase SHA-256")
            if not _text(reference.get("permission")):
                errors.append(f"{ref_prefix}.permission: required")
            purpose = reference.get("purpose")
            if not isinstance(purpose, str) or purpose not in REFERENCE_PURPOSES:
                errors.append(f"{ref_prefix}.purpose: invalid")
            if origin == "self-generated-prior-frame" and _text(source_reference):
                prior_match = FRAME_RE.fullmatch(str(source_reference))
                if (
                    not prior_match
                    or int(prior_match.group("id")) >= index
                    or source_reference not in seen_frames
                ):
                    errors.append(f"{ref_prefix}.source_reference: expected a declared earlier deck frame")

        provenance = _dict(scene.get("provenance"))
        source_type = provenance.get("source_type")
        if not isinstance(source_type, str) or source_type not in SOURCE_TYPES:
            errors.append(f"{prefix}.provenance.source_type: invalid")
        if not _text(provenance.get("license_permission")):
            errors.append(f"{prefix}.provenance.license_permission: required")
        if isinstance(source_type, str) and source_type in {"licensed", "mixed"} and not _text(
            provenance.get("source_reference")
        ):
            errors.append(f"{prefix}.provenance.source_reference: required for licensed/mixed")
        if _text(provenance.get("source_reference")) and BROADCAST_REFERENCE_RE.search(
            str(provenance.get("source_reference"))
        ):
            errors.append(f"{prefix}.provenance.source_reference: broadcast/program artwork is forbidden")
        if stage == "render":
            for key in ("tool", "prompt_version", "human_edit"):
                if not _text(provenance.get(key)):
                    errors.append(f"{prefix}.provenance.{key}: required at render stage")

    if stage == "render":
        frames_dir = root / "frames"
        actual = {path.resolve() for path in frames_dir.glob("*.png")} if frames_dir.is_dir() else set()
        extra = sorted(path.name for path in actual - expected_frame_paths)
        if extra:
            errors.append(f"frames: unreferenced PNG files: {', '.join(extra)}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_dir")
    parser.add_argument("--stage", choices=("plan", "render"), default="render")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.deck_dir).expanduser().resolve()
    errors = validate(root, args.stage)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"SUMMARY 0/{len(errors)} errors={len(errors)}")
        return 1
    print(f"PASS stage={args.stage} deck={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
