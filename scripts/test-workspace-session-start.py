#!/usr/bin/env python3
"""Deterministic regression tests for safe SessionStart workspace refresh."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SESSION_SCRIPT = ROOT / "scripts" / "workspace-session-start.py"


def load_session_module():
    spec = importlib.util.spec_from_file_location("plugify_workspace_session_start_test", SESSION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load workspace-session-start.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SESSION = load_session_module()
MIGRATION = SESSION.MIGRATION


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {command!r}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def git(repo: Path, *arguments: str) -> str:
    return run(["git", "-C", str(repo), *arguments]).strip()


@contextlib.contextmanager
def unsafe_helper(module: ModuleType):
    with tempfile.TemporaryDirectory(prefix="plugify-session-askpass-unsafe-") as temp:
        helper = Path(temp) / "no-askpass.py"
        helper.write_text("#!/usr/bin/env python3\nraise SystemExit(1)\n", encoding="utf-8")
        helper.chmod(0o644)
        original = module.NO_ASKPASS
        module.NO_ASKPASS = helper
        try:
            yield helper
        finally:
            module.NO_ASKPASS = original


class WorkspaceFixture:
    def __init__(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="plugify-session-sync-test-"))
        self.root = self.temp / "workspace"
        self.root.mkdir()
        self.remotes = self.temp / "remotes"
        self.seeds = self.temp / "seeds"
        self.remotes.mkdir()
        self.seeds.mkdir()
        self.origins: dict[str, str] = {}
        self.clone: dict[str, Path] = {}
        self.seed: dict[str, Path] = {}
        for spec in MIGRATION.REPOSITORIES:
            self._create_repository(spec)
        (self.root / MIGRATION.MANIFEST_NAME).write_text(
            MIGRATION.manifest_content(self.origins), encoding="utf-8"
        )
        self.marker = self.temp / "agent-marker.txt"
        self.install_marker = self.temp / "install-marker.txt"

    def close(self) -> None:
        shutil.rmtree(self.temp)

    def _create_repository(self, spec: object) -> None:
        remote = self.remotes / f"{spec.key}.git"
        seed = self.seeds / spec.key
        checkout = self.root / spec.directory
        run(["git", "init", "--bare", "--initial-branch=main", str(remote)])
        run(["git", "init", "--initial-branch=main", str(seed)])
        git(seed, "config", "user.email", "fixture@example.invalid")
        git(seed, "config", "user.name", "Fixture")
        (seed / "base.txt").write_text(f"{spec.key}-base\n", encoding="utf-8")
        if spec.key == "plugify":
            self._write_plugify_assets(seed, "v1")
        git(seed, "add", "-A")
        git(seed, "commit", "-m", "base")
        git(seed, "remote", "add", "origin", str(remote))
        git(seed, "push", "-u", "origin", "main")
        run(["git", "clone", "--quiet", str(remote), str(checkout)])
        git(checkout, "config", "user.email", "fixture@example.invalid")
        git(checkout, "config", "user.name", "Fixture")
        self.origins[spec.key] = str(remote)
        self.clone[spec.key] = checkout
        self.seed[spec.key] = seed

    def _write_plugify_assets(self, repo: Path, version: str) -> None:
        scripts = repo / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / "sync-agents.py").write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "import time\n"
            "from pathlib import Path\n"
            "if os.environ.get('PLUGIFY_TEST_AGENT_STALE'):\n"
            "    sys.stderr.write('[warn] x.md: codex-model-stale: model gpt-5.4 is retired\\n')\n"
            "marker = os.environ.get('PLUGIFY_TEST_AGENT_MARKER')\n"
            "delay = float(os.environ.get('PLUGIFY_TEST_AGENT_SLEEP', '0'))\n"
            f"version = {version!r}\n"
            "if delay:\n"
            "    time.sleep(delay)\n"
            "if marker:\n"
            "    with Path(marker).open('a', encoding='utf-8') as handle:\n"
            "        handle.write(version + '\\n')\n",
            encoding="utf-8",
        )
        (scripts / "install.sh").write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "if [ -n \"${PLUGIFY_TEST_INSTALL_MARKER:-}\" ]; then\n"
            f"  printf '%s\\n' {version!r} >> \"$PLUGIFY_TEST_INSTALL_MARKER\"\n"
            "fi\n",
            encoding="utf-8",
        )
        os.chmod(scripts / "sync-agents.py", 0o755)
        os.chmod(scripts / "install.sh", 0o755)

    def advance(self, name: str, relative: str = "remote.txt", content: str = "remote\n") -> str:
        path = self.seed[name] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        git(self.seed[name], "add", "-f", relative)
        git(self.seed[name], "commit", "-m", "advance")
        git(self.seed[name], "push", "origin", "main")
        return git(self.seed[name], "rev-parse", "HEAD")

    def sync_invocation(
        self, *, timeout: str = "3", extra_env: dict[str, str] | None = None, lock_timeout: str = "15"
    ) -> tuple[list[str], dict[str, str]]:
        env = dict(os.environ)
        env["PLUGIFY_TEST_AGENT_MARKER"] = str(self.marker)
        env["PLUGIFY_TEST_INSTALL_MARKER"] = str(self.install_marker)
        env["CLAUDE_CONFIG_DIR"] = str(self.temp / "claude")
        env["CODEX_HOME"] = str(self.temp / "codex")
        if extra_env:
            env.update(extra_env)
        command = [
            sys.executable,
            str(SESSION_SCRIPT),
            "--repo-root",
            str(self.clone["plugify"]),
            "--git-timeout",
            timeout,
            "--lock-timeout",
            lock_timeout,
        ]
        return command, env

    def run_sync(
        self, *, timeout: str = "3", extra_env: dict[str, str] | None = None, lock_timeout: str = "15"
    ):
        command, env = self.sync_invocation(timeout=timeout, extra_env=extra_env, lock_timeout=lock_timeout)
        return subprocess.run(
            command,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=20,
        )


class SessionSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = WorkspaceFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_up_to_date_is_quiet_and_assets_run(self) -> None:
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v1\n")

    def test_clean_behind_fast_forwards_exact_remote(self) -> None:
        target = self.fx.advance("second_brain")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(self.fx.clone["second_brain"], "rev-parse", "HEAD"), target)
        self.assertIn("updated second_brain", result.stdout)

    def test_tracked_dirty_fetches_but_preserves_head_and_filename(self) -> None:
        checkout = self.fx.clone["second_brain"]
        old_head = git(checkout, "rev-parse", "HEAD")
        target = self.fx.advance("second_brain")
        secret = "highly-sensitive-filename.txt"
        (checkout / secret).write_text("local\n", encoding="utf-8")
        git(checkout, "add", secret)
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertEqual(git(checkout, "rev-parse", "origin/main"), target)
        self.assertIn("second_brain:tracked-dirty", result.stdout)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_local_ahead_is_preserved(self) -> None:
        checkout = self.fx.clone["second_brain"]
        (checkout / "local.txt").write_text("local\n", encoding="utf-8")
        git(checkout, "add", "local.txt")
        git(checkout, "commit", "-m", "local ahead")
        head = git(checkout, "rev-parse", "HEAD")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), head)
        self.assertIn("second_brain:ahead", result.stdout)

    def test_diverged_is_preserved(self) -> None:
        checkout = self.fx.clone["second_brain"]
        (checkout / "local.txt").write_text("local\n", encoding="utf-8")
        git(checkout, "add", "local.txt")
        git(checkout, "commit", "-m", "local")
        local_head = git(checkout, "rev-parse", "HEAD")
        self.fx.advance("second_brain")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), local_head)
        self.assertIn("second_brain:diverged", result.stdout)

    def test_feature_and_detached_states_are_preserved(self) -> None:
        for mode in ("feature", "detached"):
            with self.subTest(mode=mode):
                checkout = self.fx.clone["second_brain"]
                if mode == "feature":
                    git(checkout, "switch", "-c", "feature")
                    expected = "second_brain:non-main"
                else:
                    git(checkout, "checkout", "--detach", "HEAD")
                    expected = "second_brain:detached"
                head = git(checkout, "rev-parse", "HEAD")
                self.fx.advance("second_brain", f"{mode}.txt")
                result = self.fx.run_sync()
                self.assert_success(result)
                self.assertEqual(git(checkout, "rev-parse", "HEAD"), head)
                self.assertIn(expected, result.stdout)
                # Restore for the next subtest without relying on the updater.
                git(checkout, "switch", "-C", "main", "origin/main")

    def test_wrong_upstream_and_operation_in_progress_are_preserved(self) -> None:
        checkout = self.fx.clone["second_brain"]
        git(checkout, "branch", "--unset-upstream")
        old_head = git(checkout, "rev-parse", "HEAD")
        self.fx.advance("second_brain", "upstream.txt")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertIn("second_brain:wrong-upstream", result.stdout)

        git(checkout, "branch", "--set-upstream-to=origin/main", "main")
        marker = Path(git(checkout, "rev-parse", "--git-path", "MERGE_HEAD"))
        if not marker.is_absolute():
            marker = checkout / marker
        marker.write_text(old_head + "\n", encoding="utf-8")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertIn("second_brain:operation-in-progress", result.stdout)

    def test_safe_untracked_output_does_not_block_fast_forward(self) -> None:
        checkout = self.fx.clone["godowon-office"]
        local = checkout / "output" / "local-only.txt"
        local.parent.mkdir()
        local.write_text("keep\n", encoding="utf-8")
        target = self.fx.advance("godowon-office", "other.txt")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), target)
        self.assertEqual(local.read_text(encoding="utf-8"), "keep\n")

    def test_untracked_parent_child_collision_is_not_overwritten(self) -> None:
        checkout = self.fx.clone["godowon-office"]
        local = checkout / "collision" / "private.txt"
        local.parent.mkdir()
        local.write_text("private\n", encoding="utf-8")
        old_head = git(checkout, "rev-parse", "HEAD")
        self.fx.advance("godowon-office", "collision", "remote file\n")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertEqual(local.read_text(encoding="utf-8"), "private\n")
        self.assertIn("godowon-office:untracked-collision", result.stdout)
        self.assertNotIn("private.txt", result.stdout)

    def test_ignored_exact_collision_is_not_overwritten(self) -> None:
        checkout = self.fx.clone["godowon-office"]
        seed = self.fx.seed["godowon-office"]
        (seed / ".gitignore").write_text("private.txt\n", encoding="utf-8")
        git(seed, "add", ".gitignore")
        git(seed, "commit", "-m", "ignore")
        git(seed, "push", "origin", "main")
        git(checkout, "pull", "--ff-only")
        local = checkout / "private.txt"
        local.write_text("local private\n", encoding="utf-8")
        old_head = git(checkout, "rev-parse", "HEAD")
        self.fx.advance("godowon-office", "private.txt", "remote tracked\n")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertEqual(local.read_text(encoding="utf-8"), "local private\n")
        self.assertIn("godowon-office:untracked-collision", result.stdout)

    def test_case_alias_collision_is_blocked_on_ignorecase_checkout(self) -> None:
        checkout = self.fx.clone["godowon-office"]
        git(checkout, "config", "core.ignorecase", "true")
        local = checkout / "private-name.txt"
        local.write_text("local private\n", encoding="utf-8")
        old_head = git(checkout, "rev-parse", "HEAD")
        self.fx.advance("godowon-office", "Private-Name.txt", "remote tracked\n")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "HEAD"), old_head)
        self.assertEqual(local.read_text(encoding="utf-8"), "local private\n")
        self.assertIn("godowon-office:untracked-collision", result.stdout)

    def test_bad_manifest_blocks_every_network_request(self) -> None:
        checkout = self.fx.clone["second_brain"]
        old_remote = git(checkout, "rev-parse", "origin/main")
        self.fx.advance("second_brain")
        (self.fx.root / MIGRATION.MANIFEST_NAME).write_text("{broken\n", encoding="utf-8")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(checkout, "rev-parse", "origin/main"), old_remote)
        self.assertEqual(result.stdout, "Plugify workspace sync attention: workspace-validation\n")

    def test_non_executable_helper_fails_closed_before_git_or_asset_refresh(self) -> None:
        fake_home = self.fx.temp / "unsafe-helper-home"
        fake_home.mkdir()
        output = io.StringIO()
        isolated_env = {
            "HOME": str(fake_home),
            "CODEX_HOME": str(fake_home / ".codex"),
            "CLAUDE_CONFIG_DIR": str(fake_home / ".claude"),
        }
        with (
            unsafe_helper(MIGRATION),
            mock.patch.object(
                SESSION, "git_command", side_effect=AssertionError("session Git must not start")
            ) as git_command,
            mock.patch.object(SESSION, "run_asset_refresh") as asset_refresh,
            mock.patch.object(
                sys, "argv", [str(SESSION_SCRIPT), "--repo-root", str(self.fx.clone["plugify"])]
            ),
            mock.patch.dict(os.environ, isolated_env),
            contextlib.redirect_stdout(output),
        ):
            result = SESSION.main()
        self.assertEqual(result, 0)
        self.assertEqual(git_command.call_count, 0)
        self.assertEqual(asset_refresh.call_count, 0)
        self.assertEqual(
            output.getvalue(),
            "Plugify workspace sync attention: workspace-validation\n",
        )

    def test_standalone_plugify_keeps_local_agent_self_heal_without_network(self) -> None:
        manifest = self.fx.root / MIGRATION.MANIFEST_NAME
        manifest.unlink()
        shutil.rmtree(self.fx.clone["second_brain"])
        shutil.rmtree(self.fx.clone["godowon-office"])
        checkout = self.fx.clone["plugify"]
        before = git(checkout, "rev-parse", "origin/main")
        self.fx.advance("plugify", "remote-only.txt")
        git(checkout, "remote", "set-url", "origin", MIGRATION.SPEC_BY_KEY["plugify"].origin)
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(git(checkout, "rev-parse", "origin/main"), before)
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v1\n")

    def test_wrong_remote_blocks_other_repository_fetch(self) -> None:
        second = self.fx.clone["second_brain"]
        old_remote = git(second, "rev-parse", "origin/main")
        self.fx.advance("second_brain")
        git(self.fx.clone["godowon-office"], "remote", "set-url", "origin", str(self.fx.remotes / "second_brain.git"))
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(second, "rev-parse", "origin/main"), old_remote)
        self.assertIn("workspace-validation", result.stdout)
        self.assertNotIn(str(self.fx.temp), result.stdout + result.stderr)

    def test_offline_fetch_is_noninteractive_and_redacted(self) -> None:
        checkout = self.fx.clone["plugify"]
        remote = "https://127.0.0.1:9/account/private-repository.git"
        git(checkout, "remote", "set-url", "origin", remote)
        git(checkout, "remote", "set-url", "--push", "origin", remote)
        self.fx.origins["plugify"] = remote
        (self.fx.root / MIGRATION.MANIFEST_NAME).write_text(
            MIGRATION.manifest_content(self.fx.origins), encoding="utf-8"
        )
        fake_marker = self.fx.temp / "inherited-askpass-ran"
        fake = self.fx.temp / "fake-askpass.sh"
        fake.write_text(f"#!/bin/sh\ntouch '{fake_marker}'\n", encoding="utf-8")
        os.chmod(fake, 0o755)
        result = self.fx.run_sync(extra_env={"GIT_ASKPASS": str(fake), "SSH_ASKPASS": str(fake)})
        self.assert_success(result)
        self.assertIn("plugify:fetch-failed", result.stdout)
        self.assertFalse(fake_marker.exists())
        self.assertNotIn("127.0.0.1", result.stdout + result.stderr)
        self.assertNotIn("private-repository", result.stdout + result.stderr)

    def test_validated_actual_transport_is_used_for_fetch(self) -> None:
        spec = MIGRATION.SPEC_BY_KEY["plugify"]
        expected = "https://github.com/chanshin0/Plugify.git"
        actual = "git@github.com:chanshin0/Plugify.git"
        calls: list[list[str]] = []

        def fake_git(_repo, arguments, **_kwargs):
            calls.append(list(arguments))
            return SESSION.CommandResult(0, "", "")

        with (
            mock.patch.object(MIGRATION, "validate_checkout", return_value=actual),
            mock.patch.object(SESSION, "immutable_state_reason", return_value="non-main"),
            mock.patch.object(SESSION, "git_command", side_effect=fake_git),
        ):
            result = SESSION.sync_repository(
                Path("/unused"),
                spec,
                expected,
                actual,
                timeout=1,
                hooks_path=Path("/unused-hooks"),
            )
        self.assertEqual(result.state, "non-main")
        self.assertEqual(len(calls), 1)
        self.assertIn(actual, calls[0])
        self.assertNotIn(expected, calls[0])

    def test_inherited_git_routing_and_trace_are_neutralized(self) -> None:
        trace = self.fx.temp / "git-trace-must-not-exist"
        result = self.fx.run_sync(
            extra_env={
                "GIT_DIR": str(self.fx.seed["second_brain"] / ".git"),
                "GIT_WORK_TREE": str(self.fx.seed["second_brain"]),
                "GIT_INDEX_FILE": str(self.fx.temp / "foreign-index"),
                "GIT_TRACE": str(trace),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor",
                "GIT_CONFIG_VALUE_0": "/definitely/not/a/real/fsmonitor",
            }
        )
        self.assert_success(result)
        self.assertEqual(result.stdout, "")
        self.assertFalse(trace.exists())

    def test_bounded_run_kills_timeout(self) -> None:
        started = time.monotonic()
        result = SESSION.bounded_run(
            [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1
        )
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - started, 2)

    def test_concurrent_follower_does_not_run_second_leader(self) -> None:
        first = SESSION.WorkspaceLock(self.fx.root, 1)
        self.assertTrue(first.acquire())
        outcome: list[bool] = []
        attempts: list[Path] = []
        real_mkdir = SESSION.os.mkdir

        def follow() -> None:
            outcome.append(SESSION.WorkspaceLock(self.fx.root, 1).acquire())

        def counted_mkdir(path: Path, mode: int = 0o777) -> None:
            attempts.append(Path(path))
            real_mkdir(path, mode)

        with mock.patch.object(SESSION.os, "mkdir", side_effect=counted_mkdir):
            thread = threading.Thread(target=follow)
            thread.start()
            deadline = time.monotonic() + 1
            while len(attempts) < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            first.release()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [False])
        self.assertEqual(len(attempts), 1, "a follower must never retry lock acquisition")

    def test_concurrent_processes_execute_assets_once(self) -> None:
        command, env = self.fx.sync_invocation(
            extra_env={"PLUGIFY_TEST_AGENT_SLEEP": "0.8"}
        )
        first = subprocess.Popen(
            command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        lock = self.fx.root / SESSION.LOCK_NAME
        deadline = time.monotonic() + 5
        while not lock.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(lock.exists(), "first updater never acquired the workspace lock")
        second = subprocess.Popen(
            command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        first_out, first_err = first.communicate(timeout=30)
        second_out, second_err = second.communicate(timeout=30)
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        self.assertEqual(first_err + second_err, "")
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v1\n")
        self.assertFalse(lock.exists())
        self.assertEqual(first_out + second_out, "")

    def test_stale_codex_model_is_surfaced_without_leaking_stderr(self) -> None:
        # sync-agents 가 stderr 로 codex-model-stale 토큰을 내면 attention 한 줄로만 올라오고,
        # 본문(stderr)은 노출되지 않으며 agent sync 자체는 정상 완료된다.
        result = self.fx.run_sync(extra_env={"PLUGIFY_TEST_AGENT_STALE": "1"})
        self.assert_success(result)
        self.assertEqual(result.stdout, "Plugify workspace sync attention: plugify:codex-model-stale\n")
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v1\n")

    def _plant_lock(self, age_seconds: float) -> Path:
        lock = self.fx.root / SESSION.LOCK_NAME
        lock.mkdir(mode=0o700)
        owner = lock / "owner.json"
        owner.write_text('{"token": "dead-leader"}\n', encoding="utf-8")
        stamp = time.time() - age_seconds
        os.utime(owner, (stamp, stamp))
        os.utime(lock, (stamp, stamp))
        return lock

    def test_stale_lock_is_reclaimed_and_sync_runs(self) -> None:
        # 2026-09-01 사고: 08-29 에 죽은 리더가 남긴 잠금 때문에 3일간 모든 세션 시작이 lock-timeout 으로
        # 세 저장소 최신화와 agent sync 를 건너뛰었다. 오래된 잠금은 이어받아 정상 실행해야 한다.
        lock = self._plant_lock(SESSION.STALE_LOCK_SECONDS + 60)
        target = self.fx.advance("second_brain")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertIn("Plugify workspace sync: updated second_brain", result.stdout)
        self.assertIn("workspace:stale-lock-reclaimed", result.stdout)
        self.assertEqual(git(self.fx.clone["second_brain"], "rev-parse", "HEAD"), target)
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v1\n")
        self.assertFalse(lock.exists())
        leftovers = [p.name for p in self.fx.root.iterdir() if p.name.startswith(SESSION.LOCK_NAME)]
        self.assertEqual(leftovers, [])

    def test_fresh_foreign_lock_is_respected(self) -> None:
        # 살아있는(방금 생긴) 잠금은 남의 것 — 가로채지 않고 기다리다 timeout 으로 물러난다.
        lock = self._plant_lock(0)
        before = (lock / "owner.json").read_bytes()
        result = self.fx.run_sync(lock_timeout="1")
        self.assert_success(result)
        self.assertEqual(result.stdout, "Plugify workspace sync attention: workspace:lock-timeout\n")
        self.assertFalse(self.fx.marker.exists())
        self.assertTrue(lock.is_dir())
        self.assertEqual((lock / "owner.json").read_bytes(), before)

    def test_plugify_update_executes_new_agent_sync(self) -> None:
        self.fx._write_plugify_assets(self.fx.seed["plugify"], "v2")
        git(self.fx.seed["plugify"], "add", "scripts")
        git(self.fx.seed["plugify"], "commit", "-m", "agent v2")
        target = git(self.fx.seed["plugify"], "rev-parse", "HEAD")
        git(self.fx.seed["plugify"], "push", "origin", "main")
        result = self.fx.run_sync()
        self.assert_success(result)
        self.assertEqual(git(self.fx.clone["plugify"], "rev-parse", "HEAD"), target)
        self.assertEqual(self.fx.marker.read_text(encoding="utf-8"), "v2\n")
        self.assertEqual(self.fx.install_marker.read_text(encoding="utf-8"), "v2\n")
        self.assertIn("updated plugify", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
