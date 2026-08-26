#!/usr/bin/env python3
"""Portable wrapper for the office-native Hymn Letter v3 contract."""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any

sys.dont_write_bytecode = True

LEGACY_FLOW_PATH = Path(__file__).resolve().with_name("hymn_video_flow.py")
LEGACY_FLOW_SHA256 = "ae6844fd07c3a764f83276a85d801f33c81a6688f8ecac4929170bfd78aec77f"
if LEGACY_FLOW_PATH.is_symlink() or not LEGACY_FLOW_PATH.is_file():
    print(f"ERROR[4] pinned legacy helper is missing or symlinked: {LEGACY_FLOW_PATH}", file=sys.stderr)
    raise SystemExit(4)
with LEGACY_FLOW_PATH.open("rb") as _legacy_handle:
    _legacy_actual_sha256 = hashlib.sha256(_legacy_handle.read()).hexdigest()
if _legacy_actual_sha256 != LEGACY_FLOW_SHA256:
    print(
        f"ERROR[4] pinned legacy helper SHA mismatch: expected {LEGACY_FLOW_SHA256}, got {_legacy_actual_sha256}",
        file=sys.stderr,
    )
    raise SystemExit(4)

_legacy_spec = importlib.util.spec_from_file_location(
    "plugify_hymn_video_flow_pinned", LEGACY_FLOW_PATH
)
if _legacy_spec is None or _legacy_spec.loader is None:
    print(f"ERROR[4] cannot load pinned legacy helper: {LEGACY_FLOW_PATH}", file=sys.stderr)
    raise SystemExit(4)
_legacy_flow = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(_legacy_flow)

EXIT_HASH = _legacy_flow.EXIT_HASH
EXIT_MISSING = _legacy_flow.EXIT_MISSING
EXIT_SCHEMA = _legacy_flow.EXIT_SCHEMA
EXIT_UNSAFE = _legacy_flow.EXIT_UNSAFE
EXIT_UNSUPPORTED = _legacy_flow.EXIT_UNSUPPORTED
FlowError = _legacy_flow.FlowError
_decode_json_bytes = _legacy_flow._decode_json_bytes
_fail = _legacy_flow._fail
_load_json_with_sha256 = _legacy_flow._load_json_with_sha256
_path_within = _legacy_flow._path_within
_read_stable_bytes = _legacy_flow._read_stable_bytes
_require_absolute_path = _legacy_flow._require_absolute_path
_require_exact_keys = _legacy_flow._require_exact_keys
_require_existing_regular_file = _legacy_flow._require_existing_regular_file
_require_nonempty_string = _legacy_flow._require_nonempty_string
_require_positive_int = _legacy_flow._require_positive_int
_require_sha256 = _legacy_flow._require_sha256
_safe_manifest_entry = _legacy_flow._safe_manifest_entry
_sha256_file = _legacy_flow._sha256_file
_write_new_text = _legacy_flow._write_new_text
verify_closed_package = _legacy_flow.verify_package


INVENTORY_SCHEMA = "plugify.hymn-letter.episode-inventory/2"
JOB_SCHEMA = "godowon.hymn-letter.v3-job/1"
SOURCE_BUNDLE_SCHEMA = "godowon.hymn-letter.source-bundle/1"
RELEASE_SCHEMA = "godowon.hymn-letter.v3-release-lock/1"
RUN_RECEIPT_SCHEMA = "plugify.hymn-letter.run-receipt/1"
PACKAGE_SCHEMA = "plugify.hymn-letter.deterministic-package/2"
DELEGATION_INPUTS_SCHEMA = "plugify.hymn-letter.delegation-inputs-lock/1"
PACKAGE_MANIFEST_NAME = "PACKAGE-MANIFEST.json"
PACKAGE_SUMS_NAME = "SHA256SUMS.txt"
REPRODUCTION_DIR = "00_재현자료"
OBJECT_ID_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
EPISODE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9][a-z0-9-]*$")
INPUT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
OUTPUT_FILENAME_RE = re.compile(r"^[^/\\\x00\r\n]{1,176}\.mp4$")
THUMBNAIL_FILENAME_RE = re.compile(r"^[^/\\\x00\r\n]{1,176}\.(jpg|jpeg|png)$")
GATE_VALUES = {"semantic-equivalent", "reference-bit-exact"}
EXIT_DELEGATE = 12
ALLOWED_SYSTEM_SYMLINK_COMPONENTS = {Path("/tmp"), Path("/var")}

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_SHA256 = _sha256_file(SCRIPT_PATH)
UPLOAD_READY_VALIDATOR_PATH = SCRIPT_PATH.with_name("upload_ready_validator.py")
UPLOAD_READY_VALIDATOR_SHA256 = "32de77d1ecb4d6ee69137c4deee8c3a484d46523334f170c6459ff8c35729a71"
SKILL_DIR = SCRIPT_PATH.parent.parent
REFERENCE_DIR = SKILL_DIR / "references"
INVENTORY_PATH = REFERENCE_DIR / "episode-inventory.v2.json"
INVENTORY_SHA256 = "752fecfe218fa4f485c02c2795d9667344920f2a2f513bac26c2eecb7519acc6"
PROJECT_RELEASE_ID = "hymn-letter-caption-v4-interview-soft-20260826"
PROJECT_RELEASE_SHA256 = "24867e11a54c33f69005ed7b033f3996200597697fa99657bb4764ea9ddff7e6"
GOLDEN_SCHEMA = "godowon.hymn-letter.v3-golden-lock/1"
ENVIRONMENT_SCHEMA = "godowon.hymn-letter.environment-lock/1"
PACKAGE_PLAN_SCHEMA = "godowon.hymn-letter.upload-ready-package-plan/1"
RENDER_RECEIPT_SCHEMA = "godowon.hymn-letter.v3-render-receipt/1"
QC_RECEIPT_SCHEMA = "godowon.hymn-letter.v3-qc-receipt/1"
HUMAN_APPROVAL_SCHEMA = "godowon.hymn-letter.human-approval-receipt/1"
UPLOAD_AUTHORITY_SCHEMA = "plugify.hymn-letter.upload-authority-lock/1"
UPLOAD_RECEIPTS_SCHEMA = "plugify.hymn-letter.upload-audio-receipts/1"
RFC3339_SECONDS_RE = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)

INVENTORY_KEYS = {"schema", "release_id", "episodes"}
INVENTORY_EPISODE_KEYS = {
    "sequence",
    "episode_id",
    "kind",
    "profile",
    "container",
    "audio_codec",
    "audio_profile",
    "audio_policy",
    "frame_count",
}
JOB_KEYS = {"schema", "release_id", "episode_id", "profile", "inputs", "settings", "output"}
OUTPUT_KEYS = {"filename", "thumbnail_filename", "container", "audio_codec", "audio_profile", "frame_count"}
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
ENVIRONMENT_KEYS = {
    "schema", "platform", "system", "release", "machine", "python_binary_name",
    "python_version", "python_sha256", "python_implementation", "python_compiler",
    "python_filesystem_encoding", "runtime_locale", "locale_environment",
    "ffmpeg_binary_name", "ffmpeg_sha256", "ffmpeg_version_line", "ffmpeg_build",
    "ffprobe_binary_name", "ffprobe_sha256", "ffprobe_version_line", "libx264_core",
    "libx264_threads", "libx264_lookahead_threads", "python_packages",
    "pillow_native_libraries",
}
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
        "audio_policy": "stream-copy-approved-aac/v1",
        "required_inputs": {"audio_policy", "program_video", "audio", "captions", "backplate", "font", "thumbnail"},
        "settings_keys": {"intro_frames", "intro_style", "post_style"},
    },
    "playlist/v1": {
        "kind": "playlist",
        "container": "mp4",
        "audio_codec": "aac",
        "audio_policy": "gapless-track-concat-aac-lc-256k/v1",
        "required_inputs": {
            "audio_policy",
            "tracks",
            "gapless_audio_contract",
            "caption_timing_contract",
            "chapter_contract",
            "font",
            "thumbnail",
            "active_rows",
        },
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
        "audio_policy": "stream-copy-approved-aac/v1",
        "required_inputs": {"audio_policy", "backplate", "audio", "captions", "font", "thumbnail"},
        "settings_keys": {"style", "restore_audio_edit", "movie_timescale", "video_track_timescale"},
    },
    "hymn-lyrics/v1": {
        "kind": "hymn_lyrics",
        "container": "mp4",
        "audio_codec": "aac",
        "audio_policy": "approved-mp3-to-aac-lc-256k/v1",
        "required_inputs": {"audio_policy", "backplate", "audio", "captions", "font", "thumbnail"},
        "settings_keys": {"style", "movie_timescale", "video_track_timescale"},
    },
}

REQUIRED_RENDERER_MODULES = {
    "aac_common",
    "caption",
    "profiles",
    "mp4",
    "package",
    "qc",
    "playlist_active_rows",
    "avfoundation_probe_source",
}
REQUIRED_RENDERER_MODULE_PATHS = {
    "aac_common": "godo-hymns/tools/hymn_letter_v3_aac_common.py",
    "caption": "godo-hymns/tools/hymn_letter_caption_v3.py",
    "profiles": "godo-hymns/tools/hymn_letter_v3_profiles_aac.py",
    "mp4": "godo-hymns/tools/hymn_letter_v3_mp4_aac.py",
    "package": "godo-hymns/tools/hymn_letter_v3_package_aac.py",
    "qc": "godo-hymns/tools/hymn_letter_v3_qc_aac.py",
    "playlist_active_rows": "godo-hymns/tools/hymn_letter_v3_playlist_active_rows.py",
    "avfoundation_probe_source": "godo-hymns/tools/hymn_letter_avfoundation_probe.m",
}
REQUIRED_SUPPORTED_PROFILES = [
    "start-hybrid/v1",
    "playlist/v1",
    "testimony-static/v1",
    "hymn-lyrics/v1",
]
REQUIRED_RELEASE_JOB_PATHS = {
    "jobs/01_start.json",
    "jobs/02_playlist.json",
    "jobs/03_491_testimony.json",
    "jobs/04_491_hymn.json",
    "jobs/05_370_testimony.json",
    "jobs/06_370_hymn.json",
}
PLAYLIST_TOTAL_SAMPLES = 120_930_048
PLAYLIST_PCM_F32LE_SHA256 = "b88ceebf62e7dbdcfdd0c692a510d399b911f4be47e99e3d7b93c1a79634c5fe"
PLAYLIST_COMBINED_SRT_SHA256 = "85ac5c9af34472639ab66c0a403895a1a5de25cd7479a7e31a5d9d89bb4d0d02"
PLAYLIST_CHAPTERS_SHA256 = "cdf0986a950517085094975a33fb906962f52692002e12acb53262857a5a973e"
PLAYLIST_START_FRAMES = [0, 11752, 18364, 24503, 30453, 35996, 42348, 49820, 56144, 61465, 68365, 75420]
PLAYLIST_SAMPLES = [17275392, 9718758, 9024624, 8745912, 8148798, 9336852, 10984428, 9296280, 7821576, 10143882, 10369674, 10063872]
PLAYLIST_PCM_SHA256 = [
    "2ce54cee2c18193028328cfd0234b2eb4aa7c73b89ab8cf3be4ce3068646fd41",
    "c030614ee7fc33b02ed69a27a45d1b82b95b83425269d196f1c814715cdb0aea",
    "adc913656cda1e9d39959896368c72b33e2a2f25a42e34a321bd37ee2459ffc2",
    "8192251ddbb406f422ea15522d063699dde56c2986f5b4c824b4fabb0018696a",
    "3112d455f4377839542be1c30694402be54225ad694661b46715024155747a0b",
    "d551ce8dd85993de2d61f78f7ed074a40367ae6ff5654230d6956b41e0b0693e",
    "3c9c2f5f19d47f4eec55df50dbdbe3efa5520e7eff4f45d3a5c705d4d39ddb44",
    "a7bc445567c09f882624b779555a1f4173b27e30c264a006d359905ee906f434",
    "42d0bc4720f8f1c1f73689c6bee42fe134f668cb8af08fe370d71b7b84ad9a87",
    "07d3ad1465f82b004de2fedbaf098d47d7b16e802185b4c3502891cddde35062",
    "6b6812d6c0b3e2d20f68f553f35d34ff315156730af6d83c6bfe23eb5676b927",
    "70c695311746b26f2d35d1e8e4091ab51a47ee7074d7c432a9e70316d157a556",
]
PACKAGE_CODE_SNAPSHOTS = {
    SCRIPT_PATH: "hymn-letter-video-production/scripts/hymn_video_flow_v3.py",
    SCRIPT_PATH.with_name("upload_ready_validator.py"): "hymn-letter-video-production/scripts/upload_ready_validator.py",
    SCRIPT_PATH.with_name("hymn_video_flow.py"): "hymn-letter-video-production/scripts/hymn_video_flow.py",
    INVENTORY_PATH: "hymn-letter-video-production/references/episode-inventory.v2.json",
    REFERENCE_DIR / "job-manifest.v2.schema.json": "hymn-letter-video-production/references/job-manifest.v2.schema.json",
    REFERENCE_DIR / "source-bundle.schema.json": "hymn-letter-video-production/references/source-bundle.schema.json",
    REFERENCE_DIR / "release-lock.schema.json": "hymn-letter-video-production/references/release-lock.schema.json",
    REFERENCE_DIR / "run-receipt.schema.json": "hymn-letter-video-production/references/run-receipt.schema.json",
    SKILL_DIR / "SKILL.md": "hymn-letter-video-production/SKILL.md",
    REFERENCE_DIR / "workflow.md": "hymn-letter-video-production/references/workflow.md",
    REFERENCE_DIR / "qc-contract.md": "hymn-letter-video-production/references/qc-contract.md",
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


def _require_byte_size(value: Any, label: str) -> int:
    """Validate byte counts without applying the legacy frame-count ceiling."""
    if type(value) is not int or value <= 0 or value > (2**63 - 1):
        _fail(EXIT_SCHEMA, f"{label} must be a positive signed 64-bit integer")
    return value


def _canonical_rfc3339_seconds(value: Any) -> bool:
    if type(value) is not str or RFC3339_SECONDS_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError:
        return False
    offset = parsed.utcoffset()
    if offset is None or abs(offset.total_seconds()) > 14 * 60 * 60:
        return False
    canonical = (
        parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        if value.endswith("Z")
        else parsed.isoformat(timespec="seconds")
    )
    return value == canonical


def _resolve_source_object_path(source_root: Path, object_id: str) -> Path:
    digest = object_id.split(":", 1)[1]
    candidate = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
    _reject_unsafe_symlink_components(candidate, f"source object {object_id}")
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
        audio_profile = _require_nonempty_string(item["audio_profile"], f"{label}.audio_profile")
        audio_policy = _require_nonempty_string(item["audio_policy"], f"{label}.audio_policy")
        if (
            container != contract["container"]
            or audio_codec != contract["audio_codec"]
            or audio_profile != "LC"
            or audio_policy != contract["audio_policy"]
        ):
            _fail(EXIT_SCHEMA, f"inventory output contract mismatch for {episode_id!r}")
        frame_count = _require_positive_int(item["frame_count"], f"{label}.frame_count")
        episode_map[episode_id] = {
            "sequence": sequence,
            "episode_id": episode_id,
            "kind": kind,
            "profile": profile,
            "container": container,
            "audio_codec": audio_codec,
            "audio_profile": audio_profile,
            "audio_policy": audio_policy,
            "frame_count": frame_count,
        }
    return inventory_path, inventory_hash, episode_map


def _validate_environment_lock(release_path: Path, release: dict[str, Any]) -> dict[str, Any]:
    environment_path = release_path.parent / _safe_relative_path_to_path(
        release["environment_lock"]
    )
    value, digest = _load_json_with_sha256(environment_path, "environment lock")
    if digest != release["environment_lock_sha256"]:
        _fail(EXIT_HASH, "environment lock SHA does not match release lock")
    environment = _require_exact_keys(value, ENVIRONMENT_KEYS, "environment lock")
    if environment["schema"] != ENVIRONMENT_SCHEMA:
        _fail(EXIT_SCHEMA, f"invalid environment lock schema: {environment['schema']!r}")
    for key in (
        "platform", "system", "release", "machine", "python_binary_name",
        "python_version", "python_implementation", "python_compiler",
        "ffmpeg_version_line", "ffmpeg_build", "ffprobe_version_line", "libx264_core",
    ):
        _require_nonempty_string(environment[key], f"environment lock.{key}")
    if environment["ffmpeg_binary_name"] != "ffmpeg":
        _fail(EXIT_SCHEMA, "environment lock.ffmpeg_binary_name must be ffmpeg")
    if environment["ffprobe_binary_name"] != "ffprobe":
        _fail(EXIT_SCHEMA, "environment lock.ffprobe_binary_name must be ffprobe")
    for key in ("python_sha256", "ffmpeg_sha256", "ffprobe_sha256"):
        _require_sha256(environment[key], f"environment lock.{key}")
    if environment["python_filesystem_encoding"] != "utf-8":
        _fail(EXIT_SCHEMA, "environment lock.python_filesystem_encoding must be utf-8")
    if environment["runtime_locale"] != "C":
        _fail(EXIT_SCHEMA, "environment lock.runtime_locale must be C")
    locale_environment = _require_exact_keys(
        environment["locale_environment"], {"LANG", "LC_ALL", "LC_CTYPE"},
        "environment lock.locale_environment",
    )
    if locale_environment != {"LANG": "C", "LC_ALL": "C", "LC_CTYPE": "C"}:
        _fail(EXIT_SCHEMA, "environment lock locale variables must all be C")
    _require_positive_int(environment["libx264_threads"], "environment lock.libx264_threads")
    _require_positive_int(
        environment["libx264_lookahead_threads"],
        "environment lock.libx264_lookahead_threads",
    )
    python_packages = _require_exact_keys(
        environment["python_packages"], {"Pillow", "numpy"},
        "environment lock.python_packages",
    )
    for name, version in python_packages.items():
        _require_nonempty_string(version, f"environment lock.python_packages.{name}")
    native_libraries = _require_exact_keys(
        environment["pillow_native_libraries"],
        {"freetype2", "libjpeg", "libjpeg_turbo", "zlib", "zlib_ng"},
        "environment lock.pillow_native_libraries",
    )
    for name, version in native_libraries.items():
        _require_nonempty_string(
            version, f"environment lock.pillow_native_libraries.{name}"
        )
    return environment


def _require_locked_runtime_environment(
    release_path: Path,
    release: dict[str, Any],
    office_root: Path,
    runtime_python: Path,
    runtime_metadata: dict[str, str],
) -> None:
    locked = _validate_environment_lock(release_path, release)
    version = runtime_metadata["version"].removeprefix("Python ")
    if (
        runtime_python.name != locked["python_binary_name"]
        or runtime_metadata["sha256"] != locked["python_sha256"]
        or version != locked["python_version"]
    ):
        _fail(EXIT_HASH, "runtime Python does not match environment lock")
    ffmpeg_raw = shutil.which("ffmpeg")
    if ffmpeg_raw is None:
        _fail(EXIT_MISSING, "locked ffmpeg is not available on PATH")
    ffmpeg_path = _require_existing_regular_file(
        Path(ffmpeg_raw), "PATH ffmpeg", no_symlink=False
    )
    if (
        ffmpeg_path.name != locked["ffmpeg_binary_name"]
        or _sha256_file(ffmpeg_path) != locked["ffmpeg_sha256"]
    ):
        _fail(EXIT_HASH, "PATH ffmpeg does not match environment lock")
    mp4_module = office_root / _safe_relative_path_to_path(
        release["renderer_modules"]["mp4"]["path"]
    )
    mp4_module = _require_existing_regular_file(
        mp4_module, "office MP4 environment probe module", no_symlink=False
    )
    if _sha256_file(mp4_module) != release["renderer_modules"]["mp4"]["sha256"]:
        _fail(EXIT_HASH, "office MP4 environment probe module SHA mismatch")
    probe_code = (
        "import importlib.util,json,sys;from pathlib import Path;"
        "p=Path(sys.argv[1]);sys.path.insert(0,str(p.parent));"
        "s=importlib.util.spec_from_file_location('hymn_v3_mp4_environment_probe',p);"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
        "print(json.dumps(m.environment_fingerprint(),sort_keys=True,separators=(',',':')))"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C",
            "LC_ALL": "C",
            "LC_CTYPE": "C",
        }
    )
    probe = subprocess.run(
        [str(runtime_python), "-c", probe_code, str(mp4_module)],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if probe.returncode != 0 or probe.stderr or len(probe.stdout.splitlines()) != 1:
        _fail(EXIT_HASH, "locked runtime environment fingerprint probe failed")
    try:
        current = json.loads(probe.stdout)
    except json.JSONDecodeError:
        _fail(EXIT_HASH, "locked runtime environment fingerprint probe returned invalid JSON")
    if type(current) is not dict:
        _fail(EXIT_HASH, "locked runtime environment fingerprint probe must return an object")
    if current != locked:
        differing = sorted(
            key for key in set(current) | set(locked) if current.get(key) != locked.get(key)
        )
        _fail(
            EXIT_HASH,
            f"runtime/Pillow/FFmpeg environment does not match environment lock: {differing}",
        )


def _require_locked_ffprobe(
    release_path: Path,
    release: dict[str, Any],
    ffprobe_path: Path,
) -> None:
    locked = _validate_environment_lock(release_path, release)
    if (
        ffprobe_path.name != locked["ffprobe_binary_name"]
        or _sha256_file(ffprobe_path) != locked["ffprobe_sha256"]
    ):
        _fail(EXIT_HASH, "ffprobe does not match environment lock")


def _load_release(release_argument: Path) -> tuple[Path, str, dict[str, Any]]:
    release_path = _require_existing_regular_file(release_argument, "release lock", no_symlink=False)
    release_value, release_hash = _load_json_with_sha256(release_path, "release lock")
    if release_hash != PROJECT_RELEASE_SHA256:
        _fail(
            EXIT_HASH,
            f"release lock SHA does not match compiled production trust pin: expected {PROJECT_RELEASE_SHA256}, got {release_hash}",
        )
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
        module_path = _safe_release_relative_path(item["path"], f"release lock.renderer_modules.{name}.path")
        if module_path != REQUIRED_RENDERER_MODULE_PATHS[name]:
            _fail(EXIT_SCHEMA, f"release lock.renderer_modules.{name}.path is not canonical")
        normalized_modules[name] = {
            "path": module_path,
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
    _validate_environment_lock(release_path, release)
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
        size = _require_byte_size(entry["size"], f"source bundle object {object_id}.size")
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


def _require_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(EXIT_SCHEMA, f"{label} must be a non-negative integer")
    return value


def _validate_contract_hash(value: Any, label: str) -> str:
    return _require_sha256(value, label)


def _normalize_job_inputs(profile: str, inputs: dict[str, Any]) -> dict[str, list[str]]:
    contract = PROFILE_CONTRACTS[profile]
    actual_keys = set(inputs)
    expected_keys = contract["required_inputs"]
    if actual_keys != expected_keys:
        _fail(
            EXIT_SCHEMA,
            f"job.inputs keys mismatch for {profile!r}; missing={sorted(expected_keys - actual_keys)}, extra={sorted(actual_keys - expected_keys)}",
        )
    audio_policy = _require_nonempty_string(inputs["audio_policy"], "job.inputs.audio_policy")
    if audio_policy != contract["audio_policy"]:
        _fail(EXIT_SCHEMA, f"job.inputs.audio_policy mismatch for {profile!r}")
    if profile != "playlist/v1":
        normalized: dict[str, list[str]] = {}
        for key in sorted(expected_keys - {"audio_policy"}):
            normalized[key] = _normalize_input_value(inputs[key], f"job.inputs.{key}")
            if len(normalized[key]) != 1:
                _fail(EXIT_SCHEMA, f"job.inputs.{key} must contain exactly one object id")
        return normalized

    normalized = {
        "font": _normalize_input_value(inputs["font"], "job.inputs.font"),
        "thumbnail": _normalize_input_value(inputs["thumbnail"], "job.inputs.thumbnail"),
        "active_rows": _normalize_input_value(inputs["active_rows"], "job.inputs.active_rows"),
    }
    for singular_key in ("font", "thumbnail"):
        if len(normalized[singular_key]) != 1:
            _fail(EXIT_SCHEMA, f"job.inputs.{singular_key} must contain exactly one object id")
    if len(normalized["active_rows"]) != 12:
        _fail(EXIT_SCHEMA, "job.inputs.active_rows must contain exactly 12 object ids")
    tracks = inputs["tracks"]
    if type(tracks) is not list or len(tracks) != 12:
        _fail(EXIT_SCHEMA, "job.inputs.tracks must contain exactly 12 ordered tracks")
    track_keys = {
        "index", "hymn_number", "title", "audio", "captions", "samples",
        "pcm_f32le_sha256", "start_sample", "start_frame",
    }
    audio_ids: list[str] = []
    caption_ids: list[str] = []
    cursor = 0
    for offset, raw_track in enumerate(tracks):
        label = f"job.inputs.tracks[{offset}]"
        track = _require_exact_keys(raw_track, track_keys, label)
        index = _require_positive_int(track["index"], f"{label}.index")
        if index != offset + 1:
            _fail(EXIT_SCHEMA, "playlist track indices must be exact 1..12 in array order")
        _require_positive_int(track["hymn_number"], f"{label}.hymn_number")
        _require_nonempty_string(track["title"], f"{label}.title")
        track_audio_ids = _normalize_input_value(track["audio"], f"{label}.audio")
        track_caption_ids = _normalize_input_value(track["captions"], f"{label}.captions")
        if len(track_audio_ids) != 1 or len(track_caption_ids) != 1:
            _fail(EXIT_SCHEMA, f"{label}.audio and captions must each contain exactly one object id")
        audio_ids.extend(track_audio_ids)
        caption_ids.extend(track_caption_ids)
        samples = _require_positive_int(track["samples"], f"{label}.samples")
        pcm_sha256 = _validate_contract_hash(track["pcm_f32le_sha256"], f"{label}.pcm_f32le_sha256")
        start_sample = _require_nonnegative_int(track["start_sample"], f"{label}.start_sample")
        start_frame = _require_nonnegative_int(track["start_frame"], f"{label}.start_frame")
        if start_sample != cursor:
            _fail(EXIT_SCHEMA, f"{label}.start_sample must equal the cumulative preceding samples")
        if start_frame != (start_sample * 30 + 44099) // 44100:
            _fail(EXIT_SCHEMA, f"{label}.start_frame must be ceil(start_sample*30/44100)")
        if (
            samples != PLAYLIST_SAMPLES[offset]
            or pcm_sha256 != PLAYLIST_PCM_SHA256[offset]
            or start_frame != PLAYLIST_START_FRAMES[offset]
        ):
            _fail(EXIT_SCHEMA, f"{label} differs from the locked production sample/PCM/frame vector")
        cursor += samples
    normalized["track_audio"] = audio_ids
    normalized["track_captions"] = caption_ids

    gapless = _require_exact_keys(
        inputs["gapless_audio_contract"],
        {"mode", "sample_rate", "channels", "total_samples", "composite_pcm_f32le_sha256"},
        "job.inputs.gapless_audio_contract",
    )
    if gapless["mode"] != "decode-each-mp3-to-f32le-concat/v1":
        _fail(EXIT_SCHEMA, "unsupported playlist gapless audio contract")
    if gapless["sample_rate"] != 44100 or gapless["channels"] != 2:
        _fail(EXIT_SCHEMA, "playlist gapless audio contract must be stereo 44100 Hz")
    if _require_positive_int(gapless["total_samples"], "job.inputs.gapless_audio_contract.total_samples") != cursor:
        _fail(EXIT_SCHEMA, "playlist total_samples must equal the ordered track sample sum")
    if cursor != PLAYLIST_TOTAL_SAMPLES:
        _fail(EXIT_SCHEMA, "playlist total_samples differs from the locked production total")
    if _validate_contract_hash(gapless["composite_pcm_f32le_sha256"], "job.inputs.gapless_audio_contract.composite_pcm_f32le_sha256") != PLAYLIST_PCM_F32LE_SHA256:
        _fail(EXIT_SCHEMA, "playlist composite PCM hash differs from the locked production value")

    caption_contract = _require_exact_keys(
        inputs["caption_timing_contract"],
        {
            "mode", "sample_rate", "combined_srt_sha256", "cue_count",
            "lyric_cue_count", "title_card_cue_count", "title_card_text_policy",
            "offset_rounding", "title_card_serialization", "title_card_placement",
        },
        "job.inputs.caption_timing_contract",
    )
    if caption_contract["mode"] != "per-track-srt-offset-by-start-sample/v1" or caption_contract["sample_rate"] != 44100:
        _fail(EXIT_SCHEMA, "unsupported playlist caption timing contract")
    if (
        caption_contract["cue_count"] != 279
        or caption_contract["lyric_cue_count"] != 267
        or caption_contract["title_card_cue_count"] != 12
        or caption_contract["title_card_text_policy"] != "sequence-numbered-title-only/v1"
        or caption_contract["offset_rounding"] != "half-up-samples-to-ms/v1"
        or caption_contract["title_card_serialization"] != "{sequence}. {title}"
        or caption_contract["title_card_placement"] != "initial-title-then-next-title-in-prior-track-outro/v1"
    ):
        _fail(EXIT_SCHEMA, "playlist combined SRT must preserve 267 lyric cues and add 12 title-only cards at the locked original intervals")
    if _validate_contract_hash(caption_contract["combined_srt_sha256"], "job.inputs.caption_timing_contract.combined_srt_sha256") != PLAYLIST_COMBINED_SRT_SHA256:
        _fail(EXIT_SCHEMA, "playlist combined SRT hash differs from the locked production value")

    chapter_contract = _require_exact_keys(
        inputs["chapter_contract"],
        {"mode", "sample_rate", "ffmetadata_sha256"},
        "job.inputs.chapter_contract",
    )
    if chapter_contract["mode"] != "track-start-sample/v1" or chapter_contract["sample_rate"] != 44100:
        _fail(EXIT_SCHEMA, "unsupported playlist chapter contract")
    if _validate_contract_hash(chapter_contract["ffmetadata_sha256"], "job.inputs.chapter_contract.ffmetadata_sha256") != PLAYLIST_CHAPTERS_SHA256:
        _fail(EXIT_SCHEMA, "playlist chapter hash differs from the locked production value")
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
        if settings != {"intro_frames": 723, "intro_style": "interview-soft", "post_style": "dense"}:
            _fail(EXIT_SCHEMA, "start-hybrid settings differ from the locked production contract")
    elif profile == "playlist/v1":
        if settings["style"] != "dense" or settings["active_row_state"] != "yellow":
            _fail(EXIT_SCHEMA, "playlist style/active row state differs from the locked contract")
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
        tracks = job["inputs"]["tracks"]
        expected_boundaries = [track["start_frame"] for track in tracks] + [job["output"]["frame_count"]]
        if normalized_boundaries != expected_boundaries:
            _fail(EXIT_SCHEMA, "playlist boundaries must equal ordered track start_frame values plus final frame_count")
        title_policy = _require_exact_keys(
            settings["title_card_policy"],
            {"mode", "expected_titles", "expected_active_rows"},
            "job.settings.title_card_policy",
        )
        if title_policy["mode"] != "playlist-title-only-prior-outro/v1":
            _fail(EXIT_SCHEMA, "unsupported playlist title-card policy")
        expected_titles = title_policy["expected_titles"]
        expected_active_rows = title_policy["expected_active_rows"]
        track_titles = [track["title"] for track in tracks]
        if expected_titles != track_titles:
            _fail(EXIT_SCHEMA, "playlist title-only cards must exactly match the twelve ordered track titles")
        if expected_active_rows != [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
            _fail(EXIT_SCHEMA, "playlist title-only cards must use the locked prior-outro active-row vector")
        if settings["movie_timescale"] != 44100 or settings["video_track_timescale"] != 15360:
            _fail(EXIT_SCHEMA, "playlist timescales differ from the locked production contract")
    elif profile == "testimony-static/v1":
        if settings != {
            "style": "center", "restore_audio_edit": True,
            "movie_timescale": 384000, "video_track_timescale": 15360,
        }:
            _fail(EXIT_SCHEMA, "testimony settings differ from the locked production contract")
    elif profile == "hymn-lyrics/v1":
        if settings != {
            "style": "center", "movie_timescale": 44100, "video_track_timescale": 15360,
        }:
            _fail(EXIT_SCHEMA, "hymn lyric settings differ from the locked production contract")


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
    for key in inputs:
        if not INPUT_KEY_RE.fullmatch(key):
            _fail(EXIT_SCHEMA, f"invalid job input key: {key!r}")
    normalized_inputs = _normalize_job_inputs(profile, inputs)
    output = _require_exact_keys(job["output"], OUTPUT_KEYS, "job.output")
    filename = _require_nonempty_string(output["filename"], "job.output.filename")
    thumbnail_filename = _require_nonempty_string(output["thumbnail_filename"], "job.output.thumbnail_filename")
    if not OUTPUT_FILENAME_RE.fullmatch(filename):
        _fail(EXIT_SCHEMA, "job.output.filename must end in .mp4")
    if not THUMBNAIL_FILENAME_RE.fullmatch(thumbnail_filename):
        _fail(EXIT_SCHEMA, "job.output.thumbnail_filename must end in .jpg/.jpeg/.png")
    container = _require_nonempty_string(output["container"], "job.output.container")
    if container != "mp4":
        _fail(EXIT_SCHEMA, "job.output.container must be mp4")
    audio_codec = _require_nonempty_string(output["audio_codec"], "job.output.audio_codec")
    audio_profile = _require_nonempty_string(output["audio_profile"], "job.output.audio_profile")
    if audio_codec != "aac" or audio_profile != "LC":
        _fail(EXIT_SCHEMA, "job.output audio must be AAC-LC")
    frame_count = _require_positive_int(output["frame_count"], "job.output.frame_count")
    _validate_settings(job, normalized_inputs)
    if (
        container != inventory_episode["container"]
        or audio_codec != inventory_episode["audio_codec"]
        or audio_profile != inventory_episode["audio_profile"]
        or job["inputs"]["audio_policy"] != inventory_episode["audio_policy"]
        or frame_count != inventory_episode["frame_count"]
    ):
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


def verify_upload_ready_contract(
    manifest_argument: Path,
    authority_lock_argument: Path,
    ffprobe_argument: Path,
    release_argument: Path | None = None,
    approval_receipt_argument: Path | None = None,
) -> dict[str, Any]:
    validator_path = _require_existing_regular_file(
        UPLOAD_READY_VALIDATOR_PATH,
        "upload-ready validator",
        no_symlink=True,
    )
    validator_sha256 = _sha256_file(validator_path)
    if validator_sha256 != UPLOAD_READY_VALIDATOR_SHA256:
        _fail(EXIT_HASH, "upload-ready validator SHA mismatch")
    manifest_path, manifest = _load_upload_manifest(manifest_argument)
    manifest_sha256 = _sha256_file(manifest_path)
    authority_path = _require_existing_regular_file(
        authority_lock_argument, "upload authority lock", no_symlink=True
    )
    authority_sha256 = _sha256_file(authority_path)
    ffprobe_path = _require_existing_regular_file(ffprobe_argument, "ffprobe", no_symlink=True)
    ffprobe_sha256 = _sha256_file(ffprobe_path)
    successor_context: tuple[
        Path,
        str,
        dict[str, Any],
        dict[int, tuple[Path, dict[str, Any]]],
        dict[str, Any],
        Path,
        str,
        dict[int, dict[str, Any]],
    ] | None = None
    if manifest.get("release_id") == PROJECT_RELEASE_ID:
        if release_argument is None:
            _fail(EXIT_SCHEMA, "successor verify-upload-ready requires --release as an external trust anchor")
        if approval_receipt_argument is None:
            _fail(EXIT_SCHEMA, "successor verify-upload-ready requires an external --approval-receipt")
        release_path, release_hash, release = _load_release(release_argument)
        _require_complete_release(release)
        # Never execute a caller-selected successor probe before it matches the
        # trusted release environment lock.
        _require_locked_ffprobe(release_path, release, ffprobe_path)
        _require_release_golden_ready(release_path, release, "verify-upload-ready")
        jobs = _collect_release_jobs(release_path, release_hash, release)
        golden = _load_golden_lock(release_path, release)
        approval_path, approval_sha256, approval = _load_human_approval_receipt(
            approval_receipt_argument
        )
        successor_context = (
            release_path,
            release_hash,
            release,
            jobs,
            golden,
            approval_path,
            approval_sha256,
            approval,
        )
    elif release_argument is not None:
        _fail(EXIT_SCHEMA, "the frozen evaluator contract does not accept a successor --release")
    elif approval_receipt_argument is not None:
        _fail(EXIT_SCHEMA, "the frozen evaluator contract does not accept a successor approval receipt")
    try:
        spec = importlib.util.spec_from_file_location("plugify_hymn_upload_ready_validator", validator_path)
        if spec is None or spec.loader is None:
            _fail(EXIT_MISSING, "cannot load pinned upload-ready validator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.validate_upload_ready(manifest_path, authority_path, ffprobe_path)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        _fail(EXIT_SCHEMA, f"upload-ready verification failed: {exc}")
    if (
        _sha256_file(validator_path) != validator_sha256
        or _sha256_file(manifest_path) != manifest_sha256
        or _sha256_file(authority_path) != authority_sha256
        or _sha256_file(ffprobe_path) != ffprobe_sha256
    ):
        _fail(EXIT_UNSAFE, "upload-ready verifier inputs changed during validation")
    if successor_context is not None:
        (
            _release_path,
            release_hash,
            _release,
            jobs,
            golden,
            approval_path,
            approval_sha256,
            approval,
        ) = successor_context
        _bind_successor_upload_graph(
            manifest_path, manifest, authority_path, jobs, golden, approval
        )
        if _sha256_file(approval_path) != approval_sha256:
            _fail(EXIT_UNSAFE, "human approval receipt changed during validation")
        result["release_sha256"] = release_hash
        result["approval_receipt_sha256"] = approval_sha256
    return result


def _load_golden_lock(release_path: Path, release: dict[str, Any]) -> dict[str, Any]:
    golden_path = release_path.parent / _safe_relative_path_to_path(release["golden_lock"])
    golden_value, golden_hash = _load_json_with_sha256(golden_path, "golden lock")
    if golden_hash != release["golden_lock_sha256"]:
        _fail(EXIT_HASH, "golden lock SHA does not match release lock")
    golden = _require_exact_keys(
        golden_value, {"schema", "release_id", "episodes"}, "golden lock"
    )
    if golden["schema"] != GOLDEN_SCHEMA or golden["release_id"] != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, "golden lock schema/release_id mismatch")
    _inventory_path, _inventory_hash, inventory = _load_inventory()
    episodes = golden["episodes"]
    if type(episodes) is not dict or set(episodes) != set(inventory):
        _fail(EXIT_SCHEMA, "golden lock episode set must be exact 01-06 inventory ids")
    base_keys = {
        "output_sha256", "filename", "frame_count", "container",
        "audio_codec", "audio_profile", "profile",
    }
    for episode_id, expected in inventory.items():
        keys = base_keys | (
            {"composite_pcm_f32le_sha256", "combined_srt_sha256", "chapters_sha256"}
            if episode_id == "02-playlist" else set()
        )
        item = _require_exact_keys(episodes[episode_id], keys, f"golden lock.episodes.{episode_id}")
        _require_sha256(item["output_sha256"], f"golden lock.episodes.{episode_id}.output_sha256")
        _require_nonempty_string(item["filename"], f"golden lock.episodes.{episode_id}.filename")
        for field in ("frame_count", "container", "audio_codec", "audio_profile", "profile"):
            if item[field] != expected[field]:
                _fail(EXIT_SCHEMA, f"golden lock.episodes.{episode_id}.{field} differs from inventory")
        if episode_id == "02-playlist":
            for field in ("composite_pcm_f32le_sha256", "combined_srt_sha256", "chapters_sha256"):
                _require_sha256(item[field], f"golden lock.episodes.{episode_id}.{field}")
    return golden


def _load_human_approval_receipt(path_argument: Path) -> tuple[Path, str, dict[int, dict[str, Any]]]:
    path = _require_existing_regular_file(
        path_argument, "human approval receipt", no_symlink=True
    )
    value, digest = _load_json_with_sha256(path, "human approval receipt")
    receipt = _require_exact_keys(
        value, {"schema", "release_id", "episodes"}, "human approval receipt"
    )
    if receipt["schema"] != HUMAN_APPROVAL_SCHEMA or receipt["release_id"] != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, "human approval receipt schema/release_id mismatch")
    raw_episodes = receipt["episodes"]
    if type(raw_episodes) is not list or len(raw_episodes) != 6:
        _fail(EXIT_SCHEMA, "human approval receipt requires exact six episodes")
    by_sequence: dict[int, dict[str, Any]] = {}
    keys = {
        "sequence", "episode_id", "profile", "reviewer", "decision", "reviewed_at",
        "final_file_sha256", "artifact_audio_payload_sha256",
    }
    for index, raw in enumerate(raw_episodes):
        item = _require_exact_keys(raw, keys, f"human approval receipt.episodes[{index}]")
        sequence = _require_positive_int(item["sequence"], f"human approval receipt.episodes[{index}].sequence")
        if sequence not in range(1, 7) or sequence in by_sequence:
            _fail(EXIT_SCHEMA, "human approval receipt sequences must be unique 01-06")
        _require_nonempty_string(item["episode_id"], f"human approval receipt.episodes[{index}].episode_id")
        _require_nonempty_string(item["profile"], f"human approval receipt.episodes[{index}].profile")
        _require_nonempty_string(item["reviewer"], f"human approval receipt.episodes[{index}].reviewer")
        if item["decision"] != "APPROVED":
            _fail(EXIT_SCHEMA, f"human approval receipt sequence {sequence:02d} is not APPROVED")
        reviewed_at = _require_nonempty_string(
            item["reviewed_at"], f"human approval receipt.episodes[{index}].reviewed_at"
        )
        if not _canonical_rfc3339_seconds(reviewed_at):
            _fail(
                EXIT_SCHEMA,
                f"human approval receipt.episodes[{index}].reviewed_at must be canonical RFC3339 seconds",
            )
        _require_sha256(item["final_file_sha256"], f"human approval receipt.episodes[{index}].final_file_sha256")
        _require_sha256(
            item["artifact_audio_payload_sha256"],
            f"human approval receipt.episodes[{index}].artifact_audio_payload_sha256",
        )
        by_sequence[sequence] = item
    if set(by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "human approval receipt sequences must be exact 01-06")
    return path, digest, by_sequence


def _bind_successor_upload_graph(
    manifest_path: Path,
    manifest: dict[str, Any],
    authority_path: Path,
    jobs: dict[int, tuple[Path, dict[str, Any]]],
    golden: dict[str, Any],
    approval: dict[int, dict[str, Any]],
) -> None:
    artifacts = manifest.get("artifacts")
    if type(artifacts) is not list or len(artifacts) != 6:
        _fail(EXIT_SCHEMA, "successor upload-ready artifacts must be exact 01-06")
    artifact_by_sequence = {
        item.get("sequence"): item for item in artifacts if type(item) is dict
    }
    if set(artifact_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "successor upload-ready artifact sequences must be exact 01-06")
    authority_value, authority_hash = _load_json_with_sha256(authority_path, "upload authority lock")
    authority = _require_exact_keys(
        authority_value, {"schema", "release_id", "episodes"}, "upload authority lock"
    )
    if authority["schema"] != UPLOAD_AUTHORITY_SCHEMA:
        _fail(EXIT_SCHEMA, "successor upload authority schema mismatch")
    authority_ref = manifest.get("authority_lock")
    if (
        type(authority_ref) is not dict
        or authority_hash != authority_ref.get("sha256")
        or authority.get("release_id") != PROJECT_RELEASE_ID
    ):
        _fail(EXIT_HASH, "successor upload authority lock binding mismatch")
    authority_episodes = authority.get("episodes")
    if type(authority_episodes) is not list or len(authority_episodes) != 6:
        _fail(EXIT_SCHEMA, "successor authority requires exact six episodes")
    authority_by_sequence = {
        item.get("sequence"): item for item in authority_episodes if type(item) is dict
    }
    if set(authority_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "successor authority sequences must be exact 01-06")

    receipt_ref = manifest.get("receipts")
    if type(receipt_ref) is not dict:
        _fail(EXIT_SCHEMA, "successor upload receipts reference missing")
    receipt_path = _resolve_manifest_file(
        manifest_path.parent.resolve(), receipt_ref.get("path"), "successor upload receipts"
    )
    receipt_value, receipt_hash = _load_json_with_sha256(receipt_path, "successor upload receipts")
    receipts = _require_exact_keys(
        receipt_value, {"schema", "release_id", "entries"}, "successor upload receipts"
    )
    if receipts["schema"] != UPLOAD_RECEIPTS_SCHEMA:
        _fail(EXIT_SCHEMA, "successor upload receipts schema mismatch")
    if receipt_hash != receipt_ref.get("sha256") or receipts.get("release_id") != PROJECT_RELEASE_ID:
        _fail(EXIT_HASH, "successor upload receipts binding mismatch")
    receipt_entries = receipts.get("entries")
    if type(receipt_entries) is not list or len(receipt_entries) != 6:
        _fail(EXIT_SCHEMA, "successor upload receipts require exact six entries")
    receipt_by_sequence = {
        item.get("sequence"): item for item in receipt_entries if type(item) is dict
    }
    if set(receipt_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "successor upload receipt sequences must be exact 01-06")

    for sequence in range(1, 7):
        artifact = artifact_by_sequence[sequence]
        locked = authority_by_sequence[sequence]
        receipt = receipt_by_sequence[sequence]
        _job_path, state = jobs[sequence]
        episode = state["episode"]
        job = state["job"]
        golden_episode = golden["episodes"][episode["episode_id"]]
        identity = (episode["episode_id"], episode["profile"])
        if any(
            (item.get("episode_id"), item.get("profile")) != identity
            for item in (artifact, locked, receipt, approval[sequence])
        ):
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: successor release identity binding mismatch")
        if locked.get("frame_count") != job["output"]["frame_count"]:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: authority frame_count differs from job")
        if any(
            golden_episode[field] != job["output"][field]
            for field in ("filename", "frame_count", "container", "audio_codec", "audio_profile")
        ):
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: golden output contract differs from job")
        final_ref = artifact.get("final_media")
        if type(final_ref) is not dict:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: successor final reference missing")
        final_hash = _require_sha256(final_ref.get("sha256"), f"sequence {sequence:02d} final sha256")
        if final_hash != golden_episode["output_sha256"] or final_hash != approval[sequence]["final_file_sha256"]:
            _fail(EXIT_HASH, f"sequence {sequence:02d}: final is not bound to golden and human approval")
        source_ref = artifact.get("source_audio")
        if sequence == 2:
            if type(source_ref) is not list or len(source_ref) != 12:
                _fail(EXIT_SCHEMA, "sequence 02: successor source_audio must be exact 12 tracks")
            job_tracks = job["inputs"]["tracks"]
            expected_source_hashes = [
                object_id.split(":", 1)[1] for object_id in state["inputs"]["track_audio"]
            ]
            actual_source_hashes = [item.get("sha256") for item in source_ref if type(item) is dict]
            if actual_source_hashes != expected_source_hashes:
                _fail(EXIT_HASH, "sequence 02: upload source tracks differ from job object ids")
            approved_tracks = locked.get("approved_source_tracks")
            if type(approved_tracks) is not list or [item.get("sha256") for item in approved_tracks] != expected_source_hashes:
                _fail(EXIT_HASH, "sequence 02: authority source tracks differ from job object ids")
            if [item.get("decoded_pcm_sha256") for item in approved_tracks] != [
                track["pcm_f32le_sha256"] for track in job_tracks
            ]:
                _fail(EXIT_HASH, "sequence 02: authority decoded PCM vector differs from job")
            caption_contract = job["inputs"]["caption_timing_contract"]
            chapter_contract = job["inputs"]["chapter_contract"]
            gapless_contract = job["inputs"]["gapless_audio_contract"]
            if (
                golden_episode["composite_pcm_f32le_sha256"] != gapless_contract["composite_pcm_f32le_sha256"]
                or golden_episode["combined_srt_sha256"] != caption_contract["combined_srt_sha256"]
                or golden_episode["chapters_sha256"] != chapter_contract["ffmetadata_sha256"]
                or locked.get("captions_sha256") != caption_contract["combined_srt_sha256"]
                or locked.get("chapters_sha256") != chapter_contract["ffmetadata_sha256"]
            ):
                _fail(EXIT_HASH, "sequence 02: golden/authority timeline hashes differ from job")
        else:
            if type(source_ref) is not dict:
                _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: successor source_audio must be one object")
            expected_source_hash = state["inputs"]["audio"][0].split(":", 1)[1]
            if (
                source_ref.get("sha256") != expected_source_hash
                or locked.get("approved_source_audio_sha256") != expected_source_hash
            ):
                _fail(EXIT_HASH, f"sequence {sequence:02d}: approved source differs from job audio object")
        receipt_approval = receipt.get("approval")
        authority_approval = locked.get("approval_authority")
        human = approval[sequence]
        if type(receipt_approval) is not dict or type(authority_approval) is not dict:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: approval evidence missing")
        if any(
            evidence.get(field) != human[field]
            for evidence in (receipt_approval, authority_approval)
            for field in ("reviewer", "decision", "reviewed_at")
        ):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: human approval identity/time binding mismatch")
        if (
            receipt.get("final_file_sha256") != human["final_file_sha256"]
            or receipt_approval.get("artifact_audio_payload_sha256")
            != human["artifact_audio_payload_sha256"]
        ):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: human approval hash binding mismatch")


def _golden_requires_bootstrap(value: Any) -> bool:
    if type(value) is dict:
        if value.get("status") == "BOOTSTRAP_REQUIRED":
            return True
        if "reference_output_sha256" in value and value["reference_output_sha256"] is None:
            return True
        if value.get("output_sha256") == "0" * 64:
            return True
        return any(_golden_requires_bootstrap(item) for item in value.values())
    if type(value) is list:
        return any(_golden_requires_bootstrap(item) for item in value)
    return False


def _require_release_golden_ready(release_path: Path, release: dict[str, Any], operation: str) -> None:
    if _golden_requires_bootstrap(_load_golden_lock(release_path, release)):
        _fail(
            EXIT_UNSUPPORTED,
            f"{operation} is blocked while golden status is BOOTSTRAP_REQUIRED or reference_output_sha256 is null",
        )


def _require_renderer_modules_pinned(release: dict[str, Any], operation: str) -> None:
    unpinned = sorted(
        name
        for name, module in release["renderer_modules"].items()
        if module["sha256"] == "0" * 64
    )
    if unpinned:
        _fail(
            EXIT_UNSUPPORTED,
            f"{operation} is blocked while renderer module pins are BOOTSTRAP_REQUIRED: {unpinned}",
        )


def _reject_ds_store_tree(root: Path, label: str) -> None:
    for candidate in root.rglob(".DS_Store"):
        if os.path.lexists(candidate):
            _fail(EXIT_UNSAFE, f"{label} contains forbidden incidental metadata: {candidate}")


def _resolve_manifest_file(root: Path, raw: Any, label: str) -> Path:
    relative = _safe_release_relative_path(raw, label)
    candidate = root / _safe_relative_path_to_path(relative)
    if candidate.is_symlink():
        _fail(EXIT_UNSAFE, f"{label} must not be a symlink: {candidate}")
    resolved = _require_existing_regular_file(candidate, label, no_symlink=True)
    if not _path_within(resolved, root):
        _fail(EXIT_UNSAFE, f"{label} escapes manifest root")
    return resolved


def _copy_new_verified(source: Path, destination: Path, expected_sha256: str) -> int:
    source = _require_existing_regular_file(source, "package source", no_symlink=True)
    if _sha256_file(source) != expected_sha256:
        _fail(EXIT_HASH, f"package source SHA changed before copy: {source}")
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    _reject_unsafe_symlink_components(destination.parent, "package payload parent")
    try:
        with source.open("rb") as source_handle, destination.open("xb") as destination_handle:
            shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
    except FileExistsError:
        _fail(EXIT_UNSAFE, f"package payload overwrite refused: {destination}")
    except OSError as exc:
        _fail(EXIT_UNSAFE, f"cannot copy package payload {destination}: {exc}")
    if _sha256_file(source) != expected_sha256 or _sha256_file(destination) != expected_sha256:
        _fail(EXIT_HASH, f"package source/destination changed during copy: {destination}")
    return destination.stat().st_size


def _load_upload_manifest(manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = _require_existing_regular_file(manifest_path, "upload-ready manifest", no_symlink=True)
    value, _digest = _load_json_with_sha256(manifest_path, "upload-ready manifest")
    if type(value) is not dict:
        _fail(EXIT_SCHEMA, "upload-ready manifest must be an object")
    return manifest_path, value


def _collect_release_jobs(
    release_path: Path,
    release_hash: str,
    release: dict[str, Any],
) -> dict[int, tuple[Path, dict[str, Any]]]:
    jobs_by_sequence: dict[int, tuple[Path, dict[str, Any]]] = {}
    for relative in sorted(release["jobs"]):
        job_path = release_path.parent / _safe_relative_path_to_path(relative)
        _path, _job_hash, state = _load_job(job_path, release_path, release_hash, release)
        sequence = state["episode"]["sequence"]
        if sequence in jobs_by_sequence:
            _fail(EXIT_SCHEMA, f"duplicate release job sequence: {sequence}")
        jobs_by_sequence[sequence] = (job_path, state)
    if set(jobs_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "package requires exact release jobs for sequences 01-06")
    return jobs_by_sequence


def _require_complete_release(release: dict[str, Any]) -> None:
    if set(release["jobs"]) != REQUIRED_RELEASE_JOB_PATHS:
        _fail(EXIT_SCHEMA, "successor promotion/package release must register the canonical six job paths")
    if release["supported_profiles"] != REQUIRED_SUPPORTED_PROFILES:
        _fail(EXIT_SCHEMA, "successor promotion/package supported_profiles must be the canonical ordered four")
    _require_renderer_modules_pinned(release, "promotion/package")


def _verify_all_source_objects(
    release_path: Path,
    release: dict[str, Any],
    source_root_argument: Path,
) -> tuple[Path, str, dict[str, dict[str, Any]], Path]:
    bundle_path, bundle_hash, object_map = _load_source_bundle(release_path, release)
    source_root_raw = _require_absolute_path(str(source_root_argument), "source root")
    source_root = _normalize_existing_directory(source_root_raw, "source root")
    for object_id, entry in sorted(object_map.items()):
        object_path = _resolve_source_object_path(source_root, object_id)
        if _sha256_file(object_path) != entry["sha256"] or object_path.stat().st_size != entry["size"]:
            _fail(EXIT_HASH, f"source object bytes/size mismatch: {object_id}")
    return bundle_path, bundle_hash, object_map, source_root


def _require_output_disjoint(output: Path, roots: dict[str, Path]) -> None:
    output = output.resolve(strict=False)
    for label, root in roots.items():
        resolved_root = root.resolve(strict=True)
        if _path_within(output, resolved_root) or _path_within(resolved_root, output):
            _fail(EXIT_UNSAFE, f"package output must be disjoint from {label}: {resolved_root}")


def _atomic_promote_new_directory(source: Path, destination: Path) -> tuple[int, int]:
    """Atomically rename a directory without ever replacing an existing path."""

    try:
        source_metadata = source.lstat()
    except OSError as exc:
        _fail(EXIT_UNSAFE, f"cannot inspect package staging directory: {exc}")
    if source.is_symlink() or not source.is_dir():
        _fail(EXIT_UNSAFE, f"package staging path is not a real directory: {source}")
    if os.path.lexists(destination):
        _fail(EXIT_UNSAFE, f"package directory appeared during build; overwrite refused: {destination}")

    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    result: int
    if sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename_exclusive = 0x00000004
        renamex_np = libc.renamex_np
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, rename_exclusive)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        at_fdcwd = -100
        rename_noreplace = 1
        renameat2 = libc.renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            at_fdcwd,
            source_bytes,
            at_fdcwd,
            destination_bytes,
            rename_noreplace,
        )
    else:
        _fail(EXIT_UNSUPPORTED, "platform lacks an atomic no-replace directory promotion primitive")

    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            _fail(
                EXIT_UNSAFE,
                f"package directory appeared during build; overwrite refused: {destination}",
            )
        _fail(
            EXIT_UNSAFE,
            f"cannot atomically promote verified package: {os.strerror(error_number)}",
        )
    try:
        promoted_metadata = destination.lstat()
    except OSError as exc:
        _fail(EXIT_UNSAFE, f"cannot inspect promoted package directory: {exc}")
    identity = (source_metadata.st_dev, source_metadata.st_ino)
    if (
        source.exists()
        or destination.is_symlink()
        or not destination.is_dir()
        or (promoted_metadata.st_dev, promoted_metadata.st_ino) != identity
    ):
        _fail(EXIT_UNSAFE, "atomic package promotion identity check failed")
    return identity


def _retract_failed_promotion(
    package_dir: Path,
    private_temporary_root: Path,
    expected_identity: tuple[int, int],
) -> None:
    """Move a failed just-created final back under the private temporary root."""

    try:
        metadata = os.lstat(package_dir)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != expected_identity
        ):
            _fail(EXIT_UNSAFE, "failed promoted package identity changed before retraction")
        retracted = private_temporary_root / "retracted-failed-package"
        if os.path.lexists(retracted):
            _fail(EXIT_UNSAFE, "failed package retraction target already exists")
        os.rename(package_dir, retracted)
        retracted_metadata = os.lstat(retracted)
        if (
            os.path.lexists(package_dir)
            or (retracted_metadata.st_dev, retracted_metadata.st_ino) != expected_identity
        ):
            _fail(EXIT_UNSAFE, "failed package retraction identity check failed")
    except FlowError:
        raise
    except OSError as exc:
        _fail(EXIT_UNSAFE, f"cannot retract failed promoted package: {exc}")


def package_release(
    manifest_argument: Path,
    authority_lock_argument: Path,
    ffprobe_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
    office_root_argument: Path | None,
    approval_receipt_argument: Path,
    package_dir_argument: Path,
    delegation_lock_argument: Path | None = None,
    expected_delegated_receipts: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    package_raw = _require_absolute_path(str(package_dir_argument), "package directory")
    _reject_unsafe_symlink_components(package_raw.parent, "package parent")
    if os.path.lexists(package_raw):
        _fail(EXIT_UNSAFE, f"package directory already exists; overwrite refused: {package_raw}")
    parent = _normalize_existing_directory(package_raw.parent, "package parent")
    package_dir = parent / package_raw.name
    if delegation_lock_argument is None or expected_delegated_receipts is None:
        _fail(
            EXIT_SCHEMA,
            "successor package construction requires the plan delegate input lock and receipt snapshots",
        )
    delegation_lock_path = _require_existing_regular_file(
        delegation_lock_argument, "delegation inputs lock", no_symlink=True
    )
    delegation_inputs_sha256 = _sha256_file(delegation_lock_path)

    upload_result = verify_upload_ready_contract(
        manifest_argument,
        authority_lock_argument,
        ffprobe_argument,
        release_argument,
        approval_receipt_argument,
    )
    manifest_path, upload_manifest = _load_upload_manifest(manifest_argument)
    manifest_root = manifest_path.parent.resolve()
    release_path, release_hash, release = _load_release(release_argument)
    _require_complete_release(release)
    _require_release_golden_ready(release_path, release, "package")
    if upload_manifest.get("release_id") != release["release_id"]:
        _fail(EXIT_SCHEMA, "upload-ready release_id does not match release lock")
    jobs = _collect_release_jobs(release_path, release_hash, release)
    bundle_path, bundle_hash, object_map, source_root = _verify_all_source_objects(
        release_path, release, source_root_argument
    )
    if office_root_argument is None:
        office_root_raw = _default_office_root()
    else:
        office_root_raw = _require_absolute_path(str(office_root_argument), "office root")
    office_root = _normalize_existing_directory(office_root_raw, "office root")
    office_modules = _snapshot_office_modules(release, office_root)
    approval_path, approval_hash, _approval = _load_human_approval_receipt(approval_receipt_argument)

    _require_output_disjoint(
        package_dir,
        {
            "upload-ready root": manifest_root,
            "release root": release_path.parent,
            "source root": source_root,
            "office root": office_root,
            "Plugify root": _plugify_root(),
            "human approval root": approval_path.parent,
        },
    )

    _reject_ds_store_tree(manifest_root, "upload-ready root")
    _reject_ds_store_tree(release_path.parent, "release root")
    _reject_ds_store_tree(source_root, "source root")

    artifacts = upload_manifest.get("artifacts")
    if type(artifacts) is not list or len(artifacts) != 6:
        _fail(EXIT_SCHEMA, "upload-ready manifest must contain exact six artifacts")
    artifact_by_sequence = {item.get("sequence"): item for item in artifacts if type(item) is dict}
    if set(artifact_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "upload-ready artifact sequences must be exact 01-06")

    payloads: dict[str, tuple[Path, str, str]] = {}
    generated_payloads: dict[str, tuple[bytes, str, str]] = {}

    def add_payload(relative: str, source: Path, role: str, expected_sha256: str | None = None) -> None:
        safe_relative = _safe_manifest_entry(relative, 0)
        if PurePosixPath(safe_relative).name == ".DS_Store":
            _fail(EXIT_UNSAFE, "package may not contain .DS_Store")
        if safe_relative in payloads:
            _fail(EXIT_SCHEMA, f"duplicate deterministic package path: {safe_relative}")
        digest = _sha256_file(source)
        if expected_sha256 is not None and digest != expected_sha256:
            _fail(EXIT_HASH, f"package input SHA mismatch for {safe_relative}")
        payloads[safe_relative] = (source, role, digest)

    for sequence in range(1, 7):
        artifact = artifact_by_sequence[sequence]
        job_path, state = jobs[sequence]
        if (artifact.get("episode_id"), artifact.get("profile")) != (
            state["episode"]["episode_id"], state["episode"]["profile"]
        ):
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: upload/job identity mismatch")
        final_ref = artifact.get("final_media")
        if type(final_ref) is not dict:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: final media reference missing")
        final_path = _resolve_manifest_file(manifest_root, final_ref.get("path"), f"sequence {sequence:02d} final")
        add_payload(
            f"{sequence:02d}/{state['job']['output']['filename']}",
            final_path,
            f"episode-media:{sequence:02d}",
            _require_sha256(final_ref.get("sha256"), f"sequence {sequence:02d} final sha256"),
        )
        thumbnail_id = state["inputs"]["thumbnail"]
        if len(thumbnail_id) != 1:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: thumbnail input must be exactly one object")
        thumbnail_path = _resolve_source_object_path(source_root, thumbnail_id[0])
        add_payload(
            f"{sequence:02d}/{state['job']['output']['thumbnail_filename']}",
            thumbnail_path,
            f"episode-thumbnail:{sequence:02d}",
            thumbnail_id[0].split(":", 1)[1],
        )

    release_prefix = f"{REPRODUCTION_DIR}/release"
    add_payload(f"{release_prefix}/release.lock.json", release_path, "release-lock", release_hash)
    add_payload(
        f"{release_prefix}/{release['source_bundle_lock']}",
        bundle_path,
        "release-source-bundle-lock",
        bundle_hash,
    )
    for lock_key, role in (("environment_lock", "environment-lock"), ("golden_lock", "golden-lock")):
        source = release_path.parent / _safe_relative_path_to_path(release[lock_key])
        add_payload(f"{release_prefix}/{release[lock_key]}", source, role, release[f"{lock_key}_sha256"])
    for relative, expected_hash in sorted(release["jobs"].items()):
        source = release_path.parent / _safe_relative_path_to_path(relative)
        add_payload(f"{release_prefix}/{relative}", source, "release-job", expected_hash)

    source_prefix = f"{REPRODUCTION_DIR}/source_bundle"
    add_payload(f"{source_prefix}/source-bundle.lock.json", bundle_path, "source-bundle-lock", bundle_hash)
    for object_id, entry in sorted(object_map.items()):
        digest = object_id.split(":", 1)[1]
        source = _resolve_source_object_path(source_root, object_id)
        add_payload(
            f"{source_prefix}/objects/sha256/{digest[:2]}/{digest[2:]}",
            source,
            "source-object",
            entry["sha256"],
        )

    office_prefix = f"{REPRODUCTION_DIR}/code/office"
    for name, snapshot in sorted(office_modules.items()):
        module = release["renderer_modules"][name]
        add_payload(
            f"{office_prefix}/{module['path']}",
            Path(snapshot["path"]),
            f"renderer-module:{name}",
            module["sha256"],
        )
    plugify_prefix = f"{REPRODUCTION_DIR}/code/plugify"
    package_code_hashes: dict[Path, str] = {}
    for source, relative in sorted(PACKAGE_CODE_SNAPSHOTS.items(), key=lambda item: item[1]):
        source = _require_existing_regular_file(source, "Plugify package code snapshot", no_symlink=False)
        source_hash = _sha256_file(source)
        package_code_hashes[source] = source_hash
        add_payload(
            f"{plugify_prefix}/{relative}",
            source,
            "plugify-code",
            source_hash,
        )

    authority_ref = upload_manifest["authority_lock"]
    receipt_ref = upload_manifest["receipts"]
    authority_path = _resolve_manifest_file(manifest_root, authority_ref["path"], "authority lock")
    receipts_path = _resolve_manifest_file(manifest_root, receipt_ref["path"], "receipts")
    receipt_prefix = f"{REPRODUCTION_DIR}/receipts"
    add_payload(f"{receipt_prefix}/upload-ready.json", manifest_path, "upload-ready-manifest")
    add_payload(
        f"{receipt_prefix}/human-approval.json",
        approval_path,
        "human-approval-receipt",
        approval_hash,
    )
    add_payload(
        f"{receipt_prefix}/{_safe_release_relative_path(authority_ref['path'], 'authority lock package path')}",
        authority_path,
        "upload-authority-lock",
        authority_ref["sha256"],
    )
    add_payload(
        f"{receipt_prefix}/{_safe_release_relative_path(receipt_ref['path'], 'receipt package path')}",
        receipts_path,
        "upload-receipts",
        receipt_ref["sha256"],
    )
    for sequence in range(1, 7):
        artifact = artifact_by_sequence[sequence]
        refs: list[dict[str, Any]] = [artifact["final_media"]]
        source_audio = artifact["source_audio"]
        if type(source_audio) is dict:
            refs.append(source_audio)
        elif type(source_audio) is list:
            refs.extend(source_audio)
        else:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: upload source_audio reference invalid")
        for ref_index, ref in enumerate(refs):
            if type(ref) is not dict:
                _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: upload media reference invalid")
            relative = _safe_release_relative_path(ref.get("path"), f"sequence {sequence:02d} upload media path")
            source = _resolve_manifest_file(manifest_root, relative, f"sequence {sequence:02d} upload media")
            digest = _require_sha256(ref.get("sha256"), f"sequence {sequence:02d} upload media sha256")
            add_payload(
                f"{receipt_prefix}/{relative}",
                source,
                "upload-graph-media",
                digest,
            )
    delegated_receipts = manifest_root / REPRODUCTION_DIR / "receipts"
    add_payload(
        f"{receipt_prefix}/delegation-inputs.lock.json",
        delegation_lock_path,
        "delegation-inputs-lock",
        delegation_inputs_sha256,
    )
    if not delegated_receipts.is_dir() or delegated_receipts.is_symlink():
        _fail(EXIT_MISSING, "office package stage is missing delegated receipt copies")
    _reject_unsafe_symlink_components(delegated_receipts, "delegated receipt root")
    delegated_receipts_resolved = delegated_receipts.resolve(strict=True)
    if not _path_within(delegated_receipts_resolved, manifest_root):
        _fail(EXIT_UNSAFE, "delegated receipt root escapes upload-ready root")
    for receipt_source in sorted(delegated_receipts.rglob("*")):
        if receipt_source.is_dir():
            continue
        _reject_unsafe_symlink_components(receipt_source, "delegated receipt")
        if receipt_source.is_symlink() or not receipt_source.is_file():
            _fail(EXIT_UNSAFE, f"delegated receipt is not a regular file: {receipt_source}")
        resolved_receipt = receipt_source.resolve(strict=True)
        if not _path_within(resolved_receipt, delegated_receipts_resolved):
            _fail(EXIT_UNSAFE, f"delegated receipt escapes receipt root: {receipt_source}")
        relative = resolved_receipt.relative_to(delegated_receipts_resolved).as_posix()
        add_payload(f"{receipt_prefix}/run/{relative}", resolved_receipt, "run-receipt")
    expected_run_paths = {
        f"{receipt_prefix}/run/{sequence:02d}-{stage}_receipt.json"
        for sequence in range(1, 7)
        for stage in ("render", "qc")
    }
    actual_run_paths = {
        relative for relative, (_source, role, _digest) in payloads.items()
        if role == "run-receipt"
    }
    if actual_run_paths != expected_run_paths:
        _fail(EXIT_SCHEMA, "delegated receipt copy exact set mismatch")
    for sequence in range(1, 7):
        expected = expected_delegated_receipts.get(sequence)
        if type(expected) is not dict or set(expected) != {"render", "qc"}:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: delegated snapshot hash map invalid")
        for stage in ("render", "qc"):
            relative = f"{receipt_prefix}/run/{sequence:02d}-{stage}_receipt.json"
            if payloads[relative][2] != expected[stage]:
                _fail(
                    EXIT_HASH,
                    f"sequence {sequence:02d}: staged {stage} receipt differs from stable input snapshot",
                )

    with tempfile.TemporaryDirectory(prefix=f".{package_dir.name}.building-", dir=parent) as temporary:
        build_dir = Path(temporary) / "package"
        build_dir.mkdir(mode=0o755)
        entries: list[dict[str, Any]] = []
        for relative in sorted(set(payloads) | set(generated_payloads)):
            if relative in payloads:
                source, role, digest = payloads[relative]
                size = _copy_new_verified(source, build_dir / _safe_relative_path_to_path(relative), digest)
            else:
                content, role, digest = generated_payloads[relative]
                destination = build_dir / _safe_relative_path_to_path(relative)
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                try:
                    with destination.open("xb") as handle:
                        handle.write(content)
                except OSError as exc:
                    _fail(EXIT_UNSAFE, f"cannot create generated package payload {relative}: {exc}")
                if _sha256_file(destination) != digest:
                    _fail(EXIT_HASH, f"generated package payload hash mismatch: {relative}")
                size = len(content)
            entries.append({"path": relative, "role": role, "sha256": digest, "size": size})
        package_manifest = {
            "schema": PACKAGE_SCHEMA,
            "build_mode": "office-plan-delegate-unattested/v1",
            "release_id": release["release_id"],
            "release_sha256": release_hash,
            "source_bundle_sha256": bundle_hash,
            "upload_ready_sha256": _sha256_file(manifest_path),
            "human_approval_sha256": approval_hash,
            "delegation_inputs_sha256": delegation_inputs_sha256,
            "entries": entries,
        }
        package_manifest_path = build_dir / PACKAGE_MANIFEST_NAME
        _write_new_text(
            package_manifest_path,
            json.dumps(package_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        )
        package_manifest_sha256 = _sha256_file(package_manifest_path)
        checksum_entries = {
            **{relative: digest for relative, (_source, _role, digest) in payloads.items()},
            **{relative: digest for relative, (_content, _role, digest) in generated_payloads.items()},
            PACKAGE_MANIFEST_NAME: package_manifest_sha256,
        }
        sums_text = "".join(
            f"{checksum_entries[relative]}  {relative}\n" for relative in sorted(checksum_entries)
        )
        sums_path = build_dir / PACKAGE_SUMS_NAME
        _write_new_text(sums_path, sums_text)
        verification = verify_deterministic_package(
            build_dir, sums_path, release_path, approval_path
        )
        if _sha256_file(SCRIPT_PATH) != SCRIPT_SHA256:
            _fail(EXIT_UNSAFE, "Plugify package wrapper changed during package build")
        if _sha256_file(UPLOAD_READY_VALIDATOR_PATH) != UPLOAD_READY_VALIDATOR_SHA256:
            _fail(EXIT_UNSAFE, "upload-ready validator changed during package build")
        if any(
            _sha256_file(source) != expected_hash
            for source, expected_hash in package_code_hashes.items()
        ):
            _fail(EXIT_UNSAFE, "Plugify package code snapshot changed during package build")
        if _sha256_file(release_path) != release_hash or _sha256_file(approval_path) != approval_hash:
            _fail(EXIT_UNSAFE, "external release/approval trust anchor changed during package build")
        if _sha256_file(delegation_lock_argument) != delegation_inputs_sha256:
            _fail(EXIT_UNSAFE, "delegation input lock changed during package build")
        _reject_ds_store_tree(build_dir, "verified package staging")
        staging_metadata = os.lstat(build_dir)
        expected_promoted_identity = (staging_metadata.st_dev, staging_metadata.st_ino)
        try:
            promoted_identity = _atomic_promote_new_directory(build_dir, package_dir)
            if promoted_identity != expected_promoted_identity:
                _fail(EXIT_UNSAFE, "promoted package identity differs from verified staging")
            verification = verify_deterministic_package(
                package_dir,
                package_dir / PACKAGE_SUMS_NAME,
                release_path,
                approval_path,
            )
            _reject_ds_store_tree(package_dir, "promoted package")
        except BaseException:
            try:
                destination_metadata = os.lstat(package_dir)
            except FileNotFoundError:
                destination_metadata = None
            except OSError as exc:
                _fail(EXIT_UNSAFE, f"cannot inspect failed package promotion: {exc}")
            if destination_metadata is not None and (
                destination_metadata.st_dev,
                destination_metadata.st_ino,
            ) == expected_promoted_identity:
                _retract_failed_promotion(
                    package_dir,
                    Path(temporary),
                    expected_promoted_identity,
                )
            raise
    return {
        "command": "package",
        "package_dir": str(package_dir),
        "package_manifest_sha256": package_manifest_sha256,
        "payload_count": verification["payload_count"],
        "delegation_origin": verification["delegation_origin"],
        "status": "ok",
        "verified_sequences": upload_result["verified_sequences"],
    }


def _load_bound_package_plan(
    plan_path: Path,
    release_path: Path,
    release_hash: str,
    release: dict[str, Any],
    source_root: Path,
    approval: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[int, dict[str, Path]]]:
    value, plan_hash = _load_json_with_sha256(plan_path, "package plan")
    plan = _require_exact_keys(
        value, {"schema", "release", "source_root", "episodes"}, "package plan"
    )
    if plan["schema"] != PACKAGE_PLAN_SCHEMA:
        _fail(EXIT_SCHEMA, "package plan schema mismatch")
    plan_release_raw = _require_absolute_path(str(plan["release"]), "package plan.release")
    plan_release = _require_existing_regular_file(
        plan_release_raw, "package plan.release", no_symlink=True
    )
    if plan_release != release_path or _sha256_file(plan_release) != release_hash:
        _fail(EXIT_HASH, "package plan.release does not match --release")
    plan_source_raw = _require_absolute_path(str(plan["source_root"]), "package plan.source_root")
    plan_source = _normalize_existing_directory(plan_source_raw, "package plan.source_root")
    if plan_source != source_root:
        _fail(EXIT_SCHEMA, "package plan.source_root does not match --source-root")
    jobs = _collect_release_jobs(release_path, release_hash, release)
    episodes = plan["episodes"]
    if type(episodes) is not list or len(episodes) != 6:
        _fail(EXIT_SCHEMA, "package plan requires exact six episode rows")
    by_sequence: dict[int, dict[str, Path]] = {}
    for index, raw in enumerate(episodes):
        item = _require_exact_keys(
            raw,
            {"sequence", "job", "render_receipt", "qc_receipt"},
            f"package plan.episodes[{index}]",
        )
        sequence = _require_positive_int(item["sequence"], f"package plan.episodes[{index}].sequence")
        if sequence not in range(1, 7) or sequence in by_sequence:
            _fail(EXIT_SCHEMA, "package plan sequences must be unique 01-06")
        job_raw = _require_absolute_path(str(item["job"]), f"package plan sequence {sequence:02d} job")
        job_path = _require_existing_regular_file(
            job_raw, f"package plan sequence {sequence:02d} job", no_symlink=True
        )
        if job_path != jobs[sequence][0] or _sha256_file(job_path) != jobs[sequence][1]["job_hash"]:
            _fail(EXIT_HASH, f"package plan sequence {sequence:02d} job differs from release")
        paths: dict[str, Path] = {}
        for key, label in (("render_receipt", "render"), ("qc_receipt", "qc")):
            raw_path = _require_absolute_path(str(item[key]), f"package plan sequence {sequence:02d} {label} receipt")
            paths[label] = _require_existing_regular_file(
                raw_path, f"package plan sequence {sequence:02d} {label} receipt", no_symlink=True
            )
        by_sequence[sequence] = paths
        # The human identity and decision come only from the external receipt.
        if approval[sequence]["decision"] != "APPROVED":
            _fail(EXIT_SCHEMA, f"package plan sequence {sequence:02d} lacks external human approval")
    if set(by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "package plan sequences must be exact 01-06")
    if _sha256_file(plan_path) != plan_hash:
        _fail(EXIT_UNSAFE, "package plan changed during binding validation")
    return plan, by_sequence


def _verify_packaged_run_receipts(
    package_dir: Path,
    roles: dict[str, list[str]],
    jobs: dict[int, tuple[Path, dict[str, Any]]],
    release_hash: str,
    release: dict[str, Any],
    upload_by_sequence: dict[int, dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    human_approval_hash: str,
    delegation_inputs_sha256: str,
) -> None:
    lock_relative = f"{REPRODUCTION_DIR}/receipts/delegation-inputs.lock.json"
    lock_value, lock_hash = _load_json_with_sha256(
        package_dir / _safe_relative_path_to_path(lock_relative),
        "delegation inputs lock",
    )
    lock = _require_exact_keys(
        lock_value,
        {
            "schema", "release_id", "release_sha256", "source_bundle_sha256",
            "package_module_sha256", "human_approval_sha256", "episodes",
        },
        "delegation inputs lock",
    )
    canonical_lock_bytes = (
        json.dumps(lock, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if _read_stable_bytes(
        package_dir / _safe_relative_path_to_path(lock_relative),
        "delegation inputs lock",
    ) != canonical_lock_bytes:
        _fail(EXIT_SCHEMA, "delegation input lock is not canonical JSON")
    for key in (
        "release_sha256",
        "source_bundle_sha256",
        "package_module_sha256",
        "human_approval_sha256",
    ):
        _require_sha256(lock[key], f"delegation inputs lock.{key}")
    if (
        lock["schema"] != DELEGATION_INPUTS_SCHEMA
        or lock["release_id"] != PROJECT_RELEASE_ID
        or lock["release_sha256"] != release_hash
        or lock["source_bundle_sha256"] != release["source_bundle_lock_sha256"]
        or lock["package_module_sha256"] != release["renderer_modules"]["package"]["sha256"]
        or lock["human_approval_sha256"] != human_approval_hash
        or lock_hash != delegation_inputs_sha256
        or entries[lock_relative]["sha256"] != lock_hash
    ):
        _fail(EXIT_HASH, "delegation input lock binding mismatch")
    lock_episodes = lock["episodes"]
    if type(lock_episodes) is not list or len(lock_episodes) != 6:
        _fail(EXIT_SCHEMA, "delegation input lock requires exact six episode rows")
    lock_by_sequence = {
        item.get("sequence"): item for item in lock_episodes if type(item) is dict
    }
    if set(lock_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "delegation input lock sequences must be exact 01-06")
    for sequence in range(1, 7):
        render_relative = f"{REPRODUCTION_DIR}/receipts/run/{sequence:02d}-render_receipt.json"
        qc_relative = f"{REPRODUCTION_DIR}/receipts/run/{sequence:02d}-qc_receipt.json"
        render_value, render_hash = _load_json_with_sha256(
            package_dir / _safe_relative_path_to_path(render_relative),
            f"sequence {sequence:02d} packaged render receipt",
        )
        qc_value, _qc_hash = _load_json_with_sha256(
            package_dir / _safe_relative_path_to_path(qc_relative),
            f"sequence {sequence:02d} packaged QC receipt",
        )
        if type(render_value) is not dict or type(qc_value) is not dict:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: packaged run receipts must be objects")
        _job_path, state = jobs[sequence]
        job_hash = state["job_hash"]
        lock_episode = _require_exact_keys(
            lock_by_sequence[sequence],
            {"sequence", "episode_id", "job_sha256", "render_receipt_sha256", "qc_receipt_sha256"},
            f"delegation input lock sequence {sequence:02d}",
        )
        for key in ("job_sha256", "render_receipt_sha256", "qc_receipt_sha256"):
            _require_sha256(
                lock_episode[key],
                f"delegation input lock sequence {sequence:02d}.{key}",
            )
        if (
            lock_episode["episode_id"] != state["episode"]["episode_id"]
            or lock_episode["job_sha256"] != job_hash
            or lock_episode["render_receipt_sha256"] != render_hash
            or lock_episode["qc_receipt_sha256"] != entries[qc_relative]["sha256"]
        ):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: delegation input receipt hash mismatch")
        if (
            render_value.get("schema") != RENDER_RECEIPT_SCHEMA
            or render_value.get("job_sha256") != job_hash
            or render_value.get("release_sha256") != release_hash
            or qc_value.get("schema") != QC_RECEIPT_SCHEMA
            or qc_value.get("job_sha256") != job_hash
            or qc_value.get("release_sha256") != release_hash
            or qc_value.get("render_receipt_sha256") != render_hash
        ):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: packaged run receipt release/job chain mismatch")
        output = render_value.get("output")
        thumbnail = render_value.get("thumbnail")
        if type(output) is not dict or type(thumbnail) is not dict:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: render output/thumbnail evidence missing")
        media_relative = roles[f"episode-media:{sequence:02d}"][0]
        thumbnail_relative = roles[f"episode-thumbnail:{sequence:02d}"][0]
        upload_final = upload_by_sequence[sequence].get("final_media")
        if (
            output.get("sha256") != entries[media_relative]["sha256"]
            or output.get("sha256") != upload_final.get("sha256")
            or output.get("frame_count") != state["job"]["output"]["frame_count"]
            or thumbnail.get("sha256") != entries[thumbnail_relative]["sha256"]
        ):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: render receipt artifact binding mismatch")
        semantic = qc_value.get("semantic_equivalent")
        reference = qc_value.get("reference_bit_exact")
        if (
            type(semantic) is not dict
            or type(reference) is not dict
            or semantic.get("status") != "PASS"
            or reference.get("status") != "PASS"
        ):
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: packaged semantic/reference QC is not PASS")


def package_from_plan(
    plan_argument: Path,
    ffprobe_argument: Path,
    release_argument: Path,
    source_root_argument: Path,
    office_root_argument: Path | None,
    runtime_python_argument: Path,
    approval_receipt_argument: Path,
    package_dir_argument: Path,
) -> dict[str, Any]:
    plan_path = _require_existing_regular_file(plan_argument, "package plan", no_symlink=True)
    plan_sha256 = _sha256_file(plan_path)
    package_raw = _require_absolute_path(str(package_dir_argument), "package directory")
    if os.path.lexists(package_raw):
        _fail(EXIT_UNSAFE, f"package directory already exists; overwrite refused: {package_raw}")
    package_parent = _normalize_existing_directory(package_raw.parent, "package parent")
    release_path, release_hash, release = _load_release(release_argument)
    _require_complete_release(release)
    _require_release_golden_ready(release_path, release, "package")
    _bundle_path, _bundle_hash, _objects, source_root = _verify_all_source_objects(
        release_path, release, source_root_argument
    )
    office_root, package_script, _package_script_sha = _load_office_script(
        release, "package", office_root_argument
    )
    modules_before = _snapshot_office_modules(release, office_root)
    approval_path, approval_hash, approval = _load_human_approval_receipt(
        approval_receipt_argument
    )
    plan_value, plan_receipts = _load_bound_package_plan(
        plan_path, release_path, release_hash, release, source_root, approval
    )
    disjoint_roots = {
        "release root": release_path.parent,
        "source root": source_root,
        "office root": office_root,
        "Plugify root": _plugify_root(),
        "human approval root": approval_path.parent,
    }
    for sequence, paths in plan_receipts.items():
        disjoint_roots[f"sequence {sequence:02d} render receipt root"] = paths["render"].parent
        disjoint_roots[f"sequence {sequence:02d} QC receipt root"] = paths["qc"].parent
    _require_output_disjoint(package_raw, disjoint_roots)
    runtime_python, runtime_metadata = _resolve_runtime_python(runtime_python_argument)
    _require_locked_runtime_environment(
        release_path, release, office_root, runtime_python, runtime_metadata
    )
    jobs = _collect_release_jobs(release_path, release_hash, release)
    with tempfile.TemporaryDirectory(prefix=".hymn-package-stage-", dir=package_parent) as temporary:
        temporary_root = Path(temporary)
        snapshot_root = temporary_root / "delegation-inputs"
        snapshot_root.mkdir(mode=0o700)
        snapshot_bytes: dict[int, dict[str, bytes]] = {}
        snapshot_hashes: dict[int, dict[str, str]] = {}
        snapshot_plan_episodes: list[dict[str, Any]] = []
        lock_episodes: list[dict[str, Any]] = []
        for sequence in range(1, 7):
            snapshot_bytes[sequence] = {}
            snapshot_hashes[sequence] = {}
            snapshot_paths: dict[str, Path] = {}
            for stage_name in ("render", "qc"):
                source_receipt = plan_receipts[sequence][stage_name]
                content = _read_stable_bytes(
                    source_receipt,
                    f"sequence {sequence:02d} {stage_name} receipt input",
                )
                digest = hashlib.sha256(content).hexdigest()
                snapshot_path = snapshot_root / f"{sequence:02d}-{stage_name}_receipt.json"
                try:
                    with snapshot_path.open("xb") as handle:
                        handle.write(content)
                except OSError as exc:
                    _fail(EXIT_UNSAFE, f"cannot snapshot delegated receipt: {exc}")
                if _read_stable_bytes(snapshot_path, "delegated receipt snapshot") != content:
                    _fail(EXIT_UNSAFE, "delegated receipt snapshot bytes changed")
                snapshot_bytes[sequence][stage_name] = content
                snapshot_hashes[sequence][stage_name] = digest
                snapshot_paths[stage_name] = snapshot_path
            snapshot_plan_episodes.append(
                {
                    "sequence": sequence,
                    "job": str(jobs[sequence][0]),
                    "render_receipt": str(snapshot_paths["render"]),
                    "qc_receipt": str(snapshot_paths["qc"]),
                }
            )
            lock_episodes.append(
                {
                    "sequence": sequence,
                    "episode_id": jobs[sequence][1]["episode"]["episode_id"],
                    "job_sha256": jobs[sequence][1]["job_hash"],
                    "render_receipt_sha256": snapshot_hashes[sequence]["render"],
                    "qc_receipt_sha256": snapshot_hashes[sequence]["qc"],
                }
            )
        snapshot_plan = {
            "schema": PACKAGE_PLAN_SCHEMA,
            "release": str(release_path),
            "source_root": str(source_root),
            "episodes": snapshot_plan_episodes,
        }
        snapshot_plan_path = snapshot_root / "delegate-plan.json"
        _write_new_text(
            snapshot_plan_path,
            json.dumps(snapshot_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        )
        delegation_lock = {
            "schema": DELEGATION_INPUTS_SCHEMA,
            "release_id": release["release_id"],
            "release_sha256": release_hash,
            "source_bundle_sha256": release["source_bundle_lock_sha256"],
            "package_module_sha256": release["renderer_modules"]["package"]["sha256"],
            "human_approval_sha256": approval_hash,
            "episodes": lock_episodes,
        }
        delegation_lock_path = snapshot_root / "delegation-inputs.lock.json"
        _write_new_text(
            delegation_lock_path,
            json.dumps(delegation_lock, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        )
        stage = temporary_root / "office-package"
        command = [
            str(runtime_python),
            str(package_script),
            "build-package",
            "--plan",
            str(snapshot_plan_path),
            "--approval-receipt",
            str(approval_path),
            "--output-dir",
            str(stage),
        ]
        _stdout_sha, delegate_payload = _run_delegate(command, "package")
        if delegate_payload.get("status") != "ok":
            _fail(EXIT_DELEGATE, "package delegate did not report status=ok")
        if _sha256_file(runtime_python) != runtime_metadata["sha256"]:
            _fail(EXIT_UNSAFE, "runtime Python changed while package delegate ran")
        if _snapshot_office_modules(release, office_root) != modules_before:
            _fail(EXIT_UNSAFE, "office renderer/package module set changed while package delegate ran")
        if _sha256_file(plan_path) != plan_sha256:
            _fail(EXIT_UNSAFE, "package plan changed while delegate ran")
        if _sha256_file(approval_path) != approval_hash:
            _fail(EXIT_UNSAFE, "human approval receipt changed while package delegate ran")
        staged_receipt_root = stage / REPRODUCTION_DIR / "receipts"
        for sequence in range(1, 7):
            for stage_name in ("render", "qc"):
                original = plan_receipts[sequence][stage_name]
                if hashlib.sha256(
                    _read_stable_bytes(original, "delegated receipt input postcheck")
                ).hexdigest() != snapshot_hashes[sequence][stage_name]:
                    _fail(
                        EXIT_UNSAFE,
                        f"sequence {sequence:02d}: source {stage_name} receipt changed during delegation",
                    )
                staged = _require_existing_regular_file(
                    staged_receipt_root / f"{sequence:02d}-{stage_name}_receipt.json",
                    f"sequence {sequence:02d} staged {stage_name} receipt",
                    no_symlink=True,
                )
                if _read_stable_bytes(staged, "staged delegated receipt") != snapshot_bytes[sequence][stage_name]:
                    _fail(
                        EXIT_HASH,
                        f"sequence {sequence:02d}: staged {stage_name} receipt is not byte-equal to snapshot",
                    )
        manifest_path = stage / "upload-ready.json"
        authority_path = stage / "authority-lock.json"
        result = package_release(
            manifest_path,
            authority_path,
            ffprobe_argument,
            release_argument,
            source_root_argument,
            office_root,
            approval_receipt_argument,
            package_raw,
            delegation_lock_path,
            snapshot_hashes,
        )
        result["delegate"] = {
            "module": str(package_script),
            "module_sha256": release["renderer_modules"]["package"]["sha256"],
            "normalized_command": command,
            "origin": "UNATTESTED",
        }
        return result


def verify_deterministic_package(
    package_argument: Path,
    sums_argument: Path,
    trusted_release_argument: Path,
    trusted_approval_argument: Path,
) -> dict[str, Any]:
    base_result = verify_closed_package(package_argument, sums_argument)
    package_dir = Path(base_result["package_dir"])
    _reject_ds_store_tree(package_dir, "package")
    trusted_release_path, trusted_release_hash, trusted_release = _load_release(trusted_release_argument)
    _require_complete_release(trusted_release)
    _require_release_golden_ready(trusted_release_path, trusted_release, "verify-package")
    trusted_approval_path, trusted_approval_hash, trusted_approval = _load_human_approval_receipt(
        trusted_approval_argument
    )
    if _path_within(trusted_release_path, package_dir) or _path_within(trusted_approval_path, package_dir):
        _fail(EXIT_UNSAFE, "verify-package trust anchors must be external to the package")
    package_manifest_path = package_dir / PACKAGE_MANIFEST_NAME
    manifest_value, manifest_sha = _load_json_with_sha256(package_manifest_path, "package manifest")
    manifest = _require_exact_keys(
        manifest_value,
        {
            "schema", "build_mode", "release_id", "release_sha256", "source_bundle_sha256",
            "upload_ready_sha256", "human_approval_sha256", "delegation_inputs_sha256", "entries",
        },
        "package manifest",
    )
    canonical_manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if _read_stable_bytes(package_manifest_path, "package manifest") != canonical_manifest_bytes:
        _fail(EXIT_SCHEMA, "package manifest is not canonical JSON")
    if manifest["schema"] != PACKAGE_SCHEMA or manifest["release_id"] != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, "package manifest schema/release_id mismatch")
    if manifest["build_mode"] != "office-plan-delegate-unattested/v1":
        _fail(EXIT_SCHEMA, "successor package must be built by the plan delegate")
    for key in ("release_sha256", "source_bundle_sha256", "upload_ready_sha256", "human_approval_sha256"):
        _require_sha256(manifest[key], f"package manifest.{key}")
    if manifest["release_sha256"] != trusted_release_hash:
        _fail(EXIT_HASH, "package release does not match the external trusted release lock")
    if manifest["human_approval_sha256"] != trusted_approval_hash:
        _fail(EXIT_HASH, "package approval does not match the external human approval receipt")
    _require_sha256(
        manifest["delegation_inputs_sha256"],
        "package manifest.delegation_inputs_sha256",
    )
    raw_entries = manifest["entries"]
    if type(raw_entries) is not list or not raw_entries:
        _fail(EXIT_SCHEMA, "package manifest entries must be a non-empty array")
    entries: dict[str, dict[str, Any]] = {}
    roles: dict[str, list[str]] = {}
    manifest_path_order: list[str] = []
    for index, raw_entry in enumerate(raw_entries):
        entry = _require_exact_keys(raw_entry, {"path", "role", "sha256", "size"}, f"package manifest.entries[{index}]")
        relative = _safe_release_relative_path(entry["path"], f"package manifest.entries[{index}].path")
        if relative in entries:
            _fail(EXIT_SCHEMA, f"duplicate package manifest path: {relative}")
        manifest_path_order.append(relative)
        role = _require_nonempty_string(entry["role"], f"package manifest.entries[{index}].role")
        digest = _require_sha256(entry["sha256"], f"package manifest.entries[{index}].sha256")
        size = _require_byte_size(entry["size"], f"package manifest.entries[{index}].size")
        payload = _require_existing_regular_file(package_dir / _safe_relative_path_to_path(relative), "package payload", no_symlink=True)
        if _sha256_file(payload) != digest or payload.stat().st_size != size:
            _fail(EXIT_HASH, f"package manifest payload mismatch: {relative}")
        entries[relative] = {"role": role, "sha256": digest, "size": size}
        roles.setdefault(role, []).append(relative)
    if manifest_path_order != sorted(manifest_path_order):
        _fail(EXIT_SCHEMA, "package manifest entries are not path-sorted")
    sums_path = Path(sums_argument)
    if not sums_path.is_absolute():
        sums_path = package_dir / sums_path
    sums_bytes = _read_stable_bytes(sums_path, "package SHA256SUMS")
    if hashlib.sha256(sums_bytes).hexdigest() != base_result["sums_sha256"]:
        _fail(EXIT_HASH, "package SHA256SUMS changed after exact-set verification")
    try:
        sums_lines = sums_bytes.decode("utf-8").splitlines()
    except UnicodeError as exc:
        _fail(EXIT_SCHEMA, f"package SHA256SUMS is not UTF-8: {exc}")
    sums_entries: dict[str, str] = {}
    for line in sums_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            _fail(EXIT_SCHEMA, "package SHA256SUMS is not canonical sorted two-space form")
        relative = _safe_release_relative_path(match.group(2), "SHA256SUMS entry")
        if relative in sums_entries:
            _fail(EXIT_SCHEMA, f"duplicate SHA256SUMS entry: {relative}")
        sums_entries[relative] = match.group(1)
    if sums_lines != sorted(sums_lines, key=lambda line: line[66:]):
        _fail(EXIT_SCHEMA, "package SHA256SUMS entries are not path-sorted")
    if set(sums_entries) != set(entries) | {PACKAGE_MANIFEST_NAME}:
        _fail(EXIT_SCHEMA, "package manifest and SHA256SUMS exact sets differ")
    expected_sums_bytes = "".join(
        f"{sums_entries[relative]}  {relative}\n" for relative in sorted(sums_entries)
    ).encode("utf-8")
    if sums_bytes != expected_sums_bytes:
        _fail(EXIT_SCHEMA, "package SHA256SUMS bytes are not canonical UTF-8 LF with final newline")
    if _sha256_file(package_manifest_path) != manifest_sha:
        _fail(EXIT_HASH, "package manifest changed during verification")

    for sequence in range(1, 7):
        for role in (f"episode-media:{sequence:02d}", f"episode-thumbnail:{sequence:02d}"):
            if len(roles.get(role, [])) != 1:
                _fail(EXIT_SCHEMA, f"package requires exactly one {role}")
    for role in ("release-lock", "release-source-bundle-lock", "environment-lock", "golden-lock", "source-bundle-lock", "upload-ready-manifest", "upload-authority-lock", "upload-receipts", "human-approval-receipt"):
        if len(roles.get(role, [])) != 1:
            _fail(EXIT_SCHEMA, f"package requires exactly one {role}")
    if set(name.removeprefix("renderer-module:") for name in roles if name.startswith("renderer-module:")) != REQUIRED_RENDERER_MODULES:
        _fail(EXIT_SCHEMA, "package renderer module role set mismatch")
    expected_plugify_code = {
        f"{REPRODUCTION_DIR}/code/plugify/{relative}"
        for relative in PACKAGE_CODE_SNAPSHOTS.values()
    }
    if set(roles.get("plugify-code", [])) != expected_plugify_code:
        _fail(EXIT_SCHEMA, "package Plugify code snapshot exact set mismatch")
    trusted_plugify_code_hashes: dict[Path, str] = {}
    for source, relative in PACKAGE_CODE_SNAPSHOTS.items():
        package_relative = f"{REPRODUCTION_DIR}/code/plugify/{relative}"
        expected_digest = _sha256_file(
            _require_existing_regular_file(source, "trusted Plugify code snapshot", no_symlink=False)
        )
        trusted_plugify_code_hashes[source] = expected_digest
        if entries[package_relative]["sha256"] != expected_digest:
            _fail(EXIT_HASH, f"packaged Plugify code differs from trusted checkout: {relative}")
    expected_run_receipts = {
        f"{REPRODUCTION_DIR}/receipts/run/{sequence:02d}-{stage}_receipt.json"
        for sequence in range(1, 7)
        for stage in ("render", "qc")
    }
    if set(roles.get("run-receipt", [])) != expected_run_receipts:
        _fail(EXIT_SCHEMA, "delegated package plan/run receipt exact set mismatch")
    if roles.get("delegation-inputs-lock") != [
        f"{REPRODUCTION_DIR}/receipts/delegation-inputs.lock.json"
    ]:
        _fail(EXIT_SCHEMA, "delegation input lock path is missing/noncanonical")
    allowed_roles = {
        "release-lock", "release-source-bundle-lock", "environment-lock", "golden-lock",
        "release-job", "source-bundle-lock", "source-object", "plugify-code",
        "upload-ready-manifest", "upload-authority-lock", "upload-receipts", "human-approval-receipt",
        "upload-graph-media", "run-receipt", "delegation-inputs-lock",
    } | {
        f"episode-media:{sequence:02d}" for sequence in range(1, 7)
    } | {
        f"episode-thumbnail:{sequence:02d}" for sequence in range(1, 7)
    } | {
        f"renderer-module:{name}" for name in REQUIRED_RENDERER_MODULES
    }
    if set(roles) - allowed_roles:
        _fail(EXIT_SCHEMA, f"package manifest has unsupported roles: {sorted(set(roles) - allowed_roles)}")

    upload_path = package_dir / _safe_relative_path_to_path(roles["upload-ready-manifest"][0])
    if roles["upload-ready-manifest"] != [f"{REPRODUCTION_DIR}/receipts/upload-ready.json"]:
        _fail(EXIT_SCHEMA, "packaged upload-ready manifest role path mismatch")
    upload_value, upload_hash = _load_json_with_sha256(upload_path, "packaged upload-ready manifest")
    if type(upload_value) is not dict:
        _fail(EXIT_SCHEMA, "packaged upload-ready manifest must be an object")
    if upload_hash != manifest["upload_ready_sha256"] or upload_value.get("release_id") != PROJECT_RELEASE_ID:
        _fail(EXIT_HASH, "packaged upload-ready manifest hash/release mismatch")
    upload_root = upload_path.parent
    for ref_key, role in (("authority_lock", "upload-authority-lock"), ("receipts", "upload-receipts")):
        ref = upload_value.get(ref_key)
        if type(ref) is not dict or len(roles.get(role, [])) != 1:
            _fail(EXIT_SCHEMA, f"packaged upload-ready {ref_key} reference invalid")
        referenced = _resolve_manifest_file(upload_root, ref.get("path"), f"packaged upload {ref_key}")
        role_path = package_dir / _safe_relative_path_to_path(roles[role][0])
        if referenced != role_path or _sha256_file(referenced) != ref.get("sha256"):
            _fail(EXIT_HASH, f"packaged upload-ready {ref_key} binding mismatch")
    upload_artifacts = upload_value.get("artifacts")
    if type(upload_artifacts) is not list or len(upload_artifacts) != 6:
        _fail(EXIT_SCHEMA, "packaged upload-ready requires exact six artifacts")
    upload_by_sequence = {
        artifact.get("sequence"): artifact
        for artifact in upload_artifacts
        if type(artifact) is dict
    }
    if set(upload_by_sequence) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "packaged upload-ready artifact sequences must be exact 01-06")
    expected_upload_media: set[str] = set()
    for sequence in range(1, 7):
        artifact = upload_by_sequence[sequence]
        source_audio = artifact.get("source_audio")
        refs = [artifact.get("final_media")]
        if type(source_audio) is dict:
            refs.append(source_audio)
        elif type(source_audio) is list:
            refs.extend(source_audio)
        else:
            _fail(EXIT_SCHEMA, f"packaged sequence {sequence:02d} source_audio invalid")
        for ref in refs:
            if type(ref) is not dict:
                _fail(EXIT_SCHEMA, f"packaged sequence {sequence:02d} media reference invalid")
            media = _resolve_manifest_file(upload_root, ref.get("path"), f"packaged sequence {sequence:02d} media")
            if _sha256_file(media) != ref.get("sha256"):
                _fail(EXIT_HASH, f"packaged sequence {sequence:02d} upload media hash mismatch")
            expected_upload_media.add(media.relative_to(package_dir).as_posix())
    if set(roles.get("upload-graph-media", [])) != expected_upload_media:
        _fail(EXIT_SCHEMA, "packaged upload-ready media exact set mismatch")

    if roles["human-approval-receipt"] != [f"{REPRODUCTION_DIR}/receipts/human-approval.json"]:
        _fail(EXIT_SCHEMA, "packaged human approval receipt role path mismatch")
    packaged_approval_path = package_dir / _safe_relative_path_to_path(
        roles["human-approval-receipt"][0]
    )
    _approval_path, packaged_approval_hash, packaged_approval = _load_human_approval_receipt(
        packaged_approval_path
    )
    if packaged_approval_hash != trusted_approval_hash:
        _fail(EXIT_HASH, "packaged human approval differs from external trusted receipt")

    release_relative = roles["release-lock"][0]
    if release_relative != f"{REPRODUCTION_DIR}/release/release.lock.json":
        _fail(EXIT_SCHEMA, "packaged release lock role path mismatch")
    release_path = package_dir / _safe_relative_path_to_path(release_relative)
    release_value, release_hash = _load_json_with_sha256(release_path, "packaged release lock")
    if release_hash != manifest["release_sha256"]:
        _fail(EXIT_HASH, "packaged release lock hash mismatch")
    _require_exact_keys(release_value, RELEASE_KEYS, "packaged release lock")
    _normalized_release_path, normalized_release_hash, release = _load_release(release_path)
    if normalized_release_hash != release_hash:
        _fail(EXIT_HASH, "packaged release changed during validation")
    if release_hash != trusted_release_hash:
        _fail(EXIT_HASH, "packaged release differs from external trusted release lock")
    release_root = release_path.parent
    packaged_jobs = _collect_release_jobs(release_path, release_hash, release)
    if set(packaged_jobs) != set(range(1, 7)):
        _fail(EXIT_SCHEMA, "packaged release requires exact jobs 01-06")
    for relative, expected_hash in release["jobs"].items():
        path = _require_existing_regular_file(release_root / _safe_relative_path_to_path(relative), "packaged release job", no_symlink=True)
        if _sha256_file(path) != expected_hash:
            _fail(EXIT_HASH, f"packaged release job hash mismatch: {relative}")
    expected_job_paths = {
        (release_root.relative_to(package_dir) / _safe_relative_path_to_path(relative)).as_posix()
        for relative in release["jobs"]
    }
    if set(roles.get("release-job", [])) != expected_job_paths:
        _fail(EXIT_SCHEMA, "packaged release job role exact set mismatch")
    for key in ("source_bundle_lock", "environment_lock", "golden_lock"):
        relative = _safe_release_relative_path(release[key], f"packaged release {key}")
        path = _require_existing_regular_file(release_root / _safe_relative_path_to_path(relative), f"packaged {key}", no_symlink=True)
        if _sha256_file(path) != release[f"{key}_sha256"]:
            _fail(EXIT_HASH, f"packaged {key} hash mismatch")
        role = {
            "source_bundle_lock": "release-source-bundle-lock",
            "environment_lock": "environment-lock",
            "golden_lock": "golden-lock",
        }[key]
        if path.relative_to(package_dir).as_posix() != roles[role][0]:
            _fail(EXIT_SCHEMA, f"packaged {key} role path mismatch")
    packaged_golden, _packaged_golden_hash = _load_json_with_sha256(
        release_root / _safe_relative_path_to_path(release["golden_lock"]),
        "packaged golden lock",
    )
    if _golden_requires_bootstrap(packaged_golden):
        _fail(EXIT_UNSUPPORTED, "packaged golden lock is still BOOTSTRAP_REQUIRED")
    _bind_successor_upload_graph(
        upload_path,
        upload_value,
        package_dir / _safe_relative_path_to_path(roles["upload-authority-lock"][0]),
        packaged_jobs,
        packaged_golden,
        packaged_approval,
    )
    _verify_packaged_run_receipts(
        package_dir,
        roles,
        packaged_jobs,
        release_hash,
        release,
        upload_by_sequence,
        entries,
        packaged_approval_hash,
        manifest["delegation_inputs_sha256"],
    )
    renderer_modules = release.get("renderer_modules")
    if type(renderer_modules) is not dict or set(renderer_modules) != REQUIRED_RENDERER_MODULES:
        _fail(EXIT_SCHEMA, "packaged release renderer module set mismatch")
    for name, module in renderer_modules.items():
        if type(module) is not dict:
            _fail(EXIT_SCHEMA, f"packaged renderer module {name} metadata invalid")
        role_paths = roles.get(f"renderer-module:{name}", [])
        if len(role_paths) != 1:
            _fail(EXIT_SCHEMA, f"packaged renderer module {name} missing")
        expected_module_relative = f"{REPRODUCTION_DIR}/code/office/{module.get('path')}"
        if role_paths != [expected_module_relative]:
            _fail(EXIT_SCHEMA, f"packaged renderer module path mismatch: {name}")
        module_path = package_dir / _safe_relative_path_to_path(role_paths[0])
        if _sha256_file(module_path) != module.get("sha256"):
            _fail(EXIT_HASH, f"packaged renderer module hash mismatch: {name}")

    source_lock_path = package_dir / _safe_relative_path_to_path(roles["source-bundle-lock"][0])
    if roles["source-bundle-lock"] != [f"{REPRODUCTION_DIR}/source_bundle/source-bundle.lock.json"]:
        _fail(EXIT_SCHEMA, "packaged source-bundle lock role path mismatch")
    source_value, source_hash = _load_json_with_sha256(source_lock_path, "packaged source bundle lock")
    release_bundle_path, release_bundle_hash, release_object_map = _load_source_bundle(release_path, release)
    if (
        source_hash != manifest["source_bundle_sha256"]
        or source_hash != release_bundle_hash
        or source_hash != release["source_bundle_lock_sha256"]
    ):
        _fail(EXIT_HASH, "packaged source bundle SHA mismatch")
    if release_bundle_path.relative_to(package_dir).as_posix() != roles["release-source-bundle-lock"][0]:
        _fail(EXIT_SCHEMA, "packaged release source-bundle role path mismatch")
    source_bundle = _require_exact_keys(source_value, SOURCE_BUNDLE_KEYS, "packaged source bundle")
    if source_bundle.get("release_id") != PROJECT_RELEASE_ID:
        _fail(EXIT_SCHEMA, "packaged source bundle release_id mismatch")
    objects = release_object_map
    object_root = source_lock_path.parent
    expected_object_paths: set[str] = set()
    for object_id, entry in objects.items():
        match = OBJECT_ID_RE.fullmatch(object_id)
        if match is None:
            _fail(EXIT_SCHEMA, f"invalid packaged object id: {object_id!r}")
        digest = match.group(1)
        relative = f"objects/sha256/{digest[:2]}/{digest[2:]}"
        expected_object_paths.add((source_lock_path.parent.relative_to(package_dir) / relative).as_posix())
        object_path = _require_existing_regular_file(object_root / relative, "packaged source object", no_symlink=True)
        if _sha256_file(object_path) != entry.get("sha256") or object_path.stat().st_size != entry.get("size"):
            _fail(EXIT_HASH, f"packaged source object mismatch: {object_id}")
    if set(roles.get("source-object", [])) != expected_object_paths:
        _fail(EXIT_SCHEMA, "packaged source object exact set differs from source bundle lock")
    for sequence in range(1, 7):
        _job_path, job_state = packaged_jobs[sequence]
        media_relative = f"{sequence:02d}/{job_state['job']['output']['filename']}"
        thumbnail_relative = f"{sequence:02d}/{job_state['job']['output']['thumbnail_filename']}"
        if roles[f"episode-media:{sequence:02d}"] != [media_relative]:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: canonical media role path mismatch")
        if roles[f"episode-thumbnail:{sequence:02d}"] != [thumbnail_relative]:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: canonical thumbnail role path mismatch")
        upload_final = upload_by_sequence[sequence].get("final_media")
        if type(upload_final) is not dict or entries[media_relative]["sha256"] != upload_final.get("sha256"):
            _fail(EXIT_HASH, f"sequence {sequence:02d}: canonical media is not bound to upload-ready final")
        thumbnail_ids = job_state["inputs"].get("thumbnail")
        if type(thumbnail_ids) is not list or len(thumbnail_ids) != 1:
            _fail(EXIT_SCHEMA, f"sequence {sequence:02d}: packaged job thumbnail input invalid")
        if entries[thumbnail_relative]["sha256"] != thumbnail_ids[0].split(":", 1)[1]:
            _fail(EXIT_HASH, f"sequence {sequence:02d}: canonical thumbnail is not bound to job source object")
    final_result = verify_closed_package(package_dir, sums_path)
    _reject_ds_store_tree(package_dir, "package final exact-set")
    if (
        final_result["sums_sha256"] != base_result["sums_sha256"]
        or final_result["payload_count"] != base_result["payload_count"]
        or _sha256_file(package_manifest_path) != manifest_sha
        or _sha256_file(trusted_release_path) != trusted_release_hash
        or _sha256_file(trusted_approval_path) != trusted_approval_hash
        or _sha256_file(SCRIPT_PATH) != SCRIPT_SHA256
        or _sha256_file(UPLOAD_READY_VALIDATOR_PATH) != UPLOAD_READY_VALIDATOR_SHA256
        or any(
            _sha256_file(source) != expected_hash
            for source, expected_hash in trusted_plugify_code_hashes.items()
        )
    ):
        _fail(EXIT_UNSAFE, "package or external trust/code anchors changed during final verification")
    base_result.update(
        {
            "command": "verify-package",
            "package_manifest_sha256": manifest_sha,
            "release_id": manifest["release_id"],
            "delegation_origin": "UNATTESTED",
            "status": "ok",
        }
    )
    return base_result


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
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"
    environment["LC_CTYPE"] = "C"
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
    _require_renderer_modules_pinned(state["release"], "render")
    office_root, office_script_path, office_script_sha = _load_office_script(
        state["release"], "profiles", office_root_argument
    )
    office_modules = _snapshot_office_modules(state["release"], office_root)
    run_root_raw = _require_absolute_path(str(run_root_argument), "run root")
    run_root = _normalize_writable_directory(run_root_raw, "run root")
    runtime_python, runtime_metadata = _resolve_runtime_python(runtime_python_argument)
    _require_locked_runtime_environment(
        state["release_path"], state["release"], office_root,
        runtime_python, runtime_metadata
    )
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
    _require_renderer_modules_pinned(state["release"], f"{gate} QC")
    if gate == "reference-bit-exact":
        _require_release_golden_ready(state["release_path"], state["release"], "reference-bit-exact QC")
    office_root, office_script_path, office_script_sha = _load_office_script(
        state["release"], "qc", office_root_argument
    )
    office_modules = _snapshot_office_modules(state["release"], office_root)
    run_root_raw = _require_absolute_path(str(run_root_argument), "run root")
    run_root = _normalize_existing_directory(run_root_raw, "run root")
    runtime_python, runtime_metadata = _resolve_runtime_python(runtime_python_argument)
    _require_locked_runtime_environment(
        state["release_path"], state["release"], office_root,
        runtime_python, runtime_metadata
    )
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

    upload_parser = subparsers.add_parser("verify-upload-ready")
    upload_parser.add_argument("--manifest", required=True, type=Path)
    upload_parser.add_argument("--authority-lock", required=True, type=Path)
    upload_parser.add_argument("--ffprobe", required=True, type=Path)
    upload_parser.add_argument("--release", type=Path)
    upload_parser.add_argument("--approval-receipt", type=Path)

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

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--plan", required=True, type=Path)
    package_parser.add_argument("--ffprobe", required=True, type=Path)
    package_parser.add_argument("--release", required=True, type=Path)
    package_parser.add_argument("--source-root", required=True, type=Path)
    package_parser.add_argument("--office-root", type=Path)
    package_parser.add_argument("--runtime-python", required=True, type=Path)
    package_parser.add_argument("--approval-receipt", required=True, type=Path)
    package_parser.add_argument("--package-dir", required=True, type=Path)

    package_verify_parser = subparsers.add_parser("verify-package")
    package_verify_parser.add_argument("--package-dir", required=True, type=Path)
    package_verify_parser.add_argument("--sums", type=Path, default=Path(PACKAGE_SUMS_NAME))
    package_verify_parser.add_argument("--release", required=True, type=Path)
    package_verify_parser.add_argument("--approval-receipt", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate-job":
            result = validate_job(args.job, args.release)
        elif args.command == "verify-source-bundle":
            result, _state = verify_source_bundle(args.job, args.release, args.source_root)
        elif args.command == "verify-upload-ready":
            result = verify_upload_ready_contract(
                args.manifest,
                args.authority_lock,
                args.ffprobe,
                args.release,
                args.approval_receipt,
            )
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
        elif args.command == "package":
            result = package_from_plan(
                args.plan,
                args.ffprobe,
                args.release,
                args.source_root,
                args.office_root,
                args.runtime_python,
                args.approval_receipt,
                args.package_dir,
            )
        elif args.command == "verify-package":
            result = verify_deterministic_package(
                args.package_dir, args.sums, args.release, args.approval_receipt
            )
        else:
            _fail(EXIT_SCHEMA, f"unknown command: {args.command!r}")
    except FlowError as exc:
        print(f"ERROR[{exc.code}] {exc}", file=sys.stderr)
        return exc.code
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError) as exc:
        print(f"ERROR[{EXIT_SCHEMA}] malformed or unstable contract input: {exc}", file=sys.stderr)
        return EXIT_SCHEMA
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if args.command == "qc":
        if result["gate_status"] == "FAIL":
            return EXIT_DELEGATE
        if result["gate_status"] == "NOT_APPLICABLE":
            return EXIT_UNSUPPORTED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
