#!/usr/bin/env python3
"""Portable wrapper for the office-native Hymn Letter v3 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any

from hymn_video_flow import (
    EXIT_HASH,
    EXIT_MISSING,
    EXIT_SCHEMA,
    EXIT_UNSAFE,
    EXIT_UNSUPPORTED,
    FlowError,
    _decode_json_bytes,
    _fail,
    _load_json_with_sha256,
    _path_within,
    _read_stable_bytes,
    _require_absolute_path,
    _require_exact_keys,
    _require_existing_regular_file,
    _require_nonempty_string,
    _require_positive_int,
    _require_sha256,
    _safe_manifest_entry,
    _sha256_file,
    _write_new_text,
)


INVENTORY_SCHEMA = "plugify.hymn-letter.episode-inventory/2"
JOB_SCHEMA = "godowon.hymn-letter.v3-job/1"
SOURCE_BUNDLE_SCHEMA = "godowon.hymn-letter.source-bundle/1"
RELEASE_SCHEMA = "godowon.hymn-letter.v3-release-lock/1"
RUN_RECEIPT_SCHEMA = "plugify.hymn-letter.run-receipt/1"
OBJECT_ID_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
EPISODE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9][a-z0-9-]*$")
INPUT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
OUTPUT_FILENAME_RE = re.compile(r"^[^/\\\x00\r\n]{1,176}\.(mp4|mov)$")
THUMBNAIL_FILENAME_RE = re.compile(r"^[^/\\\x00\r\n]{1,176}\.(jpg|jpeg|png)$")
GATE_VALUES = {"semantic-equivalent", "reference-bit-exact"}
EXIT_DELEGATE = 12
ALLOWED_SYSTEM_SYMLINK_COMPONENTS = {Path("/tmp"), Path("/var")}

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_SHA256 = _sha256_file(SCRIPT_PATH)
SKILL_DIR = SCRIPT_PATH.parent.parent
REFERENCE_DIR = SKILL_DIR / "references"
INVENTORY_PATH = REFERENCE_DIR / "episode-inventory.v2.json"
INVENTORY_SHA256 = "46ec5aa6f2543b75c1aba765dd9e34d12f9141c5764ee2aa85d63ae420bafda5"
PROJECT_RELEASE_ID = "hymn-letter-caption-v3-20260822"

INVENTORY_KEYS = {"schema", "release_id", "episodes"}
INVENTORY_EPISODE_KEYS = {
    "sequence",
    "episode_id",
    "kind",
    "profile",
    "container",
    "audio_codec",
    "frame_count",
}
JOB_KEYS = {"schema", "release_id", "episode_id", "profile", "inputs", "settings", "output"}
OUTPUT_KEYS = {"filename", "thumbnail_filename", "container", "frame_count"}
RELEASE_KEYS = {
    "schema",
    "release_id",
    "created_at",
    "source_bundle_lock",
    "environment_lock",
    "golden_lock",
    "jobs",
    "renderer_modules",
    "supported_profiles",
    "notes",
    "source_bundle_lock_sha256",
    "environment_lock_sha256",
    "golden_lock_sha256",
}
RELEASE_JOB_KEYS = {"path", "sha256"}
RENDERER_MODULE_KEYS = {"path", "sha256"}
SOURCE_BUNDLE_KEYS = {"schema", "release_id", "storage_layout", "objects"}
SOURCE_OBJECT_KEYS = {"sha256", "size", "filenames", "roles"}
RUN_RECEIPT_KEYS = {
    "schema",
    "release_id",
    "stage",
    "job_sha256",
    "release_sha256",
    "source_bundle_sha256",
    "wrapper_path",
    "wrapper_sha256",
    "office_root",
    "office_script_path",
    "office_script_sha256",
    "runtime_python",
    "normalized_command",
    "run_root",
    "delegate_stdout_sha256",
    "delegate_payload",
    "gate",
}

PROFILE_CONTRACTS: dict[str, dict[str, Any]] = {
    "start-hybrid/v1": {
        "kind": "start",
        "container": "mp4",
        "audio_codec": "aac",
        "required_inputs": {"program_video", "audio", "captions", "backplate", "font", "thumbnail"},
        "settings_keys": {"intro_frames", "intro_style", "post_style"},
    },
    "playlist/v1": {
        "kind": "playlist",
        "container": "mov",
        "audio_codec": "mp3",
        "required_inputs": {"audio", "captions", "chapters", "font", "thumbnail", "active_rows"},
        "settings_keys": {
            "style",
            "active_row_state",
            "active_row_frame_boundaries",
            "title_card_policy",
            "movie_timescale",
            "video_track_timescale",
        },
    },
    "testimony-static/v1": {
        "kind": "testimony_intro",
        "container": "mp4",
        "audio_codec": "aac",
        "required_inputs": {"backplate", "audio", "captions", "font", "thumbnail"},
        "settings_keys": {"style", "restore_audio_edit", "movie_timescale", "video_track_timescale"},
    },
    "hymn-lyrics/v1": {
        "kind": "hymn_lyrics",
        "container": "mov",
        "audio_codec": "mp3",
        "required_inputs": {"backplate", "audio", "captions", "font", "thumbnail"},
        "settings_keys": {"style", "movie_timescale", "video_track_timescale"},
    },
}

REQUIRED_RENDERER_MODULES = {
    "caption",
    "profiles",
    "mp4",
    "qc",
    "playlist_active_rows",
    "avfoundation_probe_source",
}


def _plugify_root() -> Path:
    return SCRIPT_PATH.parents[3]


def _default_office_root() -> Path:
    return _plugify_root().parent / "godowon-office"


def _reject_unsafe_symlink_components(path: Path, label: str) -> None:
    absolute = path if path.is_absolute() else (Path.cwd() / path)
    for component in reversed((absolute, *absolute.parents)):
        if os.path.lexists(component) and component.is_symlink():
            if component in ALLOWED_SYSTEM_SYMLINK_COMPONENTS:
                continue
            _fail(EXIT_UNSAFE, f"{label} contains a symlink component: {component}")


def _normalize_existing_directory(path: Path, label: str) -> Path:
    _reject_unsafe_symlink_components(path, label)
    if not os.path.lexists(path):
        _fail(EXIT_MISSING, f"{label} does not exist: {path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve {label}: {exc}")
    if not resolved.is_dir():
        _fail(EXIT_MISSING, f"{label} is not a directory: {path}")
    return resolved


def _normalize_writable_directory(path: Path, label: str) -> Path:
    _reject_unsafe_symlink_components(path, label)
    if os.path.lexists(path):
        if path.is_symlink():
            _fail(EXIT_UNSAFE, f"{label} must not be a symlink: {path}")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            _fail(EXIT_MISSING, f"cannot resolve {label}: {exc}")
        if not resolved.is_dir():
            _fail(EXIT_UNSAFE, f"{label} is not a directory: {path}")
        return resolved
    parent = path.parent
    if not os.path.lexists(parent):
        _fail(EXIT_MISSING, f"{label} parent does not exist: {parent}")
    # macOS exposes /tmp and /var as stable system aliases into /private.
    # Allow those two roots, but continue to reject arbitrary symlink parents.
    parent_resolved = parent.resolve(strict=True)
    if not parent_resolved.is_dir():
        _fail(EXIT_UNSAFE, f"{label} parent is not a directory: {parent}")
    path.mkdir(mode=0o755)
    return path.resolve(strict=True)


def _resolve_runtime_python(path_argument: Path) -> tuple[Path, dict[str, str]]:
    raw = _require_absolute_path(str(path_argument), "runtime python")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve runtime python: {exc}")
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        _fail(EXIT_MISSING, f"runtime python is not an executable regular file: {resolved}")
    probe = subprocess.run(
        [str(resolved), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        _fail(EXIT_MISSING, f"runtime python --version failed: {resolved}")
    version = (probe.stdout or probe.stderr).strip()
    return resolved, {
        "path": str(resolved),
        "sha256": _sha256_file(resolved),
        "version": version,
    }


def _safe_release_relative_path(value: Any, label: str) -> str:
    raw = _require_nonempty_string(value, label)
    return _safe_manifest_entry(raw, 0)


def _safe_relative_path_to_path(relative: str) -> Path:
    return Path(*PurePosixPath(relative).parts)


def _resolve_source_object_path(source_root: Path, object_id: str) -> Path:
    digest = object_id.split(":", 1)[1]
    candidate = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
    if not os.path.lexists(candidate):
        _fail(EXIT_MISSING, f"source object is missing: {object_id}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        _fail(EXIT_MISSING, f"cannot resolve source object {object_id}: {exc}")
    if not _path_within(resolved, source_root):
        _fail(EXIT_UNSAFE, f"source object escapes source root: {object_id}")
    if not resolved.is_file():
        _fail(EXIT_MISSING, f"source object is not a regular file: {object_id}")
    return resolved


def _load_inventory() -> tuple[Path, str, dict[str, dict[str, Any]]]:
    inventory_path = _require_existing_regular_file(INVENTORY_PATH, "episode inventory", no_symlink=False)
    inventory_bytes = _read_stable_bytes(inventory_path, "episode inventory")
    inventory_hash = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_hash != INVENTORY_SHA256:
        _fail(
            EXIT_HASH,
            f"episode inventory SHA mismatch: expected {INVENTORY_SHA256}, got {inventory_hash}",
        )
    inventory_value = _decode_json_bytes(inventory_bytes, "episode inventory")
    inventory = _require_exact_keys(inventory_value, INVENTORY_KEYS, "episode inventory")
    if inventory["schema"] != INVENTORY_SCHEMA:
        _fail(EXIT_SCHEMA, f"invalid inventory schema: {inventory['schema']!r}")
    if inventory["release_id"] != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, f"unexpected inventory release_id: {inventory['release_id']!r}")
    raw_episodes = inventory["episodes"]
    if type(raw_episodes) is not list or not raw_episodes:
        _fail(EXIT_SCHEMA, "episode inventory.episodes must be a non-empty array")
    episode_map: dict[str, dict[str, Any]] = {}
    seen_sequences: set[int] = set()
    for index, raw_episode in enumerate(raw_episodes):
        label = f"episode inventory.episodes[{index}]"
        item = _require_exact_keys(raw_episode, INVENTORY_EPISODE_KEYS, label)
        sequence = _require_positive_int(item["sequence"], f"{label}.sequence")
        if sequence in seen_sequences:
            _fail(EXIT_SCHEMA, f"duplicate inventory sequence: {sequence}")
        seen_sequences.add(sequence)
        episode_id = _require_nonempty_string(item["episode_id"], f"{label}.episode_id")
        if not EPISODE_ID_RE.fullmatch(episode_id):
            _fail(EXIT_SCHEMA, f"invalid inventory episode_id: {episode_id!r}")
        if episode_id in episode_map:
            _fail(EXIT_SCHEMA, f"duplicate inventory episode_id: {episode_id!r}")
        profile = _require_nonempty_string(item["profile"], f"{label}.profile")
        contract = PROFILE_CONTRACTS.get(profile)
        if contract is None:
            _fail(EXIT_SCHEMA, f"unknown inventory profile: {profile!r}")
        kind = _require_nonempty_string(item["kind"], f"{label}.kind")
        if kind != contract["kind"]:
            _fail(EXIT_SCHEMA, f"inventory kind/profile mismatch for {episode_id!r}")
        container = _require_nonempty_string(item["container"], f"{label}.container")
        audio_codec = _require_nonempty_string(item["audio_codec"], f"{label}.audio_codec")
        if container != contract["container"] or audio_codec != contract["audio_codec"]:
            _fail(EXIT_SCHEMA, f"inventory output contract mismatch for {episode_id!r}")
        frame_count = _require_positive_int(item["frame_count"], f"{label}.frame_count")
        episode_map[episode_id] = {
            "sequence": sequence,
            "episode_id": episode_id,
            "kind": kind,
            "profile": profile,
            "container": container,
            "audio_codec": audio_codec,
            "frame_count": frame_count,
        }
    return inventory_path, inventory_hash, episode_map


def _load_release(release_argument: Path) -> tuple[Path, str, dict[str, Any]]:
    release_path = _require_existing_regular_file(release_argument, "release lock", no_symlink=False)
    release_value, release_hash = _load_json_with_sha256(release_path, "release lock")
    release = _require_exact_keys(release_value, RELEASE_KEYS, "release lock")
    if release["schema"] != RELEASE_SCHEMA:
        _fail(EXIT_SCHEMA, f"invalid release schema: {release['schema']!r}")
    if release["release_id"] != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, f"unexpected release_id: {release['release_id']!r}")
    _require_nonempty_string(release["created_at"], "release lock.created_at")
    release["source_bundle_lock"] = _safe_release_relative_path(release["source_bundle_lock"], "release lock.source_bundle_lock")
    release["environment_lock"] = _safe_release_relative_path(release["environment_lock"], "release lock.environment_lock")
    release["golden_lock"] = _safe_release_relative_path(release["golden_lock"], "release lock.golden_lock")
    release["source_bundle_lock_sha256"] = _require_sha256(release["source_bundle_lock_sha256"], "release lock.source_bundle_lock_sha256")
    release["environment_lock_sha256"] = _require_sha256(release["environment_lock_sha256"], "release lock.environment_lock_sha256")
    release["golden_lock_sha256"] = _require_sha256(release["golden_lock_sha256"], "release lock.golden_lock_sha256")

    raw_jobs = release["jobs"]
    if type(raw_jobs) is not list or not raw_jobs:
        _fail(EXIT_SCHEMA, "release lock.jobs must be a non-empty array")
    seen_job_paths: set[str] = set()
    normalized_jobs: dict[str, str] = {}
    for index, raw_job in enumerate(raw_jobs):
        label = f"release lock.jobs[{index}]"
        item = _require_exact_keys(raw_job, RELEASE_JOB_KEYS, label)
        path = _safe_release_relative_path(item["path"], f"{label}.path")
        if path in seen_job_paths:
            _fail(EXIT_SCHEMA, f"duplicate release job path: {path}")
        seen_job_paths.add(path)
        normalized_jobs[path] = _require_sha256(item["sha256"], f"{label}.sha256")
    release["jobs"] = normalized_jobs

    renderer_modules = release["renderer_modules"]
    if type(renderer_modules) is not dict:
        _fail(EXIT_SCHEMA, "release lock.renderer_modules must be an object")
    actual_module_keys = set(renderer_modules)
    if actual_module_keys != REQUIRED_RENDERER_MODULES:
        _fail(
            EXIT_SCHEMA,
            f"release lock.renderer_modules keys mismatch; missing={sorted(REQUIRED_RENDERER_MODULES - actual_module_keys)}, extra={sorted(actual_module_keys - REQUIRED_RENDERER_MODULES)}",
        )
    normalized_modules: dict[str, dict[str, str]] = {}
    for name in sorted(renderer_modules):
        item = _require_exact_keys(
            renderer_modules[name], RENDERER_MODULE_KEYS, f"release lock.renderer_modules.{name}"
        )
        normalized_modules[name] = {
            "path": _safe_release_relative_path(item["path"], f"release lock.renderer_modules.{name}.path"),
            "sha256": _require_sha256(item["sha256"], f"release lock.renderer_modules.{name}.sha256"),
        }
    release["renderer_modules"] = normalized_modules

    supported_profiles = release["supported_profiles"]
    if type(supported_profiles) is not list or not supported_profiles:
        _fail(EXIT_SCHEMA, "release lock.supported_profiles must be a non-empty array")
    normalized_profiles: list[str] = []
    seen_profiles: set[str] = set()
    for index, raw_profile in enumerate(supported_profiles):
        profile = _require_nonempty_string(raw_profile, f"release lock.supported_profiles[{index}]")
        if profile not in PROFILE_CONTRACTS:
            _fail(EXIT_SCHEMA, f"unknown supported profile in release: {profile!r}")
        if profile in seen_profiles:
            _fail(EXIT_SCHEMA, f"duplicate release supported profile: {profile!r}")
        seen_profiles.add(profile)
        normalized_profiles.append(profile)
    release["supported_profiles"] = normalized_profiles

    notes = release["notes"]
    if type(notes) is not list:
        _fail(EXIT_SCHEMA, "release lock.notes must be an array")
    for index, note in enumerate(notes):
        _require_nonempty_string(note, f"release lock.notes[{index}]")

    for relative_key, hash_key in (
        ("source_bundle_lock", "source_bundle_lock_sha256"),
        ("environment_lock", "environment_lock_sha256"),
        ("golden_lock", "golden_lock_sha256"),
    ):
        referenced_path = release_path.parent / _safe_relative_path_to_path(release[relative_key])
        referenced_path = _require_existing_regular_file(referenced_path, relative_key, no_symlink=False)
        actual_hash = _sha256_file(referenced_path)
        if actual_hash != release[hash_key]:
            _fail(EXIT_HASH, f"{relative_key} hash mismatch in release lock")
    return release_path, release_hash, release


def _load_source_bundle(release_path: Path, release: dict[str, Any]) -> tuple[Path, str, dict[str, dict[str, Any]]]:
    bundle_path = release_path.parent / _safe_relative_path_to_path(release["source_bundle_lock"])
    bundle_path = _require_existing_regular_file(bundle_path, "source bundle lock", no_symlink=False)
    bundle_value, bundle_hash = _load_json_with_sha256(bundle_path, "source bundle lock")
    if bundle_hash != release["source_bundle_lock_sha256"]:
        _fail(EXIT_HASH, "source bundle lock SHA does not match release lock")
    bundle = _require_exact_keys(bundle_value, SOURCE_BUNDLE_KEYS, "source bundle lock")
    if bundle["schema"] != SOURCE_BUNDLE_SCHEMA:
        _fail(EXIT_SCHEMA, f"invalid source bundle schema: {bundle['schema']!r}")
    if bundle["release_id"] != release["release_id"]:
        _fail(EXIT_SCHEMA, "source bundle release_id does not match release lock")
    if bundle["storage_layout"] != "objects/sha256/<prefix>/<digest-rest>":
        _fail(EXIT_SCHEMA, "unsupported source bundle storage_layout")
    raw_objects = bundle["objects"]
    if type(raw_objects) is not dict or not raw_objects:
        _fail(EXIT_SCHEMA, "source bundle objects must be a non-empty object")
    object_map: dict[str, dict[str, Any]] = {}
    for object_id, raw_entry in raw_objects.items():
        if not OBJECT_ID_RE.fullmatch(object_id):
            _fail(EXIT_SCHEMA, f"invalid source object id: {object_id!r}")
        entry = _require_exact_keys(raw_entry, SOURCE_OBJECT_KEYS, f"source bundle object {object_id}")
        sha256 = _require_sha256(entry["sha256"], f"source bundle object {object_id}.sha256")
        if object_id.split(":", 1)[1] != sha256:
            _fail(EXIT_SCHEMA, f"source bundle object sha mismatch for {object_id}")
        size = _require_positive_int(entry["size"], f"source bundle object {object_id}.size")
        filenames = entry["filenames"]
        roles = entry["roles"]
        if type(filenames) is not list or not filenames:
            _fail(EXIT_SCHEMA, f"source bundle filenames missing for {object_id}")
        if type(roles) is not list or not roles:
            _fail(EXIT_SCHEMA, f"source bundle roles missing for {object_id}")
        for index, filename in enumerate(filenames):
            _require_nonempty_string(filename, f"source bundle object {object_id}.filenames[{index}]")
        for index, role in enumerate(roles):
            _require_nonempty_string(role, f"source bundle object {object_id}.roles[{index}]")
        object_map[object_id] = {
            "sha256": sha256,
            "size": size,
            "filenames": filenames,
            "roles": roles,
        }
    return bundle_path, bundle_hash, object_map


def _normalize_input_value(value: Any, label: str) -> list[str]:
    if type(value) is str:
        values = [value]
    elif type(value) is list and value:
        values = []
        for index, item in enumerate(value):
            if type(item) is not str:
                _fail(EXIT_SCHEMA, f"{label}[{index}] must be a string object id")
            values.append(item)
    else:
        _fail(EXIT_SCHEMA, f"{label} must be a string object id or a non-empty list")
    normalized: list[str] = []
    for index, item in enumerate(values):
        if not OBJECT_ID_RE.fullmatch(item):
            _fail(EXIT_SCHEMA, f"{label}[{index}] must match sha256:<64hex>")
        normalized.append(item)
    return normalized


def _validate_settings(job: dict[str, Any], required_input_values: dict[str, list[str]]) -> None:
    profile = job["profile"]
    contract = PROFILE_CONTRACTS[profile]
    settings = job["settings"]
    if type(settings) is not dict:
        _fail(EXIT_SCHEMA, "job.settings must be an object")
    actual_keys = set(settings)
    expected_keys = contract["settings_keys"]
    if actual_keys != expected_keys:
        _fail(
            EXIT_SCHEMA,
            f"job.settings keys mismatch for {profile!r}; missing={sorted(expected_keys - actual_keys)}, extra={sorted(actual_keys - expected_keys)}",
        )
    if profile == "start-hybrid/v1":
        _require_positive_int(settings["intro_frames"], "job.settings.intro_frames")
        _require_nonempty_string(settings["intro_style"], "job.settings.intro_style")
        _require_nonempty_string(settings["post_style"], "job.settings.post_style")
    elif profile == "playlist/v1":
        _require_nonempty_string(settings["style"], "job.settings.style")
        _require_nonempty_string(settings["active_row_state"], "job.settings.active_row_state")
        boundaries = settings["active_row_frame_boundaries"]
        if type(boundaries) is not list or len(boundaries) < 2:
            _fail(EXIT_SCHEMA, "job.settings.active_row_frame_boundaries must be an array of at least two integers")
        normalized_boundaries: list[int] = []
        for index, boundary in enumerate(boundaries):
            value = _require_positive_int(boundary if index else 1 if boundary == 0 else boundary, f"job.settings.active_row_frame_boundaries[{index}]")
            normalized_boundaries.append(0 if index == 0 and boundary == 0 else value)
        if normalized_boundaries[0] != 0:
            _fail(EXIT_SCHEMA, "playlist boundaries must start at 0")
        if sorted(normalized_boundaries) != normalized_boundaries or len(set(normalized_boundaries)) != len(normalized_boundaries):
            _fail(EXIT_SCHEMA, "playlist boundaries must be strictly increasing")
        if len(normalized_boundaries) != len(required_input_values["active_rows"]) + 1:
            _fail(EXIT_SCHEMA, "playlist boundaries length must equal active_rows + 1")
        title_policy = _require_exact_keys(
            settings["title_card_policy"],
            {"mode", "expected_titles", "expected_active_rows"},
            "job.settings.title_card_policy",
        )
        if title_policy["mode"] != "playlist-prior-outro/v1":
            _fail(EXIT_SCHEMA, "unsupported playlist title-card policy")
        expected_titles = title_policy["expected_titles"]
        expected_active_rows = title_policy["expected_active_rows"]
        track_count = len(required_input_values["active_rows"])
        if type(expected_titles) is not list or len(expected_titles) != track_count:
            _fail(EXIT_SCHEMA, "playlist title policy must contain one expected title per track")
        for index, title in enumerate(expected_titles):
            _require_nonempty_string(title, f"job.settings.title_card_policy.expected_titles[{index}]")
        if type(expected_active_rows) is not list or len(expected_active_rows) != track_count:
            _fail(EXIT_SCHEMA, "playlist title policy must contain one active-row expectation per title")
        normalized_title_rows = [
            _require_positive_int(value, f"job.settings.title_card_policy.expected_active_rows[{index}]")
            for index, value in enumerate(expected_active_rows)
        ]
        required_title_rows = [1, *range(1, track_count)]
        if normalized_title_rows != required_title_rows:
            _fail(
                EXIT_SCHEMA,
                "playlist-prior-outro/v1 requires active rows [1, 1, 2, ..., track_count-1]",
            )
        _require_positive_int(settings["movie_timescale"], "job.settings.movie_timescale")
        _require_positive_int(settings["video_track_timescale"], "job.settings.video_track_timescale")
    elif profile == "testimony-static/v1":
        _require_nonempty_string(settings["style"], "job.settings.style")
        if type(settings["restore_audio_edit"]) is not bool:
            _fail(EXIT_SCHEMA, "job.settings.restore_audio_edit must be boolean")
        _require_positive_int(settings["movie_timescale"], "job.settings.movie_timescale")
        _require_positive_int(settings["video_track_timescale"], "job.settings.video_track_timescale")
    elif profile == "hymn-lyrics/v1":
        _require_nonempty_string(settings["style"], "job.settings.style")
        _require_positive_int(settings["movie_timescale"], "job.settings.movie_timescale")
        _require_positive_int(settings["video_track_timescale"], "job.settings.video_track_timescale")


def _load_job(job_argument: Path, release_path: Path, release_hash: str, release: dict[str, Any]) -> tuple[Path, str, dict[str, Any]]:
    _inventory_path, inventory_hash, inventory_map = _load_inventory()
    job_path = _require_existing_regular_file(job_argument, "job manifest", no_symlink=False)
    job_value, job_hash = _load_json_with_sha256(job_path, "job manifest")
    job = _require_exact_keys(job_value, JOB_KEYS, "job manifest")
    if job["schema"] != JOB_SCHEMA:
        _fail(EXIT_SCHEMA, f"invalid job schema: {job['schema']!r}")
    if job["release_id"] != release["release_id"]:
        _fail(EXIT_SCHEMA, "job release_id does not match release lock")
    episode_id = _require_nonempty_string(job["episode_id"], "job.episode_id")
    if not EPISODE_ID_RE.fullmatch(episode_id):
        _fail(EXIT_SCHEMA, f"invalid job episode_id: {episode_id!r}")
    inventory_episode = inventory_map.get(episode_id)
    if inventory_episode is None:
        _fail(EXIT_UNSUPPORTED, f"UNSUPPORTED_EPISODE: {episode_id}")
    profile = _require_nonempty_string(job["profile"], "job.profile")
    if profile not in PROFILE_CONTRACTS:
        _fail(EXIT_SCHEMA, f"unknown job profile: {profile!r}")
    if profile != inventory_episode["profile"]:
        _fail(EXIT_SCHEMA, f"job profile does not match inventory for {episode_id!r}")
    if profile not in release["supported_profiles"]:
        _fail(EXIT_UNSUPPORTED, f"release does not support profile: {profile}")
    try:
        job_rel_from_release = job_path.resolve().relative_to(release_path.parent.resolve())
    except ValueError:
        _fail(EXIT_UNSAFE, "job manifest must be inside the release directory")
    release_jobs: dict[str, str] = release["jobs"]
    expected_hash = release_jobs.get(job_rel_from_release.as_posix())
    if expected_hash is None:
        _fail(EXIT_UNSUPPORTED, f"job is not listed in release lock: {job_rel_from_release.as_posix()}")
    if expected_hash != job_hash:
        _fail(EXIT_HASH, "job SHA does not match release lock")
    inputs = job["inputs"]
    if type(inputs) is not dict:
        _fail(EXIT_SCHEMA, "job.inputs must be an object")
    actual_input_keys = set(inputs)
    expected_input_keys = PROFILE_CONTRACTS[profile]["required_inputs"]
    if actual_input_keys != expected_input_keys:
        _fail(
            EXIT_SCHEMA,
            f"job.inputs keys mismatch for {profile!r}; missing={sorted(expected_input_keys - actual_input_keys)}, extra={sorted(actual_input_keys - expected_input_keys)}",
        )
    normalized_inputs: dict[str, list[str]] = {}
    for key in sorted(inputs):
        if not INPUT_KEY_RE.fullmatch(key):
            _fail(EXIT_SCHEMA, f"invalid job input key: {key!r}")
        normalized_inputs[key] = _normalize_input_value(inputs[key], f"job.inputs.{key}")
    _validate_settings(job, normalized_inputs)
    output = _require_exact_keys(job["output"], OUTPUT_KEYS, "job.output")
    filename = _require_nonempty_string(output["filename"], "job.output.filename")
    thumbnail_filename = _require_nonempty_string(output["thumbnail_filename"], "job.output.thumbnail_filename")
    if not OUTPUT_FILENAME_RE.fullmatch(filename):
        _fail(EXIT_SCHEMA, "job.output.filename must end in .mp4 or .mov")
    if not THUMBNAIL_FILENAME_RE.fullmatch(thumbnail_filename):
        _fail(EXIT_SCHEMA, "job.output.thumbnail_filename must end in .jpg/.jpeg/.png")
    container = _require_nonempty_string(output["container"], "job.output.container")
    if container not in {"mp4", "mov"}:
        _fail(EXIT_SCHEMA, "job.output.container must be mp4 or mov")
    frame_count = _require_positive_int(output["frame_count"], "job.output.frame_count")
    if container != inventory_episode["container"] or frame_count != inventory_episode["frame_count"]:
        _fail(EXIT_SCHEMA, f"job output contract mismatch for {episode_id!r}")
    if _sha256_file(release_path) != release_hash:
        _fail(EXIT_HASH, "release lock changed during job validation")
    if _sha256_file(job_path) != job_hash:
        _fail(EXIT_UNSAFE, "job manifest changed during validation")
    if _sha256_file(INVENTORY_PATH) != inventory_hash:
        _fail(EXIT_HASH, "inventory changed during job validation")
    return job_path, job_hash, {
        "episode": inventory_episode,
        "inputs": normalized_inputs,
        "job": job,
        "job_hash": job_hash,
        "job_path": job_path,
    }


def validate_job(job_argument: Path, release_argument: Path) -> dict[str, Any]:
    inventory_path, inventory_hash, _inventory_map = _load_inventory()
    release_path, release_hash, release = _load_release(release_argument)
    _job_path, _job_hash, job_state = _load_job(job_argument, release_path, release_hash, release)
    return {
        "command": "validate-job",
        "episode_id": job_state["episode"]["episode_id"],
        "inventory": {
            "path": str(inventory_path),
            "sha256": inventory_hash,
        },
        "job_manifest": str(job_state["job_path"]),
        "job_sha256": job_state["job_hash"],
        "output_audio_codec": job_state["episode"]["audio_codec"],
        "output_container": job_state["episode"]["container"],
        "output_filename": job_state["job"]["output"]["filename"],
        "profile": job_state["episode"]["profile"],
        "release_lock": str(release_path),
        "release_sha256": release_hash,
        "status": "ok",
    }


def verify_source_bundle(
    job_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    release_path, release_hash, release = _load_release(release_argument)
    job_path, job_hash, job_state = _load_job(job_argument, release_path, release_hash, release)
    bundle_path, bundle_hash, object_map = _load_source_bundle(release_path, release)
    source_root_raw = _require_absolute_path(str(source_root_argument), "source root")
    source_root = _normalize_existing_directory(source_root_raw, "source root")
    for object_id, entry in object_map.items():
        resolved = _resolve_source_object_path(source_root, object_id)
        actual_hash = _sha256_file(resolved)
        if actual_hash != entry["sha256"]:
            _fail(EXIT_HASH, f"source object SHA mismatch for {object_id}")
        actual_size = resolved.stat().st_size
        if actual_size != entry["size"]:
            _fail(EXIT_HASH, f"source object size mismatch for {object_id}")
    referenced_object_ids: set[str] = set()
    for input_key, values in job_state["inputs"].items():
        for object_id in values:
            referenced_object_ids.add(object_id)
            if object_id not in object_map:
                _fail(EXIT_HASH, f"job input {input_key!r} references missing source object: {object_id}")
    if _sha256_file(release_path) != release_hash:
        _fail(EXIT_HASH, "release lock changed during source bundle verification")
    if _sha256_file(job_path) != job_hash:
        _fail(EXIT_UNSAFE, "job manifest changed during source bundle verification")
    if _sha256_file(bundle_path) != bundle_hash:
        _fail(EXIT_HASH, "source bundle lock changed during verification")
    result = {
        "command": "verify-source-bundle",
        "episode_id": job_state["episode"]["episode_id"],
        "job_sha256": job_hash,
        "release_sha256": release_hash,
        "source_bundle_lock": str(bundle_path),
        "source_bundle_sha256": bundle_hash,
        "source_root": str(source_root),
        "status": "ok",
        "verified_object_count": len(object_map),
        "referenced_object_count": len(referenced_object_ids),
    }
    state = {
        "bundle_path": bundle_path,
        "bundle_sha256": bundle_hash,
        "job_hash": job_hash,
        "job_path": job_path,
        "job_state": job_state,
        "release": release,
        "release_hash": release_hash,
        "release_path": release_path,
        "source_root": source_root,
    }
    return result, state


def _load_office_script(release: dict[str, Any], module_key: str, office_root_argument: Path | None) -> tuple[Path, Path, str]:
    if office_root_argument is None:
        office_root_raw = _default_office_root()
    else:
        office_root_raw = _require_absolute_path(str(office_root_argument), "office root")
    office_root = _normalize_existing_directory(office_root_raw, "office root")
    module = release["renderer_modules"][module_key]
    script_path = office_root / _safe_relative_path_to_path(module["path"])
    script_path = _require_existing_regular_file(script_path, f"office module {module_key}", no_symlink=False)
    actual_hash = _sha256_file(script_path)
    if actual_hash != module["sha256"]:
        _fail(EXIT_HASH, f"office module SHA mismatch for {module_key}")
    return office_root, script_path, actual_hash


def _snapshot_office_modules(release: dict[str, Any], office_root: Path) -> dict[str, dict[str, str]]:
    snapshot: dict[str, dict[str, str]] = {}
    for module_key, module in sorted(release["renderer_modules"].items()):
        path = office_root / _safe_relative_path_to_path(module["path"])
        path = _require_existing_regular_file(path, f"office module {module_key}", no_symlink=False)
        actual_hash = _sha256_file(path)
        if actual_hash != module["sha256"]:
            _fail(EXIT_HASH, f"office module SHA mismatch for {module_key}")
        snapshot[module_key] = {"path": str(path), "sha256": actual_hash}
    return snapshot


def _assert_execution_inputs_unchanged(
    *,
    job_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
    state_before: dict[str, Any],
    office_root: Path,
    office_modules_before: dict[str, dict[str, str]],
    runtime_python: Path,
    runtime_sha256: str,
) -> None:
    if _sha256_file(SCRIPT_PATH) != SCRIPT_SHA256:
        _fail(EXIT_UNSAFE, "Plugify v3 wrapper changed while the delegate was running")
    if _sha256_file(runtime_python) != runtime_sha256:
        _fail(EXIT_UNSAFE, "runtime Python changed while the delegate was running")
    office_modules_after = _snapshot_office_modules(state_before["release"], office_root)
    if office_modules_after != office_modules_before:
        _fail(EXIT_UNSAFE, "office renderer module set changed while the delegate was running")
    _verification, state_after = verify_source_bundle(
        job_argument,
        release_argument,
        source_root_argument,
    )
    for key in ("job_hash", "release_hash", "bundle_sha256"):
        if state_after[key] != state_before[key]:
            _fail(EXIT_UNSAFE, f"{key} changed while the delegate was running")


def _run_delegate(command: list[str], stage: str) -> tuple[str, dict[str, Any]]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() or "(empty stderr)"
        _fail(EXIT_DELEGATE, f"{stage} delegate failed with exit {process.returncode}: {stderr}")
    if process.stderr:
        _fail(EXIT_DELEGATE, f"{stage} delegate wrote stderr despite success")
    lines = process.stdout.splitlines()
    if len(lines) != 1:
        _fail(EXIT_DELEGATE, f"{stage} delegate must emit exactly one JSON line")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        _fail(EXIT_DELEGATE, f"{stage} delegate stdout is not valid JSON: {exc}")
    if type(payload) is not dict:
        _fail(EXIT_DELEGATE, f"{stage} delegate payload must be a JSON object")
    stdout_sha = hashlib.sha256(process.stdout.encode("utf-8")).hexdigest()
    return stdout_sha, payload


def _write_receipt(path: Path, payload: dict[str, Any]) -> str:
    receipt = _require_exact_keys(payload, RUN_RECEIPT_KEYS, "wrapper run receipt")
    text = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    _write_new_text(path, text)
    return _sha256_file(path)


def render(
    job_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
    run_root_argument: Path,
    office_root_argument: Path | None,
    runtime_python_argument: Path,
) -> dict[str, Any]:
    _verify_payload, state = verify_source_bundle(job_argument, release_argument, source_root_argument)
    office_root, office_script_path, office_script_sha = _load_office_script(
        state["release"], "profiles", office_root_argument
    )
    office_modules = _snapshot_office_modules(state["release"], office_root)
    run_root_raw = _require_absolute_path(str(run_root_argument), "run root")
    run_root = _normalize_writable_directory(run_root_raw, "run root")
    runtime_python, runtime_metadata = _resolve_runtime_python(runtime_python_argument)
    command = [
        str(runtime_python),
        str(office_script_path),
        "render",
        "--job",
        str(state["job_path"]),
        "--release",
        str(state["release_path"]),
        "--source-root",
        str(state["source_root"]),
        "--run-root",
        str(run_root),
    ]
    stdout_sha, delegate_payload = _run_delegate(command, "render")
    if delegate_payload.get("status") != "ok":
        _fail(EXIT_DELEGATE, f"render delegate did not report status=ok: {delegate_payload.get('status')!r}")
    _assert_execution_inputs_unchanged(
        job_argument=job_argument,
        release_argument=release_argument,
        source_root_argument=source_root_argument,
        state_before=state,
        office_root=office_root,
        office_modules_before=office_modules,
        runtime_python=runtime_python,
        runtime_sha256=runtime_metadata["sha256"],
    )
    episode_id = state["job_state"]["episode"]["episode_id"]
    receipt_path = run_root / f"plugify-render-wrapper-receipt-{episode_id}.json"
    receipt_sha = _write_receipt(
        receipt_path,
        {
            "schema": RUN_RECEIPT_SCHEMA,
            "release_id": state["release"]["release_id"],
            "stage": "render",
            "job_sha256": state["job_hash"],
            "release_sha256": state["release_hash"],
            "source_bundle_sha256": state["bundle_sha256"],
            "wrapper_path": str(SCRIPT_PATH),
            "wrapper_sha256": SCRIPT_SHA256,
            "office_root": str(office_root),
            "office_script_path": str(office_script_path),
            "office_script_sha256": office_script_sha,
            "runtime_python": runtime_metadata,
            "normalized_command": command,
            "run_root": str(run_root),
            "delegate_stdout_sha256": stdout_sha,
            "delegate_payload": delegate_payload,
            "gate": None,
        },
    )
    return {
        "command": "render",
        "episode_id": state["job_state"]["episode"]["episode_id"],
        "receipt": str(receipt_path),
        "receipt_sha256": receipt_sha,
        "status": "ok",
    }


def qc(
    job_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
    run_root_argument: Path,
    gate: str,
    office_root_argument: Path | None,
    runtime_python_argument: Path,
) -> dict[str, Any]:
    if gate not in GATE_VALUES:
        _fail(EXIT_SCHEMA, "gate must be semantic-equivalent or reference-bit-exact")
    _verify_payload, state = verify_source_bundle(job_argument, release_argument, source_root_argument)
    office_root, office_script_path, office_script_sha = _load_office_script(
        state["release"], "qc", office_root_argument
    )
    office_modules = _snapshot_office_modules(state["release"], office_root)
    run_root_raw = _require_absolute_path(str(run_root_argument), "run root")
    run_root = _normalize_existing_directory(run_root_raw, "run root")
    runtime_python, runtime_metadata = _resolve_runtime_python(runtime_python_argument)
    command = [
        str(runtime_python),
        str(office_script_path),
        "qc",
        "--job",
        str(state["job_path"]),
        "--release",
        str(state["release_path"]),
        "--source-root",
        str(state["source_root"]),
        "--run-root",
        str(run_root),
        "--gate",
        gate,
    ]
    stdout_sha, delegate_payload = _run_delegate(command, "qc")
    gate_status = delegate_payload.get("status")
    if gate_status not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
        _fail(EXIT_DELEGATE, f"qc delegate returned invalid status: {gate_status!r}")
    _assert_execution_inputs_unchanged(
        job_argument=job_argument,
        release_argument=release_argument,
        source_root_argument=source_root_argument,
        state_before=state,
        office_root=office_root,
        office_modules_before=office_modules,
        runtime_python=runtime_python,
        runtime_sha256=runtime_metadata["sha256"],
    )
    episode_id = state["job_state"]["episode"]["episode_id"]
    receipt_path = run_root / f"plugify-qc-wrapper-receipt-{episode_id}-{gate}.json"
    receipt_sha = _write_receipt(
        receipt_path,
        {
            "schema": RUN_RECEIPT_SCHEMA,
            "release_id": state["release"]["release_id"],
            "stage": "qc",
            "job_sha256": state["job_hash"],
            "release_sha256": state["release_hash"],
            "source_bundle_sha256": state["bundle_sha256"],
            "wrapper_path": str(SCRIPT_PATH),
            "wrapper_sha256": SCRIPT_SHA256,
            "office_root": str(office_root),
            "office_script_path": str(office_script_path),
            "office_script_sha256": office_script_sha,
            "runtime_python": runtime_metadata,
            "normalized_command": command,
            "run_root": str(run_root),
            "delegate_stdout_sha256": stdout_sha,
            "delegate_payload": delegate_payload,
            "gate": gate,
        },
    )
    return {
        "command": "qc",
        "episode_id": state["job_state"]["episode"]["episode_id"],
        "gate": gate,
        "gate_status": gate_status,
        "receipt": str(receipt_path),
        "receipt_sha256": receipt_sha,
        "status": (
            "ok" if gate_status == "PASS" else
            "not_applicable" if gate_status == "NOT_APPLICABLE" else
            "failed"
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hymn_video_flow_v3.py",
        description="Portable validator/wrapper for the office-native Hymn Letter v3 contract.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-job")
    validate_parser.add_argument("--job", required=True, type=Path)
    validate_parser.add_argument("--release", required=True, type=Path)

    verify_parser = subparsers.add_parser("verify-source-bundle")
    verify_parser.add_argument("--job", required=True, type=Path)
    verify_parser.add_argument("--release", required=True, type=Path)
    verify_parser.add_argument("--source-root", required=True, type=Path)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--job", required=True, type=Path)
    render_parser.add_argument("--release", required=True, type=Path)
    render_parser.add_argument("--source-root", required=True, type=Path)
    render_parser.add_argument("--run-root", required=True, type=Path)
    render_parser.add_argument("--office-root", type=Path)
    render_parser.add_argument("--runtime-python", required=True, type=Path)

    qc_parser = subparsers.add_parser("qc")
    qc_parser.add_argument("--job", required=True, type=Path)
    qc_parser.add_argument("--release", required=True, type=Path)
    qc_parser.add_argument("--source-root", required=True, type=Path)
    qc_parser.add_argument("--run-root", required=True, type=Path)
    qc_parser.add_argument("--gate", required=True)
    qc_parser.add_argument("--office-root", type=Path)
    qc_parser.add_argument("--runtime-python", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate-job":
            result = validate_job(args.job, args.release)
        elif args.command == "verify-source-bundle":
            result, _state = verify_source_bundle(args.job, args.release, args.source_root)
        elif args.command == "render":
            result = render(
                args.job,
                args.release,
                args.source_root,
                args.run_root,
                args.office_root,
                args.runtime_python,
            )
        elif args.command == "qc":
            result = qc(
                args.job,
                args.release,
                args.source_root,
                args.run_root,
                args.gate,
                args.office_root,
                args.runtime_python,
            )
        else:
            _fail(EXIT_SCHEMA, f"unknown command: {args.command!r}")
    except FlowError as exc:
        print(f"ERROR[{exc.code}] {exc}", file=sys.stderr)
        return exc.code
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if args.command == "qc":
        if result["gate_status"] == "FAIL":
            return EXIT_DELEGATE
        if result["gate_status"] == "NOT_APPLICABLE":
            return EXIT_UNSUPPORTED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
