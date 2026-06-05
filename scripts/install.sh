#!/usr/bin/env bash
#
# plugify install — 정본 스킬/에이전트를 ~/.claude 로 symlink (멱등 · no-clobber)
#
# 왜 필요한가:
#   Claude Code 는 세션 시작 시 ~/.claude/skills/<name>/SKILL.md 와
#   ~/.claude/agents/<name>.md 를 스캔해 스킬 트리거 / agentType 으로 등록한다.
#   이 레포의 skills/ 는 정본이지만 ~/.claude 아래로 노출돼야 잡힌다.
#   marketplace.json 의 plugins:[] 가 비어 있어 "plugin install 자동 dereference"
#   경로가 없으므로(README §plugin caching 참고), 그 등록을 이 스크립트가 대신한다.
#
# 동작:
#   - skills/<dir>/SKILL.md 마다  ~/.claude/skills/<dir>      symlink
#   - skills/*/agents/<x>.md (name: frontmatter 보유) 마다  ~/.claude/agents/<x>.md  symlink
#   - 이미 올바른 symlink → skip. 실디렉토리/딴 곳 링크가 점유 중이면 건드리지 않고 WARN.
#
# 사용:
#   bash scripts/install.sh            # 적용
#   bash scripts/install.sh --dry-run  # 무엇을 할지 출력만
#
# ⚠ 적용은 "세션 재시작 후" 실효한다. 특히 agentType 레지스트리는 세션 시작에 고정된다.
#
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILLS_DST="$CLAUDE_DIR/skills"
AGENTS_DST="$CLAUDE_DIR/agents"

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
# 상대 링크여야 ~/.claude 통째 이동에도 안 깨진다. BSD ln 은 --relative 가 없어 직접 계산.
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

echo "plugify install${DRY_RUN:+}$([ "$DRY_RUN" = 1 ] && echo ' (--dry-run)')"
echo "  REPO       = $REPO"
echo "  CLAUDE_DIR = $CLAUDE_DIR"
[ "$DRY_RUN" = 1 ] || mkdir -p "$SKILLS_DST" "$AGENTS_DST"

echo "[skills]"
for d in "$REPO"/skills/*/; do
  [ -f "${d}SKILL.md" ] || continue
  name="$(basename "$d")"
  link_one "${d%/}" "$SKILLS_DST/$name" "skills/$name"
done

echo "[agents]"
for f in "$REPO"/skills/*/agents/*.md; do
  [ -e "$f" ] || continue
  # 진짜 에이전트 정의만(frontmatter 에 name:) — 헬퍼 .md 오등록 방지
  head -10 "$f" | grep -qE '^name:[[:space:]]*\S' || continue
  name="$(basename "$f")"
  link_one "$f" "$AGENTS_DST/$name" "agents/$name"
done

echo "done. linked=$linked skipped=$skipped warned=$warned"
[ "$DRY_RUN" = 1 ] && echo "(dry-run — 변경 없음. 실제 적용: bash scripts/install.sh)"
echo "⚠ 세션 재시작 후 실효 (agentType 레지스트리는 세션 시작에 고정)."
