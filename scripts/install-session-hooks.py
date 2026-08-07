#!/usr/bin/env python3
"""Bind Claude/Codex SessionStart agent sync hooks to the active Plugify SSOT."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


PYTHON_COMMAND = r"(?:(?:/\S*)?/python3|python3|/usr/bin/env python3)"
SCRIPT_ARGUMENT = r'(?P<script>"[^"]*/scripts/sync-agents\.py"|\S*/scripts/sync-agents\.py)'
MANAGED_COMMAND = re.compile(rf"^{PYTHON_COMMAND}\s+{SCRIPT_ARGUMENT}\s+--ensure$")


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


def managed_script_path(command: object) -> str | None:
    if not isinstance(command, str):
        return None
    match = MANAGED_COMMAND.fullmatch(command)
    if not match:
        return None
    script = match.group("script").strip('"')
    if "plugify" not in {part.casefold() for part in Path(script).parts}:
        return None
    return script


def desired_command(repo_root: Path) -> str:
    script = repo_root / "scripts" / "sync-agents.py"
    return f'/usr/bin/env python3 "{script}" --ensure'


def update_document(
    original: dict[str, Any], desired: str
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

    found = False
    changed = False
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
            old_script = managed_script_path(handler.get("command"))
            if old_script is None:
                kept_handlers.append(handler)
                continue

            old_paths.append(old_script)
            if not found:
                found = True
                updated = dict(handler)
                if updated.get("command") != desired:
                    updated["command"] = desired
                    changed = True
                kept_handlers.append(updated)
            else:
                changed = True

        if kept_handlers:
            if kept_handlers != handlers:
                updated_group = dict(group)
                updated_group["hooks"] = kept_handlers
                kept_groups.append(updated_group)
            else:
                kept_groups.append(group)
        elif handlers:
            changed = True

    if not found:
        kept_groups.append(
            {
                "matcher": "startup|resume|clear|compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": desired,
                        "timeout": 60,
                        "statusMessage": "plugify agent sync",
                    }
                ],
            }
        )
        changed = True

    if kept_groups != groups:
        hooks["SessionStart"] = kept_groups
        changed = True
    elif "SessionStart" not in hooks:
        hooks["SessionStart"] = kept_groups
        changed = True

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


def process(path: Path, desired: str, dry_run: bool) -> bool:
    document = load_json(path)
    updated, changed, old_paths = update_document(document, desired)
    if not changed:
        print(f"ok {path}: already bound to current Plugify SSOT")
        return False

    old_label = ", ".join(old_paths) if old_paths else "<missing>"
    new_script = desired.split('"', 2)[1]
    prefix = "DRY-RUN update" if dry_run else "update"
    print(f"{prefix} {path}: {old_label} -> {new_script}")
    if not dry_run:
        atomic_write_json(path, updated)
    return True


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    sync_script = repo_root / "scripts" / "sync-agents.py"
    if not sync_script.is_file():
        raise SystemExit(f"Plugify sync script not found: {sync_script}")

    home = Path.home()
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")).expanduser()
    codex_dir = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    desired = desired_command(repo_root)

    process(claude_dir / "settings.json", desired, args.dry_run)
    process(codex_dir / "hooks.json", desired, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
