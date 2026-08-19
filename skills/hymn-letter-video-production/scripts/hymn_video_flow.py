#!/usr/bin/env python3
"""Fail-closed helpers for the Hymn Letter video production flow.

This module deliberately uses only the Python standard library.  It does not
render video or perform delivery; it validates immutable job inputs, emits a
frame-exact still-image ffconcat timeline, and verifies a local review package.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any, NoReturn


TIMELINE_SCHEMA = "plugify.hymn-letter.still-timeline/1"
JOB_SCHEMA = "plugify.hymn-letter.video-job/1"
PROJECT_ID = "godowon-hymn-letter-26"
CANONICAL_MODULE_PATH = Path(
    "/mnt/c/work/godowon-office/godo-hymns/tools/hymn_letter_visual_template.py"
)
CANONICAL_MODULE_SHA256 = (
    "0634d97c6eaa0a79f667108b551a7f65b0985bf810bd7e6ce9f950daab52cf80"
)
CANONICAL_TEMPLATE_VERSION = "hymn-letter-visual-v2"
CANONICAL_TEMPLATE_ID = "godowon-hymn-letter-recital-caption"
CANONICAL_LOCK_SHA256 = (
    "915c84bcb6d91b3d51fac77662baf10de9e6f51aed63784ab6a860f2a174698e"
)
EPISODE_INVENTORY_SCHEMA = "plugify.hymn-letter.episode-inventory/1"
EPISODE_INVENTORY_PATH = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "episode-inventory.json"
)
EPISODE_INVENTORY_SHA256 = (
    "e03eb7974cd6f4726f0a07e8b64a0d128c95caf6b77e80d5e56b55742e50a711"
)

EXIT_SCHEMA = 2
EXIT_MISSING = 3
EXIT_HASH = 4
EXIT_UNSUPPORTED = 6
EXIT_UNSAFE = 7
EXIT_PACKAGE = 11

TOP_JOB_KEYS = {
    "schema",
    "project_id",
    "episode",
    "inputs",
    "visual_template",
    "output",
    "delivery_intent",
}
EPISODE_KEYS = {"id", "kind", "profile"}
INPUT_KEYS = {"role", "path", "sha256"}
VISUAL_TEMPLATE_KEYS = {
    "module_path",
    "module_sha256",
    "bundle_path",
    "lock_sha256",
    "version",
}
OUTPUT_KEYS = {"run_root", "filename", "overwrite"}
DELIVERY_KEYS = {
    "render",
    "drive_upload",
    "youtube_private_stage",
    "youtube_publish",
    "bot_notify",
}
TEMPLATE_LOCK_KEYS = {
    "schema_version",
    "template_id",
    "template_version",
    "tracked_module_sha256",
    "config_sha256",
    "assets",
}
EPISODE_INVENTORY_KEYS = {
    "schema",
    "project_id",
    "selection_status",
    "episodes",
}
EPISODE_INVENTORY_ITEM_KEYS = {
    "id",
    "kind",
    "profile",
    "hymn_number",
}

SUPPORTED_PROFILES = {
    "start-hybrid/v1": {
        "kind": "start",
        "required_roles": {"program_video", "approved_audio", "captions"},
    },
    "testimony-static/v1": {
        "kind": "testimony_intro",
        "required_roles": {"approved_audio", "captions"},
    },
}
UNSUPPORTED_PROFILES = {
    "hymn-lyrics/v1": "hymn_lyrics",
    "playlist/v1": "playlist",
}
ALLOWED_INPUT_ROLES = {
    "program_video",
    "approved_audio",
    "approved_script",
    "captions",
    "reviewed_ass",
    "edit_manifest",
    "reference_layout",
    "lyrics",
    "lyric_timing",
    "golden_fixture",
    "track_manifest",
    "playlist_timing",
    "thumbnail",
    "publishing_metadata",
    "package_manifest",
}
FORBIDDEN_SUPPORTED_PROFILE_ROLES = {
    "lyrics",
    "lyric_timing",
    "track_manifest",
    "playlist_timing",
    "package_manifest",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")
VIDEO_FILENAME_RE = re.compile(r"^[^/\\\x00\r\n]{1,176}\.mp4$")
SUM_LINE_RE = re.compile(r"^([0-9a-f]{64}) ([ *])(.+)$")
MAX_FRAME_COUNT = 2_147_483_647
MAX_FPS = 1000


class FlowError(Exception):
    """Expected validation failure with a stable process exit code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class _DuplicateJsonKey(ValueError):
    pass


def _fail(code: int, message: str) -> NoReturn:
    raise FlowError(code, message)


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _read_stable_bytes(path: Path, label: str) -> bytes:
    if not os.path.lexists(path):
        _fail(EXIT_MISSING, f"{label} does not exist: {path}")
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                _fail(EXIT_UNSAFE, f"{label} is not a regular file: {path}")
            data = handle.read()
            after = os.fstat(handle.fileno())
            identity_before = (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            )
            identity_after = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
            if identity_before != identity_after:
                _fail(EXIT_UNSAFE, f"{label} changed while reading: {path}")
            return data
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if exc.errno == errno.ELOOP:
            _fail(EXIT_UNSAFE, f"refusing to read symlink for {label}: {path}")
        _fail(EXIT_MISSING, f"cannot read {label}: {exc}")


def _decode_json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        _fail(EXIT_SCHEMA, f"invalid JSON in {label}: {exc}")


def _load_json_with_sha256(path: Path, label: str) -> tuple[Any, str]:
    data = _read_stable_bytes(path, label)
    return _decode_json_bytes(data, label), hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> Any:
    value, _digest = _load_json_with_sha256(path, label)
    return value


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(EXIT_SCHEMA, f"{label} must be an object")
    return value


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    obj = _require_object(value, label)
    actual = set(obj)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        _fail(EXIT_SCHEMA, f"{label} keys mismatch; missing={missing}, extra={extra}")
    return obj


def _require_nonempty_string(value: Any, label: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        _fail(EXIT_SCHEMA, f"{label} must be a non-empty string")
    return value


def _require_identifier(value: Any, label: str) -> str:
    text = _require_nonempty_string(value, label)
    if not IDENTIFIER_RE.fullmatch(text):
        _fail(EXIT_SCHEMA, f"{label} must be a lowercase hyphenated identifier")
    return text


def _require_positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0 or value > MAX_FRAME_COUNT:
        _fail(
            EXIT_SCHEMA,
            f"{label} must be a positive integer no larger than {MAX_FRAME_COUNT}",
        )
    return value


def _require_sha256(value: Any, label: str) -> str:
    if type(value) is not str or not SHA256_RE.fullmatch(value):
        _fail(EXIT_SCHEMA, f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _require_absolute_path(value: Any, label: str) -> Path:
    raw = _require_nonempty_string(value, label)
    if "\r" in raw or "\n" in raw:
        _fail(EXIT_SCHEMA, f"{label} contains a line break")
    path = Path(raw)
    if not path.is_absolute():
        _fail(EXIT_SCHEMA, f"{label} must be an absolute path")
    return path


def _reject_existing_symlink_components(path: Path, label: str) -> None:
    absolute = path if path.is_absolute() else (Path.cwd() / path)
    for component in reversed((absolute, *absolute.parents)):
        if os.path.lexists(component) and component.is_symlink():
            _fail(EXIT_UNSAFE, f"{label} contains a symlink component: {component}")


def _require_existing_regular_file(path: Path, label: str, *, no_symlink: bool) -> Path:
    if not os.path.lexists(path):
        _fail(EXIT_MISSING, f"{label} does not exist: {path}")
    if no_symlink and path.is_symlink():
        _fail(EXIT_UNSAFE, f"{label} must not be a symlink: {path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve {label}: {exc}")
    if not resolved.is_file():
        _fail(EXIT_MISSING, f"{label} is not a regular file: {path}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                _fail(EXIT_UNSAFE, f"file is not a regular file: {path}")
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
            identity_before = (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            )
            identity_after = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
            if identity_before != identity_after:
                _fail(EXIT_UNSAFE, f"file changed while hashing: {path}")
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if exc.errno == errno.ELOOP:
            _fail(EXIT_UNSAFE, f"refusing to hash symlink: {path}")
        _fail(EXIT_MISSING, f"cannot read file for SHA-256: {path}: {exc}")
    return digest.hexdigest()


def _quote_ffconcat_path(path: Path) -> str:
    text = str(path)
    if any(character in text for character in ("\x00", "\r", "\n")):
        _fail(EXIT_SCHEMA, f"interval file path cannot be represented safely: {path}")
    return text.replace("'", "'\\''")


def _duration_text(frames: int, fps: int) -> str:
    """Return enough decimal places to stay safely within half a frame."""

    places = max(9, len(str(fps)) + 2)
    with localcontext() as context:
        context.prec = len(str(frames)) + places + 8
        value = Decimal(frames) / Decimal(fps)
        return f"{value:.{places}f}"


def _write_new_text(path: Path, text: str) -> None:
    if os.path.lexists(path):
        _fail(EXIT_UNSAFE, f"refusing to overwrite existing output: {path}")
    parent = path.parent
    _reject_existing_symlink_components(parent, "output parent")
    if not parent.exists():
        _fail(EXIT_MISSING, f"output parent does not exist: {parent}")
    if not parent.is_dir():
        _fail(EXIT_UNSAFE, f"output parent is not a directory: {parent}")

    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        _fail(EXIT_UNSAFE, f"refusing to overwrite existing output: {path}")
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        _fail(EXIT_UNSAFE, f"cannot create output safely: {path}: {exc}")


def build_timeline(spec_argument: Path, output_argument: Path) -> dict[str, Any]:
    """Validate a still-timeline spec and create a new ffconcat file."""

    spec_path = _require_existing_regular_file(spec_argument, "timeline spec", no_symlink=False)
    spec_value, spec_hash = _load_json_with_sha256(spec_path, "timeline spec")
    spec = _require_exact_keys(
        spec_value,
        {"schema", "fps", "expected_frames", "intervals"},
        "timeline spec",
    )
    if spec["schema"] != TIMELINE_SCHEMA:
        _fail(EXIT_SCHEMA, f"timeline spec schema must be {TIMELINE_SCHEMA!r}")
    fps = _require_positive_int(spec["fps"], "timeline spec.fps")
    if fps > MAX_FPS:
        _fail(EXIT_SCHEMA, f"timeline spec.fps must be between 1 and {MAX_FPS}")
    expected_frames = _require_positive_int(
        spec["expected_frames"], "timeline spec.expected_frames"
    )
    intervals = spec["intervals"]
    if type(intervals) is not list or not intervals:
        _fail(EXIT_SCHEMA, "timeline spec.intervals must be a non-empty array")

    normalized: list[tuple[Path, int]] = []
    total_frames = 0
    for index, raw_interval in enumerate(intervals):
        interval = _require_exact_keys(
            raw_interval, {"file", "frames"}, f"timeline spec.intervals[{index}]"
        )
        raw_file = _require_nonempty_string(
            interval["file"], f"timeline spec.intervals[{index}].file"
        )
        if any(character in raw_file for character in ("\r", "\n")):
            _fail(
                EXIT_SCHEMA,
                f"timeline spec.intervals[{index}].file contains a line break",
            )
        frames = _require_positive_int(
            interval["frames"], f"timeline spec.intervals[{index}].frames"
        )
        candidate = Path(raw_file)
        if not candidate.is_absolute():
            candidate = spec_path.parent / candidate
        resolved = _require_existing_regular_file(
            candidate, f"timeline interval file {index}", no_symlink=False
        )
        normalized.append((resolved, frames))
        total_frames += frames
        if total_frames > MAX_FRAME_COUNT:
            _fail(
                EXIT_SCHEMA,
                f"timeline interval frame sum must not exceed {MAX_FRAME_COUNT}",
            )

    if total_frames != expected_frames:
        _fail(
            EXIT_SCHEMA,
            "timeline interval frame sum does not match expected_frames: "
            f"{total_frames} != {expected_frames}",
        )

    lines = ["ffconcat version 1.0"]
    for interval_path, frames in normalized:
        lines.append(f"file '{_quote_ffconcat_path(interval_path)}'")
        lines.append(f"option framerate {fps}")
        lines.append(f"duration {_duration_text(frames, fps)}")
    terminal_path = normalized[-1][0]
    lines.append(f"file '{_quote_ffconcat_path(terminal_path)}'")
    lines.append(f"option framerate {fps}")

    expanded_output = output_argument.expanduser()
    if not expanded_output.is_absolute():
        expanded_output = Path.cwd() / expanded_output
    if os.path.lexists(expanded_output):
        _fail(EXIT_UNSAFE, f"refusing to overwrite existing output: {expanded_output}")
    output_path = expanded_output.absolute()
    if _sha256_file(spec_path) != spec_hash:
        _fail(EXIT_UNSAFE, "timeline spec changed during timeline construction")
    _write_new_text(output_path, "\n".join(lines) + "\n")
    if _sha256_file(spec_path) != spec_hash:
        try:
            output_path.unlink()
        except OSError:
            pass
        _fail(EXIT_UNSAFE, "timeline spec changed while writing the timeline")
    output_hash = _sha256_file(output_path)
    return {
        "command": "build-timeline",
        "expected_frames": expected_frames,
        "fps": fps,
        "interval_count": len(normalized),
        "output": str(output_path),
        "output_sha256": output_hash,
        "spec_sha256": spec_hash,
        "status": "ok",
    }


def _load_episode_inventory() -> tuple[Path, str, dict[str, tuple[str, str]]]:
    """Load the byte-pinned, skill-local episode allowlist."""

    inventory_path = EPISODE_INVENTORY_PATH
    _reject_existing_symlink_components(inventory_path, "episode inventory")
    inventory_path = _require_existing_regular_file(
        inventory_path, "episode inventory", no_symlink=True
    )
    inventory_bytes = _read_stable_bytes(inventory_path, "episode inventory")
    inventory_hash = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_hash != EPISODE_INVENTORY_SHA256:
        _fail(
            EXIT_HASH,
            "episode inventory bytes do not match the pinned SHA-256: "
            f"expected {EPISODE_INVENTORY_SHA256}, got {inventory_hash}",
        )
    inventory_value = _decode_json_bytes(inventory_bytes, "episode inventory")
    inventory = _require_exact_keys(
        inventory_value, EPISODE_INVENTORY_KEYS, "episode inventory"
    )
    if inventory["schema"] != EPISODE_INVENTORY_SCHEMA:
        _fail(
            EXIT_SCHEMA,
            f"episode inventory schema must be {EPISODE_INVENTORY_SCHEMA!r}",
        )
    if inventory["project_id"] != PROJECT_ID:
        _fail(EXIT_SCHEMA, f"episode inventory project_id must be {PROJECT_ID!r}")
    _require_nonempty_string(
        inventory["selection_status"], "episode inventory.selection_status"
    )
    raw_episodes = inventory["episodes"]
    if type(raw_episodes) is not list or not raw_episodes:
        _fail(EXIT_SCHEMA, "episode inventory.episodes must be a non-empty array")

    episode_map: dict[str, tuple[str, str]] = {}
    for index, raw_episode in enumerate(raw_episodes):
        label = f"episode inventory.episodes[{index}]"
        item = _require_exact_keys(
            raw_episode, EPISODE_INVENTORY_ITEM_KEYS, label
        )
        episode_id = _require_identifier(item["id"], f"{label}.id")
        if episode_id in episode_map:
            _fail(EXIT_SCHEMA, f"duplicate episode inventory id: {episode_id!r}")
        kind = _require_nonempty_string(item["kind"], f"{label}.kind")
        profile = _require_nonempty_string(item["profile"], f"{label}.profile")
        contract = SUPPORTED_PROFILES.get(profile)
        if contract is None or kind != contract["kind"]:
            _fail(
                EXIT_SCHEMA,
                f"{label} does not name a supported kind/profile contract",
            )
        hymn_number = item["hymn_number"]
        if hymn_number is not None and (
            type(hymn_number) is not int or hymn_number <= 0
        ):
            _fail(
                EXIT_SCHEMA,
                f"{label}.hymn_number must be null or a positive integer",
            )
        if (kind == "start") != (hymn_number is None):
            _fail(
                EXIT_SCHEMA,
                f"{label}.hymn_number must be null only for the start episode",
            )
        episode_map[episode_id] = (kind, profile)
    return inventory_path, inventory_hash, episode_map


def _validate_profile(
    episode: dict[str, Any],
) -> tuple[str, str, set[str], bool]:
    episode_id = _require_identifier(episode["id"], "episode.id")
    kind = _require_nonempty_string(episode["kind"], "episode.kind")
    profile = _require_nonempty_string(episode["profile"], "episode.profile")

    if profile in SUPPORTED_PROFILES:
        contract = SUPPORTED_PROFILES[profile]
        if kind != contract["kind"]:
            _fail(
                EXIT_SCHEMA,
                f"episode.kind {kind!r} does not match profile {profile!r}",
            )
        return episode_id, profile, set(contract["required_roles"]), False
    if profile in UNSUPPORTED_PROFILES:
        expected_kind = UNSUPPORTED_PROFILES[profile]
        if kind != expected_kind:
            _fail(
                EXIT_SCHEMA,
                f"episode.kind {kind!r} does not match profile {profile!r}",
            )
        return episode_id, profile, set(), True
    _fail(EXIT_SCHEMA, f"unknown episode.profile: {profile!r}")


def _validate_hashed_absolute_file(
    path_value: Any,
    hash_value: Any,
    label: str,
) -> tuple[Path, str]:
    path = _require_absolute_path(path_value, f"{label}.path")
    expected_hash = _require_sha256(hash_value, f"{label}.sha256")
    resolved = _require_existing_regular_file(path, f"{label}.path", no_symlink=True)
    actual_hash = _sha256_file(resolved)
    if actual_hash != expected_hash:
        _fail(
            EXIT_HASH,
            f"SHA-256 mismatch for {label}: expected {expected_hash}, got {actual_hash}",
        )
    return resolved, actual_hash


def _safe_bundle_relative_path(value: Any, label: str) -> PurePosixPath:
    raw = _require_nonempty_string(value, label)
    if any(character in raw for character in ("\\", "\r", "\n")):
        _fail(EXIT_UNSAFE, f"{label} is not a safe relative path: {raw!r}")
    if raw.startswith("/") or raw.startswith("./") or re.match(r"^[A-Za-z]:", raw):
        _fail(EXIT_UNSAFE, f"{label} is not a safe relative path: {raw!r}")
    components = raw.split("/")
    if any(component in {"", ".", ".."} for component in components):
        _fail(EXIT_UNSAFE, f"{label} is not a safe relative path: {raw!r}")
    relative = PurePosixPath(*components)
    if relative.is_absolute() or relative.as_posix() != raw:
        _fail(EXIT_UNSAFE, f"{label} is not a safe relative path: {raw!r}")
    return relative


def validate_job(manifest_argument: Path) -> dict[str, Any]:
    """Validate and pin a Hymn Letter job without creating its run directory."""

    manifest_path = _require_existing_regular_file(
        manifest_argument, "job manifest", no_symlink=False
    )
    manifest_value, manifest_hash = _load_json_with_sha256(
        manifest_path, "job manifest"
    )
    manifest = _require_exact_keys(
        manifest_value, TOP_JOB_KEYS, "job manifest"
    )
    if manifest["schema"] != JOB_SCHEMA:
        _fail(EXIT_SCHEMA, f"job manifest schema must be {JOB_SCHEMA!r}")
    project_id = _require_identifier(manifest["project_id"], "project_id")
    if project_id != PROJECT_ID:
        _fail(EXIT_SCHEMA, f"project_id must be {PROJECT_ID!r}")

    inventory_path, inventory_hash, episode_map = _load_episode_inventory()
    episode = _require_exact_keys(manifest["episode"], EPISODE_KEYS, "episode")
    episode_id, profile, required_roles, unsupported_profile = _validate_profile(
        episode
    )
    expected_episode = episode_map.get(episode_id)
    unsupported_episode = expected_episode is None
    if expected_episode is not None:
        actual_episode = (episode["kind"], profile)
        if actual_episode != expected_episode:
            _fail(
                EXIT_SCHEMA,
                f"episode {episode_id!r} must use kind/profile "
                f"{expected_episode!r}, got {actual_episode!r}",
            )

    raw_inputs = manifest["inputs"]
    if type(raw_inputs) is not list or not raw_inputs:
        _fail(EXIT_SCHEMA, "inputs must be a non-empty array")
    seen_roles: set[str] = set()
    verified_inputs: list[dict[str, str]] = []
    for index, raw_input in enumerate(raw_inputs):
        item = _require_exact_keys(raw_input, INPUT_KEYS, f"inputs[{index}]")
        role = _require_nonempty_string(item["role"], f"inputs[{index}].role")
        if role not in ALLOWED_INPUT_ROLES:
            _fail(EXIT_SCHEMA, f"unsupported inputs[{index}].role: {role!r}")
        if role in seen_roles:
            _fail(EXIT_SCHEMA, f"duplicate input role: {role!r}")
        seen_roles.add(role)
        path, digest = _validate_hashed_absolute_file(
            item["path"], item["sha256"], f"inputs[{index}]"
        )
        verified_inputs.append({"path": str(path), "role": role, "sha256": digest})
    if not unsupported_profile:
        forbidden_roles = sorted(seen_roles & FORBIDDEN_SUPPORTED_PROFILE_ROLES)
        if forbidden_roles:
            _fail(
                EXIT_SCHEMA,
                f"profile {profile!r} forbids input roles: {forbidden_roles}",
            )
    missing_roles = sorted(required_roles - seen_roles)
    if missing_roles:
        _fail(
            EXIT_SCHEMA,
            f"profile {profile!r} is missing required input roles: {missing_roles}",
        )

    visual = _require_exact_keys(
        manifest["visual_template"], VISUAL_TEMPLATE_KEYS, "visual_template"
    )
    raw_module_path = _require_nonempty_string(
        visual["module_path"], "visual_template.module_path"
    )
    if raw_module_path != str(CANONICAL_MODULE_PATH):
        _fail(
            EXIT_UNSAFE,
            "visual_template.module_path must be the exact canonical path: "
            f"{CANONICAL_MODULE_PATH}",
        )
    declared_module_path = _require_absolute_path(
        raw_module_path, "visual_template.module_path"
    )
    module_path = _require_existing_regular_file(
        declared_module_path, "visual_template.module_path", no_symlink=True
    )
    canonical_module_path = _require_existing_regular_file(
        CANONICAL_MODULE_PATH, "canonical visual template module", no_symlink=True
    )
    if module_path != canonical_module_path:
        _fail(
            EXIT_UNSAFE,
            "visual_template.module_path is not the canonical Hymn Letter module: "
            f"{module_path}",
        )
    declared_module_hash = _require_sha256(
        visual["module_sha256"], "visual_template.module_sha256"
    )
    if declared_module_hash != CANONICAL_MODULE_SHA256:
        _fail(EXIT_HASH, "visual_template.module_sha256 is not the canonical SHA-256")
    module_hash = _sha256_file(module_path)
    if module_hash != CANONICAL_MODULE_SHA256:
        _fail(
            EXIT_HASH,
            "canonical visual template module bytes do not match the pinned SHA-256",
        )
    bundle_path = _require_absolute_path(
        visual["bundle_path"], "visual_template.bundle_path"
    )
    if not os.path.lexists(bundle_path):
        _fail(EXIT_MISSING, f"visual template bundle does not exist: {bundle_path}")
    if bundle_path.is_symlink():
        _fail(EXIT_UNSAFE, f"visual template bundle must not be a symlink: {bundle_path}")
    try:
        bundle_path = bundle_path.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve visual template bundle: {exc}")
    if not bundle_path.is_dir():
        _fail(EXIT_MISSING, f"visual template bundle is not a directory: {bundle_path}")

    lock_expected_hash = _require_sha256(
        visual["lock_sha256"], "visual_template.lock_sha256"
    )
    version = _require_nonempty_string(visual["version"], "visual_template.version")
    if lock_expected_hash != CANONICAL_LOCK_SHA256:
        _fail(EXIT_HASH, "visual_template.lock_sha256 is not the canonical SHA-256")
    if version != CANONICAL_TEMPLATE_VERSION:
        _fail(EXIT_HASH, "visual_template.version is not the canonical template version")
    lock_path = _require_existing_regular_file(
        bundle_path / "template.lock.json",
        "visual template lock",
        no_symlink=True,
    )
    lock_value, lock_actual_hash = _load_json_with_sha256(
        lock_path, "visual template lock"
    )
    if lock_actual_hash != lock_expected_hash:
        _fail(
            EXIT_HASH,
            "SHA-256 mismatch for visual template lock: "
            f"expected {lock_expected_hash}, got {lock_actual_hash}",
        )
    lock = _require_exact_keys(
        lock_value, TEMPLATE_LOCK_KEYS, "visual template lock"
    )
    if type(lock["schema_version"]) is not int or lock["schema_version"] != 1:
        _fail(EXIT_SCHEMA, "visual template lock.schema_version must be integer 1")
    if lock["template_id"] != CANONICAL_TEMPLATE_ID:
        _fail(EXIT_HASH, "visual template lock.template_id is not canonical")
    if lock["template_version"] != version:
        _fail(
            EXIT_HASH,
            "visual template version does not match lock: "
            f"{version!r} != {lock['template_version']!r}",
        )
    lock_module_hash = _require_sha256(
        lock["tracked_module_sha256"],
        "visual template lock.tracked_module_sha256",
    )
    if lock_module_hash != module_hash:
        _fail(EXIT_HASH, "visual template module SHA-256 does not match template lock")

    config_expected_hash = _require_sha256(
        lock["config_sha256"], "visual template lock.config_sha256"
    )
    config_path = bundle_path / "template_config.json"
    _reject_existing_symlink_components(config_path, "visual template config")
    config_path = _require_existing_regular_file(
        config_path, "visual template config", no_symlink=True
    )
    config_actual_hash = _sha256_file(config_path)
    if config_actual_hash != config_expected_hash:
        _fail(
            EXIT_HASH,
            "visual template config SHA-256 mismatch: "
            f"expected {config_expected_hash}, got {config_actual_hash}",
        )

    lock_assets = _require_object(lock["assets"], "visual template lock.assets")
    if not lock_assets:
        _fail(EXIT_SCHEMA, "visual template lock.assets must not be empty")
    verified_bundle_files: dict[Path, str] = {config_path: config_actual_hash}
    for index, (raw_asset_path, raw_asset_hash) in enumerate(
        sorted(lock_assets.items())
    ):
        relative_asset = _safe_bundle_relative_path(
            raw_asset_path, f"visual template lock.assets key {index}"
        )
        expected_asset_hash = _require_sha256(
            raw_asset_hash,
            f"visual template lock.assets[{raw_asset_path!r}]",
        )
        asset_path = bundle_path.joinpath(*relative_asset.parts)
        _reject_existing_symlink_components(asset_path, "visual template asset")
        asset_path = _require_existing_regular_file(
            asset_path,
            f"visual template asset {raw_asset_path!r}",
            no_symlink=True,
        )
        if not _path_within(asset_path, bundle_path):
            _fail(EXIT_UNSAFE, f"visual template asset escapes bundle: {raw_asset_path!r}")
        actual_asset_hash = _sha256_file(asset_path)
        if actual_asset_hash != expected_asset_hash:
            _fail(
                EXIT_HASH,
                f"visual template asset SHA-256 mismatch for {raw_asset_path!r}: "
                f"expected {expected_asset_hash}, got {actual_asset_hash}",
            )
        verified_bundle_files[asset_path] = actual_asset_hash

    output = _require_exact_keys(manifest["output"], OUTPUT_KEYS, "output")
    run_root_raw = _require_absolute_path(output["run_root"], "output.run_root")
    _reject_existing_symlink_components(run_root_raw, "output.run_root")
    if os.path.lexists(run_root_raw):
        if run_root_raw.is_symlink():
            _fail(EXIT_UNSAFE, f"output.run_root must not be a symlink: {run_root_raw}")
        if not run_root_raw.is_dir():
            _fail(EXIT_UNSAFE, f"output.run_root is not a directory: {run_root_raw}")
    run_root = run_root_raw.resolve(strict=False)
    if run_root == Path(run_root.anchor):
        _fail(EXIT_UNSAFE, "output.run_root must not be a filesystem root")
    filename = _require_nonempty_string(output["filename"], "output.filename")
    if not VIDEO_FILENAME_RE.fullmatch(filename) or Path(filename).name != filename:
        _fail(EXIT_SCHEMA, "output.filename must be a basename ending in lowercase .mp4")
    if type(output["overwrite"]) is not bool or output["overwrite"] is not False:
        _fail(EXIT_SCHEMA, "output.overwrite must be false")
    output_target = run_root / filename
    if os.path.lexists(output_target):
        _fail(EXIT_UNSAFE, f"output target already exists: {output_target}")

    delivery = _require_exact_keys(
        manifest["delivery_intent"], DELIVERY_KEYS, "delivery_intent"
    )
    for key in sorted(DELIVERY_KEYS):
        if type(delivery[key]) is not bool:
            _fail(EXIT_SCHEMA, f"delivery_intent.{key} must be a boolean")
    if delivery["youtube_publish"] and not delivery["youtube_private_stage"]:
        _fail(
            EXIT_SCHEMA,
            "delivery_intent.youtube_publish requires youtube_private_stage=true",
        )

    if _sha256_file(manifest_path) != manifest_hash:
        _fail(EXIT_UNSAFE, "job manifest changed during validation")
    if _sha256_file(inventory_path) != inventory_hash:
        _fail(EXIT_HASH, "episode inventory changed during validation")
    for item in verified_inputs:
        if _sha256_file(Path(item["path"])) != item["sha256"]:
            _fail(EXIT_HASH, f"validated input changed: {item['role']}")
    if _sha256_file(module_path) != module_hash:
        _fail(EXIT_HASH, "canonical visual template module changed during validation")
    if _sha256_file(lock_path) != lock_actual_hash:
        _fail(EXIT_HASH, "visual template lock changed during validation")
    for verified_path, verified_hash in verified_bundle_files.items():
        if _sha256_file(verified_path) != verified_hash:
            _fail(
                EXIT_HASH,
                f"visual template bundle file changed during validation: {verified_path}",
            )
    if _sha256_file(manifest_path) != manifest_hash:
        _fail(EXIT_UNSAFE, "job manifest changed during validation")
    if os.path.lexists(output_target):
        _fail(EXIT_UNSAFE, f"output target appeared during validation: {output_target}")
    if unsupported_episode:
        _fail(EXIT_UNSUPPORTED, f"UNSUPPORTED_EPISODE: {episode_id}")
    if unsupported_profile:
        _fail(EXIT_UNSUPPORTED, f"UNSUPPORTED_PROFILE: {profile}")

    return {
        "command": "validate-job",
        "episode_id": episode_id,
        "episode_inventory": {
            "path": str(inventory_path),
            "sha256": inventory_hash,
        },
        "input_count": len(verified_inputs),
        "inputs": verified_inputs,
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "output_target": str(output_target),
        "profile": profile,
        "project_id": project_id,
        "status": "ok",
        "template": {
            "lock_sha256": lock_actual_hash,
            "module_path": str(module_path),
            "module_sha256": module_hash,
            "version": version,
        },
    }


def _safe_manifest_entry(raw: str, line_number: int) -> str:
    if not raw:
        _fail(EXIT_PACKAGE, f"empty package path on sums line {line_number}")
    if any(character in raw for character in ("\\", "\x00", "\r", "\n")):
        _fail(EXIT_UNSAFE, f"unsafe package path on sums line {line_number}: {raw!r}")
    if raw.startswith("./"):
        raw = raw[2:]
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        _fail(EXIT_UNSAFE, f"unsafe package path on sums line {line_number}: {raw!r}")
    components = raw.split("/")
    if any(component in {"", ".", ".."} for component in components):
        _fail(EXIT_UNSAFE, f"unsafe package path on sums line {line_number}: {raw!r}")
    normalized = PurePosixPath(*components)
    if normalized.is_absolute() or str(normalized) != "/".join(components):
        _fail(EXIT_UNSAFE, f"unsafe package path on sums line {line_number}: {raw!r}")
    return normalized.as_posix()


def _path_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _walk_safe_regular_files(package_dir: Path) -> set[str]:
    payloads: set[str] = set()

    def fail_walk(error: OSError) -> NoReturn:
        _fail(EXIT_PACKAGE, f"cannot scan package directory: {error}")

    for root_text, directory_names, file_names in os.walk(
        package_dir, followlinks=False, onerror=fail_walk
    ):
        root = Path(root_text)
        for name in directory_names:
            candidate = root / name
            try:
                mode = candidate.lstat().st_mode
            except OSError as exc:
                _fail(EXIT_PACKAGE, f"cannot inspect package directory: {candidate}: {exc}")
            if stat.S_ISLNK(mode):
                _fail(EXIT_UNSAFE, f"package contains a symlink directory: {candidate}")
            if not stat.S_ISDIR(mode):
                _fail(EXIT_UNSAFE, f"package contains an unsafe directory entry: {candidate}")
        for name in file_names:
            candidate = root / name
            try:
                mode = candidate.lstat().st_mode
            except OSError as exc:
                _fail(EXIT_PACKAGE, f"cannot inspect package file: {candidate}: {exc}")
            if stat.S_ISLNK(mode):
                _fail(EXIT_UNSAFE, f"package contains a symlink file: {candidate}")
            if not stat.S_ISREG(mode):
                _fail(EXIT_UNSAFE, f"package contains a non-regular file: {candidate}")
            relative = candidate.relative_to(package_dir).as_posix()
            safe_relative = _safe_manifest_entry(relative, 0)
            if safe_relative in payloads:
                _fail(EXIT_PACKAGE, f"duplicate package payload path: {safe_relative}")
            payloads.add(safe_relative)
    return payloads


def _package_payload_identity(path: Path, relative: str) -> tuple[int, int, int, int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        _fail(EXIT_PACKAGE, f"cannot inspect package payload {relative}: {exc}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        _fail(EXIT_UNSAFE, f"unsafe package payload: {relative}")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_package_identity(
    path: Path,
    relative: str,
    expected: tuple[int, int, int, int, int],
    checkpoint: str,
) -> None:
    actual = _package_payload_identity(path, relative)
    if actual != expected:
        _fail(
            EXIT_HASH,
            f"package payload identity changed at {checkpoint}: {relative}",
        )


def _resolve_sums_path(package_dir: Path, sums_argument: Path) -> tuple[Path, str]:
    if sums_argument.is_absolute():
        candidate = sums_argument
    else:
        safe_relative = _safe_manifest_entry(sums_argument.as_posix(), 0)
        candidate = package_dir / safe_relative
    if not os.path.lexists(candidate):
        _fail(EXIT_MISSING, f"checksum file does not exist: {candidate}")
    if candidate.is_symlink():
        _fail(EXIT_UNSAFE, f"checksum file must not be a symlink: {candidate}")
    resolved = _require_existing_regular_file(candidate, "checksum file", no_symlink=True)
    if not _path_within(resolved, package_dir):
        _fail(EXIT_UNSAFE, f"checksum file must be inside package directory: {candidate}")
    relative = resolved.relative_to(package_dir).as_posix()
    return resolved, _safe_manifest_entry(relative, 0)


def _parse_sums_bytes(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        _fail(EXIT_PACKAGE, f"checksum file is not valid UTF-8: {exc}")
    lines = text.splitlines()
    if not lines:
        _fail(EXIT_PACKAGE, "checksum file is empty")
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        if not line:
            _fail(EXIT_PACKAGE, f"blank checksum line: {line_number}")
        match = SUM_LINE_RE.fullmatch(line)
        if not match:
            _fail(EXIT_PACKAGE, f"invalid checksum syntax on line {line_number}")
        digest, _mode, raw_path = match.groups()
        relative = _safe_manifest_entry(raw_path, line_number)
        if relative in entries:
            _fail(EXIT_PACKAGE, f"duplicate checksum entry: {relative}")
        entries[relative] = digest
    return entries


def verify_package(package_argument: Path, sums_argument: Path) -> dict[str, Any]:
    """Verify a closed local package against an exact SHA256SUMS payload set."""

    if not os.path.lexists(package_argument):
        _fail(EXIT_MISSING, f"package directory does not exist: {package_argument}")
    if package_argument.is_symlink():
        _fail(EXIT_UNSAFE, f"package directory must not be a symlink: {package_argument}")
    try:
        package_dir = package_argument.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve package directory: {exc}")
    if not package_dir.is_dir():
        _fail(EXIT_PACKAGE, f"package path is not a directory: {package_dir}")

    sums_path, sums_relative = _resolve_sums_path(package_dir, sums_argument)
    sums_bytes_before = _read_stable_bytes(sums_path, "checksum file")
    sums_hash_before = hashlib.sha256(sums_bytes_before).hexdigest()
    all_files = _walk_safe_regular_files(package_dir)
    if sums_relative not in all_files:
        _fail(EXIT_PACKAGE, "checksum file disappeared during package scan")
    payload_files = all_files - {sums_relative}
    entries = _parse_sums_bytes(sums_bytes_before)
    entry_paths = set(entries)
    if entry_paths != payload_files:
        missing_from_sums = sorted(payload_files - entry_paths)
        absent_from_package = sorted(entry_paths - payload_files)
        _fail(
            EXIT_PACKAGE,
            "checksum payload set mismatch; "
            f"missing_from_sums={missing_from_sums[:5]}, "
            f"absent_from_package={absent_from_package[:5]}",
        )

    payload_paths = {
        relative: package_dir / relative for relative in sorted(entries)
    }
    initial_identities = {
        relative: _package_payload_identity(path, relative)
        for relative, path in payload_paths.items()
    }
    first_pass_hashes: dict[str, str] = {}
    for pass_number in (1, 2):
        for relative in sorted(entries):
            payload = payload_paths[relative]
            _require_package_identity(
                payload,
                relative,
                initial_identities[relative],
                f"before hash pass {pass_number}",
            )
            actual_hash = _sha256_file(payload)
            _require_package_identity(
                payload,
                relative,
                initial_identities[relative],
                f"after hash pass {pass_number}",
            )
            expected_hash = entries[relative]
            if actual_hash != expected_hash:
                _fail(
                    EXIT_HASH,
                    f"SHA-256 mismatch for package payload {relative} on pass "
                    f"{pass_number}: expected {expected_hash}, got {actual_hash}",
                )
            if pass_number == 1:
                first_pass_hashes[relative] = actual_hash
            elif actual_hash != first_pass_hashes[relative]:
                _fail(
                    EXIT_HASH,
                    f"package payload changed between hash passes: {relative}",
                )

    final_files = _walk_safe_regular_files(package_dir)
    if final_files != all_files:
        _fail(EXIT_PACKAGE, "package payload set changed during verification")
    sums_bytes_after = _read_stable_bytes(sums_path, "checksum file")
    sums_hash_after = hashlib.sha256(sums_bytes_after).hexdigest()
    if sums_bytes_after != sums_bytes_before or sums_hash_after != sums_hash_before:
        _fail(EXIT_PACKAGE, "checksum file changed during verification")
    for relative, payload in payload_paths.items():
        _require_package_identity(
            payload,
            relative,
            initial_identities[relative],
            "final verification",
        )

    return {
        "command": "verify-package",
        "package_dir": str(package_dir),
        "payload_count": len(entries),
        "status": "ok",
        "sums": str(sums_path),
        "sums_sha256": sums_hash_after,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hymn_video_flow.py",
        description="Validate deterministic Hymn Letter video-production artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    timeline = subparsers.add_parser("build-timeline")
    timeline.add_argument("--spec", required=True, type=Path)
    timeline.add_argument("--output", required=True, type=Path)

    job = subparsers.add_parser("validate-job")
    job.add_argument("--manifest", required=True, type=Path)

    package = subparsers.add_parser("verify-package")
    package.add_argument("--package-dir", required=True, type=Path)
    package.add_argument("--sums", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "build-timeline":
            result = build_timeline(arguments.spec, arguments.output)
        elif arguments.command == "validate-job":
            result = validate_job(arguments.manifest)
        elif arguments.command == "verify-package":
            result = verify_package(arguments.package_dir, arguments.sums)
        else:  # argparse makes this unreachable, but keep the dispatch fail-closed.
            _fail(EXIT_SCHEMA, f"unknown command: {arguments.command!r}")
    except FlowError as exc:
        print(f"ERROR[{exc.code}] {exc}", file=sys.stderr)
        return exc.code
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
