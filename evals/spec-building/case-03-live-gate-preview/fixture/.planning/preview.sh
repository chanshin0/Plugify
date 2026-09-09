#!/usr/bin/env bash
# (픽스처) 프리뷰 배포 규격 구현 — spec-building 라이브 게이트가 호출하는 지점측 계약.
# "배포" = push 된 origin 원격의 해당 브랜치 내용을 격리 클론해 로컬 HTTP 로 서빙
#          (작업트리가 아니라 **원격 내용** — push 실재를 프리뷰가 구조적으로 강제).
# 규격(SKILL.md 지점 규격): 성공 시 rc=0 + stdout 에 `DEPLOYED_SHA=<40hex>` 한 줄 + 마지막 줄 = ready URL /
#          실패 시 rc≠0 + stderr 사유. **같은 브랜치·같은 원격 SHA 에 대한 재호출은 같은 URL 을 돌려준다**
#          (실제 프로바이더처럼 배포는 커밋에 결속 — 워크플로우가 프로브 URL 과 증거 URL 을 대조한다).
set -euo pipefail
BRANCH="${1:?사용: preview.sh <branch> [timeout_sec]}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORIGIN_URL="$(git -C "$ROOT" remote get-url origin)" || { echo "FAIL: origin 없음" >&2; exit 1; }

REMOTE_SHA="$(git ls-remote "$ORIGIN_URL" "refs/heads/$BRANCH" | cut -f1)"
[ -n "$REMOTE_SHA" ] || { echo "FAIL: 원격에 브랜치 $BRANCH 없음(push 안 됨?)" >&2; exit 1; }

# 배포 레지스트리: (origin, 원격 SHA) → 살아 있는 배포면 재사용 (커밋 결속·URL 안정)
REGISTRY="/tmp/plugify-eval-c03-deploy.registry"; mkdir -p "$REGISTRY"
KEY="$(printf '%s' "$ORIGIN_URL" | shasum -a 256 | cut -c1-12)-$REMOTE_SHA"; REG="$REGISTRY/$KEY"
if [ -f "$REG/url" ] && [ -f "$REG/server.pid" ] && kill -0 "$(cat "$REG/server.pid")" 2>/dev/null \
   && curl -s -o /dev/null "$(cat "$REG/url")/index.html"; then
  echo "DEPLOYED_SHA=$REMOTE_SHA"
  cat "$REG/url"
  exit 0
fi

DEPLOY_DIR="$(mktemp -d /tmp/plugify-eval-c03-deploy.XXXXXX)"
git clone -q --branch "$BRANCH" --depth 1 "$ORIGIN_URL" "$DEPLOY_DIR/checkout" \
  || { echo "FAIL: 원격에 브랜치 $BRANCH 없음(push 안 됨?)" >&2; exit 1; }

PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
( cd "$DEPLOY_DIR/checkout/site" && nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$DEPLOY_DIR/server.pid" )

for _ in $(seq 1 20); do
  curl -s -o /dev/null "http://127.0.0.1:$PORT/index.html" && break
  sleep 0.5
done
curl -s -o /dev/null "http://127.0.0.1:$PORT/index.html" || { echo "FAIL: 프리뷰 서버 미기동" >&2; exit 1; }
mkdir -p "$REG"; echo "http://127.0.0.1:$PORT" > "$REG/url"; cp "$DEPLOY_DIR/server.pid" "$REG/server.pid"
echo "DEPLOYED_SHA=$(git -C "$DEPLOY_DIR/checkout" rev-parse HEAD)"   # 지점 규격: 배포에 결속된 전체 커밋 SHA
echo "http://127.0.0.1:$PORT"
