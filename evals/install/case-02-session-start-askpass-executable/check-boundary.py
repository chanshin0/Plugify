#!/usr/bin/env python3
"""Confirmed regression boundary for the SessionStart askpass helper."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
MIGRATE_PATH = ROOT / "scripts" / "workspace-migrate.py"
SESSION_PATH = ROOT / "scripts" / "workspace-session-start.py"
HELPER_PATH = ROOT / "scripts" / "no-askpass.py"
EXPECTED_TESTS = (
    "testGitIndexModeIsExecutable",
    "testFilesystemHelperIsExecutable",
    "testPreflightRejectsUnsafeHelperBeforePlan",
    "testStrictVerifyRejectsUnsafeHelperBeforeRepositoryChecks",
    "testSessionStartSanitizesUnsafeHelperBeforeGit",
)

sys.dont_write_bytecode = True


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "production module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MIGRATION = load_module("askpass_eval_workspace_migrate", MIGRATE_PATH)


def expected_origins() -> dict[str, str]:
    return {spec.key: spec.origin for spec in MIGRATION.REPOSITORIES}


def run(
    *arguments: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "managed workspace fixture command failed")
    return result


def make_managed_workspace(base: Path) -> Path:
    control = base / "git-control"
    hooks = control / "hooks"
    template = control / "template"
    fake_home = control / "home"
    hooks.mkdir(parents=True)
    template.mkdir()
    fake_home.mkdir()
    global_config = control / "global.gitconfig"
    global_config.write_text("", encoding="utf-8")
    git_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(fake_home),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(global_config),
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
    }
    git_prefix = (
        "git",
        "-c",
        f"core.hooksPath={hooks}",
        "-c",
        f"init.templateDir={template}",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "maintenance.auto=false",
        "-c",
        "gc.auto=0",
    )
    root = base / "workspace"
    root.mkdir()
    origins = expected_origins()
    for spec in MIGRATION.REPOSITORIES:
        repo = root / spec.directory
        repo.mkdir()
        run(*git_prefix, "init", "--quiet", "-b", "main", cwd=repo, env=git_env)
        run(*git_prefix, "config", "--local", "user.name", "Askpass Eval", cwd=repo, env=git_env)
        run(
            *git_prefix,
            "config",
            "--local",
            "user.email",
            "askpass-eval@localhost",
            cwd=repo,
            env=git_env,
        )
        (repo / "README.md").write_text(f"# {spec.key}\n", encoding="utf-8")
        run(*git_prefix, "add", "README.md", cwd=repo, env=git_env)
        run(*git_prefix, "commit", "--quiet", "-m", "fixture", cwd=repo, env=git_env)
        run(*git_prefix, "remote", "add", "origin", origins[spec.key], cwd=repo, env=git_env)
        run(
            *git_prefix, "config", "--local", "core.autocrlf", "false", cwd=repo, env=git_env
        )
        run(*git_prefix, "config", "--local", "core.eol", "lf", cwd=repo, env=git_env)
    (root / "AGENTS.md").write_text(MIGRATION.router_template(), encoding="utf-8")
    (root / MIGRATION.MANIFEST_NAME).write_text(
        MIGRATION.manifest_content(origins), encoding="utf-8"
    )
    return root


@contextlib.contextmanager
def unsafe_helper(module: ModuleType):
    with tempfile.TemporaryDirectory(prefix="askpass-eval-", dir=os.environ.get("TMPDIR")) as temp:
        helper = Path(temp) / "no-askpass.py"
        helper.write_text("#!/usr/bin/env python3\nraise SystemExit(1)\n", encoding="utf-8")
        helper.chmod(0o644)
        original = module.NO_ASKPASS
        module.NO_ASKPASS = helper
        try:
            yield helper
        finally:
            module.NO_ASKPASS = original


def test_git_index_mode_is_executable() -> None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--stage", "--", "scripts/no-askpass.py"],
        text=True,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "git index query failed")
    fields = result.stdout.split()
    require(len(fields) >= 4, "helper missing from git index")
    require(fields[0] == "100755", "helper git index mode is not 100755")


def test_filesystem_helper_is_executable() -> None:
    require(HELPER_PATH.is_file(), "helper is not a regular file")
    require(not HELPER_PATH.is_symlink(), "helper must not be a symlink")
    require(os.access(HELPER_PATH, os.X_OK), "helper is not executable")
    require(stat.S_IMODE(HELPER_PATH.stat().st_mode) & 0o111 != 0, "helper lacks execute bits")


def test_preflight_rejects_unsafe_helper_before_plan() -> None:
    with tempfile.TemporaryDirectory(prefix="askpass-preflight-", dir=os.environ.get("TMPDIR")) as temp:
        root = make_managed_workspace(Path(temp))
        output = io.StringIO()
        error = ""
        with unsafe_helper(MIGRATION):
            try:
                with contextlib.redirect_stdout(output):
                    MIGRATION.preflight(root, expected_origins(), allow_dirty=False)
            except MIGRATION.WorkspaceError as exc:
                error = str(exc)
        require(
            error.startswith("noninteractive askpass helper is missing or unsafe:"),
            "preflight did not reject unsafe helper",
        )
        require(output.getvalue() == "", "preflight emitted workspace status before helper validation")


def test_strict_verify_rejects_unsafe_helper_before_repository_checks() -> None:
    with tempfile.TemporaryDirectory(prefix="askpass-verify-", dir=os.environ.get("TMPDIR")) as temp:
        root = make_managed_workspace(Path(temp))
        error = ""
        output = io.StringIO()
        with unsafe_helper(MIGRATION):
            try:
                with contextlib.redirect_stdout(output):
                    MIGRATION.strict_verify(root, expected_origins(), allow_dirty=False)
            except MIGRATION.WorkspaceError as exc:
                error = str(exc)
        require(
            error.startswith("noninteractive askpass helper is missing or unsafe:"),
            "strict verify checked repositories before helper",
        )
        require(output.getvalue() == "", "strict verify emitted success before helper validation")


def test_session_start_sanitizes_unsafe_helper_before_git() -> None:
    session = load_module("askpass_eval_workspace_session_start", SESSION_PATH)
    with tempfile.TemporaryDirectory(
        prefix="askpass-session-", dir=os.environ.get("TMPDIR")
    ) as temp, unsafe_helper(session.MIGRATION):
        base = Path(temp)
        root = make_managed_workspace(base)
        fake_home = base / "home"
        fake_home.mkdir()
        output = io.StringIO()
        isolated_env = {
            "HOME": str(fake_home),
            "CODEX_HOME": str(Path(fake_home) / ".codex"),
            "CLAUDE_CONFIG_DIR": str(Path(fake_home) / ".claude"),
        }
        with mock.patch.object(
            session, "git_command", side_effect=AssertionError("session Git must not start")
        ) as git_command, mock.patch.object(session, "run_asset_refresh") as asset_refresh, mock.patch.object(
            sys, "argv", [str(SESSION_PATH), "--repo-root", str(root / "Plugify")]
        ), mock.patch.dict(os.environ, isolated_env), contextlib.redirect_stdout(output):
            result = session.main()
        require(result == 0, "SessionStart must not brick the coding session")
        require(git_command.call_count == 0, "SessionStart attempted askpass-bound Git before validation")
        require(asset_refresh.call_count == 0, "SessionStart attempted user asset refresh before validation")
        require(
            output.getvalue().strip() == "Plugify workspace sync attention: workspace-validation",
            "SessionStart did not emit the sanitized workspace-validation signal",
        )


TESTS = (
    (EXPECTED_TESTS[0], test_git_index_mode_is_executable),
    (EXPECTED_TESTS[1], test_filesystem_helper_is_executable),
    (EXPECTED_TESTS[2], test_preflight_rejects_unsafe_helper_before_plan),
    (EXPECTED_TESTS[3], test_strict_verify_rejects_unsafe_helper_before_repository_checks),
    (EXPECTED_TESTS[4], test_session_start_sanitizes_unsafe_helper_before_git),
)


def main() -> int:
    require(tuple(name for name, _ in TESTS) == EXPECTED_TESTS, "test manifest drift")
    failures = 0
    for name, test in TESTS:
        try:
            test()
        except BaseException as exc:
            failures += 1
            print(f"not ok - {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok - {name}")
    if failures:
        print(f"{len(TESTS) - failures}/{len(TESTS)} askpass executable boundary checks passed")
        return 1
    print("5/5 askpass executable boundary checks PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
