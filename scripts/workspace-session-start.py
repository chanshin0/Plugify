#!/usr/bin/env python3
"""Safely refresh the portable three-repository workspace at SessionStart."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable


SCRIPT_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
MIGRATION_SCRIPT = SCRIPT_REPO_ROOT / "scripts" / "workspace-migrate.py"
LOCK_NAME = ".plugify-session-sync.lock"
DEFAULT_GIT_TIMEOUT = 15.0
# A follower waits for the complete leader run, not just one Git request.  The
# leader can perform three bounded fetches and then refresh/install Plugify
# assets, so this must remain comfortably above that normal upper envelope.
DEFAULT_LOCK_TIMEOUT = 120.0
# 죽은 리더가 남긴 잠금을 살아있는 것으로 오인하지 않기 위한 나이 상한. 리더의 전체 실행은 훅 timeout
# (Claude 180s) 안에서 끝나므로 10분 넘은 잠금은 주인이 없다. (2026-09-01 사고: 08-29 에 죽은 리더의
# 잠금이 3일간 남아 모든 SessionStart 가 lock-timeout 으로 세 저장소 최신화·agent sync 를 건너뛰었다.)
STALE_LOCK_SECONDS = 600.0


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("plugify_workspace_migrate", MIGRATION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("workspace validator unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MIGRATION = load_migration_module()


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True)
class RepoResult:
    name: str
    state: str
    updated: bool = False


class WorkspaceLock:
    """A cross-process atomic-directory lock; followers reuse the leader's run."""

    def __init__(self, root: Path, timeout: float) -> None:
        self.path = root / LOCK_NAME
        self.timeout = max(0.0, timeout)
        self.token = uuid.uuid4().hex
        self.leader = False
        self.wait_timed_out = False
        self.peer_completed = False
        self.error = False
        self.reclaimed_stale = False

    def _lock_age(self) -> float | None:
        """잠금이 생긴 뒤 흐른 초. 리더가 첫 행동으로 쓰는 owner.json 기준, 없으면 디렉터리 기준."""
        for candidate in (self.path / "owner.json", self.path):
            try:
                return max(0.0, time.time() - os.stat(candidate, follow_symlinks=False).st_mtime)
            except OSError:
                continue
        return None

    def _reclaim_stale(self) -> bool:
        """STALE_LOCK_SECONDS 를 넘긴 잠금을 원자적으로 치운다. rename 경쟁에 이긴 프로세스 하나만 True."""
        age = self._lock_age()
        if age is None or age < STALE_LOCK_SECONDS:
            return False
        graveyard = self.path.with_name(f"{LOCK_NAME}.stale-{self.token}")
        try:
            os.rename(self.path, graveyard)
        except OSError:
            return False  # 다른 프로세스가 먼저 치웠거나 이미 사라짐 — 우리는 뒤따른다
        shutil.rmtree(graveyard, ignore_errors=True)
        return True

    def _follow_or_reclaim(self) -> bool:
        """살아있는 잠금이면 완료까지 기다리고 False. 죽은 잠금을 우리가 치웠으면 새 잠금을 만들고 True.

        살아있는 잠금을 본 프로세스는 follower 다: 디렉터리가 사라졌다고 두 번째 리더가 되지 않는다
        (같은 일을 두 번 하지 않기 위해). 유일한 예외는 STALE_LOCK_SECONDS 를 넘긴 잠금 — 그 리더는
        죽었고 일을 끝내지 못했으므로 rename 경쟁에 이긴 하나가 이어받는다. mkdir 재시도는 그때뿐이다.
        """
        deadline = time.monotonic() + self.timeout
        while True:
            if self._reclaim_stale():
                self.reclaimed_stale = True
                try:
                    os.mkdir(self.path, 0o700)
                    return True
                except FileExistsError:
                    continue  # 치우는 사이 다른 프로세스가 새 리더가 됐다 → follower 로 기다린다
                except OSError:
                    self.error = True
                    return False
            if not (self.path.exists() or self.path.is_symlink()):
                self.peer_completed = True
                return False
            if time.monotonic() >= deadline:
                self.wait_timed_out = True
                return False
            time.sleep(0.1)

    def acquire(self) -> bool:
        try:
            os.mkdir(self.path, 0o700)
        except FileExistsError:
            if not self._follow_or_reclaim():
                return False
        except OSError:
            self.error = True
            return False

        owner = self.path / "owner.json"
        try:
            fd = os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"token": self.token}, handle)
                handle.write("\n")
        except BaseException:
            try:
                os.rmdir(self.path)
            except OSError:
                pass
            raise
        self.leader = True
        return True

    def release(self) -> None:
        if not self.leader:
            return
        owner = self.path / "owner.json"
        try:
            data = json.loads(owner.read_text(encoding="utf-8"))
            if data != {"token": self.token}:
                return
            owner.unlink()
            os.rmdir(self.path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Never delete a lock whose ownership can no longer be proven.
            return
        finally:
            self.leader = False

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.release()


def bounded_run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float,
) -> CommandResult:
    """Run without stdin and terminate the whole subprocess group on timeout."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, timeout))
        return CommandResult(process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
        stdout, stderr = process.communicate()
        return CommandResult(process.returncode or 124, stdout, stderr, timed_out=True)


def git_environment() -> dict[str, str]:
    no_askpass = MIGRATION.validate_noninteractive_askpass_helper()
    return MIGRATION.clean_git_environment(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": str(no_askpass),
            "SSH_ASKPASS": str(no_askpass),
            "SSH_ASKPASS_REQUIRE": "never",
            "GCM_INTERACTIVE": "Never",
            "GIT_SSH_COMMAND": "ssh -oBatchMode=yes -oStrictHostKeyChecking=yes",
            "GIT_SSH_VARIANT": "ssh",
            "GIT_LFS_SKIP_SMUDGE": "1",
        }
    )


def git_command(
    repo: Path,
    arguments: Iterable[str],
    *,
    timeout: float,
    hooks_path: Path,
) -> CommandResult:
    return bounded_run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.eol=lf",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={hooks_path}",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            "-c",
            "credential.interactive=false",
            "-C",
            str(repo),
            *arguments,
        ],
        env=git_environment(),
        timeout=timeout,
    )


def output(result: CommandResult) -> str:
    return result.stdout.strip()


def git_path_exists(repo: Path, name: str, *, timeout: float, hooks_path: Path) -> bool:
    result = git_command(repo, ["rev-parse", "--git-path", name], timeout=timeout, hooks_path=hooks_path)
    if result.returncode != 0 or result.timed_out:
        return True
    path = Path(output(result))
    if not path.is_absolute():
        path = repo / path
    return path.exists() or path.is_symlink()


def immutable_state_reason(repo: Path, *, timeout: float, hooks_path: Path) -> str | None:
    branch = git_command(
        repo,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    if branch.timed_out:
        return "local-timeout"
    if branch.returncode != 0:
        return "detached"
    if output(branch) != "main":
        return "non-main"

    upstream = git_command(
        repo,
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    if upstream.timed_out:
        return "local-timeout"
    if upstream.returncode != 0 or output(upstream) != "origin/main":
        return "wrong-upstream"

    for marker in (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "BISECT_LOG",
        "rebase-apply",
        "rebase-merge",
        "sequencer",
    ):
        if git_path_exists(repo, marker, timeout=timeout, hooks_path=hooks_path):
            return "operation-in-progress"

    dirty = git_command(
        repo,
        ["status", "--porcelain=v1", "--untracked-files=no"],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    if dirty.timed_out:
        return "local-timeout"
    if dirty.returncode != 0:
        return "local-error"
    if dirty.stdout:
        return "tracked-dirty"
    return None


def nul_paths(result: CommandResult) -> list[str]:
    if result.returncode != 0 or result.timed_out:
        raise RuntimeError("local path inventory failed")
    return [item for item in result.stdout.split("\0") if item]


def paths_collide(left: str, right: str, *, ignore_case: bool) -> bool:
    left = unicodedata.normalize("NFC", left.rstrip("/"))
    right = unicodedata.normalize("NFC", right.rstrip("/"))
    if ignore_case:
        left = left.casefold()
        right = right.casefold()
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


def has_untracked_collision(
    repo: Path,
    old_head: str,
    new_head: str,
    *,
    timeout: float,
    hooks_path: Path,
) -> bool:
    incoming = nul_paths(
        git_command(
            repo,
            ["diff", "--name-only", "-z", old_head, new_head, "--"],
            timeout=timeout,
            hooks_path=hooks_path,
        )
    )
    if not incoming:
        return False
    ignore_case_result = git_command(
        repo,
        ["config", "--bool", "core.ignorecase"],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    ignore_case = ignore_case_result.returncode == 0 and output(ignore_case_result) == "true"
    local: list[str] = []
    for arguments in (
        ["ls-files", "--others", "--exclude-standard", "-z", "--"],
        ["ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--"],
    ):
        local.extend(
            nul_paths(git_command(repo, arguments, timeout=timeout, hooks_path=hooks_path))
        )
    return any(
        paths_collide(remote_path, local_path, ignore_case=ignore_case)
        for remote_path in incoming
        for local_path in local
    )


def rev(repo: Path, name: str, *, timeout: float, hooks_path: Path) -> str | None:
    result = git_command(
        repo,
        ["rev-parse", "--verify", f"{name}^{{commit}}"],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    value = output(result)
    if result.returncode != 0 or result.timed_out or not value:
        return None
    return value


def is_ancestor(
    repo: Path,
    older: str,
    newer: str,
    *,
    timeout: float,
    hooks_path: Path,
) -> bool:
    result = git_command(
        repo,
        ["merge-base", "--is-ancestor", older, newer],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    return result.returncode == 0 and not result.timed_out


def sync_repository(
    repo: Path,
    spec: object,
    expected_origin: str,
    fetch_origin: str,
    *,
    timeout: float,
    hooks_path: Path,
) -> RepoResult:
    name = str(spec.key)
    try:
        MIGRATION.validate_checkout(repo, spec, expected_origin)
    except MIGRATION.WorkspaceError:
        return RepoResult(name, "identity-changed")
    precondition = immutable_state_reason(repo, timeout=timeout, hooks_path=hooks_path)
    fetch = git_command(
        repo,
        [
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-recurse-submodules",
            "--",
            fetch_origin,
            "+refs/heads/main:refs/remotes/origin/main",
        ],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    if fetch.timed_out:
        return RepoResult(name, "fetch-timeout")
    if fetch.returncode != 0:
        return RepoResult(name, "fetch-failed")
    if precondition is not None:
        return RepoResult(name, precondition)

    old_head = rev(repo, "HEAD", timeout=timeout, hooks_path=hooks_path)
    new_head = rev(repo, "refs/remotes/origin/main", timeout=timeout, hooks_path=hooks_path)
    if old_head is None or new_head is None:
        return RepoResult(name, "invalid-ref")
    if old_head == new_head:
        return RepoResult(name, "current")
    if is_ancestor(repo, new_head, old_head, timeout=timeout, hooks_path=hooks_path):
        return RepoResult(name, "ahead")
    if not is_ancestor(repo, old_head, new_head, timeout=timeout, hooks_path=hooks_path):
        return RepoResult(name, "diverged")

    try:
        if has_untracked_collision(
            repo, old_head, new_head, timeout=timeout, hooks_path=hooks_path
        ):
            return RepoResult(name, "untracked-collision")
    except RuntimeError:
        return RepoResult(name, "local-error")

    # Revalidate identity and mutable preconditions immediately before applying.
    try:
        MIGRATION.validate_checkout(repo, spec, expected_origin)
    except MIGRATION.WorkspaceError:
        return RepoResult(name, "identity-changed")
    if immutable_state_reason(repo, timeout=timeout, hooks_path=hooks_path) is not None:
        return RepoResult(name, "state-changed")
    if rev(repo, "HEAD", timeout=timeout, hooks_path=hooks_path) != old_head:
        return RepoResult(name, "state-changed")
    if rev(repo, "refs/remotes/origin/main", timeout=timeout, hooks_path=hooks_path) != new_head:
        return RepoResult(name, "state-changed")

    merge = git_command(
        repo,
        ["merge", "--ff-only", "--quiet", new_head],
        timeout=timeout,
        hooks_path=hooks_path,
    )
    if merge.timed_out:
        current = rev(repo, "HEAD", timeout=timeout, hooks_path=hooks_path)
        if current == new_head:
            post = immutable_state_reason(repo, timeout=timeout, hooks_path=hooks_path)
            state = "updated-after-timeout" if post is None else "postcheck-failed"
            return RepoResult(name, state, updated=True)
        if current != old_head:
            return RepoResult(name, "postcheck-failed")
        return RepoResult(name, "apply-timeout")
    if merge.returncode != 0:
        current = rev(repo, "HEAD", timeout=timeout, hooks_path=hooks_path)
        if current == new_head:
            post = immutable_state_reason(repo, timeout=timeout, hooks_path=hooks_path)
            state = "updated-after-error" if post is None else "postcheck-failed"
            return RepoResult(name, state, updated=True)
        if current != old_head:
            return RepoResult(name, "postcheck-failed")
        return RepoResult(name, "apply-failed")
    if rev(repo, "HEAD", timeout=timeout, hooks_path=hooks_path) != new_head:
        return RepoResult(name, "postcheck-failed")
    if immutable_state_reason(repo, timeout=timeout, hooks_path=hooks_path) is not None:
        return RepoResult(name, "postcheck-failed", updated=True)
    return RepoResult(name, "updated", updated=True)


def validate_workspace(
    repo_root: Path,
) -> tuple[Path, dict[str, str], list[tuple[object, Path, str]]]:
    repo_root = repo_root.resolve(strict=True)
    root = repo_root.parent
    manifest = root / MIGRATION.MANIFEST_NAME
    if manifest.is_symlink() or not manifest.is_file():
        raise MIGRATION.WorkspaceError("managed workspace manifest missing")
    MIGRATION.validate_workspace_container(root)
    MIGRATION.validate_required_name_collisions(root)
    origins = MIGRATION.manifest_origins(root)
    repositories: list[tuple[object, Path, str]] = []
    for spec in MIGRATION.REPOSITORIES:
        path = root / spec.directory
        fetch_origin = MIGRATION.validate_checkout(path, spec, origins[spec.key])
        repositories.append((spec, path, fetch_origin))
    if repositories[0][1].resolve(strict=True) != repo_root:
        raise MIGRATION.WorkspaceError("active Plugify checkout is not the managed sibling")
    order = {"second_brain": 0, "godowon-office": 1, "plugify": 2}
    repositories.sort(key=lambda item: order[item[0].key])
    return root, origins, repositories


def run_asset_refresh(repo_root: Path, *, plugify_updated: bool, timeout: float) -> str | None:
    asset_env = dict(os.environ)
    for key in (
        "BASH_ENV",
        "ENV",
        "CDPATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        asset_env.pop(key, None)
    asset_env["PYTHONNOUSERSITE"] = "1"
    sync_script = repo_root / "scripts" / "sync-agents.py"
    if sync_script.is_symlink() or not sync_script.is_file():
        return "asset-sync-missing"
    result = bounded_run(
        [sys.executable, "-I", str(sync_script), "--ensure"],
        env=asset_env,
        timeout=max(timeout, 20.0),
    )
    if result.returncode != 0 or result.timed_out:
        return "asset-sync-failed"
    # sync-agents 는 Codex 모델 카탈로그 대조에서 퇴역/미지원을 exit 0 + stderr 토큰으로 알린다
    # (세션을 막지 않기 위해). 토큰만 attention 으로 올리고 stderr 본문은 노출하지 않는다.
    # 토큰 정본 = scripts/sync-agents.py CODEX_MODEL_STALE_TOKEN.
    codex_model_stale = "codex-model-stale" in result.stderr

    if plugify_updated:
        installer = repo_root / "scripts" / "install.sh"
        if installer.is_symlink() or not installer.is_file():
            return "asset-install-missing"
        install = bounded_run(
            ["bash", "--noprofile", "--norc", str(installer)],
            env=asset_env,
            timeout=max(timeout * 2, 30.0),
        )
        if install.returncode != 0 or install.timed_out:
            return "asset-install-failed"
    return "codex-model-stale" if codex_model_stale else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=SCRIPT_REPO_ROOT,
        help="Active Plugify checkout (default: this script's repository).",
    )
    parser.add_argument("--git-timeout", type=float, default=DEFAULT_GIT_TIMEOUT)
    parser.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT)
    return parser.parse_args()


def refresh_standalone_plugify(repo_root: Path, *, timeout: float, lock_timeout: float) -> bool:
    """Preserve the legacy single-repo installer without claiming workspace sync."""
    try:
        resolved = repo_root.resolve(strict=True)
    except OSError:
        return False
    manifest = resolved.parent / MIGRATION.MANIFEST_NAME
    if manifest.exists() or manifest.is_symlink():
        return False
    if any(
        (resolved.parent / spec.directory).exists()
        for spec in MIGRATION.REPOSITORIES
        if spec.key != "plugify"
    ):
        return False
    spec = MIGRATION.SPEC_BY_KEY["plugify"]
    try:
        MIGRATION.validate_checkout(resolved, spec, spec.origin)
    except MIGRATION.WorkspaceError:
        return False
    lock = WorkspaceLock(resolved.parent, lock_timeout)
    with lock as leader:
        if not leader:
            if lock.wait_timed_out:
                print("Plugify workspace sync attention: plugify:lock-timeout")
            elif lock.error:
                print("Plugify workspace sync attention: plugify:lock-error")
            return True
        if lock.reclaimed_stale:
            print("Plugify workspace sync attention: workspace:stale-lock-reclaimed")
        try:
            error = run_asset_refresh(resolved, plugify_updated=False, timeout=timeout)
        except BaseException:
            error = "asset-sync-failed"
    if error is not None:
        print(f"Plugify workspace sync attention: plugify:{error}")
    return True


def main() -> int:
    args = parse_args()
    warnings: list[RepoResult] = []
    updated: list[str] = []
    workspace_validation = False
    repo_root = args.repo_root.expanduser()
    try:
        root, origins, repositories = validate_workspace(repo_root)
        MIGRATION.validate_noninteractive_askpass_helper()
    except (OSError, RuntimeError, MIGRATION.WorkspaceError):
        if refresh_standalone_plugify(
            repo_root, timeout=args.git_timeout, lock_timeout=args.lock_timeout
        ):
            return 0
        # A broken identity contract must prevent every network request, but should
        # not brick the coding session, disclose local paths, or execute code from
        # a checkout whose identity was not proven.
        print("Plugify workspace sync attention: workspace-validation")
        return 0

    lock = WorkspaceLock(root, args.lock_timeout)
    with lock as leader:
        if not leader:
            if lock.wait_timed_out:
                print("Plugify workspace sync attention: workspace:lock-timeout")
            elif lock.error:
                print("Plugify workspace sync attention: workspace:lock-error")
            return 0
        if lock.reclaimed_stale:
            # 이전 세션의 리더가 죽어 남긴 잠금을 치우고 이어받았다 — 한 번은 보이게 남긴다.
            warnings.append(RepoResult("workspace", "stale-lock-reclaimed"))
        try:
            with tempfile.TemporaryDirectory(prefix="plugify-empty-hooks-") as hooks:
                hooks_path = Path(hooks)
                for spec, path, fetch_origin in repositories:
                    result = sync_repository(
                        path,
                        spec,
                        origins[spec.key],
                        fetch_origin,
                        timeout=max(0.1, args.git_timeout),
                        hooks_path=hooks_path,
                    )
                    if result.updated:
                        updated.append(result.name)
                        if result.state != "updated":
                            warnings.append(result)
                    elif result.state != "current":
                        warnings.append(result)
            plugify_spec, plugify_path, _ = next(
                item for item in repositories if item[0].key == "plugify"
            )
            try:
                MIGRATION.validate_checkout(
                    plugify_path, plugify_spec, origins["plugify"]
                )
            except MIGRATION.WorkspaceError:
                warnings.append(RepoResult("plugify", "asset-identity-changed"))
            else:
                asset_error = run_asset_refresh(
                    repo_root.resolve(strict=True),
                    plugify_updated="plugify" in updated,
                    timeout=args.git_timeout,
                )
                if asset_error is not None:
                    warnings.append(RepoResult("plugify", asset_error))
        except MIGRATION.WorkspaceError:
            workspace_validation = True
        except BaseException:
            # SessionStart is best-effort. Do not expose exception text, command
            # stderr, paths, URLs, or filenames to the agent context.
            warnings.append(RepoResult("workspace", "unexpected-error"))

    if updated:
        print(f"Plugify workspace sync: updated {','.join(updated)}")
    if workspace_validation:
        print("Plugify workspace sync attention: workspace-validation")
    elif warnings:
        summary = ",".join(f"{item.name}:{item.state}" for item in warnings)
        print(f"Plugify workspace sync attention: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
