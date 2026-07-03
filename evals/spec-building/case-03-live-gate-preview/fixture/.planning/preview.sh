#!/usr/bin/env bash
# (픽스처) 프리뷰 배포 규격 구현 — spec-building 라이브 게이트가 호출하는 지점측 계약.
# "배포" = push 된 origin 원격의 해당 브랜치 내용을 격리 클론해 로컬 HTTP 로 서빙
#          (작업트리가 아니라 **원격 내용** — push 실재를 프리뷰가 구조적으로 강제).
# 규격: 성공 시 rc=0 + stdout 마지막 줄 = ready URL / 실패 시 rc≠0 + stderr 사유.
set -euo pipefail
BRANCH="${1:?사용: preview.sh <branch> [timeout_sec]}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORIGIN_URL="$(git -C "$ROOT" remote get-url origin)" || { echo "FAIL: origin 없음" >&2; exit 1; }

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
echo "http://127.0.0.1:$PORT"
