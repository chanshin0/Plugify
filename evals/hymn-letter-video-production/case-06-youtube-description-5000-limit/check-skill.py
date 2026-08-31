#!/usr/bin/env python3
from pathlib import Path


root = Path(__file__).resolve().parents[3]
skill = (root / "skills/hymn-letter-video-production/SKILL.md").read_text(encoding="utf-8")
reference = (
    root / "skills/hymn-letter-video-production/references/recorded-testimony-pair.md"
).read_text(encoding="utf-8")
skill_norm = " ".join(skill.split())
reference_norm = " ".join(reference.split())

skill_required = [
    "each video's complete YouTube description separately",
    "either exceeds 5,000 characters",
    "testimony count covers the shared body",
    "listening count also includes its production/contact notice",
    "Exclude the video title from the 5,000-character description count",
    "paired TXT's combined file length",
    "copy-instruction marker",
    "Record the 5,000-character maximum and both final per-video counts",
]
reference_required = [
    "영상별 완성 설명을 각각 최대 5,000자",
    "홀수 간증편은 공용 본문 전체",
    "짝수 찬송듣기편은 공용 본문과 전용 제작·문의 안내",
    "영상 제목은 5,000자 본문 계산에서 제외",
    "둘 중 하나라도 넘으면 TXT 생성과 전달을 실패",
    "합본 TXT 전체 길이",
    "복사 안내 마커",
    "중복 해시태그·도입·부제목·안내를 압축",
    "별도 요약 후보를 사람 검토 대상",
    "최대값 5,000과 두 편의 최종 문자 수",
]
skill_forbidden = [
    "paired TXT must be at most 5,000 characters",
    "count the title toward the 5,000-character description limit",
]
reference_forbidden = [
    "합본 TXT 전체를 5,000자 이하",
    "제목을 본문 5,000자에 포함",
]

missing = [f"SKILL:{item}" for item in skill_required if item not in skill_norm]
missing += [f"reference:{item}" for item in reference_required if item not in reference_norm]
if missing:
    raise SystemExit("missing YouTube description limit controls: " + ", ".join(missing))
forbidden = [f"SKILL:{item}" for item in skill_forbidden if item in skill_norm]
forbidden += [f"reference:{item}" for item in reference_forbidden if item in reference_norm]
if forbidden:
    raise SystemExit("stale contradictory description controls remain: " + ", ".join(forbidden))
print("PASS: per-video YouTube descriptions are bounded to 5,000 characters")
