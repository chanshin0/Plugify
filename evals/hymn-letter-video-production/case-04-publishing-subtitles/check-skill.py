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
    "title/body RTF",
]
reference_required = [
    "[부제목]",
    "최소 네 개",
    "승인 대본",
    "앞뒤 개행까지 그대로 복원",
    "부제목까지 정확히 공유",
    "제작·문의 안내",
    "RTF를 다시 평문으로 읽어",
]
missing = [f"SKILL:{item}" for item in skill_required if item not in skill_norm]
missing += [f"reference:{item}" for item in reference_required if item not in reference_norm]
if missing:
    raise SystemExit("missing publishing subtitle controls: " + ", ".join(missing))
print("PASS: publishing subtitle controls are present")
