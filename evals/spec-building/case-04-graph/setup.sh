#!/usr/bin/env bash
# spec-building eval case-04 부트스트랩 — 그래프 실행(★1 Phase D) 픽스처.
# /tmp 격리 사본 + git init + 작업 브랜치(결정적). push 없음(그래프 실행은 로컬 커밋만).
# 사용:
#   bash setup.sh            # 유효 3-task 그래프(T1←T2, T3 독립 = 2 wave), work/graph-run 브랜치 (합격선 ②)
#   bash setup.sh cyclic     # 순환 그래프, work 브랜치 (합격선 ① — 반려)
#   bash setup.sh dangling   # dangling depends, work 브랜치 (합격선 ① — 반려)
#   bash setup.sh livegate   # {PREVIEW_URL} 포함, work 브랜치 (합격선 ④ — v1 범위 밖 반려)
#   bash setup.sh main       # 유효 그래프지만 main 브랜치에 머무름 (합격선 ③ — fail-fast)
# 마지막 줄에 RUN_DIR 출력.
set -euo pipefail
VARIANT="${1:-valid}"
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-specb-c04.XXXXXX)"

cp -R "$CASE_DIR/fixture/." "$RUN_DIR/"
rm -rf "$RUN_DIR/variants"   # 변형 STATE 원본은 작업 레포에 남기지 않는다

case "$VARIANT" in
  valid|main) : ;;  # 기본 .planning/STATE.md (유효 그래프) 사용
  cyclic)   cp "$CASE_DIR/fixture/variants/STATE-cyclic.md"   "$RUN_DIR/.planning/STATE.md" ;;
  dangling) cp "$CASE_DIR/fixture/variants/STATE-dangling.md" "$RUN_DIR/.planning/STATE.md" ;;
  livegate) cp "$CASE_DIR/fixture/variants/STATE-livegate.md" "$RUN_DIR/.planning/STATE.md" ;;
  *) echo "unknown variant: $VARIANT (valid|cyclic|dangling|livegate|main)" >&2; exit 2 ;;
esac

cd "$RUN_DIR"
git init -q -b main
git add -A
git commit -qm "픽스처 초기 상태 (계산 유틸 스텁 3모듈 — 그래프 실행 task)"

# main 변형은 main 브랜치에 머무른다(fail-fast 시험). 그 외는 작업 브랜치로.
if [ "$VARIANT" != "main" ]; then
  git checkout -q -b work/graph-run   # 작업 브랜치 — 그래프 실행 대상(main 아님)
fi

echo "VARIANT=$VARIANT"
echo "BRANCH=$(git branch --show-current)"
echo "RUN_DIR=$RUN_DIR"
