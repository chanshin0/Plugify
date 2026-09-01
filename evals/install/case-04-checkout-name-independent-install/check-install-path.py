#!/usr/bin/env python3
"""install case-04 runner — 폴더명이 `Plugify` 가 아닌 checkout 에서도 훅 설치가 되고 멱등하며, 옛 경로 정리·사용자 훅 보존이 유지된다.

production `scripts/install-session-hooks.py` 를 폴더명에 `plugify` 가 없는 임시 checkout 으로 실행한다.
`PLUGIFY_EVAL_REPO_ROOT` 로 다른 checkout(수정 전)을 가리켜 pre-fix 결과를 재현할 수 있다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("PLUGIFY_EVAL_REPO_ROOT") or Path(__file__).resolve().parents[3]).resolve()
NEEDED = ("install-session-hooks.py", "sync-agents.py", "workspace-session-start.py")
UNRELATED = {"type": "command", "command": "/usr/bin/env python3 /opt/other-tool/scripts/sync-agents.py --ensure", "timeout": 5}
LEGACY_WS = "/usr/bin/env python3 \"/Users/x/.claude/plugins/marketplaces/plugify/scripts/workspace-session-start.py\""
LEGACY_AG = "/usr/bin/env python3 \"/Users/x/.plugify/scripts/sync-agents.py\" --ensure"


def renamed_checkout(tmp: Path) -> Path:
    # 경로 어디에도 plugify/.plugify 폴더명이 없어야 한다 (사고 조건).
    # 설치기는 --repo-root 를 resolve() 해 기록하므로(macOS /tmp → /private/tmp) 기대값도 resolve 한 경로로 만든다.
    root = (tmp / "Renamed-Checkout").resolve()
    (root / "scripts").mkdir(parents=True)
    for name in NEEDED:
        shutil.copy(ROOT / "scripts" / name, root / "scripts" / name)
    assert not ({"plugify", ".plugify"} & {p.casefold() for p in root.parts}), f"fixture path leaks marker: {root}"
    return root


def seed_settings(home: Path) -> tuple[Path, Path]:
    claude = home / ".claude"; codex = home / ".codex"
    claude.mkdir(parents=True); codex.mkdir(parents=True)
    legacy = [
        {"matcher": "startup|resume", "hooks": [{"type": "command", "command": LEGACY_WS, "timeout": 180}]},
        {"matcher": "clear|compact", "hooks": [UNRELATED, {"type": "command", "command": LEGACY_AG, "timeout": 60}]},
    ]
    (claude / "settings.json").write_text(json.dumps({"model": "keep-me", "hooks": {"SessionStart": legacy}}, indent=2) + "\n", encoding="utf-8")
    (codex / "hooks.json").write_text(json.dumps({"marker": "codex-preserved", "hooks": {"SessionStart": legacy}}, indent=2) + "\n", encoding="utf-8")
    return claude / "settings.json", codex / "hooks.json"


def run_installer(root: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update({"HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"), "CODEX_HOME": str(home / ".codex")})
    return subprocess.run(
        [sys.executable, "-I", str(root / "scripts" / "install-session-hooks.py"), "--repo-root", str(root), *args],
        env=env, text=True, encoding="utf-8", capture_output=True, check=False, timeout=60,
    )


def managed_groups(doc: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for group in doc["hooks"]["SessionStart"]:
        for h in group.get("hooks", []):
            out.setdefault(group.get("matcher"), []).append(h["command"])
    return out


def test_install_from_renamed_checkout_succeeds(tmp: Path) -> None:
    root = renamed_checkout(tmp); settings, hooks = seed_settings(tmp / "home")
    result = run_installer(root, tmp / "home")
    assert result.returncode == 0, f"installer refused a checkout without a `Plugify` folder name:\n{result.stdout}{result.stderr}"
    for path in (settings, hooks):
        doc = json.loads(path.read_text(encoding="utf-8"))
        groups = managed_groups(doc)
        ws = [c for c in groups.get("startup|resume", []) if "workspace-session-start.py" in c]
        ag = [c for c in groups.get("clear|compact", []) if "sync-agents.py" in c and "/opt/other-tool/" not in c]
        assert ws == [f'/usr/bin/env python3 "{root / "scripts" / "workspace-session-start.py"}"'], f"{path.name}: workspace hook wrong/duplicated: {ws}"
        assert ag == [f'/usr/bin/env python3 "{root / "scripts" / "sync-agents.py"}" --ensure'], f"{path.name}: agents hook wrong/duplicated: {ag}"
        flat = [c for cmds in groups.values() for c in cmds]
        assert LEGACY_WS not in flat and LEGACY_AG not in flat, f"{path.name}: legacy plugify/.plugify hooks not replaced"
        assert UNRELATED["command"] in flat, f"{path.name}: unrelated user hook was removed"
    assert json.loads(settings.read_text(encoding="utf-8"))["model"] == "keep-me"
    assert json.loads(hooks.read_text(encoding="utf-8"))["marker"] == "codex-preserved"


def test_second_run_is_idempotent(tmp: Path) -> None:
    # 사고의 진짜 위험: 자기 훅을 못 알아보면 매 실행마다 훅이 하나씩 늘어난다.
    root = renamed_checkout(tmp); settings, hooks = seed_settings(tmp / "home")
    first = run_installer(root, tmp / "home"); assert first.returncode == 0, first.stdout + first.stderr
    before = (settings.read_bytes(), hooks.read_bytes())
    second = run_installer(root, tmp / "home")
    assert second.returncode == 0, second.stdout + second.stderr
    assert (settings.read_bytes(), hooks.read_bytes()) == before, "second run changed bytes (hook duplicated?)"
    assert second.stdout.count("already bound") == 2, f"second run did not report both files as bound:\n{second.stdout}"


def test_dry_run_from_renamed_checkout_does_not_write(tmp: Path) -> None:
    root = renamed_checkout(tmp); settings, hooks = seed_settings(tmp / "home")
    before = (settings.read_bytes(), hooks.read_bytes())
    result = run_installer(root, tmp / "home", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRY-RUN update" in result.stdout and str(root) in result.stdout
    assert (settings.read_bytes(), hooks.read_bytes()) == before, "dry-run wrote files"


def test_plugify_named_checkout_still_works(tmp: Path) -> None:
    # 회귀 방지: 정상 경로(폴더명 Plugify)는 그대로 동작·멱등.
    root = (tmp / "Plugify").resolve(); (root / "scripts").mkdir(parents=True)
    for name in NEEDED:
        shutil.copy(ROOT / "scripts" / name, root / "scripts" / name)
    settings, hooks = seed_settings(tmp / "home")
    assert run_installer(root, tmp / "home").returncode == 0
    before = (settings.read_bytes(), hooks.read_bytes())
    assert run_installer(root, tmp / "home").returncode == 0
    assert (settings.read_bytes(), hooks.read_bytes()) == before


TESTS = [
    test_install_from_renamed_checkout_succeeds,
    test_second_run_is_idempotent,
    test_dry_run_from_renamed_checkout_does_not_write,
    test_plugify_named_checkout_still_works,
]


def main() -> int:
    passed = 0
    for fn in TESTS:
        label = "".join(p.capitalize() for p in fn.__name__.removeprefix("test_").split("_"))
        with tempfile.TemporaryDirectory(prefix="eval-hooks-") as tmp:
            try:
                fn(Path(tmp))
            except (AssertionError, OSError, subprocess.SubprocessError) as exc:
                print(f"not ok - test{label}: {type(exc).__name__}: {exc}")
                continue
        print(f"ok - test{label}")
        passed += 1
    total = len(TESTS)
    if passed == total:
        print(f"{total}/{total} checkout-name-independent install checks PASS")
        return 0
    print(f"{passed}/{total} checkout-name-independent install checks passed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
