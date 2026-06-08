#!/usr/bin/env bash
#
# plugify install — 정본 스킬/에이전트를 Claude(~/.claude) + Codex(~/.codex) 로 노출
#
# 왜 필요한가:
#   Claude Code 는 ~/.claude/skills/<n>/SKILL.md / ~/.claude/agents/<n>.md 를,
#   Codex 는 ~/.codex/skills/<n>/SKILL.md / ~/.codex/agents/<n>.toml 을 스캔한다.
#   이 레포의 skills/ 가 정본(SSOT)이며, 두 툴 아래로 노출돼야 잡힌다.
#
# 동작:
#   [skills]  skills/<dir>/SKILL.md 마다  <claude|codex>/skills/<dir>  symlink
#             — SKILL.md 는 양쪽 포맷이 같고, Codex 도 스킬 심링크를 따라간다.
#   [agents]  skills/*/agents/*.md (스킬 소유) + agents/*.md (스킬 비종속 독립,
#             예: debugger) — dual-block frontmatter SSOT — 에서 sync-agents.py 가
#             ~/.claude/agents/<n>.md  +  ~/.codex/agents/<n>.toml 을 "생성"한다.
#             (Codex 는 에이전트 심링크를 따라가지 않으므로 실파일 생성;
#             openai/codex#15345. 또 .md↔.toml 포맷이 달라 한 파일 공유 불가.)
#
# 멱등 · no-clobber. 이미 올바른 symlink → skip. 실파일/딴 링크 점유 → 보존하고 WARN.
#
# 사용:
#   bash scripts/install.sh            # 적용
#   bash scripts/install.sh --dry-run  # 무엇을 할지 출력만
#
# ⚠ 적용은 "세션 재시작 후" 실효한다. 특히 agentType 레지스트리는 세션 시작에 고정된다.
#   (SessionStart 훅이 sync-agents.py --ensure 를 호출하도록 wiring 돼 있으면 자동 self-heal)
#
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"

linked=0 skipped=0 warned=0

# 심링크가 가리키는 곳을 절대경로로 해소(상대·절대 모두)
resolve_link() {
  local l="$1" t
  t="$(readlink "$l")"
  case "$t" in
    /*) printf '%s\n' "$t" ;;
    *)  printf '%s/%s\n' "$(cd "$(dirname "$l")" && cd "$(dirname "$t")" && pwd)" "$(basename "$t")" ;;
  esac
}

# $1=target(절대)  $2=base 디렉토리(절대) → target 을 base 기준 상대경로로.
# 상대 링크여야 홈 디렉터리 통째 이동에도 안 깨진다. BSD ln 은 --relative 가 없어 직접 계산.
relpath() {
  local target="$1" common="$2" up=""
  while [ "${target#"$common"/}" = "$target" ] && [ "$common" != "/" ]; do
    common="$(dirname "$common")"; up="../$up"
  done
  [ "$common" = "/" ] && printf '%s\n' "${up}${target#/}" || printf '%s\n' "${up}${target#"$common"/}"
}

# $1=target(절대 실파일/디렉토리)  $2=link(생성할 경로)  $3=label
link_one() {
  local target="$1" link="$2" label="$3"
  if [ -L "$link" ]; then
    if [ "$(resolve_link "$link")" = "$target" ]; then
      echo "  ok    $label"; skipped=$((skipped+1)); return
    fi
    echo "  WARN  $label — 기존 symlink 가 다른 곳을 가리킴: $(readlink "$link") (보존)"; warned=$((warned+1)); return
  fi
  if [ -e "$link" ]; then
    echo "  WARN  $label — 실파일/디렉토리 점유 중(정본 아닐 수 있음, 보존): $link"; warned=$((warned+1)); return
  fi
  local rel; rel="$(relpath "$target" "$(dirname "$link")")"
  if [ "$DRY_RUN" = 1 ]; then
    echo "  +DRY  $label → $rel"; linked=$((linked+1)); return
  fi
  ln -s "$rel" "$link"
  echo "  +     $label → $rel"; linked=$((linked+1))
}

echo "plugify install$([ "$DRY_RUN" = 1 ] && echo ' (--dry-run)')"
echo "  REPO       = $REPO"
echo "  CLAUDE_DIR = $CLAUDE_DIR"
echo "  CODEX_DIR  = $CODEX_DIR"

echo "[skills]  (claude + codex 양쪽 symlink)"
for base in "$CLAUDE_DIR" "$CODEX_DIR"; do
  blabel="$(basename "$base")"
  if [ ! -d "$base" ]; then
    echo "  skip  $blabel — 디렉터리 없음($base), 그 툴 미설치로 간주"; continue
  fi
  dst="$base/skills"
  [ "$DRY_RUN" = 1 ] || mkdir -p "$dst"
  for d in "$REPO"/skills/*/; do
    [ -f "${d}SKILL.md" ] || continue
    name="$(basename "$d")"
    link_one "${d%/}" "$dst/$name" "$blabel/skills/$name"
  done
done

echo "[agents]  (SSOT: skills/*/agents/*.md + agents/*.md → 생성)"
echo "  claude → $CLAUDE_DIR/agents/*.md   codex → $CODEX_DIR/agents/*.toml"
if [ "$DRY_RUN" = 1 ]; then
  echo "  +DRY  python3 scripts/sync-agents.py 를 실행할 예정"
else
  CLAUDE_CONFIG_DIR="$CLAUDE_DIR" CODEX_HOME="$CODEX_DIR" python3 "$SCRIPT_DIR/sync-agents.py"
fi

echo "done. (skills) linked=$linked skipped=$skipped warned=$warned"
[ "$DRY_RUN" = 1 ] && echo "(dry-run — 변경 없음. 실제 적용: bash scripts/install.sh)"
echo "⚠ 세션 재시작 후 실효 (agentType 레지스트리는 세션 시작에 고정)."
