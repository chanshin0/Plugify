#!/usr/bin/env bash
set -euo pipefail

case_root="$(cd "$(dirname "$0")" && pwd)"
plugify_root="$(cd "$case_root/../../.." && pwd)"
work_root="$(mktemp -d "${TMPDIR:-/tmp}/hymn-letter-eval.XXXXXX")"

cp -R "$case_root" "$work_root/case"
mkdir -p "$work_root/repo/skills/hymn-letter-video-production/scripts"
if [[ -f "$plugify_root/skills/hymn-letter-video-production/scripts/hymn_video_flow.py" ]]; then
  cp "$plugify_root/skills/hymn-letter-video-production/scripts/hymn_video_flow.py" \
    "$work_root/repo/skills/hymn-letter-video-production/scripts/hymn_video_flow.py"
fi

printf '%s\n' "$work_root"
