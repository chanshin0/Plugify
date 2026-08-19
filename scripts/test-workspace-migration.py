#!/usr/bin/env python3
"""Deterministic local tests for scripts/workspace-migrate.py."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATE = ROOT / "scripts" / "workspace-migrate.py"
REPO_NAMES = ("plugify", "second_brain", "godowon-office")
DIRECTORIES = {
    "plugify": "Plugify",
    "second_brain": "second_brain",
    "godowon-office": "godowon-office",
}
CANONICAL = {
    "plugify": "https://github.com/chanshin0/Plugify.git",
    "second_brain": "https://github.com/chanshin0/second_brain.git",
    "godowon-office": "https://github.com/chanshin0/godowon-office.git",
}


def command(
    *arguments: str,
    cwd: Path | None = None,
    check: bool = True,
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
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(arguments)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return command("git", "-C", str(repo), *arguments, check=check)


class WorkspaceMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="plugify-workspace-test-")
        self.base = Path(self.temporary.name)
        self.remotes = self.base / "remotes"
        self.remotes.mkdir()
        self.remote_paths = {name: self.make_remote(name) for name in REPO_NAMES}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_remote(self, name: str) -> Path:
        source = self.base / f"source-{name}"
        source.mkdir()
        git(source, "init", "--quiet")
        git(source, "checkout", "--quiet", "-b", "main")
        git(source, "config", "user.name", "Workspace Test")
        git(source, "config", "user.email", "workspace-test@localhost")
        (source / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        git(source, "add", "README.md")
        git(source, "commit", "--quiet", "-m", "fixture")
        bare = self.remotes / f"{name}.git"
        command("git", "clone", "--quiet", "--bare", str(source), str(bare))
        return bare

    def migration_args(self, workspace: Path) -> list[str]:
        args = ["python3", str(MIGRATE), "--root", str(workspace)]
        for name in REPO_NAMES:
            args.extend(("--repo-url", f"{name}={self.remote_paths[name]}"))
        return args

    def run_migration(
        self,
        workspace: Path,
        *extra: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        clean_env = os.environ.copy()
        for key in ("PLUGIFY_HOME", "SECOND_BRAIN_HOME", "GODOWON_OFFICE_HOME"):
            clean_env.pop(key, None)
        if env:
            clean_env.update(env)
        return command(
            *self.migration_args(workspace),
            *extra,
            check=False,
            cwd=self.base,
            env=clean_env,
        )

    def clone_fixture(self, workspace: Path, name: str, origin: str | None = None) -> Path:
        workspace.mkdir(parents=True, exist_ok=True)
        target = workspace / DIRECTORIES[name]
        command("git", "clone", "--quiet", str(self.remote_paths[name]), str(target))
        if origin is not None:
            git(target, "remote", "set-url", "origin", origin)
        return target

    def test_default_is_dry_run_and_creates_nothing(self) -> None:
        workspace = self.base / "new-workspace"
        result = self.run_migration(workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY-RUN complete", result.stdout)
        self.assertFalse(workspace.exists())

    def test_apply_clones_records_configures_and_is_idempotent(self) -> None:
        workspace = self.base / "workspace"
        workspace.mkdir()
        artifact = workspace / "local-validation-artifacts"
        artifact.mkdir()
        (artifact / "keep.txt").write_text("preserve\n", encoding="utf-8")
        fake_home = self.base / "global-config-home"
        fake_home.mkdir()
        (fake_home / ".gitconfig").write_text(
            "[core]\n\tautocrlf = true\n", encoding="utf-8"
        )
        first = self.run_migration(
            workspace, "--apply", env={"HOME": str(fake_home)}
        )
        self.assertEqual(first.returncode, 0, first.stderr)

        for name in REPO_NAMES:
            repo = workspace / DIRECTORIES[name]
            self.assertTrue((repo / ".git").exists())
            self.assertEqual(git(repo, "config", "--local", "--get", "core.autocrlf").stdout.strip(), "false")
            self.assertEqual(git(repo, "config", "--local", "--get", "core.eol").stdout.strip(), "lf")
            self.assertNotIn(b"\r\n", (repo / "README.md").read_bytes())
        router_before = (workspace / "AGENTS.md").read_bytes()
        manifest_before = (workspace / ".plugify-workspace.json").read_bytes()
        manifest = json.loads(manifest_before)
        self.assertEqual(manifest["layout"], "independent-sibling-repositories")
        self.assertEqual(set(manifest["repositories"]), set(REPO_NAMES))

        second = self.run_migration(workspace, "--apply")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((workspace / "AGENTS.md").read_bytes(), router_before)
        self.assertEqual((workspace / ".plugify-workspace.json").read_bytes(), manifest_before)
        self.assertEqual((artifact / "keep.txt").read_text(encoding="utf-8"), "preserve\n")

        verified = self.run_migration(workspace, "--verify")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("VERIFIED", verified.stdout)

        router_target = workspace / "router-copy.md"
        router_target.write_bytes(router_before)
        (workspace / "AGENTS.md").unlink()
        (workspace / "AGENTS.md").symlink_to(router_target)
        symlink_verify = self.run_migration(workspace, "--verify")
        self.assertEqual(symlink_verify.returncode, 2)
        self.assertIn("is a symlink", symlink_verify.stderr)
        (workspace / "AGENTS.md").unlink()

        (workspace / "AGENTS.md").write_text(
            "<!-- plugify-workspace-router:v1 -->\n# stale managed router\n",
            encoding="utf-8",
        )
        refreshed = self.run_migration(workspace, "--apply")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        self.assertEqual((workspace / "AGENTS.md").read_bytes(), router_before)

    def test_wrong_remote_fails_before_any_write(self) -> None:
        workspace = self.base / "wrong-remote-workspace"
        plugify = self.clone_fixture(workspace, "plugify")
        wrong = self.base / "wrong.git"
        command("git", "init", "--quiet", "--bare", str(wrong))
        git(plugify, "remote", "set-url", "origin", str(wrong))

        result = self.run_migration(workspace, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("wrong origin", result.stderr)
        self.assertFalse((workspace / "second_brain").exists())
        self.assertFalse((workspace / "AGENTS.md").exists())
        self.assertIsNone(self.local_config(plugify, "core.autocrlf"))

    def test_dirty_checkout_is_preserved_and_requires_opt_in(self) -> None:
        workspace = self.base / "dirty-workspace"
        repos = {name: self.clone_fixture(workspace, name) for name in REPO_NAMES}
        changed = repos["second_brain"] / "README.md"
        changed.write_text("local uncommitted work\n", encoding="utf-8")
        sensitive_name = "confidential-client-name.txt"
        (repos["second_brain"] / sensitive_name).write_text("private\n", encoding="utf-8")

        blocked = self.run_migration(workspace, "--apply")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("dirty checkout", blocked.stderr)
        self.assertNotIn(sensitive_name, blocked.stdout + blocked.stderr)
        self.assertEqual(changed.read_text(encoding="utf-8"), "local uncommitted work\n")
        self.assertFalse((workspace / "AGENTS.md").exists())

        allowed = self.run_migration(workspace, "--apply", "--allow-dirty")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(changed.read_text(encoding="utf-8"), "local uncommitted work\n")

    def test_dry_run_and_verify_do_not_refresh_git_indexes(self) -> None:
        workspace = self.base / "read-only-metadata-workspace"
        applied = self.run_migration(workspace, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        fsmonitor_marker = self.base / "fsmonitor-called"
        fsmonitor = self.base / "fsmonitor-hook"
        fsmonitor.write_text(
            "#!/bin/sh\n"
            f"printf called > {fsmonitor_marker}\n"
            "exit 1\n",
            encoding="utf-8",
        )
        fsmonitor.chmod(0o755)
        indexes = []
        for name in REPO_NAMES:
            repo = workspace / DIRECTORIES[name]
            git(repo, "config", "core.fsmonitor", str(fsmonitor))
            tracked = repo / "README.md"
            stat = tracked.stat()
            os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
            index = repo / ".git" / "index"
            indexes.append((index, index.read_bytes(), index.stat().st_mtime_ns))

        for mode in ((), ("--verify",)):
            with self.subTest(mode=mode or ("dry-run",)):
                result = self.run_migration(workspace, *mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                for index, before_bytes, before_mtime in indexes:
                    self.assertEqual(index.read_bytes(), before_bytes)
                    self.assertEqual(index.stat().st_mtime_ns, before_mtime)
                self.assertFalse(fsmonitor_marker.exists())

    def test_custom_root_router_is_never_overwritten(self) -> None:
        workspace = self.base / "custom-router-workspace"
        workspace.mkdir()
        custom = workspace / "AGENTS.md"
        custom.write_text("# My local rules\n", encoding="utf-8")

        result = self.run_migration(workspace, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("un-managed AGENTS.md", result.stderr)
        self.assertEqual(custom.read_text(encoding="utf-8"), "# My local rules\n")
        for name in REPO_NAMES:
            self.assertFalse((workspace / DIRECTORIES[name]).exists())

    def test_symlink_router_is_never_replaced(self) -> None:
        workspace = self.base / "symlink-router-workspace"
        workspace.mkdir()
        target = self.base / "router-target.md"
        target.write_text("# keep me\n", encoding="utf-8")
        (workspace / "AGENTS.md").symlink_to(target)

        result = self.run_migration(workspace, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("is a symlink", result.stderr)
        self.assertTrue((workspace / "AGENTS.md").is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "# keep me\n")

    def test_broken_repository_symlink_is_never_replaced(self) -> None:
        workspace = self.base / "broken-repo-link-workspace"
        workspace.mkdir()
        plugify = workspace / "Plugify"
        plugify.symlink_to(self.base / "does-not-exist")

        result = self.run_migration(workspace, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("physical sibling checkout required", result.stderr)
        self.assertTrue(plugify.is_symlink())
        self.assertFalse((workspace / "second_brain").exists())

    def test_valid_repository_symlink_fails_apply_and_verify(self) -> None:
        workspace = self.base / "valid-repo-link-workspace"
        workspace.mkdir()
        outside = self.clone_fixture(self.base / "outside-repo", "plugify")
        (workspace / "Plugify").symlink_to(outside, target_is_directory=True)

        for mode in ("--apply", "--verify"):
            with self.subTest(mode=mode):
                result = self.run_migration(workspace, mode)
                self.assertEqual(result.returncode, 2)
                self.assertIn("physical sibling checkout required", result.stderr)
                self.assertTrue((workspace / "Plugify").is_symlink())

    def test_failed_clone_removes_its_temporary_directory(self) -> None:
        workspace = self.base / "failed-clone-workspace"
        missing_remote = self.base / "missing-private-repo.git"
        args = [
            "python3",
            str(MIGRATE),
            "--root",
            str(workspace),
            "--apply",
            "--repo-url",
            f"plugify={missing_remote}",
        ]
        for name in ("second_brain", "godowon-office"):
            args.extend(("--repo-url", f"{name}={self.remote_paths[name]}"))

        result = command(*args, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("clone failed for plugify", result.stderr)
        leftovers = [path for path in workspace.iterdir() if ".plugify-clone-" in path.name]
        self.assertEqual(leftovers, [])
        self.assertFalse((workspace / "Plugify").exists())

    def test_github_https_and_ssh_origins_are_equivalent(self) -> None:
        workspace = self.base / "github-origin-workspace"
        forms = {
            "plugify": "git@github.com:chanshin0/Plugify.git",
            "second_brain": "ssh://git@github.com:22/chanshin0/second_brain.git",
            "godowon-office": "https://github.com:443/chanshin0/godowon-office",
        }
        for name in REPO_NAMES:
            self.clone_fixture(workspace, name, forms[name])

        args = ["python3", str(MIGRATE), "--root", str(workspace), "--apply"]
        result = command(*args, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_default_remote_port_is_a_distinct_identity(self) -> None:
        workspace = self.base / "non-default-port-workspace"
        for name in REPO_NAMES:
            origin = CANONICAL[name]
            if name == "plugify":
                origin = "ssh://git@github.com:2222/chanshin0/Plugify.git"
            self.clone_fixture(workspace, name, origin)

        result = command(
            "python3", str(MIGRATE), "--root", str(workspace), "--apply", check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("wrong origin", result.stderr)
        self.assertIn(":2222/", result.stderr)

    def test_insecure_or_unsupported_network_schemes_are_rejected_before_clone(self) -> None:
        for scheme in ("http", "git", "ftp", "custom"):
            with self.subTest(scheme=scheme):
                workspace = self.base / f"scheme-{scheme}-workspace"
                result = command(
                    "python3",
                    str(MIGRATE),
                    "--root",
                    str(workspace),
                    "--apply",
                    "--repo-url",
                    f"plugify={scheme}://github.com/chanshin0/Plugify.git",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("unsupported or insecure Git remote scheme", result.stderr)
                self.assertFalse(workspace.exists())

    def test_non_github_scp_remote_paths_remain_case_sensitive(self) -> None:
        workspace = self.base / "case-sensitive-mirror-workspace"
        for name in REPO_NAMES:
            origin = CANONICAL[name]
            if name == "plugify":
                origin = "git@mirror.example:Team/Private.git"
            self.clone_fixture(workspace, name, origin)

        result = command(
            "python3",
            str(MIGRATE),
            "--root",
            str(workspace),
            "--apply",
            "--repo-url",
            "plugify=git@mirror.example:team/private.git",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("wrong origin", result.stderr)

    def test_non_github_dot_git_suffix_is_not_collapsed(self) -> None:
        for suffix in ("", ".GIT"):
            with self.subTest(suffix=suffix):
                workspace = self.base / f"dot-git-{suffix or 'none'}-workspace"
                for name in REPO_NAMES:
                    origin = CANONICAL[name]
                    if name == "plugify":
                        origin = "git@mirror.example:Team/Private.git"
                    self.clone_fixture(workspace, name, origin)

                result = command(
                    "python3",
                    str(MIGRATE),
                    "--root",
                    str(workspace),
                    "--apply",
                    "--repo-url",
                    f"plugify=git@mirror.example:Team/Private{suffix}",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("wrong origin", result.stderr)

    def test_file_url_authority_is_part_of_remote_identity(self) -> None:
        workspace = self.base / "file-authority-workspace"
        for name in REPO_NAMES:
            origin = CANONICAL[name]
            if name == "plugify":
                origin = "file://server-a/share/Private.git"
            self.clone_fixture(workspace, name, origin)

        result = command(
            "python3",
            str(MIGRATE),
            "--root",
            str(workspace),
            "--apply",
            "--repo-url",
            "plugify=file://server-b/share/Private.git",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("wrong origin", result.stderr)

    def test_non_github_ssh_username_is_part_of_remote_identity(self) -> None:
        forms = (
            ("ssh://alice@mirror.example/Team/Private.git", "ssh://bob@mirror.example/Team/Private.git"),
            ("alice@mirror.example:Team/Private.git", "bob@mirror.example:Team/Private.git"),
        )
        for index, (actual, expected) in enumerate(forms):
            with self.subTest(form=actual):
                workspace = self.base / f"ssh-user-{index}-workspace"
                for name in REPO_NAMES:
                    origin = actual if name == "plugify" else CANONICAL[name]
                    self.clone_fixture(workspace, name, origin)
                result = command(
                    "python3",
                    str(MIGRATE),
                    "--root",
                    str(workspace),
                    "--apply",
                    "--repo-url",
                    f"plugify={expected}",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("wrong origin", result.stderr)
                output = result.stdout + result.stderr
                self.assertNotIn("alice", output)
                self.assertNotIn("bob", output)
                self.assertNotIn("Team/", output)

    def test_effective_push_urls_must_match_and_never_leak_passwords(self) -> None:
        workspace = self.base / "push-url-workspace"
        applied = self.run_migration(workspace, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        target = workspace / "second_brain"
        wrong = self.base / "wrong-push.git"
        command("git", "init", "--quiet", "--bare", str(wrong))
        git(target, "remote", "set-url", "--add", "--push", "origin", str(wrong))

        rejected = self.run_migration(workspace, "--verify")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("wrong push URL", rejected.stderr)

        git(target, "config", "--unset-all", "remote.origin.pushurl")
        secret = "push-password-must-never-leak"
        git(
            target,
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            f"ssh://git:{secret}@github.com/chanshin0/second_brain.git",
        )
        secret_rejected = self.run_migration(workspace, "--verify")
        combined = secret_rejected.stdout + secret_rejected.stderr
        self.assertEqual(secret_rejected.returncode, 2)
        self.assertIn("URL password", secret_rejected.stderr)
        self.assertNotIn(secret, combined)
        self.assertNotIn(secret, (workspace / ".plugify-workspace.json").read_text(encoding="utf-8"))

    def test_workspace_container_cannot_be_a_git_worktree_or_descendant(self) -> None:
        for nested in (False, True):
            with self.subTest(nested=nested):
                outer = self.base / f"outer-git-{nested}"
                outer.mkdir()
                git(outer, "init", "--quiet")
                workspace = outer / "workspace" if nested else outer
                result = self.run_migration(workspace, "--apply")
                self.assertEqual(result.returncode, 2)
                self.assertIn("inside an existing Git worktree", result.stderr)
                self.assertFalse((workspace / "AGENTS.md").exists())

    def test_workspace_container_cannot_be_git_metadata_or_bare_repository(self) -> None:
        worktree = self.base / "metadata-parent"
        worktree.mkdir()
        git(worktree, "init", "--quiet")
        bare = self.base / "bare.git"
        command("git", "init", "--quiet", "--bare", str(bare))
        candidates = (
            worktree / ".git",
            worktree / ".git" / "objects",
            bare,
            bare / "objects",
        )
        for workspace in candidates:
            with self.subTest(workspace=workspace):
                result = self.run_migration(workspace, "--apply")
                self.assertEqual(result.returncode, 2)
                self.assertIn("inside Git metadata or a bare repository", result.stderr)
                self.assertFalse((workspace / "AGENTS.md").exists())

    def test_inherited_git_context_cannot_redirect_workspace_operations(self) -> None:
        workspace = self.base / "sanitized-context-workspace"
        external = self.base / "external-context"
        external.mkdir()
        git(external, "init", "--quiet")
        sentinel = external / "sentinel.txt"
        sentinel.write_text("untouched\n", encoding="utf-8")
        env = {
            "GIT_DIR": str(external / ".git"),
            "GIT_WORK_TREE": str(external),
            "GIT_INDEX_FILE": str(external / "alternate-index"),
            "GIT_CEILING_DIRECTORIES": str(workspace),
            "GIT_SHALLOW_FILE": str(external / "fake-shallow"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.bare",
            "GIT_CONFIG_VALUE_0": "true",
        }
        result = self.run_migration(workspace, "--apply", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched\n")
        self.assertFalse((external / "alternate-index").exists())
        self.assertTrue((workspace / "AGENTS.md").is_file())

    def test_case_colliding_required_name_is_rejected(self) -> None:
        workspace = self.base / "case-collision-workspace"
        workspace.mkdir()
        collision = workspace / "plugify"
        collision.mkdir()
        if (workspace / "Plugify").exists():
            self.skipTest("filesystem is case-insensitive")
        marker = collision / "keep.txt"
        marker.write_text("preserve\n", encoding="utf-8")

        result = self.run_migration(workspace, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("case-colliding workspace child", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((workspace / "Plugify").exists())

    def test_clone_neutralizes_askpass_and_uses_batch_ssh(self) -> None:
        workspace = self.base / "askpass-workspace"
        fake_bin = self.base / "fake-git-bin"
        fake_bin.mkdir()
        marker = self.base / "inherited-askpass-called"
        capture = self.base / "clone-environment.json"
        inherited_askpass = self.base / "inherited-askpass.py"
        inherited_askpass.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('called', encoding='utf-8')\n",
            encoding="utf-8",
        )
        inherited_askpass.chmod(0o755)
        real_git = subprocess.check_output(["which", "git"], text=True).strip()
        fake_git = fake_bin / "git"
        fake_git.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            f"capture = Path({str(capture)!r})\n"
            "if 'clone' in sys.argv[1:]:\n"
            "    keys = ('GIT_TERMINAL_PROMPT', 'GIT_ASKPASS', 'SSH_ASKPASS', "
            "'SSH_ASKPASS_REQUIRE', 'GCM_INTERACTIVE', 'GIT_SSH_COMMAND', "
            "'GIT_DIR', 'GIT_WORK_TREE', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', "
            "'GIT_OPTIONAL_LOCKS', 'GIT_CONFIG_GLOBAL', 'GIT_EXEC_PATH', "
            "'GIT_TEMPLATE_DIR', 'GIT_TRACE', 'GIT_CURL_VERBOSE')\n"
            "    capture.write_text(json.dumps({key: os.environ.get(key) for key in keys}), encoding='utf-8')\n"
            "    raise SystemExit(1)\n"
            f"os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        fake_git.chmod(0o755)
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "GIT_ASKPASS": str(inherited_askpass),
            "SSH_ASKPASS": str(inherited_askpass),
            "GIT_DIR": str(self.base / "wrong.git"),
            "GIT_WORK_TREE": str(self.base / "wrong-worktree"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.askPass",
            "GIT_CONFIG_VALUE_0": str(inherited_askpass),
            "GIT_CONFIG_GLOBAL": str(self.base / "untrusted-global-config"),
            "GIT_EXEC_PATH": str(self.base / "untrusted-exec-path"),
            "GIT_TEMPLATE_DIR": str(self.base / "untrusted-template"),
            "GIT_TRACE": str(self.base / "untrusted-trace"),
            "GIT_CURL_VERBOSE": "1",
        }
        result = self.run_migration(workspace, "--apply", env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("clone failed", result.stderr)
        self.assertFalse(marker.exists())
        recorded = json.loads(capture.read_text(encoding="utf-8"))
        self.assertEqual(recorded["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(Path(recorded["GIT_ASKPASS"]), ROOT / "scripts" / "no-askpass.py")
        self.assertEqual(recorded["SSH_ASKPASS"], recorded["GIT_ASKPASS"])
        self.assertEqual(recorded["SSH_ASKPASS_REQUIRE"], "never")
        self.assertEqual(recorded["GCM_INTERACTIVE"], "Never")
        self.assertIn("BatchMode=yes", recorded["GIT_SSH_COMMAND"])
        self.assertIn("StrictHostKeyChecking=yes", recorded["GIT_SSH_COMMAND"])
        self.assertEqual(recorded["GIT_OPTIONAL_LOCKS"], "0")
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0"):
            self.assertIsNone(recorded[key])
        for key in (
            "GIT_CONFIG_GLOBAL",
            "GIT_EXEC_PATH",
            "GIT_TEMPLATE_DIR",
            "GIT_TRACE",
            "GIT_CURL_VERBOSE",
        ):
            self.assertIsNone(recorded[key])

    def test_clone_ignores_malicious_git_template_hooks(self) -> None:
        workspace = self.base / "template-hook-workspace"
        malicious_template = self.base / "malicious-template"
        hooks = malicious_template / "hooks"
        hooks.mkdir(parents=True)
        marker = self.base / "template-hook-ran"
        hook = hooks / "post-checkout"
        hook.write_text(
            "#!/bin/sh\n"
            f"printf called > {marker}\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)
        fsmonitor_marker = self.base / "clone-fsmonitor-ran"
        fsmonitor = self.base / "clone-fsmonitor"
        fsmonitor.write_text(
            "#!/bin/sh\n"
            f"printf called > {fsmonitor_marker}\n",
            encoding="utf-8",
        )
        fsmonitor.chmod(0o755)
        fake_home = self.base / "template-home"
        fake_home.mkdir()
        (fake_home / ".gitconfig").write_text(
            f"[init]\n\ttemplateDir = {malicious_template}\n"
            f"[core]\n\thooksPath = {hooks}\n\tfsmonitor = {fsmonitor}\n",
            encoding="utf-8",
        )

        result = self.run_migration(
            workspace,
            "--apply",
            env={
                "HOME": str(fake_home),
                "GIT_TEMPLATE_DIR": str(malicious_template),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse(fsmonitor_marker.exists())
        for name in REPO_NAMES:
            self.assertFalse(
                (workspace / DIRECTORIES[name] / ".git" / "hooks" / "post-checkout").exists()
            )

    def test_resolve_prefers_explicit_override_then_plugify_sibling(self) -> None:
        workspace = self.base / "resolve-workspace"
        plugify = self.clone_fixture(workspace, "plugify", CANONICAL["plugify"])
        sibling = self.clone_fixture(workspace, "second_brain", CANONICAL["second_brain"])
        outside = self.clone_fixture(self.base / "outside", "second_brain", CANONICAL["second_brain"])

        env = os.environ.copy()
        env.update({"PLUGIFY_HOME": str(plugify), "SECOND_BRAIN_HOME": str(outside)})
        explicit = command("python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(Path(explicit.stdout.strip()), outside.resolve())

        env.pop("SECOND_BRAIN_HOME")
        defaulted = command("python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False)
        self.assertEqual(defaulted.returncode, 0, defaulted.stderr)
        self.assertEqual(Path(defaulted.stdout.strip()), sibling.resolve())

        sibling.rename(workspace / "second_brain-missing")
        missing = command("python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("missing second_brain", missing.stderr)

    def test_resolve_rejects_relative_or_wrong_override(self) -> None:
        relative_env = os.environ.copy()
        relative_env["SECOND_BRAIN_HOME"] = "relative/second_brain"
        relative = command(
            "python3", str(MIGRATE), "--resolve", "second_brain", env=relative_env, check=False
        )
        self.assertEqual(relative.returncode, 2)
        self.assertIn("must be an absolute path", relative.stderr)

        wrong = self.clone_fixture(
            self.base / "wrong-override", "second_brain", CANONICAL["plugify"]
        )
        wrong_env = os.environ.copy()
        wrong_env["SECOND_BRAIN_HOME"] = str(wrong)
        rejected = command(
            "python3", str(MIGRATE), "--resolve", "second_brain", env=wrong_env, check=False
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("wrong origin", rejected.stderr)

    def test_credential_bearing_url_is_rejected_without_leaking_secret(self) -> None:
        cases = {
            "https-userinfo": "https://{secret}@github.com/chanshin0/Plugify.git",
            "ssh-password": "ssh://git:{secret}@github.com/chanshin0/Plugify.git",
            "git-password": "git://reader:{secret}@github.com/chanshin0/Plugify.git",
        }
        for label, pattern in cases.items():
            with self.subTest(label=label):
                workspace = self.base / f"secret-url-{label}"
                secret = f"never-print-{label}"
                result = command(
                    "python3",
                    str(MIGRATE),
                    "--root",
                    str(workspace),
                    "--apply",
                    "--repo-url",
                    f"plugify={pattern.format(secret=secret)}",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertFalse((workspace / ".plugify-workspace.json").exists())

    def test_mirror_manifest_drives_resolver_and_is_strictly_validated(self) -> None:
        workspace = self.base / "mirror-workspace"
        applied = self.run_migration(workspace, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        env = os.environ.copy()
        env["PLUGIFY_HOME"] = str(workspace / "Plugify")

        resolved = command(
            "python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False
        )
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertEqual(Path(resolved.stdout.strip()), (workspace / "second_brain").resolve())

        manifest_path = workspace / ".plugify-workspace.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["repositories"]["second_brain"]["unexpected"] = "not-trusted"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        invalid = command(
            "python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("entry fields are invalid", invalid.stderr)

        secret = "manifest-password-must-never-leak"
        del manifest["repositories"]["second_brain"]["unexpected"]
        manifest["repositories"]["second_brain"]["origin"] = (
            f"ssh://git:{secret}@github.com/chanshin0/second_brain.git"
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        credential_rejected = command(
            "python3", str(MIGRATE), "--resolve", "second_brain", env=env, check=False
        )
        self.assertEqual(credential_rejected.returncode, 2)
        self.assertIn("URL password", credential_rejected.stderr)
        self.assertNotIn(secret, credential_rejected.stdout + credential_rejected.stderr)

    def test_windows_drive_and_unc_remotes_normalize_without_path_disclosure(self) -> None:
        workspace = self.base / "windows-remote-workspace"
        origins = {
            "plugify": r"C:\Repos\Plugify.git",
            "second_brain": r"\\Server\Private\second_brain.git",
            "godowon-office": CANONICAL["godowon-office"],
        }
        expected = {
            "plugify": "c:/repos/plugify.git",
            "second_brain": "//server/private/second_brain.git",
            "godowon-office": CANONICAL["godowon-office"],
        }
        for name in REPO_NAMES:
            self.clone_fixture(workspace, name, origins[name])

        args = ["python3", str(MIGRATE), "--root", str(workspace), "--apply"]
        for name in REPO_NAMES:
            args.extend(("--repo-url", f"{name}={expected[name]}"))
        result = command(*args, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (result.stdout + result.stderr).casefold()
        self.assertNotIn("c:/repos", output)
        self.assertNotIn("server/private", output)

    def test_product_scan_scripts_share_portable_precedence(self) -> None:
        expected = 'PROJECTS_DIR="${1:-${PLUGIFY_PROJECTS_DIR:-$HOME/Projects}}"'
        for relative in (
            "scripts/status.sh",
            "scripts/heartbeat.sh",
            "scripts/telemetry-digest.sh",
        ):
            content = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(expected, content, relative)

    @staticmethod
    def local_config(repo: Path, key: str) -> str | None:
        result = git(repo, "config", "--local", "--get", key, check=False)
        return result.stdout.strip() if result.returncode == 0 else None


if __name__ == "__main__":
    unittest.main(verbosity=2)
