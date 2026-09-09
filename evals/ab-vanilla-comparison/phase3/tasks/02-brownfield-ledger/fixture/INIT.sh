#!/bin/sh
# 반드시 복사한 픽스처 디렉터리에서 실행한다.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -e .git ]; then
    echo "이미 초기화된 저장소입니다" >&2
    exit 2
fi
git init -q -b main && git add -A && git commit -qm "초기 상태"
