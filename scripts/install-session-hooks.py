#!/usr/bin/env python3
"""Bind Claude/Codex SessionStart workspace hooks to the active Plugify SSOT."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any


MANAGED_SCRIPTS = {
    "sync-agents.py": "agents",
    "workspace-session-start.py": "workspace",
}

# "이 훅 명령이 Plugify 것인가" 판별은 두 갈래다.
#  1) 레거시: 경로에 `plugify`/`.plugify` 폴더명이 있으면 Plugify 훅 — 옛 marketplace clone·`.plugify` 호환 경로를
#     현재 정본으로 교체·중복 제거하기 위한 규칙.
#  2) 현재 checkout: 스크립트 경로가 `--repo-root/scripts/<name>` 과 같은 파일이면 폴더명과 무관하게 Plugify 훅.
#     (2026-09-01: 폴더명이 `Plugify-model-tier` 같은 worktree 에서 자기 훅을 인식 못 해 설치가
#     "internal error" 로 멈췄다. 이 인식은 재실행 멱등성의 근거이므로 절대 경로 일치로 넓힌다.)
# 어느 쪽에도 안 걸리면 사용자 훅으로 보고 손대지 않는다.
LEGACY_PATH_MARKERS = frozenset({"plugify", ".plugify"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Canonical Plugify repository root (default: this script's parent repo).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON, refusing to overwrite {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"expected a JSON object, refusing to overwrite {path}")
    return data


def managed_script(command: object, current_scripts: Path | None = None) -> tuple[str, str] | None:
    if not isinstance(command, str):
        return None
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if len(tokens) >= 2 and Path(tokens[0]).name == "env" and tokens[1] == "python3":
        tokens = tokens[2:]
    elif tokens and Path(tokens[0]).name == "python3":
        tokens = tokens[1:]
    else:
        return None
    if not tokens:
        return None
    script = tokens[0]
    kind = MANAGED_SCRIPTS.get(Path(script).name)
    if kind == "agents" and tokens[1:] != ["--ensure"]:
        return None
    if kind == "workspace" and tokens[1:]:
        return None
    if kind is None:
        return None
    parts = {part.casefold() for part in Path(script).parts}
    if LEGACY_PATH_MARKERS & parts:
        return kind, script
    if current_scripts is not None and _same_path(Path(script), current_scripts / Path(script).name):
        return kind, script
    return None


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.expanduser().resolve() == b.expanduser().resolve()
    except (OSError, RuntimeError):
        return False


def desired_commands(repo_root: Path) -> dict[str, str]:
    scripts = repo_root / "scripts"
    return {
        "workspace": f'/usr/bin/env python3 "{scripts / "workspace-session-start.py"}"',
        "agents": f'/usr/bin/env python3 "{scripts / "sync-agents.py"}" --ensure',
    }


def update_document(
    original: dict[str, Any], desired: dict[str, str], current_scripts: Path | None = None
) -> tuple[dict[str, Any], bool, list[str]]:
    hooks = original.get("hooks")
    if hooks is None:
        hooks = {}
        original["hooks"] = hooks
    if not isinstance(hooks, dict):
        raise SystemExit("expected 'hooks' to be a JSON object; refusing to overwrite")

    groups = hooks.get("SessionStart")
    if groups is None:
        groups = []
    if not isinstance(groups, list):
        raise SystemExit("expected 'hooks.SessionStart' to be a JSON array; refusing to overwrite")

    old_paths: list[str] = []
    kept_groups: list[Any] = []

    for group in groups:
        if not isinstance(group, dict):
            kept_groups.append(group)
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            kept_groups.append(group)
            continue

        kept_handlers: list[Any] = []
        for handler in handlers:
            if not isinstance(handler, dict):
                kept_handlers.append(handler)
                continue
            managed = managed_script(handler.get("command"), current_scripts)
            if managed is None:
                kept_handlers.append(handler)
                continue
            _, old_script = managed
            old_paths.append(old_script)

        if kept_handlers == handlers:
            kept_groups.append(group)
        elif kept_handlers:
            updated_group = dict(group)
            updated_group["hooks"] = kept_handlers
            kept_groups.append(updated_group)
    kept_groups.extend(
        [
            {
                "matcher": "startup|resume",
                "hooks": [
                    {
                        "type": "command",
                        "command": desired["workspace"],
                        "timeout": 180,
                        "statusMessage": "plugify workspace sync",
                    }
                ],
            },
            {
                "matcher": "clear|compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": desired["agents"],
                        "timeout": 60,
                        "statusMessage": "plugify agent sync",
                    }
                ],
            },
        ]
    )
    changed = kept_groups != groups or "SessionStart" not in hooks
    hooks["SessionStart"] = kept_groups
    return original, changed, old_paths


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    mode = path.stat().st_mode if path.exists() else None
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    if mode is not None:
        os.chmod(temp_path, mode)
    os.replace(temp_path, path)


def process(path: Path, desired: dict[str, str], dry_run: bool, current_scripts: Path) -> bool:
    document = load_json(path)
    updated, changed, old_paths = update_document(document, desired, current_scripts)
    if not changed:
        print(f"ok {path}: already bound to current Plugify SSOT")
        return False

    old_label = ", ".join(old_paths) if old_paths else "<missing>"
    new_paths = [managed_script(desired[k], current_scripts) for k in ("workspace", "agents")]
    if any(item is None for item in new_paths):
        # 다음 실행이 자기 훅을 못 알아보면 중복 설치되므로 여기서 멈춘다(정상 경로에선 도달 불가).
        raise SystemExit(
            "internal error: the hook command this installer is about to write would not be recognised "
            f"as a Plugify hook on the next run (repo scripts dir: {current_scripts}); refusing to install"
        )
    new_label = ", ".join(item[1] for item in new_paths if item is not None)
    prefix = "DRY-RUN update" if dry_run else "update"
    print(f"{prefix} {path}: {old_label} -> {new_label}")
    if not dry_run:
        atomic_write_json(path, updated)
    return True


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    for name in ("sync-agents.py", "workspace-session-start.py"):
        script = repo_root / "scripts" / name
        if not script.is_file():
            raise SystemExit(f"Plugify managed hook script not found: {script}")

    home = Path.home()
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")).expanduser()
    codex_dir = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    desired = desired_commands(repo_root)
    current_scripts = repo_root / "scripts"

    process(claude_dir / "settings.json", desired, args.dry_run, current_scripts)
    process(codex_dir / "hooks.json", desired, args.dry_run, current_scripts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
