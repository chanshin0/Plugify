#!/usr/bin/env python3
"""Emit Claude (`~/.claude/agents/*.md`) and Codex (`~/.codex/agents/*.toml`)
sub-agent definitions from the shared SSOT.

SSOT sources (both scanned):
  - skills/*/agents/*.md   — agents owned by a skill (spawned by that workflow)
  - agents/*.md            — skill-independent standalone agents (e.g. debugger)

Each SSOT file uses YAML frontmatter with two top-level blocks — `claude:`
and `codex:` — holding tool-specific keys. The shared markdown body after
the frontmatter is emitted as Claude's system prompt body and as Codex's
`developer_instructions` TOML string. The body (the agent's real brain) is
written ONCE; only the per-platform knobs (model / tools vs sandbox_mode)
differ between the two blocks.

Targets are USER-level (not project-level), honoring `CLAUDE_CONFIG_DIR`
and `CODEX_HOME`. Generated files live outside this repo, so they are never
committed — the SSOT is `skills/*/agents/*.md`.

Modes:
  default (`sync`): regenerate every target idempotently.
  `--ensure`:       silent fast-path. If every target file exists as a real
                    file with matching content, exit 0. Otherwise write only
                    diffs. Used by the user-level SessionStart hooks.

Migration safety: if a target path is a SYMLINK (the pre-sync install.sh
linked `~/.claude/agents/<n>.md` → repo SSOT), it is unlinked and replaced
with a real generated file. Writing through the symlink would clobber the
SSOT, so symlinked targets are always treated as a mismatch.

Exits non-zero if any source file fails validation.

Stdlib only. The mini YAML parser is scoped to the agent frontmatter shape
(top-level `claude` / `codex` blocks, 2-space indent, scalar values, inline
flow lists). The TOML emitter is hand-rolled — replace with `tomli_w` if the
codex frontmatter ever grows beyond strings, lists, and developer_instructions.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

SOURCE_GLOBS = ("skills/*/agents/*.md", "agents/*.md")


def _user_dir(env: str, default_name: str) -> Path:
    val = os.environ.get(env)
    base = Path(val).expanduser() if val else Path.home() / default_name
    return base / "agents"


CLAUDE_DIR = _user_dir("CLAUDE_CONFIG_DIR", ".claude")
CODEX_DIR = _user_dir("CODEX_HOME", ".codex")

# Public schemas — used to warn (not fail) on unknown keys, for forward-compat
# with future Claude/Codex additions.
CLAUDE_KEYS = {
    "name", "description", "tools", "disallowedTools", "model",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks",
    "memory", "background", "effort", "isolation", "color", "initialPrompt",
}
CODEX_KEYS = {
    "name", "description", "model", "model_reasoning_effort",
    "sandbox_mode", "mcp_servers", "skills.config", "nickname_candidates",
}

# Stable emission order so diffs stay readable.
CLAUDE_ORDER = (
    "name", "description", "model", "tools", "disallowedTools",
    "permissionMode", "color", "memory", "background", "effort",
    "isolation", "maxTurns", "initialPrompt",
)
CODEX_ORDER = (
    "name", "description", "model", "model_reasoning_effort",
    "sandbox_mode", "nickname_candidates",
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _parse_frontmatter(text: str, source: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text).

    Supported syntax (only what SSOT files use):
      ---
      claude:                 # top-level key — only `claude` / `codex` allowed
        name: value           # 2-space indent, scalar values
        tools: [A, B, C]      # or inline flow list
      codex:
        ...
      ---
      <markdown body>

    Multi-line strings and `#`-bearing values must be quoted.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        sys.exit(f"[sync-agents] {source}: file must start with '---' frontmatter delimiter")
    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        sys.exit(f"[sync-agents] {source}: frontmatter closing '---' not found")
    body = "\n".join(lines[close + 1:]).lstrip("\n")

    fm: dict[str, dict] = {}
    current: str | None = None
    for raw in lines[1:close]:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            if not stripped.endswith(":"):
                sys.exit(f"[sync-agents] {source}: top-level line must be 'claude:' or 'codex:', got: {raw!r}")
            key = stripped[:-1].strip()
            if key not in {"claude", "codex"}:
                sys.exit(f"[sync-agents] {source}: unknown top-level key {key!r} — only 'claude' / 'codex' allowed")
            current = key
            fm.setdefault(key, {})
            continue

        if indent != 2:
            sys.exit(f"[sync-agents] {source}: expected 2-space indent under block, got {indent}: {raw!r}")
        if current is None:
            sys.exit(f"[sync-agents] {source}: indented line before any top-level block: {raw!r}")
        if ":" not in stripped:
            sys.exit(f"[sync-agents] {source}: missing ':' in block line: {raw!r}")
        k, _, v = stripped.partition(":")
        fm[current][k.strip()] = _parse_value(v.strip())

    return fm, body


def _parse_value(s: str):
    """Parse a YAML scalar: inline flow list, quoted string, or bare scalar."""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(item.strip()) for item in inner.split(",")]
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def _emit_claude(block: dict, body: str) -> str:
    lines = ["---"]
    seen: set[str] = set()
    for key in CLAUDE_ORDER:
        if key in block:
            lines.append(_yaml_kv(key, block[key]))
            seen.add(key)
    for key, val in block.items():
        if key not in seen:
            lines.append(_yaml_kv(key, val))
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def _yaml_kv(key: str, val) -> str:
    if isinstance(val, list):
        # Claude's `tools` / `disallowedTools` spec uses a comma-separated
        # string (e.g. `tools: Read, Glob, Grep`), not a YAML list.
        if key in ("tools", "disallowedTools"):
            return f"{key}: {', '.join(str(v) for v in val)}"
        return f"{key}: [{', '.join(str(v) for v in val)}]"
    return f"{key}: {val}"


def _emit_codex(block: dict, body: str, source: Path) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for key in CODEX_ORDER:
        if key in block:
            lines.append(_toml_kv(key, block[key]))
            seen.add(key)
    for key, val in block.items():
        if key in seen or key == "developer_instructions":
            continue
        lines.append(_toml_kv(key, val))

    if '"""' in body:
        sys.exit(f'[sync-agents] {source}: body contains \'"""\' which would break the TOML triple-quoted string')
    # Inside a TOML basic multi-line string, backslash is an escape char. The
    # body is markdown prose, so escape any literal backslash to keep the TOML
    # valid (and round-trip identical). No-op for backslash-free bodies.
    safe_body = body.rstrip().replace("\\", "\\\\")
    lines.append('developer_instructions = """')
    lines.append(safe_body)
    lines.append('"""')
    return "\n".join(lines) + "\n"


def _toml_kv(key: str, val) -> str:
    if isinstance(val, list):
        items = [f'"{_toml_escape(str(v))}"' for v in val]
        return f"{key} = [{', '.join(items)}]"
    return f'{key} = "{_toml_escape(str(val))}"'


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def load_agents() -> list[dict]:
    seen_paths: set[Path] = set()
    sources: list[Path] = []
    for glob in SOURCE_GLOBS:
        for p in sorted(REPO.glob(glob)):
            if p not in seen_paths:
                seen_paths.add(p)
                sources.append(p)
    if not sources:
        sys.exit(f"[sync-agents] no agent files match any of {SOURCE_GLOBS} under {REPO}")
    seen_stems: dict[str, Path] = {}
    out = []
    for path in sources:
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text, path)
        if not fm:
            sys.exit(f"[sync-agents] {path}: frontmatter must contain at least one of 'claude:' / 'codex:'")
        if not body.strip():
            sys.exit(f"[sync-agents] {path}: body (system prompt) is empty")
        stem = path.stem
        if stem in seen_stems:
            sys.exit(f"[sync-agents] duplicate agent stem {stem!r}: {path} and {seen_stems[stem]} would collide")
        seen_stems[stem] = path
        for tool in ("claude", "codex"):
            block = fm.get(tool)
            if block is None:
                continue
            if "name" not in block or "description" not in block:
                sys.exit(f"[sync-agents] {path}: {tool} block missing 'name' or 'description'")
            if block["name"] != stem:
                sys.exit(
                    f"[sync-agents] {path}: {tool}.name ({block['name']!r}) "
                    f"must match filename stem ({stem!r})"
                )
            allowed = CLAUDE_KEYS if tool == "claude" else CODEX_KEYS
            for k in block:
                if k not in allowed:
                    _log(f"[warn] {path}: {tool}.{k} is not in the known {tool} key set")
        out.append({"stem": stem, "fm": fm, "body": body, "source": path})
    return out


def _matches(dest: Path, content: str) -> bool:
    # A symlinked target is a leftover from the old symlink-based install.
    # Treat it as a mismatch so it gets replaced by a real file (and reading
    # through it would just read the SSOT, masking real drift).
    if dest.is_symlink():
        return False
    return dest.is_file() and dest.read_text(encoding="utf-8") == content


def _write(dest: Path, content: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Never write THROUGH a symlink — that clobbers the SSOT it points to.
    if dest.is_symlink():
        dest.unlink()
    dest.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="Silent fast-path: exit 0 if all targets already match. Otherwise emit only the diffs.",
    )
    args = parser.parse_args()

    agents = load_agents()
    if not agents:
        sys.exit(f"[sync-agents] no agent files under {REPO}/{SOURCE_GLOB}")

    emissions: list[tuple[Path, str]] = []
    for a in agents:
        if "claude" in a["fm"]:
            content = _emit_claude(a["fm"]["claude"], a["body"])
            emissions.append((CLAUDE_DIR / f"{a['stem']}.md", content))
        if "codex" in a["fm"]:
            content = _emit_codex(a["fm"]["codex"], a["body"], a["source"])
            emissions.append((CODEX_DIR / f"{a['stem']}.toml", content))

    if args.ensure:
        if all(_matches(dest, content) for dest, content in emissions):
            return 0

    written: list[str] = []
    skipped = 0
    for dest, content in emissions:
        if _matches(dest, content):
            skipped += 1
            continue
        _write(dest, content)
        written.append(str(dest))

    _log("[sync-agents] ==== summary ====")
    _log(f"  claude → {CLAUDE_DIR}")
    _log(f"  codex  → {CODEX_DIR}")
    _log(f"  written: {len(written)}  unchanged: {skipped}")
    for w in written:
        _log(f"    + {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
