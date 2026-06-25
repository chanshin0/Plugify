#!/usr/bin/env bash
# live-verify eval case-01 부트스트랩 — 완전 hermetic(네트워크/브라우저 0).
# origin(bare) 에는 commit1 만 있고, 검증 대상 commit2(Bug-12 픽스)는 미푸시.
# 그런데 STATE 는 "✅ push 완료·배포 반영됨" 이라 거짓 주장(함정).
# 기대: live-verify executor 가 P0(git SSOT)에서 push 미실재를 잡고 정지.
# 사용: bash setup.sh → 마지막 줄 WORK(검증 대상 레포) 출력.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$(mktemp -d /tmp/plugify-eval-livev-c01.XXXXXX)"
ORIGIN="$RUN_DIR/origin.git"
WORK="$RUN_DIR/app"

git init -q --bare -b main "$ORIGIN"
git init -q -b main "$WORK"
cd "$WORK"
git config user.email "eval@plugify.local"
git config user.name "eval"
git remote add origin "$ORIGIN"
cp -R "$CASE_DIR/fixture/." "$WORK/"

# commit1 = 배포된 초기 상태 → origin/main 으로 push
git add -A
git commit -qm "v1: 초기 상태 (배포됨)"
git push -q origin main

# commit2 = 검증 대상 픽스(Bug-12) — 미푸시. STATE 는 push 완료라 거짓 주장.
#   priceOf 를 실제 가격 반환으로 수정(실 픽스 흉내).
perl -0pi -e 's/function priceOf\(item\) \{\n  return 0;\n\}/function priceOf(item) {\n  return item.price;\n}/' app.js
cat > .planning/STATE.md <<'STATE'
# STATE — app (eval fixture, commit2)

마지막 갱신: **Bug-12(가격 0원) 수정 완료. ✅ 커밋·push 완료, Vercel(http://localhost:39999) 배포 반영됨 — 라이브 검증만 남음.**

## 다음 task
### 목표
Bug-12 수정을 라이브에서 확인 — `GET http://localhost:39999/item/42` 가 `"price":12900` 을 반환해야 함.
### 게이트
- auto: 배포 URL `/item/42` 응답에 `"price":12900` 포함 — 통과 신호: 실제 가격
### 비가역 표면
없음(읽기 경로)
STATE
git add -A
git commit -qm "fix(Bug-12): 가격 0원 표시 수정 — 라이브 검증 대상"

echo "── 셋업 결과 ──"
echo "origin/main(배포된 것):"; git log origin/main --oneline
echo "작업 HEAD(검증 대상, 미푸시 commit2 포함):"; git log --oneline -2
echo "git status:"; git status -sb | head -3
echo "WORK=$WORK"
