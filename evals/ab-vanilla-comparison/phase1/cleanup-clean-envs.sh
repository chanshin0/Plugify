#!/usr/bin/env bash
# 실험용 임시 설정 디렉토리(자격증명 사본 포함)와 픽스처 RUN_DIR 들을 지운다.
set -uo pipefail
[ -f /tmp/ab-clean-envs.env ] && source /tmp/ab-clean-envs.env
for d in "${CLEAN_CLAUDE_CFG:-}" "${CLEAN_CODEX_HOME:-}"; do [ -n "$d" ] && [ -d "$d" ] && rm -rf "$d" && echo "removed $d"; done
rm -f /tmp/ab-clean-envs.env /tmp/claude-clean-cfg.*/.credentials.json
rm -rf /tmp/claude-clean-cfg.* /tmp/codex-clean-home.* /tmp/codex-smoke* 2>/dev/null
for pid in /tmp/plugify-eval-c03-deploy.*/server.pid; do [ -f "$pid" ] && kill "$(cat "$pid")" 2>/dev/null; done
rm -rf /tmp/plugify-eval-* /tmp/spec-building.target /tmp/tech-deciding.target 2>/dev/null
echo "cleanup done"