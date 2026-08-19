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


def managed_script(command: object) -> tuple[str, str] | None:
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
    if not ({"plugify", ".plugify"} & parts):
        return None
    return kind, script


def desired_commands(repo_root: Path) -> dict[str, str]:
    scripts = repo_root / "scripts"
    return {
        "workspace": f'/usr/bin/env python3 "{scripts / "workspace-session-start.py"}"',
        "agents": f'/usr/bin/env python3 "{scripts / "sync-agents.py"}" --ensure',
    }


def update_document(
    original: dict[str, Any], desired: dict[str, str]
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
            managed = managed_script(handler.get("command"))
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


def process(path: Path, desired: dict[str, str], dry_run: bool) -> bool:
    document = load_json(path)
    updated, changed, old_paths = update_document(document, desired)
    if not changed:
        print(f"ok {path}: already bound to current Plugify SSOT")
        return False

    old_label = ", ".join(old_paths) if old_paths else "<missing>"
    new_paths = [managed_script(desired[k]) for k in ("workspace", "agents")]
    if any(item is None for item in new_paths):
        raise SystemExit("internal error: desired managed hook command is invalid")
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

    process(claude_dir / "settings.json", desired, args.dry_run)
    process(codex_dir / "hooks.json", desired, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
