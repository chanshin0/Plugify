#!/usr/bin/env python3
"""Validate a service-planning persistent project context package."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FILES = {
    "README.md",
    "STATUS.md",
    "기획서.md",
    "gaps.md",
    "DELIVERY-REPORT.md",
}
LEGACY_FILES = {
    "BUSINESS-CAPABILITY-MAP.md",
    "PROCESS-CATALOG.md",
    "M0A-DISCOVERY-GUIDE.md",
}
PROMPTS = {
    "00-ORCHESTRATOR.md",
    "10-BUSINESS-DISCOVERY.md",
    "20-SOURCE-CARTOGRAPHER.md",
    "30-WORKFLOW-MODELER.md",
    "40-DATA-ARCHITECT.md",
    "50-PORTAL-PLANNER.md",
    "60-MIGRATION-PLANNER.md",
    "70-SECURITY-AI-REVIEWER.md",
    "90-COMPLETENESS-CRITIC.md",
}
PROMPT_HEADINGS = (
    "## 역할",
    "## 필수 읽기",
    "## 호출 입력",
    "## 수행",
    "## 안전·금지 경계",
    "## 산출물",
    "## 완료 검증",
    "## 중단·질문 조건",
)
PROMPT_TOKENS = ("TASK", "TARGETS", "OUTPUT", "EVIDENCE", "APPROVALS")
REPORT_HEADINGS = (
    "## 결과와 현재 gate",
    "## 사실·가정·미확인",
    "## 핵심 결정과 중단선",
    "## 검증",
    "## 실제 디렉터리 구조",
    "## 재진입 경로",
    "## 다음 gate",
    "## 유보·승인 필요",
)
PROFILES = {"persistent-context", "legacy-modernization"}


def without_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def fence_opening(line: str) -> tuple[str, int] | None:
    """Return CommonMark fence character and run length for an opening line."""
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3:
        return None
    stripped = line[indent:]
    match = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
    if not match:
        return None
    run, info = match.groups()
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


def fence_closes(line: str, opening: tuple[str, int]) -> bool:
    """A closing run uses the same character, is long enough, and has no text."""
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3:
        return False
    character, length = opening
    return bool(
        re.fullmatch(rf"{re.escape(character)}{{{length},}}[ \t]*", line[indent:])
    )


def contains_raw_html_block(text: str) -> bool:
    """Contract structure must use Markdown, not raw HTML block containers."""
    visible_comments_removed = without_html_comments(text)
    return bool(
        re.search(
            r"(?mi)^[ \t]{0,3}<(?!!--)(?:/?[A-Za-z]|[!?])",
            visible_comments_removed,
        )
    )


def visible_markdown(text: str) -> str:
    """Remove fenced examples and HTML comments before semantic structure checks."""
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    for line in without_html_comments(text).splitlines():
        if fence:
            if fence_closes(line, fence):
                fence = None
            continue
        opening = fence_opening(line)
        if opening:
            fence = opening
            continue
        visible.append(line)
    return "\n".join(visible)


def markdown_sections(
    text: str, headings: tuple[str, ...], label: str, errors: list[str]
) -> dict[str, str]:
    visible = visible_markdown(text)
    matches: dict[str, re.Match[str]] = {}
    for heading in headings:
        found = list(re.finditer(rf"(?m)^{re.escape(heading)}\s*$", visible))
        if len(found) != 1:
            errors.append(f"{label} heading count differs: {heading} -> {len(found)}")
        else:
            matches[heading] = found[0]
    if len(matches) != len(headings):
        return {}
    positions = [matches[heading].start() for heading in headings]
    if positions != sorted(positions):
        errors.append(f"{label} heading order differs")
        return {}
    sections: dict[str, str] = {}
    for index, heading in enumerate(headings):
        start = matches[heading].end()
        end = matches[headings[index + 1]].start() if index + 1 < len(headings) else len(visible)
        sections[heading] = visible[start:end].strip()
    return sections


def text_fence_after_heading(text: str, heading: str) -> str | None:
    """Return a visible ```text block immediately following a visible heading."""
    lines = without_html_comments(text).splitlines()
    fence: tuple[str, int] | None = None
    heading_line: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if fence:
            if fence_closes(line, fence):
                fence = None
            continue
        opening = fence_opening(line)
        if opening:
            fence = opening
            continue
        if stripped == heading:
            heading_line = index
            break
    if heading_line is None:
        return None
    index = heading_line + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if (
        index >= len(lines)
        or lines[index].strip() != "```text"
        or fence_opening(lines[index]) != ("`", 3)
    ):
        return None
    content: list[str] = []
    for line in lines[index + 1 :]:
        if fence_closes(line, ("`", 3)):
            return "\n".join(content)
        content.append(line)
    return None


def declared_profiles(package: Path) -> list[str]:
    report = package / "DELIVERY-REPORT.md"
    if not report.is_file():
        return []
    profiles: list[str] = []
    visible = visible_markdown(report.read_text(encoding="utf-8"))
    for line in visible.splitlines():
        if line.lstrip().startswith(">"):
            profiles.extend(re.findall(r"\bprofile:\s*([A-Za-z0-9_-]+)", line))
    return profiles


def parse_tree(
    block: str, expected_root: str, errors: list[str]
) -> tuple[set[str], set[str]]:
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if not lines or lines[0] != f"{expected_root}/":
        errors.append("actual tree root does not match package directory name")
        return set(), set()
    directories: list[str] = []
    files: set[str] = set()
    reported_directories: set[str] = set()
    for line in lines[1:]:
        match = re.match(r"^((?:│   |    )*)(?:├── |└── )(.+)$", line)
        if not match:
            errors.append(f"invalid actual-tree line: {line}")
            continue
        depth = len(match.group(1)) // 4
        name = match.group(2)
        segment = name[:-1] if name.endswith("/") else name
        if not segment or segment in {".", ".."} or "/" in segment or "\\" in segment:
            errors.append(f"invalid actual-tree path segment: {name}")
            continue
        if depth > len(directories):
            errors.append(f"actual-tree depth jumps without directory node: {line}")
            continue
        if name.endswith("/"):
            directories = directories[:depth]
            directory_path = "/".join([*directories, segment])
            if directory_path in reported_directories:
                errors.append(f"duplicate actual-tree directory: {directory_path}")
            reported_directories.add(directory_path)
            directories.append(segment)
        else:
            file_path = "/".join([*directories[:depth], segment])
            if file_path in files:
                errors.append(f"duplicate actual-tree file: {file_path}")
            files.add(file_path)
    return files, reported_directories


def validate(package: Path, legacy: bool) -> list[str]:
    errors: list[str] = []
    if not package.is_dir():
        return [f"package directory missing: {package}"]
    package = package.resolve()
    profiles = declared_profiles(package)
    if len(profiles) != 1:
        errors.append(
            "DELIVERY-REPORT profile declaration count differs: "
            f"expected=1, actual={len(profiles)}"
        )
    profile = profiles[0] if len(profiles) == 1 and profiles[0] in PROFILES else None
    if len(profiles) == 1 and profiles[0] not in PROFILES:
        errors.append("DELIVERY-REPORT profile declaration missing or invalid")
    if legacy and profile != "legacy-modernization":
        errors.append("--legacy-modernization conflicts with DELIVERY-REPORT profile")
    effective_legacy = legacy or "legacy-modernization" in profiles

    required = set(REQUIRED_FILES)
    if effective_legacy:
        required |= LEGACY_FILES
    for relative in sorted(required):
        path = package / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"required file missing or empty: {relative}")

    prompt_dir = package / "prompts"
    actual_prompts = (
        {path.name for path in prompt_dir.iterdir() if path.is_file()}
        if prompt_dir.is_dir()
        else set()
    )
    if actual_prompts != PROMPTS:
        errors.append(
            "prompt set differs: "
            f"missing={sorted(PROMPTS - actual_prompts)}, "
            f"extra={sorted(actual_prompts - PROMPTS)}"
        )
    if prompt_dir.is_dir():
        extra_directories = sorted(path.name for path in prompt_dir.iterdir() if path.is_dir())
        if extra_directories:
            errors.append(f"prompt directories are not allowed: {extra_directories}")
    for name in sorted(PROMPTS & actual_prompts):
        path = prompt_dir / name
        if path.is_symlink():
            errors.append(f"prompt must be a regular file, not symlink: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        if contains_raw_html_block(text):
            errors.append(f"raw HTML block is not allowed: {name}")
        if not text.strip():
            errors.append(f"prompt is empty: {name}")
        sections = markdown_sections(text, PROMPT_HEADINGS, name, errors)
        for heading, content in sections.items():
            if len(content) < 20:
                errors.append(f"prompt section too thin: {name} -> {heading}")
        for token in PROMPT_TOKENS:
            if token not in sections.get("## 호출 입력", ""):
                errors.append(f"prompt input token missing: {name} -> {token}")

    orchestrator = prompt_dir / "00-ORCHESTRATOR.md"
    if orchestrator.is_file():
        text = orchestrator.read_text(encoding="utf-8")
        sections = markdown_sections(text, PROMPT_HEADINGS, orchestrator.name, [])
        routing = sections.get("## 수행", "")
        for name in sorted(PROMPTS - {orchestrator.name}):
            if name not in routing:
                errors.append(f"orchestrator route missing: {name}")

    report = package / "DELIVERY-REPORT.md"
    if report.is_file():
        text = report.read_text(encoding="utf-8")
        if contains_raw_html_block(text):
            errors.append("raw HTML block is not allowed: DELIVERY-REPORT.md")
        markdown_sections(text, REPORT_HEADINGS, "DELIVERY-REPORT", errors)
        tree_block = text_fence_after_heading(text, "## 실제 디렉터리 구조")
        if tree_block is None:
            errors.append("DELIVERY-REPORT actual-tree text block missing")
        else:
            reported, reported_directories = parse_tree(
                tree_block, package.name, errors
            )
            actual = {
                path.relative_to(package).as_posix()
                for path in package.rglob("*")
                if path.is_file()
            }
            actual_directories = {
                path.relative_to(package).as_posix()
                for path in package.rglob("*")
                if path.is_dir()
            }
            if reported != actual:
                errors.append(
                    "DELIVERY-REPORT tree differs: "
                    f"missing={sorted(actual - reported)}, "
                    f"extra={sorted(reported - actual)}"
                )
            if reported_directories != actual_directories:
                errors.append(
                    "DELIVERY-REPORT directories differ: "
                    f"missing={sorted(actual_directories - reported_directories)}, "
                    f"extra={sorted(reported_directories - actual_directories)}"
                )
    symlinks = sorted(
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_symlink()
    )
    if symlinks:
        errors.append(f"package symlinks are not allowed: {symlinks}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-modernization", action="store_true")
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    errors = validate(args.package, args.legacy_modernization)
    profiles = declared_profiles(args.package.resolve())
    profile = profiles[0] if len(profiles) == 1 else "invalid"
    print(f"profile={profile}")
    print(f"validation_errors={len(errors)}")
    for error in errors:
        print(f"- {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
