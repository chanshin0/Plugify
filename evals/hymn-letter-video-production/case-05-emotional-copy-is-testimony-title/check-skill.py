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
    "selected shared emotional copy is also the testimony episode's title hook",
    "join its locked thumbnail lines with one space immediately after the series name",
    "Do not invent a separate paraphrase",
    "listening episode's established song-title-led format",
    "generator must fail when the selected emotional copy and testimony title do not match",
]
reference_required = [
    "공용 감성문구는 홀수 간증편 게시 제목의 핵심 문구",
    "잠긴 1행·2행을 공백 하나로 이어 시리즈명 바로 뒤에 그대로",
    "별도의 유사 문구나 요약 제목을 만들지 않는다",
    "짝수 찬송듣기편 제목은 곡명 중심의 기존 형식",
    "관계가 다르면 실패",
]
skill_forbidden = [
    "testimony title may use a separate paraphrase",
    "do not repeat the emotional copy in the testimony title",
]
reference_forbidden = [
    "간증편 제목은 별도의 유사 문구",
    "간증편 제목에 감성문구를 반복하지 않는다",
]
missing = [f"SKILL:{item}" for item in skill_required if item not in skill_norm]
missing += [f"reference:{item}" for item in reference_required if item not in reference_norm]
if missing:
    raise SystemExit("missing emotional-copy title controls: " + ", ".join(missing))
forbidden = [f"SKILL:{item}" for item in skill_forbidden if item in skill_norm]
forbidden += [f"reference:{item}" for item in reference_forbidden if item in reference_norm]
if forbidden:
    raise SystemExit("stale contradictory title controls remain: " + ", ".join(forbidden))
print("PASS: selected emotional copy is bound to the testimony title")
