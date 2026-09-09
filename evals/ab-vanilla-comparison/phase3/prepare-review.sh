#!/usr/bin/env bash
# 사람 눈 평가 준비 — 한 과제·한 회차의 팔별 스냅샷을 익명화(X/Y/Z)하고 콘솔용 번들을 만든다.
# 사용: bash prepare-review.sh <01|02|03> <run번호> [--arms "plugify claude-vanilla codex-vanilla"]
# 출력: ~/ab-phase3-review/<task>-run<k>/{X,Y,Z}/ + pairs.json + *.bundle.json + SEALED-mapping.json(0600 — 판정 끝날 때까지 열지 않는다)
set -euo pipefail
TASK="${1:?task 01|02|03}"; RUN="${2:?run k}"; shift 2
ARMS="plugify claude-vanilla codex-vanilla"
[ "${1:-}" = "--arms" ] && ARMS="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
TASK_DIR="$(ls -d "$HERE/tasks/$TASK"-* | head -1)"; TASK_KEY="$(basename "$TASK_DIR")"
OUT="$HOME/ab-phase3-review"; ID="$TASK_KEY-run$RUN"
[ -e "$OUT/$ID" ] && { echo "이미 존재: $OUT/$ID (지우고 다시 하라)" >&2; exit 3; }
INS=()
for A in $ARMS; do
  W="$HOME/ab-phase3-runs/$TASK_KEY/$A/run$RUN/work"
  [ -d "$W" ] || { echo "스냅샷 없음: $W" >&2; exit 3; }
  INS+=(--in "$A=$W")
done
[ "${#INS[@]}" -ge 4 ] || { echo "팔이 2개 미만" >&2; exit 3; }
# 팔 고유 흔적 추가 용어(도구 기본 목록 외): 실행 디렉터리명·워커 트레이스·과제 파일명 관례
EXTRA="$(mktemp "${TMPDIR:-/tmp}/extra-terms.XXXXXX")"
printf '%s\n' ab-phase3-runs codex-worker CODEX_EXIT task-orchestrating claude-vanilla codex-vanilla lean-agent-design > "$EXTRA"
python3 "$HERE/tools/anonymize.py" --task "$ID" "${INS[@]}" --out "$OUT" --extra-terms "$EXTRA"
rm -f "$EXTRA"
# 팔이 받은 TASK-SPEC.md 는 공통 입력이라 식별 정보가 아니지만, 익명화가 [TOOL] 로 바꿨을 수 있으니 원본으로 되돌려 둔다(비교 시 참고용)
for L in "$OUT/$ID"/*/; do
  [ -f "$L/TASK-SPEC.md" ] && cp "$TASK_DIR/TASK-SPEC.md" "$L/TASK-SPEC.md"
  python3 "$HERE/tools/bundle.py" "$L" --out "$OUT/$ID/$(basename "$L").bundle.json"
done
# 번들 재생성 후 스냅샷 git 은 anonymize 가 만든 단일 커밋 그대로 둔다(TASK-SPEC 복원은 작업트리 변경으로만 남음 — 평가자가 diff 를 보지 않으므로 무해)
echo
echo "준비 완료: $OUT/$ID"
ls "$OUT/$ID"
echo
echo "다음: tools/review-console.html 을 브라우저(file://)로 열고 pairs.json + *.bundle.json 을 불러온다."
echo "      PREREG §5 의 과제별 10분 대본·엣지케이스·깨기는 각 익명 디렉터리에서 직접 실행한다: cd $OUT/$ID/X 등"
echo "      SEALED-mapping.json 은 판정·재판정이 끝날 때까지 열지 않는다."
