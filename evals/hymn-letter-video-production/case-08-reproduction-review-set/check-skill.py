#!/usr/bin/env python3
from pathlib import Path


root = Path(__file__).resolve().parents[3]
skill = (root / "skills/hymn-letter-video-production/SKILL.md").read_text(encoding="utf-8")
reference = (
    root / "skills/hymn-letter-video-production/references/recorded-testimony-pair.md"
).read_text(encoding="utf-8")
def contract_block(document: str, heading: str) -> str:
    start = document.find(heading)
    if start < 0:
        return ""
    remainder = document[start + len(heading):]
    next_heading = remainder.find("\n## ")
    block = remainder if next_heading < 0 else remainder[:next_heading]
    return " ".join(block.split())


skill_norm = contract_block(skill, "## Deterministic reproduction review/output contract")
reference_norm = contract_block(reference, "## 결정적 재현 review/output 계약")

skill_required = [
    "deterministic reproduction",
    "renderer workspace",
    "review/output set",
    "two MP4s, two backplates, and two thumbnails",
    "Each episode contributes exactly one MP4, one backplate, and one thumbnail",
    "INCOMPLETE_REVIEW_SET",
    "A backplate that exists only in the input lock, source-object storage, or encoded MP4 raster does not satisfy the separate backplate output role",
    "episode ID, role, target name, size, SHA-256, and authoritative source",
    "exactly six media files as direct children",
    "receipt is a sibling outside that media directory",
    "Do not open or present",
    "new no-overwrite review set",
    "without re-encoding the already verified MP4s",
    "byte-exact",
    "The local six-media review/output set is distinct from and must not be conflated with the seven-role final delivery set",
]
reference_required = [
    "결정적 재현",
    "renderer workspace",
    "review/output set",
    "MP4 2개·영상 배경 2개·썸네일 2개",
    "각 편은 MP4 1개·영상 배경 1개·썸네일 1개",
    "INCOMPLETE_REVIEW_SET",
    "input lock·source object·인코딩된 MP4 raster에만 존재하는 backplate는 별도 영상 배경 output role을 충족하지 않는다",
    "episode ID·role·target name·size·SHA-256·authoritative source",
    "media directory의 direct child는 정확히 6개 media 파일",
    "receipt는 그 밖의 sibling",
    "사용자에게 열거나 완전한 아웃풋으로 보고하지 않는다",
    "새 no-overwrite review set",
    "검증된 MP4를 재인코딩하지 않고 byte-exact",
    "로컬 6-media review/output set은 7-role 최종 delivery set과 구분하며 서로 같은 것으로 간주하지 않는다",
]
skill_forbidden = [
    "appearance in the encoded MP4 satisfies the backplate output role",
    "renderer workspace is a complete review/output set",
    "missing backplates may still be reported as PASS",
    "an incomplete review/output set may be opened",
    "six-media review/output set is the seven-role final delivery set",
]
reference_forbidden = [
    "MP4 raster에 보이면 영상 배경 출력 역할을 충족",
    "renderer workspace를 완전한 review/output set으로 본다",
    "영상 배경이 없어도 PASS",
    "불완전한 review/output set을 사용자에게 열 수 있다",
    "6-media review/output set은 7-role 최종 delivery set이다",
]

missing = [f"SKILL:{item}" for item in skill_required if item not in skill_norm]
missing += [f"reference:{item}" for item in reference_required if item not in reference_norm]
if missing:
    raise SystemExit("missing reproduction review-set controls: " + ", ".join(missing))
forbidden = [f"SKILL:{item}" for item in skill_forbidden if item in skill_norm]
forbidden += [f"reference:{item}" for item in reference_forbidden if item in reference_norm]
if forbidden:
    raise SystemExit("contradictory reproduction review-set controls: " + ", ".join(forbidden))
print("PASS: deterministic reproduction review set requires all six media roles")
