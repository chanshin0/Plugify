#!/usr/bin/env bash
set -euo pipefail

case_root="$(cd "$(dirname "$0")" && pwd)"
plugify_root="$(cd "$case_root/../../.." && pwd)"
run_root="$(mktemp -d "${TMPDIR:-/tmp}/hymn-upload-aac-eval.XXXXXX")"

mkdir -p "$run_root/repo/skills"
cp -R "$case_root" "$run_root/case"
cp -R "$plugify_root/skills/hymn-letter-video-production" \
  "$run_root/repo/skills/hymn-letter-video-production"

git -C "$run_root/repo" init -q -b main
git -C "$run_root/repo" config user.email "eval@plugify.local"
git -C "$run_root/repo" config user.name "Plugify Eval"
git -C "$run_root/repo" add -A
git -C "$run_root/repo" commit -qm "fixture: pre-fix hymn production snapshot"

printf '%s\n' "$run_root"
