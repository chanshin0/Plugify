"""cc-plugify CLI — Claude Code marketplace bootstrapper.

Writes extraKnownMarketplaces (always) and enabledPlugins (for `install`
subcommand) to .claude/settings.json so Claude Code picks up the marketplace
+ plugins automatically on next start.

Mirrors bootstrap/cli.mjs behavior (Node.js variant). Keep the two in sync.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MARKETPLACE_KEY = "plugify"
MARKETPLACE_REPO = "chanshin0/Plugify"

# ANSI color helpers (degrade gracefully when piped).
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


RESET = _c("\x1b[0m")
BOLD = _c("\x1b[1m")
DIM = _c("\x1b[2m")
GREEN = _c("\x1b[32m")
YELLOW = _c("\x1b[33m")
CYAN = _c("\x1b[36m")
RED = _c("\x1b[31m")


def log(msg: str = "") -> None:
    sys.stdout.write(msg + "\n")


def fail(msg: str) -> None:
    sys.stderr.write(f"{RED}✗{RESET} {msg}\n")
    sys.exit(1)


def parse_args(argv: list[str]) -> dict:
    args = {"global": False, "help": False, "uninstall": False, "install": None}
    rest = argv[1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ("--global", "-g"):
            args["global"] = True
        elif a in ("--help", "-h"):
            args["help"] = True
        elif a == "--uninstall":
            args["uninstall"] = True
        elif a == "install":
            nxt = rest[i + 1] if i + 1 < len(rest) else None
            if not nxt or nxt.startswith("-"):
                fail("'install' requires a plugin name. Example: uvx cc-plugify install <plugin>")
            args["install"] = nxt
            i += 1
        else:
            fail(f"Unknown argument: {a}")
        i += 1
    return args


def print_help() -> None:
    log(f"{BOLD}cc-plugify{RESET} — Claude Code marketplace bootstrapper")
    log("")
    log(f"{BOLD}Usage{RESET}")
    log(f"  uvx cc-plugify                          {DIM}# register marketplace only (project scope){RESET}")
    log(f"  uvx cc-plugify install <plugin>         {DIM}# register + enable a plugin{RESET}")
    log(f"  uvx cc-plugify install <plugin> -g      {DIM}# user-global scope{RESET}")
    log(f"  uvx cc-plugify --uninstall              {DIM}# remove marketplace entry{RESET}")
    log(f"  uvx cc-plugify --help")
    log("")
    log(f"{BOLD}Project mode{RESET} {DIM}(default){RESET}")
    log("  Writes to <cwd>/.claude/settings.json — commit it to share.")
    log("")
    log(f"{BOLD}Global mode{RESET}")
    log("  Writes to ~/.claude/settings.json — applies to all projects on this machine.")
    log("")
    log(f"{BOLD}Examples{RESET}")
    log(f"  {CYAN}uvx cc-plugify install <plugin>{RESET}        {DIM}# project: register + enable <plugin>{RESET}")
    log(f"  {CYAN}uvx cc-plugify install <plugin> -g{RESET}     {DIM}# global: same, for all projects{RESET}")
    log("")
    log(f"{BOLD}Available plugins{RESET} {DIM}(see https://github.com/{MARKETPLACE_REPO}){RESET}")
    log(f"  {DIM}(현재 번들 없음 — marketplace.json plugins 배열 참고){RESET}")


def read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"Failed to parse {path}: {e}")
        return {}  # unreachable


def write_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_marketplace(settings: dict) -> tuple[dict, bool]:
    raw = settings.get("extraKnownMarketplaces")
    existing = dict(raw) if isinstance(raw, dict) else {}

    current = existing.get(MARKETPLACE_KEY)
    desired = {"source": {"source": "github", "repo": MARKETPLACE_REPO}}

    already_correct = (
        isinstance(current, dict)
        and isinstance(current.get("source"), dict)
        and current["source"].get("source") == desired["source"]["source"]
        and current["source"].get("repo") == desired["source"]["repo"]
    )
    if already_correct:
        return settings, False

    existing[MARKETPLACE_KEY] = desired
    return {**settings, "extraKnownMarketplaces": existing}, True


def merge_plugin(settings: dict, plugin_name: str) -> tuple[dict, bool, str]:
    key = f"{plugin_name}@{MARKETPLACE_KEY}"
    raw = settings.get("enabledPlugins")
    existing = dict(raw) if isinstance(raw, dict) else {}

    if existing.get(key) is True:
        return settings, False, key

    existing[key] = True
    return {**settings, "enabledPlugins": existing}, True, key


def unmerge_marketplace(settings: dict) -> tuple[dict, bool]:
    raw = settings.get("extraKnownMarketplaces")
    if not isinstance(raw, dict) or MARKETPLACE_KEY not in raw:
        return settings, False

    existing = {k: v for k, v in raw.items() if k != MARKETPLACE_KEY}
    new_settings = dict(settings)
    if existing:
        new_settings["extraKnownMarketplaces"] = existing
    else:
        new_settings.pop("extraKnownMarketplaces", None)
    return new_settings, True


def resolve_settings_path(use_global: bool) -> Path:
    if use_global:
        return Path.home() / ".claude" / "settings.json"
    return Path.cwd() / ".claude" / "settings.json"


def _canonical(p: Path) -> Path:
    try:
        return p.resolve(strict=False)
    except Exception:
        return p


def guard_project_mode(use_global: bool) -> None:
    if use_global:
        return
    if _canonical(Path.cwd()) == _canonical(Path.home()):
        fail(
            f"cwd is your home directory ({Path.home()}).\n"
            "  Project mode would write to ~/.claude/settings.json — same as --global.\n"
            "  → cd into a project first, or pass --global if that's what you want."
        )


def main() -> None:
    args = parse_args(sys.argv)
    if args["help"]:
        print_help()
        return

    if sys.version_info < (3, 9):
        fail(f"Python 3.9+ required. Current: {sys.version.split()[0]}")

    guard_project_mode(args["global"])

    settings_path = resolve_settings_path(args["global"])
    scope_label = "user-global" if args["global"] else "project"

    if args["uninstall"]:
        mode_label = "uninstall"
    elif args["install"]:
        mode_label = f"install {args['install']}"
    else:
        mode_label = "register marketplace"

    log(f"{BOLD}cc-plugify {mode_label}{RESET} {DIM}({scope_label} scope){RESET}")
    log(f"{DIM}Target: {settings_path}{RESET}\n")

    current = read_settings(settings_path)

    if args["uninstall"]:
        settings, removed = unmerge_marketplace(current)
        if removed:
            write_settings(settings_path, settings)
            log(f'{GREEN}✓{RESET} Removed "{MARKETPLACE_KEY}" from extraKnownMarketplaces')
        else:
            log(f'{YELLOW}•{RESET} "{MARKETPLACE_KEY}" not registered — nothing to do')
        log("")
        log(f"{BOLD}Cleanup complete.{RESET} {DIM}To also remove installed plugins:{RESET}")
        log(f"  {CYAN}claude plugin uninstall <plugin>@{MARKETPLACE_KEY}{RESET}")
        return

    # Step 1: marketplace
    next_settings, added_mp = merge_marketplace(current)
    if added_mp:
        log(f'{GREEN}✓{RESET} Registered "{MARKETPLACE_KEY}" → {MARKETPLACE_REPO}')
    else:
        log(f'{YELLOW}•{RESET} "{MARKETPLACE_KEY}" already registered')

    # Step 2: plugin (if install subcommand)
    added_plugin = False
    plugin_key = None
    if args["install"]:
        next_settings, added_plugin, plugin_key = merge_plugin(next_settings, args["install"])
        if added_plugin:
            log(f'{GREEN}✓{RESET} Enabled "{plugin_key}"')
        else:
            log(f'{YELLOW}•{RESET} "{plugin_key}" already enabled')

    if added_mp or added_plugin:
        write_settings(settings_path, next_settings)

    log("")
    if not args["global"]:
        log(f"{BOLD}Share with team?{RESET} {DIM}(commit to share with future cloners){RESET}")
        log(f'  {CYAN}git add .claude/settings.json && git commit -m "chore: register plugify"{RESET}')
        log("")
    log(f"{BOLD}Next{RESET}")
    if args["install"]:
        log(f"  {CYAN}1.{RESET} Restart Claude Code (or run /reload-plugins)")
        log(f"  {CYAN}2.{RESET} Claude Code prompts: trust marketplace + install plugin")
        log(f"  {CYAN}3.{RESET} {args['install']}@{MARKETPLACE_KEY} is ready to use")
    else:
        log(f"  Use {CYAN}claude plugin install <plugin>@{MARKETPLACE_KEY}{RESET} inside Claude Code,")
        log(f"  or re-run {CYAN}uvx cc-plugify install <plugin>{RESET} to enable one declaratively.")


if __name__ == "__main__":
    main()
