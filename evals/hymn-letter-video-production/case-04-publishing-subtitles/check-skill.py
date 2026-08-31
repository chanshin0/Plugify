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
    "bracketed section",
    "at least four",
    "approved script exactly",
    "leading and trailing line breaks",
    "share the subtitles and body across",
    "production/contact notice only to the listening episode",
    "title/body UTF-8 TXT",
    "do not create or deliver RTF",
    "exactly three blank lines",
    "four newline characters",
]
reference_required = [
    "[부제목]",
    "최소 네 개",
    "승인 대본",
    "앞뒤 개행까지 그대로 복원",
    "부제목까지 정확히 공유",
    "제작·문의 안내",
    "UTF-8 TXT",
    "RTF는 만들거나 전달하지 않는다",
    "빈 줄을 정확히 세 줄",
    "문자 기준 개행 4개",
    "전달 전 TXT를 다시 읽어",
]
skill_forbidden = [
    "include one paired title/body RTF as a required",
    "title/body RTF",
    "one blank line between the preceding body sentence",
    "two newline characters between the preceding body sentence",
]
reference_forbidden = [
    "안내를 한 쌍 RTF로",
    "RTF를 다시 평문으로 읽어",
    "부제목과 바로 앞 본문 문장 사이에는 빈 줄 한 줄",
    "부제목과 바로 앞 본문 문장 사이에는 개행 2개",
]
missing = [f"SKILL:{item}" for item in skill_required if item not in skill_norm]
missing += [f"reference:{item}" for item in reference_required if item not in reference_norm]
if missing:
    raise SystemExit("missing publishing subtitle controls: " + ", ".join(missing))
forbidden = [f"SKILL:{item}" for item in skill_forbidden if item in skill_norm]
forbidden += [f"reference:{item}" for item in reference_forbidden if item in reference_norm]
if forbidden:
    raise SystemExit("stale publishing subtitle controls remain: " + ", ".join(forbidden))
print("PASS: publishing subtitle controls are present")
