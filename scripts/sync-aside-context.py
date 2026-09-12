#!/usr/bin/env python3
"""Generate the Aside account-level AGENTS.md so Aside sessions share the same
context as Claude Code / Codex.

Aside injects `<ASIDE_HOME>/u/<account>/AGENTS.md` into every session's system
prompt (sidepanel, CLI, Project). Project-less sessions have their workspace
root at the account dir, so they cannot read the repo-level routers. This
script composes:

  templates/aside-agents-preamble.md   (Aside-specific rules, SSOT in Plugify)
  + ~/.codex/AGENTS.md                 (brain router, mirrored verbatim)

into that file. Idempotent. `--ensure` is the silent fast path for SessionStart
hooks: writes only when the composed content differs, exits 0 when Aside is not
installed on this machine.

Env: ASIDE_HOME (default ~/.aside), ASIDE_ACCOUNT (default 0), CODEX_HOME.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREAMBLE = REPO / "templates" / "aside-agents-preamble.md"
MARKER = "<!-- plugify-aside-context:v1 — 생성 파일. 정본: Plugify/templates/aside-agents-preamble.md + ~/.codex/AGENTS.md. 재생성: python3 Plugify/scripts/sync-aside-context.py -->"
BEGIN = "<!-- begin: mirrored from ~/.codex/AGENTS.md — do not edit here -->"
END = "<!-- end: mirrored from ~/.codex/AGENTS.md -->"


def paths() -> tuple[Path, Path]:
    aside_home = Path(os.environ.get("ASIDE_HOME", Path.home() / ".aside"))
    account = os.environ.get("ASIDE_ACCOUNT", "0")
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return aside_home / "u" / account / "AGENTS.md", codex_home / "AGENTS.md"


def compose(router: Path) -> str:
    preamble = PREAMBLE.read_text(encoding="utf-8").strip()
    body = router.read_text(encoding="utf-8").strip()
    return "\n\n".join([MARKER, preamble, "---", BEGIN, body, END]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ensure", action="store_true", help="silent; write only on diff; exit 0 if Aside absent")
    ap.add_argument("--check", action="store_true", help="exit 1 if target is missing or stale, print status")
    a = ap.parse_args()
    target, router = paths()

    if not target.parent.is_dir():
        if a.ensure:
            return 0
        print(f"[sync-aside-context] Aside account dir not found: {target.parent}", file=sys.stderr)
        return 0 if not a.check else 1
    if not router.is_file():
        print(f"[sync-aside-context] router missing: {router}", file=sys.stderr)
        return 1
    if not PREAMBLE.is_file():
        print(f"[sync-aside-context] preamble missing: {PREAMBLE}", file=sys.stderr)
        return 1

    want = compose(router)
    have = target.read_text(encoding="utf-8") if target.is_file() else None
    if a.check:
        state = "missing" if have is None else ("ok" if have == want else "stale")
        print(f"[sync-aside-context] {target}: {state}")
        return 0 if state == "ok" else 1
    if have == want:
        if not a.ensure:
            print(f"[sync-aside-context] up to date: {target}")
        return 0
    target.write_text(want, encoding="utf-8")
    print(f"[sync-aside-context] wrote {target} ({len(want)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
