#!/usr/bin/env bash
set -euo pipefail

case_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="$(mktemp -d /tmp/illustrated-story-slides-case01.XXXXXX)"

cp -R "$case_dir/fixture/." "$target/"
git -C "$target" init --quiet
git -C "$target" add .
git -C "$target" \
  -c user.name="Plugify Eval" \
  -c user.email="eval@localhost" \
  commit --quiet -m "평가 픽스처 초기화"

printf '%s\n' "$target"
