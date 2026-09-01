#!/usr/bin/env python3
"""sync-agents.py 의 Codex 모델 카탈로그 대조 계약.

2026-09-01 사고: gpt-5.4 가 08-31 퇴역(카탈로그 `upgrade.retirement_at`)했는데 codex 블록 8개가 계속
가리켰고 아무 경고도 없었다. 이 대조가 SessionStart 에 있었으면 그날 attention 으로 떴다.

실행: python3 scripts/test-sync-agents-models.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sync-agents.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plugify_sync_agents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SYNC = load_module()
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
ALL = ["low", "medium", "high", "xhigh", "max", "ultra"]
LEGACY = ["low", "medium", "high", "xhigh"]


def entry(slug: str, efforts: list[str], upgrade: dict | None = None) -> dict:
    return {
        "slug": slug,
        "supported_reasoning_levels": [{"effort": e} for e in efforts],
        "upgrade": upgrade,
    }


# 2026-09-01 실제 models_cache.json 의 형태를 축약한 fixture (슬러그·effort·upgrade 필드만).
CATALOG = {
    "gpt-5.6-sol": entry("gpt-5.6-sol", ALL),
    "gpt-5.6-terra": entry("gpt-5.6-terra", ALL),
    "gpt-5.6-luna": entry("gpt-5.6-luna", ["low", "medium", "high", "xhigh", "max"]),
    "gpt-5.5": entry("gpt-5.5", LEGACY),
    "gpt-5.4": entry(
        "gpt-5.4", LEGACY, {"model": "gpt-5.6-terra", "retirement_at": "2026-08-31T19:00:00Z"}
    ),
    "gpt-5.4-mini": entry(
        "gpt-5.4-mini", LEGACY, {"model": "gpt-5.6-luna", "retirement_at": "2099-01-01T00:00:00Z"}
    ),
}


def block(model: str, effort: str) -> dict:
    return {"name": "x", "description": "x", "model": model, "model_reasoning_effort": effort}


class CheckCodexModelTest(unittest.TestCase):
    def test_current_tier_models_are_clean(self) -> None:
        for model, effort in (("gpt-5.6-sol", "xhigh"), ("gpt-5.6-terra", "medium"), ("gpt-5.6-sol", "max")):
            with self.subTest(model=model, effort=effort):
                self.assertEqual(SYNC.check_codex_model(block(model, effort), CATALOG, now=NOW), [])

    def test_retired_model_names_replacement(self) -> None:
        findings = SYNC.check_codex_model(block("gpt-5.4", "medium"), CATALOG, now=NOW)
        self.assertEqual(len(findings), 1)
        self.assertIn("retired", findings[0])
        self.assertIn("gpt-5.6-terra", findings[0])

    def test_future_retirement_is_deprecated_not_retired(self) -> None:
        findings = SYNC.check_codex_model(block("gpt-5.4-mini", "medium"), CATALOG, now=NOW)
        self.assertEqual(len(findings), 1)
        self.assertIn("deprecated", findings[0])
        self.assertNotIn("retired", findings[0])
        self.assertIn("gpt-5.6-luna", findings[0])

    def test_unsupported_effort_is_reported(self) -> None:
        findings = SYNC.check_codex_model(block("gpt-5.5", "max"), CATALOG, now=NOW)
        self.assertEqual(len(findings), 1)
        self.assertIn("not supported", findings[0])

    def test_unknown_model_is_reported(self) -> None:
        findings = SYNC.check_codex_model(block("gpt-9-nope", "high"), CATALOG, now=NOW)
        self.assertEqual(len(findings), 1)
        self.assertIn("not in the Codex model catalog", findings[0])

    def test_ultra_is_forbidden_even_without_catalog(self) -> None:
        # ultra = 자동 위임(모델이 하위 에이전트를 띄움) — 서브에이전트 정의에서는 함대 금지 위반.
        self.assertEqual(len(SYNC.check_codex_model(block("gpt-5.6-sol", "ultra"), None)), 1)
        self.assertEqual(len(SYNC.check_codex_model(block("gpt-5.6-sol", "ultra"), CATALOG, now=NOW)), 1)

    def test_missing_catalog_only_applies_static_rules(self) -> None:
        self.assertEqual(SYNC.check_codex_model(block("gpt-5.4", "medium"), None), [])

    def test_ssot_codex_blocks_are_clean_against_fixture_catalog(self) -> None:
        # 현재 SSOT 전체가 티어 표(sol/terra/luna)를 벗어나지 않는다 — 다음 이관 때 이 테스트가 먼저 빨개져야 한다.
        for agent in SYNC.load_agents():
            codex = agent["fm"].get("codex")
            if codex is None:
                continue
            with self.subTest(agent=agent["stem"]):
                self.assertEqual(SYNC.check_codex_model(codex, CATALOG, now=NOW), [])

    def test_ssot_codex_blocks_are_clean_against_live_catalog(self) -> None:
        # 이 기기의 실제 Codex 카탈로그(있을 때만) — 퇴역 공지가 서버에서 오면 여기서 먼저 잡힌다.
        catalog = SYNC.load_codex_catalog()
        if catalog is None:
            self.skipTest(f"no readable Codex catalog at {SYNC.CODEX_MODELS_CACHE}")
        for agent in SYNC.load_agents():
            codex = agent["fm"].get("codex")
            if codex is None:
                continue
            with self.subTest(agent=agent["stem"]):
                self.assertEqual(SYNC.check_codex_model(codex, catalog), [])


class SyncAgentsCliTest(unittest.TestCase):
    """실제 스크립트를 격리 HOME 에서 실행 — 토큰 방출·--strict-models 종료코드 계약."""

    def run_sync(self, catalog: dict | None, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="plugify-sync-models-") as tmp:
            home = Path(tmp)
            codex_home = home / ".codex"
            codex_home.mkdir()
            if catalog is not None:
                (codex_home / "models_cache.json").write_text(
                    json.dumps({"models": list(catalog.values())}), encoding="utf-8"
                )
            env = dict(os.environ)
            env.update(
                {
                    "HOME": str(home),
                    "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                    "CODEX_HOME": str(codex_home),
                }
            )
            return subprocess.run(
                [sys.executable, "-I", str(SCRIPT), *args],
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
                timeout=60,
            )

    def retired_catalog(self) -> dict:
        # 티어 슬러그 전부를 "이미 퇴역" 으로 표시한 카탈로그 → 현재 SSOT 가 전부 stale 로 잡혀야 한다.
        retired = {}
        for slug, item in CATALOG.items():
            retired[slug] = dict(item, upgrade={"model": "gpt-next", "retirement_at": "2000-01-01T00:00:00Z"})
        return retired

    def test_healthy_catalog_emits_no_token(self) -> None:
        for extra in ((), ("--ensure",)):
            with self.subTest(args=extra):
                result = self.run_sync(CATALOG, *extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(SYNC.CODEX_MODEL_STALE_TOKEN, result.stderr)

    def test_retired_catalog_emits_token_but_still_exits_zero(self) -> None:
        # 경고 전용 — SessionStart 훅이 세션을 막지 않도록 exit 0. 토큰은 훅이 attention 으로 올린다.
        for extra in ((), ("--ensure",)):
            with self.subTest(args=extra):
                result = self.run_sync(self.retired_catalog(), *extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(SYNC.CODEX_MODEL_STALE_TOKEN, result.stderr)
                self.assertIn("gpt-next", result.stderr)

    def test_strict_models_fails_on_retired_and_on_missing_catalog(self) -> None:
        self.assertEqual(self.run_sync(self.retired_catalog(), "--strict-models").returncode, 1)
        self.assertEqual(self.run_sync(None, "--strict-models").returncode, 1)
        self.assertEqual(self.run_sync(CATALOG, "--strict-models").returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
