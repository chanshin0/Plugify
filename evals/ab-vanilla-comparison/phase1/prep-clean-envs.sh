#!/usr/bin/env bash
# "기본(vanilla)" 팔용 깨끗한 설정 디렉토리 2개를 만든다 — 자격증명만 복사, 스킬·플러그인·CLAUDE.md·훅·에이전트 0.
#   Claude Code: CLAUDE_CONFIG_DIR=<tmp> (+ keychain 의 OAuth 자격증명을 .credentials.json 으로)
#   Codex:       CODEX_HOME=<tmp> (+ auth.json 만)
# 출력: /tmp/ab-clean-envs.env (source 해서 사용). 실험 후 cleanup-clean-envs.sh 로 삭제.
set -euo pipefail
umask 077
CFG="$(mktemp -d /tmp/ab-claude-clean.XXXXXX)"
CH="$(mktemp -d /tmp/ab-codex-clean.XXXXXX)"
security find-generic-password -s "Claude Code-credentials" -w > "$CFG/.credentials.json"
cp ~/.codex/auth.json "$CH/auth.json"
cat > /tmp/ab-clean-envs.env <<EOF
export CLEAN_CLAUDE_CFG="$CFG"
export CLEAN_CODEX_HOME="$CH"
EOF
echo "CLEAN_CLAUDE_CFG=$CFG"; echo "CLEAN_CODEX_HOME=$CH"
echo "(자격증명 파일만 존재 — 스킬/플러그인/CLAUDE.md/훅/에이전트 없음)"