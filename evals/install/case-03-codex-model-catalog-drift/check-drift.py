#!/usr/bin/env python3
"""install case-03 runner — Codex 모델 카탈로그 드리프트가 조용히 출하되지 않는다.

production 코드(`scripts/sync-agents.py`, `scripts/workspace-session-start.py`)를 격리 HOME 에서 실행해 판정한다.
`PLUGIFY_EVAL_REPO_ROOT` 로 다른 checkout(예: 수정 전 origin/main archive)을 가리켜 pre-fix 결과를 재현할 수 있다.
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
SYNC = ROOT / "scripts" / "sync-agents.py"
HOOK_TEST = ROOT / "scripts" / "test-workspace-session-start.py"
TOKEN = "codex-model-stale"
ALL = ["low", "medium", "high", "xhigh", "max", "ultra"]
LEGACY = ["low", "medium", "high", "xhigh"]


def entry(slug, efforts, upgrade=None):
    return {"slug": slug, "supported_reasoning_levels": [{"effort": e} for e in efforts], "upgrade": upgrade}


# 2026-09-01 실제 카탈로그 축약: 현 티어 3종 + 퇴역한 gpt-5.4(→terra).
CATALOG = [
    entry("gpt-5.6-sol", ALL),
    entry("gpt-5.6-terra", ALL),
    entry("gpt-5.6-luna", ["low", "medium", "high", "xhigh", "max"]),
    entry("gpt-5.4", LEGACY, {"model": "gpt-5.6-terra", "retirement_at": "2026-08-31T19:00:00Z"}),
]

AGENT_MD = """---
claude:
  name: {name}
  description: eval fixture agent
  model: sonnet
  tools: [Read]
  effort: medium
codex:
  name: {name}
  description: eval fixture agent
  model: {model}
  model_reasoning_effort: {effort}
  sandbox_mode: read-only
---

fixture body — this is not a real agent.
"""


def fixture_repo(tmp: Path, agents: dict[str, tuple[str, str]]) -> Path:
    """production sync-agents.py 를 그대로 복사한 미니 레포 + 지정한 codex model/effort 의 SSOT."""
    repo = tmp / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SYNC, repo / "scripts" / "sync-agents.py")
    (repo / "agents").mkdir()
    for name, (model, effort) in agents.items():
        (repo / "agents" / f"{name}.md").write_text(
            AGENT_MD.format(name=name, model=model, effort=effort), encoding="utf-8"
        )
    return repo


def run_sync(repo: Path, home: Path, catalog, *args: str) -> subprocess.CompletedProcess[str]:
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    if catalog is not None:
        (codex_home / "models_cache.json").write_text(json.dumps({"models": catalog}), encoding="utf-8")
    env = dict(os.environ)
    env.update({"HOME": str(home), "CLAUDE_CONFIG_DIR": str(home / ".claude"), "CODEX_HOME": str(codex_home)})
    return subprocess.run(
        [sys.executable, "-I", str(repo / "scripts" / "sync-agents.py"), *args],
        env=env, text=True, encoding="utf-8", capture_output=True, check=False, timeout=60,
    )


def test_pre_fix_shape_is_caught_by_production_sync(tmp: Path) -> None:
    # 사고 그대로: SSOT 가 퇴역 슬러그(gpt-5.4)를 가리키고 카탈로그가 퇴역을 알린다.
    repo = fixture_repo(tmp, {"implementer": ("gpt-5.4", "xhigh"), "reviewer": ("gpt-5.6-sol", "xhigh")})
    for extra in ((), ("--ensure",)):
        result = run_sync(repo, tmp / f"home{len(extra)}", CATALOG, *extra)
        assert result.returncode == 0, f"sync must not block the session (exit {result.returncode}): {result.stderr}"
        assert TOKEN in result.stderr, f"retired model shipped silently with args={extra}: {result.stderr!r}"
        assert "gpt-5.6-terra" in result.stderr, "warning must name the replacement model"
        assert "reviewer" not in "".join(l for l in result.stderr.splitlines() if TOKEN in l), "healthy agent flagged"
    toml = tmp / "home0" / ".codex" / "agents" / "implementer.toml"
    assert toml.is_file(), "warn-only: the TOML must still be generated"


def test_strict_models_fails_closed(tmp: Path) -> None:
    repo = fixture_repo(tmp, {"implementer": ("gpt-5.4", "xhigh")})
    assert run_sync(repo, tmp / "a", CATALOG, "--strict-models").returncode == 1, "strict must fail on retired model"
    assert run_sync(repo, tmp / "b", None, "--strict-models").returncode == 1, "strict must fail without a catalog"
    healthy = fixture_repo(tmp / "h", {"implementer": ("gpt-5.6-terra", "xhigh")})
    assert run_sync(healthy, tmp / "c", CATALOG, "--strict-models").returncode == 0, "strict must pass a healthy SSOT"


def test_unsupported_effort_and_ultra_are_caught(tmp: Path) -> None:
    repo = fixture_repo(tmp, {"a": ("gpt-5.4", "max"), "b": ("gpt-5.6-sol", "ultra")})
    result = run_sync(repo, tmp / "home", CATALOG)
    lines = [l for l in result.stderr.splitlines() if TOKEN in l]
    assert any("not supported" in l for l in lines), f"effort unsupported by model not caught: {lines}"
    assert any("ultra" in l and "delegation" in l for l in lines), f"ultra (auto-delegation) not rejected: {lines}"
    # ultra 는 카탈로그가 없어도 걸려야 한다(정적 규칙).
    result = run_sync(repo, tmp / "home2", None)
    assert any("ultra" in l for l in result.stderr.splitlines() if TOKEN in l), "ultra must be rejected without catalog"


def test_session_start_surfaces_attention_only(tmp: Path) -> None:
    # production 훅 실경로: stderr 토큰 → `plugify:codex-model-stale` attention 1줄, stderr 본문 비노출.
    name = "SessionSyncTest.test_stale_codex_model_is_surfaced_without_leaking_stderr"
    result = subprocess.run(
        [sys.executable, str(HOOK_TEST), name], text=True, encoding="utf-8", capture_output=True, check=False, timeout=120,
    )
    assert result.returncode == 0, f"hook does not surface the token as attention:\n{result.stderr[-1500:]}"


def test_current_ssot_is_clean_against_tier_catalog(tmp: Path) -> None:
    # 이 checkout 의 실제 SSOT 전체가 티어 표(sol/terra/luna) 안에 있고 퇴역 슬러그가 없다.
    home = tmp / "home"
    result = run_sync(ROOT, home, CATALOG, "--strict-models")
    assert result.returncode == 0, f"current SSOT has stale codex models:\n{result.stderr}"
    tomls = list((home / ".codex" / "agents").glob("*.toml"))
    assert tomls, "no codex agents generated"
    stale = [t.name for t in tomls if 'model = "gpt-5.4"' in t.read_text(encoding="utf-8") or 'model = "gpt-5.5"' in t.read_text(encoding="utf-8")]
    assert not stale, f"generated TOML still on retired/previous-gen slugs: {stale}"


TESTS = [
    test_pre_fix_shape_is_caught_by_production_sync,
    test_strict_models_fails_closed,
    test_unsupported_effort_and_ultra_are_caught,
    test_session_start_surfaces_attention_only,
    test_current_ssot_is_clean_against_tier_catalog,
]


def main() -> int:
    passed = 0
    for fn in TESTS:
        label = "".join(p.capitalize() for p in fn.__name__.removeprefix("test_").split("_"))
        with tempfile.TemporaryDirectory(prefix="plugify-eval-drift-") as tmp:
            try:
                fn(Path(tmp))
            except (AssertionError, OSError, subprocess.SubprocessError) as exc:
                print(f"not ok - test{label}: {type(exc).__name__}: {exc}")
                continue
        print(f"ok - test{label}")
        passed += 1
    total = len(TESTS)
    if passed == total:
        print(f"{total}/{total} codex model catalog drift checks PASS")
        return 0
    print(f"{passed}/{total} codex model catalog drift checks passed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
