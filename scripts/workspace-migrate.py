#!/usr/bin/env python3
"""Plan, apply, verify, or resolve the portable three-repository workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse


SCRIPT_REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTER_TEMPLATE = SCRIPT_REPO_ROOT / "templates" / "workspace" / "AGENTS.md"
ROUTER_MARKER = "<!-- plugify-workspace-router:v1 -->"
MANIFEST_NAME = ".plugify-workspace.json"
MANAGED_BY = "Plugify/scripts/workspace-migrate.py"
DEFAULT_REMOTE_PORTS = {"http": 80, "https": 443, "ssh": 22, "git": 9418}
NO_ASKPASS = SCRIPT_REPO_ROOT / "scripts" / "no-askpass.py"
GIT_CONTEXT_VARIABLES = {
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_SHALLOW_FILE",
    "GIT_NAMESPACE",
    "GIT_GRAFT_FILE",
    "GIT_REPLACE_REF_BASE",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR",
    "GIT_CURL_VERBOSE",
    "GIT_REDIRECT_STDERR",
}


class WorkspaceError(RuntimeError):
    """A fail-closed workspace validation error."""


@dataclass(frozen=True)
class RepoSpec:
    key: str
    directory: str
    environment: str
    origin: str


REPOSITORIES = (
    RepoSpec("plugify", "Plugify", "PLUGIFY_HOME", "https://github.com/chanshin0/Plugify.git"),
    RepoSpec(
        "second_brain",
        "second_brain",
        "SECOND_BRAIN_HOME",
        "https://github.com/chanshin0/second_brain.git",
    ),
    RepoSpec(
        "godowon-office",
        "godowon-office",
        "GODOWON_OFFICE_HOME",
        "https://github.com/chanshin0/godowon-office.git",
    ),
)
SPEC_BY_KEY = {spec.key: spec for spec in REPOSITORIES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create and verify Plugify, second_brain, and godowon-office as independent "
            "sibling repositories. The default mode is a read-only plan."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Workspace container (default: parent of the active Plugify checkout).",
    )
    parser.add_argument("--apply", action="store_true", help="Apply the validated plan.")
    parser.add_argument("--verify", action="store_true", help="Read-only strict verification.")
    parser.add_argument(
        "--install",
        action="store_true",
        help="After --apply, run the target Plugify scripts/install.sh (changes user tool config).",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permit dirty existing checkouts without modifying their working trees.",
    )
    parser.add_argument(
        "--resolve",
        choices=tuple(SPEC_BY_KEY),
        metavar="REPOSITORY",
        help="Print one validated repository path using env override, then Plugify sibling.",
    )
    parser.add_argument(
        "--repo-url",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="Override an expected clone/remote URL (repeatable; useful for approved mirrors).",
    )
    args = parser.parse_args()

    if args.apply and args.verify:
        parser.error("--apply and --verify are mutually exclusive")
    if args.install and not args.apply:
        parser.error("--install requires --apply")
    if args.resolve and (
        args.root or args.apply or args.verify or args.install or args.allow_dirty or args.repo_url
    ):
        parser.error("--resolve cannot be combined with migration options")
    return args


def run(
    command: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise WorkspaceError(f"command failed: {redacted_command(command)}\n{redact_text(detail)}")
    return result


def clean_git_environment(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Remove inherited repository/index routing while preserving normal Git config."""
    env = dict(os.environ)
    for key in list(env):
        if key in GIT_CONTEXT_VARIABLES or key.startswith(
            ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE")
        ):
            env.pop(key, None)
    # Diagnostic commands such as status must not refresh index stat data in
    # dry-run/verify mode. Required writes (clone/config) still take locks.
    env["GIT_OPTIONAL_LOCKS"] = "0"
    if overrides:
        env.update(overrides)
    return env


def validate_noninteractive_askpass_helper() -> Path:
    helper = NO_ASKPASS
    if helper.is_symlink() or not helper.is_file() or not os.access(helper, os.X_OK):
        raise WorkspaceError(f"noninteractive askpass helper is missing or unsafe: {helper}")
    return helper


def git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["git", "-C", str(repo), *arguments],
        check=check,
        env=clean_git_environment(),
    )


def normalized_git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.eol=lf",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(repo),
            *arguments,
        ],
        check=check,
        env=clean_git_environment(),
    )


def absolute_path(raw: str, label: str) -> Path:
    if not raw.strip():
        raise WorkspaceError(f"{label} is set but empty")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise WorkspaceError(f"{label} must be an absolute path: {raw}")
    return path.resolve(strict=False)


def active_plugify_root() -> Path:
    configured = os.environ.get("PLUGIFY_HOME")
    if configured is not None:
        return absolute_path(configured, "PLUGIFY_HOME")
    return SCRIPT_REPO_ROOT


def workspace_root(argument: Path | None) -> Path:
    if argument is not None:
        expanded = argument.expanduser()
        if not expanded.is_absolute():
            expanded = Path.cwd() / expanded
        return expanded.resolve(strict=False)
    return active_plugify_root().parent


def github_slug(path: str) -> str:
    """Canonicalize only GitHub's documented owner/repository URL forms."""
    value = path.strip().strip("/")
    return value[:-4] if value.casefold().endswith(".git") else value


def windows_remote_identity(value: str) -> str | None:
    """Normalize drive/UNC remotes before urlparse can mistake a drive for a scheme."""
    normalized = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        return f"windows:{normalized.casefold()}"
    if normalized.startswith("//"):
        return f"windows-unc:{normalized[2:].casefold()}"
    return None


def reject_credential_remote(remote: str, label: str) -> None:
    """Reject credential-bearing network URLs before they reach logs or manifests."""
    parsed = urlparse(remote.strip())
    scheme = parsed.scheme.casefold()
    if parsed.password is not None:
        raise WorkspaceError(f"{label} contains a URL password; use a credential helper or SSH agent")
    if scheme in {"http", "https", "file"} and parsed.username is not None:
        raise WorkspaceError(f"{label} contains URL userinfo; use a credential helper or SSH remote")
    if scheme in {"http", "https", "ssh", "git", "file"} and (
        parsed.query or parsed.fragment
    ):
        raise WorkspaceError(f"{label} contains a query or fragment; refusing possible credential leakage")


def remote_identity(remote: str) -> str:
    """Normalize equivalent GitHub HTTPS/SSH URLs and stable local test remotes."""
    value = remote.strip()
    if not value:
        raise WorkspaceError("empty Git remote URL")

    windows_identity = windows_remote_identity(value)
    if windows_identity is not None:
        return windows_identity

    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme != "file":
        scheme = parsed.scheme.casefold()
        if scheme not in {"https", "ssh"}:
            raise WorkspaceError(
                f"unsupported or insecure Git remote scheme: {scheme or '<empty>'}"
            )
        host = (parsed.hostname or "").casefold()
        try:
            port = parsed.port
        except ValueError as exc:
            raise WorkspaceError("invalid port in Git remote URL") from exc
        path = unquote(parsed.path)
        effective_port = None if port in {None, DEFAULT_REMOTE_PORTS.get(scheme)} else port
        port_suffix = f":{effective_port}" if effective_port is not None else ""
        if host == "github.com":
            slug = github_slug(path).casefold()
            return f"github:{host}{port_suffix}/{slug}" if port_suffix else f"github:{slug}"
        username = unquote(parsed.username) if parsed.username is not None else None
        user_prefix = f"{username}@" if username is not None else ""
        return f"{scheme}:{user_prefix}{host}{port_suffix}{path}"

    if parsed.scheme == "file":
        try:
            port = parsed.port
        except ValueError as exc:
            raise WorkspaceError("invalid port in file Git remote URL") from exc
        if port is not None:
            raise WorkspaceError("file Git remote URL must not include a port")
        if parsed.netloc:
            host = (parsed.hostname or "").casefold()
            if not host:
                raise WorkspaceError("file Git remote URL has an invalid authority")
            return f"file-unc:{host}{unquote(parsed.path)}"
        local_path = Path(unquote(parsed.path)).expanduser().resolve(strict=False)
        return f"file:{local_path}"

    scp_match = re.fullmatch(
        r"(?:(?P<user>[^@/\s]+)@)?(?P<host>[^:/\s]+):(?P<path>.+)", value
    )
    if scp_match and not re.match(r"^[A-Za-z]:[\\/]", value):
        host = scp_match.group("host").casefold()
        path = scp_match.group("path")
        if host == "github.com":
            return f"github:{github_slug(path).casefold()}"
        username = scp_match.group("user")
        user_prefix = f"{username}@" if username is not None else ""
        return f"ssh:{user_prefix}{host}:{path}"

    return f"file:{Path(value).expanduser().resolve(strict=False)}"


def redacted_remote(remote: str) -> str:
    """Return a useful repository identity without URL userinfo or local parent paths."""
    try:
        identity = remote_identity(remote)
    except WorkspaceError:
        return "<invalid remote>"
    if identity.startswith("github:"):
        return identity
    if identity.startswith("file:"):
        return f"local:{Path(identity[5:]).name}"
    if identity.startswith(("file-unc:", "windows:", "windows-unc:")):
        return f"local:{identity.rsplit('/', 1)[-1].rsplit(':', 1)[-1]}"
    if identity.startswith(("ssh:", "https:")):
        value = remote.strip()
        parsed = urlparse(value)
        if parsed.scheme:
            scheme = parsed.scheme.casefold()
            host = (parsed.hostname or "<host>").casefold()
            try:
                port = parsed.port
            except ValueError:
                port = None
            port_suffix = f":{port}" if port is not None else ""
            leaf = unquote(parsed.path).rstrip("/").rsplit("/", 1)[-1] or "<repo>"
            return f"{scheme}:{host}{port_suffix}/{leaf}"
        scp_match = re.fullmatch(
            r"(?:(?P<user>[^@/\s]+)@)?(?P<host>[^:/\s]+):(?P<path>.+)", value
        )
        if scp_match:
            host = scp_match.group("host").casefold()
            leaf = scp_match.group("path").rstrip("/").rsplit("/", 1)[-1]
            return f"ssh:{host}/{leaf}"
        return "<network-remote>"
    return identity


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, redacted_remote(secret))
    result = re.sub(r"https?://[^\s'\"]+", "<redacted-network-url>", result)
    return result


def redacted_command(command: Iterable[str]) -> str:
    rendered: list[str] = []
    for argument in command:
        if windows_remote_identity(argument) is not None or re.match(
            r"^(?:https?|ssh|git|file)://", argument
        ) or re.match(
            r"^(?:[^@/\s]+@)?[^:/\s]+:.+", argument
        ):
            rendered.append(redacted_remote(argument))
        else:
            rendered.append(argument)
    return " ".join(rendered)


def expected_origins(overrides: Iterable[str]) -> dict[str, str]:
    result = {spec.key: spec.origin for spec in REPOSITORIES}
    for item in overrides:
        if "=" not in item:
            raise WorkspaceError("--repo-url must use NAME=URL (value omitted from error output)")
        name, url = item.split("=", 1)
        if name not in result:
            choices = ", ".join(result)
            raise WorkspaceError(f"unknown repository name in --repo-url (choose: {choices})")
        if not url.strip():
            raise WorkspaceError(f"empty URL for --repo-url {name}")
        reject_credential_remote(url, f"--repo-url {name}")
        result[name] = url
    for name, url in result.items():
        reject_credential_remote(url, f"origin for {name}")
        remote_identity(url)
    return result


def validate_checkout(path: Path, spec: RepoSpec, expected_origin: str) -> str:
    if path.is_symlink():
        raise WorkspaceError(
            f"repository path is a symlink; physical sibling checkout required: {path}"
        )
    if not path.exists():
        raise WorkspaceError(f"missing {spec.directory}: {path}")
    if not path.is_dir():
        raise WorkspaceError(f"repository path is not a directory: {path}")

    top_result = git(path, "rev-parse", "--show-toplevel", check=False)
    if top_result.returncode != 0:
        raise WorkspaceError(f"existing path is not a Git checkout; refusing to overwrite: {path}")
    top = Path(top_result.stdout.strip()).resolve(strict=False)
    if top != path.resolve(strict=False):
        raise WorkspaceError(f"expected repository root {path}, but Git root is {top}")

    origin_result = git(path, "remote", "get-url", "origin", check=False)
    if origin_result.returncode != 0:
        raise WorkspaceError(f"origin remote missing in {path}; refusing to guess repository identity")
    actual_origin = origin_result.stdout.strip()
    reject_credential_remote(actual_origin, f"origin for {spec.directory}")
    if remote_identity(actual_origin) != remote_identity(expected_origin):
        raise WorkspaceError(
            f"wrong origin for {spec.directory}; refusing to overwrite:\n"
            f"  expected identity: {redacted_remote(expected_origin)}\n"
            f"  actual identity:   {redacted_remote(actual_origin)}"
        )

    push_result = git(path, "remote", "get-url", "--push", "--all", "origin", check=False)
    if push_result.returncode != 0:
        raise WorkspaceError(f"effective origin push URL missing in {path}")
    push_urls = [line.strip() for line in push_result.stdout.splitlines() if line.strip()]
    if not push_urls:
        raise WorkspaceError(f"effective origin push URL missing in {path}")
    for push_url in push_urls:
        reject_credential_remote(push_url, f"push URL for {spec.directory}")
        if remote_identity(push_url) != remote_identity(expected_origin):
            raise WorkspaceError(
                f"wrong push URL for {spec.directory}; refusing possible data disclosure:\n"
                f"  expected identity: {redacted_remote(expected_origin)}\n"
                f"  actual identity:   {redacted_remote(push_url)}"
            )
    return actual_origin


def validate_workspace_container(root: Path) -> None:
    """Reject a container inside a Git worktree, Git metadata, or bare repo."""
    probe = root
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if probe.exists() and not probe.is_dir():
        probe = probe.parent
    inside_git_dir = git(probe, "rev-parse", "--is-inside-git-dir", check=False)
    if inside_git_dir.returncode == 0 and inside_git_dir.stdout.strip() == "true":
        raise WorkspaceError("workspace container must not be inside Git metadata or a bare repository")

    result = git(probe, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        return
    worktree = Path(result.stdout.strip()).resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_root.relative_to(worktree)
    except ValueError:
        return
    raise WorkspaceError(
        f"workspace container must not be inside an existing Git worktree: {worktree}"
    )


def validate_required_name_collisions(root: Path) -> None:
    """Reject layouts that cannot round-trip to case-insensitive devices."""
    if not root.exists():
        return
    expected = {spec.directory.casefold(): spec.directory for spec in REPOSITORIES}
    for child in root.iterdir():
        required = expected.get(child.name.casefold())
        if required is not None and child.name != required:
            raise WorkspaceError(
                f"case-colliding workspace child {child.name!r}; required spelling is {required!r}"
            )


def dirty_entries(path: Path) -> list[str]:
    result = normalized_git(path, "status", "--porcelain=v1", "--untracked-files=normal")
    return [line for line in result.stdout.splitlines() if line]


def resolve_repository(name: str) -> Path:
    spec = SPEC_BY_KEY[name]
    configured = os.environ.get(spec.environment)
    if configured is not None:
        candidate = absolute_path(configured, spec.environment)
    elif spec.key == "plugify":
        candidate = SCRIPT_REPO_ROOT
    else:
        plugify = active_plugify_root()
        candidate = plugify.parent / spec.directory

    anchor = candidate if spec.key == "plugify" else active_plugify_root()
    origins = manifest_origins(anchor.parent)
    if configured is None and spec.key != "plugify":
        validate_checkout(anchor, SPEC_BY_KEY["plugify"], origins["plugify"])
    validate_checkout(candidate, spec, origins[spec.key])
    return candidate.resolve(strict=False)


def router_template() -> str:
    try:
        content = ROUTER_TEMPLATE.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkspaceError(f"workspace router template unavailable: {ROUTER_TEMPLATE}: {exc}") from exc
    if not content.startswith(f"{ROUTER_MARKER}\n"):
        raise WorkspaceError(f"workspace router template has no managed marker: {ROUTER_TEMPLATE}")
    return content


def manifest_content(origins: dict[str, str]) -> str:
    document = {
        "schemaVersion": 1,
        "managedBy": MANAGED_BY,
        "layout": "independent-sibling-repositories",
        "repositories": {
            spec.key: {
                "directory": spec.directory,
                "environmentOverride": spec.environment,
                "origin": origins[spec.key],
            }
            for spec in REPOSITORIES
        },
        "resolutionOrder": [
            "repository-specific environment override",
            "named sibling under the consumer workspace parent",
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def parse_managed_manifest(content: str, path: Path) -> dict[str, str]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"invalid local workspace manifest; refusing to trust {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise WorkspaceError(f"workspace manifest must be a JSON object: {path}")
    expected_header = {
        "schemaVersion": 1,
        "managedBy": MANAGED_BY,
        "layout": "independent-sibling-repositories",
    }
    if set(document) != {
        "schemaVersion",
        "managedBy",
        "layout",
        "repositories",
        "resolutionOrder",
    }:
        raise WorkspaceError(f"workspace manifest top-level fields are invalid: {path}")
    for key, expected in expected_header.items():
        if document.get(key) != expected:
            raise WorkspaceError(f"workspace manifest has invalid {key}; refusing to trust: {path}")
    if document.get("resolutionOrder") != [
        "repository-specific environment override",
        "named sibling under the consumer workspace parent",
    ]:
        raise WorkspaceError(f"workspace manifest resolutionOrder is invalid: {path}")

    repositories = document.get("repositories")
    if not isinstance(repositories, dict) or set(repositories) != set(SPEC_BY_KEY):
        raise WorkspaceError(f"workspace manifest repository set is invalid: {path}")
    origins: dict[str, str] = {}
    for spec in REPOSITORIES:
        entry = repositories.get(spec.key)
        if not isinstance(entry, dict):
            raise WorkspaceError(f"workspace manifest entry is invalid for {spec.key}: {path}")
        if set(entry) != {"directory", "environmentOverride", "origin"}:
            raise WorkspaceError(f"workspace manifest entry fields are invalid for {spec.key}: {path}")
        if entry.get("directory") != spec.directory or entry.get("environmentOverride") != spec.environment:
            raise WorkspaceError(f"workspace manifest routing fields are invalid for {spec.key}: {path}")
        origin = entry.get("origin")
        if not isinstance(origin, str) or not origin.strip():
            raise WorkspaceError(f"workspace manifest origin is invalid for {spec.key}: {path}")
        reject_credential_remote(origin, f"workspace manifest origin for {spec.key}")
        remote_identity(origin)
        origins[spec.key] = origin
    return origins


def manifest_origins(root: Path) -> dict[str, str]:
    path = root / MANIFEST_NAME
    if path.is_symlink():
        raise WorkspaceError(f"workspace manifest is a symlink; refusing to trust: {path}")
    if not path.exists():
        return {spec.key: spec.origin for spec in REPOSITORIES}
    if not path.is_file():
        raise WorkspaceError(f"workspace manifest is not a regular file: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError(f"workspace manifest is unreadable; refusing to trust: {path}") from exc
    return parse_managed_manifest(content, path)


def managed_file_action(path: Path, desired: str, kind: str) -> str:
    if path.is_symlink():
        raise WorkspaceError(f"{kind} path is a symlink; refusing to replace it: {path}")
    if not path.exists():
        return "create"
    if not path.is_file():
        raise WorkspaceError(f"{kind} path is not a regular file; refusing to overwrite: {path}")
    try:
        current = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError(f"{kind} file is unreadable; refusing to overwrite: {path}") from exc
    if current == desired:
        return "ok"

    if kind == "router":
        if not current.startswith("<!-- plugify-workspace-router:"):
            raise WorkspaceError(
                f"existing un-managed AGENTS.md differs; refusing to overwrite: {path}\n"
                "Reconcile it manually with the managed template, then retry."
            )
        if not current.startswith(f"{ROUTER_MARKER}\n"):
            raise WorkspaceError(f"unsupported managed router version; refusing to overwrite: {path}")
        return "update"

    parse_managed_manifest(current, path)
    return "update"


def local_config(path: Path, key: str) -> str | None:
    result = git(path, "config", "--local", "--get", key, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def preflight(
    root: Path,
    origins: dict[str, str],
    *,
    allow_dirty: bool,
) -> tuple[list[RepoSpec], str, str]:
    validate_noninteractive_askpass_helper()
    if root.exists() and not root.is_dir():
        raise WorkspaceError(f"workspace root is not a directory: {root}")
    validate_workspace_container(root)
    validate_required_name_collisions(root)

    desired_router = router_template()
    desired_manifest = manifest_content(origins)
    router_action = managed_file_action(root / "AGENTS.md", desired_router, "router") if root.exists() else "create"
    manifest_action = (
        managed_file_action(root / MANIFEST_NAME, desired_manifest, "manifest")
        if root.exists()
        else "create"
    )

    missing: list[RepoSpec] = []
    for spec in REPOSITORIES:
        path = root / spec.directory
        if path.is_symlink():
            raise WorkspaceError(
                f"repository path is a symlink; physical sibling checkout required: {path}"
            )
        if not path.exists():
            missing.append(spec)
            print(f"PLAN clone {spec.key}: {redacted_remote(origins[spec.key])} -> {path}")
            continue
        actual = validate_checkout(path, spec, origins[spec.key])
        dirty = dirty_entries(path)
        if dirty and not allow_dirty:
            raise WorkspaceError(
                f"dirty checkout {spec.directory} ({len(dirty)} entries); "
                "filenames withheld from logs. "
                "Commit/stash/remove the changes, or rerun with --allow-dirty to leave them untouched."
            )
        state = f"dirty({len(dirty)}), preserved" if dirty else "clean"
        print(f"OK   {spec.key}: {path} [{state}] origin={redacted_remote(actual)}")

    print(f"{router_action.upper():6} router: {root / 'AGENTS.md'}")
    print(f"{manifest_action.upper():6} manifest: {root / MANIFEST_NAME}")
    for spec in REPOSITORIES:
        path = root / spec.directory
        if path.exists():
            for key, desired in (("core.autocrlf", "false"), ("core.eol", "lf")):
                actual = local_config(path, key)
                label = "OK" if actual == desired else "PLAN"
                print(f"{label:4} {spec.key} {key}={desired}" + ("" if actual == desired else f" (was {actual!r})"))
        else:
            print(f"PLAN {spec.key} core.autocrlf=false, core.eol=lf after clone")
    return missing, router_action, manifest_action


def clone_missing(root: Path, missing: list[RepoSpec], origins: dict[str, str]) -> None:
    helper = validate_noninteractive_askpass_helper() if missing else None
    staged: list[tuple[RepoSpec, Path]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="plugify-empty-git-template-") as template:
            for spec in missing:
                stage = root / f".{spec.directory}.plugify-clone-{uuid.uuid4().hex}"
                staged.append((spec, stage))
                print(f"APPLY clone {spec.key} -> {root / spec.directory}")
                result = run(
                    [
                        "git",
                        "-c",
                        "credential.interactive=false",
                        "-c",
                        f"core.hooksPath={template}",
                        "-c",
                        "core.fsmonitor=false",
                        "clone",
                        "--quiet",
                        "--template",
                        template,
                        "--config",
                        "core.autocrlf=false",
                        "--config",
                        "core.eol=lf",
                        "--origin",
                        "origin",
                        "--",
                        origins[spec.key],
                        str(stage),
                    ],
                    check=False,
                    env=clean_git_environment(
                        {
                            "GIT_TERMINAL_PROMPT": "0",
                            "GIT_ASKPASS": str(helper),
                            "SSH_ASKPASS": str(helper),
                            "SSH_ASKPASS_REQUIRE": "never",
                            "GCM_INTERACTIVE": "Never",
                            "GIT_SSH_COMMAND": "ssh -oBatchMode=yes -oStrictHostKeyChecking=yes",
                            "GIT_SSH_VARIANT": "ssh",
                        }
                    ),
                )
                if result.returncode != 0:
                    detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
                    raise WorkspaceError(
                        f"clone failed for {spec.key}: {redact_text(detail, (origins[spec.key],))}"
                    )
                validate_checkout(stage, spec, origins[spec.key])

        for spec, stage in staged:
            target = root / spec.directory
            if target.exists() or target.is_symlink():
                raise WorkspaceError(f"target appeared during migration; refusing to overwrite: {target}")
            os.replace(stage, target)
    except BaseException:
        for _, stage in staged:
            if stage.exists():
                shutil.rmtree(stage)
        raise


def configure_eol(root: Path) -> None:
    for spec in REPOSITORIES:
        path = root / spec.directory
        git(path, "config", "--local", "core.autocrlf", "false")
        git(path, "config", "--local", "core.eol", "lf")
        print(f"APPLY {spec.key}: core.autocrlf=false, core.eol=lf")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_managed_file(path: Path, desired: str, kind: str) -> None:
    action = managed_file_action(path, desired, kind)
    if action == "ok":
        return
    atomic_write(path, desired)
    print(f"APPLY {action} {path}")


def strict_verify(root: Path, origins: dict[str, str], *, allow_dirty: bool) -> None:
    validate_noninteractive_askpass_helper()
    if not root.is_dir():
        raise WorkspaceError(f"workspace root missing: {root}")
    validate_workspace_container(root)
    validate_required_name_collisions(root)
    for spec in REPOSITORIES:
        path = root / spec.directory
        validate_checkout(path, spec, origins[spec.key])
        dirty = dirty_entries(path)
        if dirty and not allow_dirty:
            raise WorkspaceError(f"dirty checkout fails strict verification: {path}")
        for key, desired in (("core.autocrlf", "false"), ("core.eol", "lf")):
            actual = local_config(path, key)
            if actual != desired:
                raise WorkspaceError(f"{path}: expected local {key}={desired}, got {actual!r}")

    router = root / "AGENTS.md"
    if managed_file_action(router, router_template(), "router") != "ok":
        raise WorkspaceError(f"workspace router missing or drifted: {router}")
    manifest = root / MANIFEST_NAME
    if managed_file_action(manifest, manifest_content(origins), "manifest") != "ok":
        raise WorkspaceError(f"workspace manifest missing or drifted: {manifest}")
    print(f"VERIFIED {root}: 3 independent sibling repositories, router, manifest, and EOL config")


def main() -> int:
    args = parse_args()
    try:
        if args.resolve:
            print(resolve_repository(args.resolve))
            return 0

        origins = expected_origins(args.repo_url)
        root = workspace_root(args.root)
        print(f"workspace root: {root}")

        if args.verify:
            strict_verify(root, origins, allow_dirty=args.allow_dirty)
            return 0

        missing, _, _ = preflight(root, origins, allow_dirty=args.allow_dirty)
        if not args.apply:
            print("DRY-RUN complete; no files changed. Re-run with --apply to execute this plan.")
            return 0

        root.mkdir(parents=True, exist_ok=True)
        clone_missing(root, missing, origins)
        configure_eol(root)
        write_managed_file(root / "AGENTS.md", router_template(), "router")
        write_managed_file(root / MANIFEST_NAME, manifest_content(origins), "manifest")
        strict_verify(root, origins, allow_dirty=args.allow_dirty)

        if args.install:
            installer = root / "Plugify" / "scripts" / "install.sh"
            if not installer.is_file():
                raise WorkspaceError(f"Plugify installer missing after verification: {installer}")
            print(f"APPLY install Plugify integrations: {installer}")
            subprocess.run(["bash", str(installer)], check=True)
        return 0
    except WorkspaceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: command failed with exit {exc.returncode}: {exc.cmd}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
