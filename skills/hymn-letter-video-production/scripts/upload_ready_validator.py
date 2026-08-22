#!/usr/bin/env python3
"""Fail-closed upload-ready validator for the frozen 01-06 AAC-LC release contract."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


SEQUENCES = set(range(1, 7))
TRANSCODE = {2, 4, 6}
STREAM_COPY = {1, 3, 5}
MP4_MAJOR_BRANDS = {"isom", "iso2", "mp41", "mp42", "avc1", "dash", "mmp4"}
EXPECTED_APPROVAL_AUTHORITIES = {
    sequence: {
        "reviewer": "fixture-reviewer",
        "decision": "APPROVED",
        "reviewed_at": f"2026-08-22T09:{0 if sequence == 1 else sequence:02d}:00+09:00",
    }
    for sequence in range(1, 7)
}
FROZEN_FIXTURE_RELEASE_ID = "hymn-letter-caption-v3-20260822"
SUCCESSOR_RELEASE_ID = "hymn-letter-caption-v3-gapless-aac-20260822"
AUTHORITY_LOCK_SCHEMA = "plugify.hymn-letter.upload-authority-lock/1"
AUDIO_RECEIPTS_SCHEMA = "plugify.hymn-letter.upload-audio-receipts/1"
PCM_COMPOSITE_DOMAIN = b"plugify.hymn-letter.ordered-pcm-manifest/v1\0"
FROZEN_PLAYLIST_PCM_COMPOSITE_SHA256 = "dc3d9fd41fdf445d30e6da054fa42e0a33f5f23ba247522aa88248b38174e6cb"
SUCCESSOR_PLAYLIST_PCM_COMPOSITE_SHA256 = "a18ae5063bb626971bdb1897a311b79b145a679655b089f588cfa1af6b5cbf76"
PLAYLIST_DISCARD_PADDING = (47, 23, 11, 29, 7, 31, 13, 19, 5, 37, 17, 41)
EXPECTED_PLAYLIST_PCM_TRACK_VECTOR = tuple(
    (track, 1105, PLAYLIST_DISCARD_PADDING[track - 1], f"d2{track:02d}" * 16)
    for track in range(1, 13)
)
PLAYLIST_DECODED_SAMPLES = 120_930_048
PLAYLIST_REMOVED_GAP_SAMPLES = 17_327
PLAYLIST_FILTER_GRAPH = (
    ";".join(f"[{index}:a]asetpts=PTS-STARTPTS[a{index}]" for index in range(1, 13))
    + ";"
    + "".join(f"[a{index}]" for index in range(1, 13))
    + "concat=n=12:v=0:a=1[aout]"
)
RFC3339_SECONDS_RE = re.compile(
    r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T"
    r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)"
)


class UploadReadyError(RuntimeError):
    """The upload-ready graph is incomplete, mutable, or internally inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _canonical_rfc3339_seconds(value: object) -> bool:
    if type(value) is not str or RFC3339_SECONDS_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    if parsed.utcoffset() is None:
        return False
    canonical = (
        parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        if value.endswith("Z")
        else parsed.isoformat(timespec="seconds")
    )
    offset = parsed.utcoffset()
    return value == canonical and offset is not None and abs(offset.total_seconds()) <= 14 * 60 * 60


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadReadyError(f"cannot load {label}: {exc}") from exc
    if type(value) is not dict:
        raise UploadReadyError(f"{label} root must be an object")
    return value


def _resolve_child(root: Path, raw: object, label: str) -> Path:
    if type(raw) is not str or not raw or Path(raw).is_absolute():
        raise UploadReadyError(f"unsafe {label} relative path: {raw!r}")
    unresolved = root / raw
    for component in (unresolved, *unresolved.parents):
        if component == root.parent:
            break
        if component.is_symlink():
            raise UploadReadyError(f"{label} contains a symlink component: {raw!r}")
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise UploadReadyError(f"{label} path escapes manifest root: {raw!r}") from exc
    if not candidate.is_file() or candidate.is_symlink():
        raise UploadReadyError(f"missing/non-regular {label}: {raw!r}")
    return candidate


def _probe(ffprobe: Path, media: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise UploadReadyError(f"ffprobe failed for {media}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise UploadReadyError(f"ffprobe returned invalid JSON for {media}") from exc
    if type(value) is not dict:
        raise UploadReadyError(f"ffprobe root is not an object for {media}")
    return value


def _stream(probe: dict[str, Any], kind: str) -> dict[str, Any]:
    streams = probe.get("streams")
    if type(streams) is not list:
        raise UploadReadyError("ffprobe streams must be an array")
    matches = [item for item in streams if type(item) is dict and item.get("codec_type") == kind]
    if len(matches) != 1:
        raise UploadReadyError(f"expected one {kind} stream, got {len(matches)}")
    return matches[0]


def _assert_final_probe(value: dict[str, Any], sequence: int) -> tuple[dict[str, Any], dict[str, Any]]:
    video = _stream(value, "video")
    audio = _stream(value, "audio")
    formats = {
        item.strip().lower()
        for item in str(value.get("format", {}).get("format_name", "")).split(",")
        if item.strip()
    }
    brand = str(value.get("format", {}).get("tags", {}).get("major_brand", "")).strip().lower()
    if "mp4" not in formats or brand not in MP4_MAJOR_BRANDS:
        raise UploadReadyError(f"sequence {sequence:02d}: actual container/brand is not allowlisted MP4")
    if video.get("codec_name") != "h264":
        raise UploadReadyError(f"sequence {sequence:02d}: actual final video is not H.264")
    if audio.get("codec_name") != "aac" or audio.get("profile") != "LC":
        raise UploadReadyError(f"sequence {sequence:02d}: actual final audio is not AAC-LC")
    return video, audio


def _pcm_vector(items: list[dict[str, Any]]) -> tuple[tuple[object, object, object, object], ...]:
    return tuple(
        (item.get("track"), item.get("skip_samples"), item.get("discard_padding"), item.get("decoded_pcm_sha256"))
        for item in items
    )


def _pcm_composite(items: list[dict[str, Any]]) -> str:
    records: list[dict[str, object]] = []
    if len(items) != 12:
        raise UploadReadyError("sequence 02: PCM composite requires exact ordered 12-track evidence")
    for expected_track, item in enumerate(items, start=1):
        record = {
            "track": item.get("track"),
            "decoded_pcm_sha256": item.get("decoded_pcm_sha256"),
            "skip_samples": item.get("skip_samples"),
            "discard_padding": item.get("discard_padding"),
        }
        if (
            record["track"] != expected_track
            or not _is_sha256(record["decoded_pcm_sha256"])
            or type(record["skip_samples"]) is not int
            or record["skip_samples"] < 0
            or type(record["discard_padding"]) is not int
            or record["discard_padding"] < 0
        ):
            raise UploadReadyError(f"sequence 02 track {expected_track}: invalid PCM evidence")
        records.append(record)
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(PCM_COMPOSITE_DOMAIN + canonical).hexdigest()


def _expected_playlist_command() -> list[str]:
    command = ["ffmpeg", "-i", "<video-only>"]
    for track in range(1, 13):
        command.extend(["-i", f"<track-{track:02d}>"])
    command.extend(
        [
            "-filter_complex", PLAYLIST_FILTER_GRAPH,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-profile:a", "aac_low",
            "-b:a", "256k", "-ar", "44100", "-ac", "2", "<new-output>.mp4",
        ]
    )
    return command


def _expected_single_command() -> list[str]:
    return [
        "ffmpeg", "-i", "<approved-source>",
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "aac", "-profile:a", "aac_low",
        "-b:a", "256k", "-ar", "44100", "-ac", "2", "<new-output>.mp4",
    ]


def _forbidden_processing(token: str) -> bool:
    option = token.strip().lower().split("=", 1)[0]
    if option == "-shortest" or option == "-af" or option.startswith("-af:"):
        return True
    if option in {"-filter_audio", "-audio_filter"}:
        return True
    if option.startswith("-filter:"):
        return any(part in {"a", "audio"} for part in option.removeprefix("-filter:").split(":"))
    if option.startswith("-filter_script:"):
        return any(part in {"a", "audio"} for part in option.removeprefix("-filter_script:").split(":"))
    return False


def _validate_encoder(encoder: object, sequence: int, playlist: bool) -> None:
    if type(encoder) is not dict or not _is_sha256(encoder.get("binary_sha256")):
        raise UploadReadyError(f"sequence {sequence:02d}: encoder binary provenance missing")
    command = encoder.get("normalized_command")
    if type(command) is not list or not all(type(token) is str for token in command):
        raise UploadReadyError(f"sequence {sequence:02d}: normalized encoder command missing")
    if any(_forbidden_processing(token) for token in command):
        raise UploadReadyError(f"sequence {sequence:02d}: audio filter/shortest shortcut forbidden")
    if playlist:
        if encoder.get("gapless_decode_policy") != "honor-skip-samples-and-discard-padding-per-track":
            raise UploadReadyError("sequence 02: per-track gapless decode policy missing")
        if command != _expected_playlist_command():
            raise UploadReadyError("sequence 02: encoder command differs from the exact 12-track concat contract")
    elif command != _expected_single_command():
        raise UploadReadyError(f"sequence {sequence:02d}: encoder command differs from exact filter-free contract")


def validate_upload_ready(manifest_path: Path, authority_argument: Path, ffprobe: Path) -> dict[str, Any]:
    if manifest_path.is_symlink():
        raise UploadReadyError("manifest must be a regular non-symlink file")
    manifest_path = manifest_path.resolve(strict=True)
    root = manifest_path.parent
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise UploadReadyError("manifest must be a regular non-symlink file")
    if authority_argument.is_symlink():
        raise UploadReadyError("authority lock must be a regular non-symlink file")
    authority_argument = authority_argument.resolve(strict=True)
    if authority_argument.is_symlink() or not authority_argument.is_file():
        raise UploadReadyError("authority lock must be a regular non-symlink file")
    if ffprobe.is_symlink():
        raise UploadReadyError("ffprobe must be a regular non-symlink file")
    ffprobe = ffprobe.resolve(strict=True)
    if ffprobe.is_symlink() or not ffprobe.is_file():
        raise UploadReadyError("ffprobe must be a regular non-symlink file")

    manifest = _load_json(manifest_path, "upload-ready manifest")
    if manifest.get("schema") != "plugify.hymn-letter.upload-ready/1":
        raise UploadReadyError("invalid upload-ready schema")
    release_id = manifest.get("release_id")
    if release_id not in {FROZEN_FIXTURE_RELEASE_ID, SUCCESSOR_RELEASE_ID}:
        raise UploadReadyError("upload-ready release_id is not supported")
    frozen_fixture = release_id == FROZEN_FIXTURE_RELEASE_ID
    authority_ref = manifest.get("authority_lock")
    receipt_ref = manifest.get("receipts")
    if type(authority_ref) is not dict or type(receipt_ref) is not dict:
        raise UploadReadyError("authority/receipt references are required")
    authority_path = _resolve_child(root, authority_ref.get("path"), "authority lock")
    receipt_path = _resolve_child(root, receipt_ref.get("path"), "receipts")
    if authority_path != authority_argument:
        raise UploadReadyError("--authority-lock does not match the manifest authority reference")
    if _sha256(authority_path) != authority_ref.get("sha256"):
        raise UploadReadyError("authority lock hash mismatch")
    if _sha256(receipt_path) != receipt_ref.get("sha256"):
        raise UploadReadyError("receipt hash mismatch")
    authority = _load_json(authority_path, "authority lock")
    receipts = _load_json(receipt_path, "receipts")
    if authority.get("schema") != AUTHORITY_LOCK_SCHEMA:
        raise UploadReadyError("invalid authority lock schema")
    if receipts.get("schema") != AUDIO_RECEIPTS_SCHEMA:
        raise UploadReadyError("invalid receipts schema")
    if authority.get("release_id") != release_id or receipts.get("release_id") != release_id:
        raise UploadReadyError("authority/receipt release_id does not match manifest")
    artifacts = manifest.get("artifacts")
    locks = authority.get("episodes")
    receipt_entries = receipts.get("entries")
    if any(type(items) is not list or len(items) != 6 for items in (artifacts, locks, receipt_entries)):
        raise UploadReadyError("exact six artifact/authority/receipt entries are required")
    by_artifact = {item.get("sequence"): item for item in artifacts if type(item) is dict}
    by_lock = {item.get("sequence"): item for item in locks if type(item) is dict}
    by_receipt = {item.get("sequence"): item for item in receipt_entries if type(item) is dict}
    if any(set(mapping) != SEQUENCES for mapping in (by_artifact, by_lock, by_receipt)):
        raise UploadReadyError("exact unique sequence set 01-06 is required")

    for sequence in sorted(SEQUENCES):
        artifact = by_artifact[sequence]
        locked = by_lock[sequence]
        receipt = by_receipt[sequence]
        identity = (artifact.get("episode_id"), artifact.get("profile"))
        if identity != (locked.get("episode_id"), locked.get("profile")) or identity != (receipt.get("episode_id"), receipt.get("profile")):
            raise UploadReadyError(f"sequence {sequence:02d}: identity/profile mismatch")
        required_authority = {
            "sequence", "episode_id", "profile", "frame_count", "captions_sha256",
            "boundaries_sha256", "chapters_sha256", "video_stream_fingerprint_sha256", "approval_authority",
        }
        if not required_authority <= set(locked):
            raise UploadReadyError(f"sequence {sequence:02d}: authority fields missing")
        if type(locked["frame_count"]) is not int or locked["frame_count"] <= 0:
            raise UploadReadyError(f"sequence {sequence:02d}: authority frame count invalid")
        approval_authority = locked["approval_authority"]
        if type(approval_authority) is not dict or not _canonical_rfc3339_seconds(approval_authority.get("reviewed_at")):
            raise UploadReadyError(f"sequence {sequence:02d}: exact approval authority is invalid")
        if frozen_fixture:
            if approval_authority != EXPECTED_APPROVAL_AUTHORITIES[sequence]:
                raise UploadReadyError(f"sequence {sequence:02d}: frozen approval authority is invalid")
        elif (
            approval_authority.get("decision") != "APPROVED"
            or not isinstance(approval_authority.get("reviewer"), str)
            or not approval_authority["reviewer"].strip()
        ):
            raise UploadReadyError(f"sequence {sequence:02d}: successor approval authority is invalid")
        for field in ("captions_sha256", "boundaries_sha256", "video_stream_fingerprint_sha256"):
            if not _is_sha256(locked[field]):
                raise UploadReadyError(f"sequence {sequence:02d}: authority {field} invalid")
        if sequence == 2:
            if not _is_sha256(locked["chapters_sha256"]):
                raise UploadReadyError("sequence 02: chapters authority must be SHA-256")
        elif locked["chapters_sha256"] is not None:
            raise UploadReadyError(f"sequence {sequence:02d}: chapters authority must be explicit null")

        derivation = receipt.get("derivation")
        approval = receipt.get("approval")
        qc = receipt.get("qc")
        if any(type(item) is not dict for item in (derivation, approval, qc)):
            raise UploadReadyError(f"sequence {sequence:02d}: derivation, approval, and QC are required")
        final_ref = artifact.get("final_media")
        if type(final_ref) is not dict:
            raise UploadReadyError(f"sequence {sequence:02d}: final reference missing")
        final_path = _resolve_child(root, final_ref.get("path"), f"sequence {sequence:02d} final")
        if final_path.suffix.lower() != ".mp4":
            raise UploadReadyError(f"sequence {sequence:02d}: final filename is not .mp4")
        final_hash = _sha256(final_path)
        if final_hash != final_ref.get("sha256") or final_hash != receipt.get("final_file_sha256"):
            raise UploadReadyError(f"sequence {sequence:02d}: final hash binding mismatch")
        final_probe = _probe(ffprobe, final_path)
        video, final_audio = _assert_final_probe(final_probe, sequence)
        final_payload = final_audio.get("tags", {}).get("payload_sha256")
        if int(video.get("nb_frames", 0)) != locked["frame_count"]:
            raise UploadReadyError(f"sequence {sequence:02d}: actual frame count differs from authority")

        if sequence == 2:
            source_refs = artifact.get("source_audio")
            locked_tracks = locked.get("approved_source_tracks")
            receipt_hashes = receipt.get("source_track_sha256")
            track_decodes = derivation.get("track_decodes")
            source_payloads = derivation.get("source_audio_payload_sha256")
            boundary_qc = qc.get("track_boundaries")
            collections = (source_refs, locked_tracks, receipt_hashes, track_decodes, source_payloads, boundary_qc)
            if any(type(items) is not list or len(items) != 12 for items in collections):
                raise UploadReadyError("sequence 02: exact ordered 12-track lineage is required")
            if [item.get("track") for item in source_refs] != list(range(1, 13)) or [item.get("track") for item in locked_tracks] != list(range(1, 13)):
                raise UploadReadyError("sequence 02: track order must be exact 1..12")
            actual_pcm: list[dict[str, Any]] = []
            for index, (source_ref, locked_track, decoded, boundary) in enumerate(zip(source_refs, locked_tracks, track_decodes, boundary_qc)):
                track = index + 1
                source_path = _resolve_child(root, source_ref.get("path"), f"sequence 02 track {track}")
                if source_path.name == "02-approved-source.mp3":
                    raise UploadReadyError("sequence 02: pre-concatenated MP3 is forbidden")
                source_hash = _sha256(source_path)
                if source_hash != source_ref.get("sha256") or source_hash != locked_track.get("sha256") or source_hash != receipt_hashes[index]:
                    raise UploadReadyError(f"sequence 02 track {track}: source hash/authority mismatch")
                source_audio = _stream(_probe(ffprobe, source_path), "audio")
                side_data = source_audio.get("side_data_list")
                if source_audio.get("codec_name") != "mp3" or type(side_data) is not list or len(side_data) != 1:
                    raise UploadReadyError(f"sequence 02 track {track}: standalone MP3 gapless probe missing")
                side = side_data[0]
                decoded_pcm = source_audio.get("tags", {}).get("decoded_pcm_sha256")
                actual = (track, side.get("skip_samples"), side.get("discard_padding"), decoded_pcm)
                expected = (locked_track.get("track"), locked_track.get("skip_samples"), locked_track.get("discard_padding"), locked_track.get("decoded_pcm_sha256"))
                decoded_expected = (decoded.get("track"), decoded.get("skip_samples"), decoded.get("discard_padding"), decoded.get("decoded_pcm_sha256"))
                if actual != expected or decoded_expected != expected:
                    raise UploadReadyError(f"sequence 02 track {track}: trim/PCM lineage mismatch")
                if source_audio.get("tags", {}).get("payload_sha256") != source_payloads[index]:
                    raise UploadReadyError(f"sequence 02 track {track}: source payload order mismatch")
                if boundary != {"track": track, "decoded_pcm_sha256": decoded_pcm, "start": "PASS", "tail": "PASS"}:
                    raise UploadReadyError(f"sequence 02 track {track}: boundary/tail QC missing")
                actual_pcm.append({"track": track, "skip_samples": side.get("skip_samples"), "discard_padding": side.get("discard_padding"), "decoded_pcm_sha256": decoded_pcm})
            if derivation.get("mode") != "approved-trackwise-gapless-pcm-concat-transcode":
                raise UploadReadyError("sequence 02: trackwise gapless PCM concat derivation required")
            composites = {_pcm_composite(actual_pcm), _pcm_composite(locked_tracks), _pcm_composite(track_decodes)}
            vectors = {_pcm_vector(actual_pcm), _pcm_vector(locked_tracks), _pcm_vector(track_decodes)}
            claims = (locked.get("ordered_pcm_concat_sha256"), derivation.get("ordered_pcm_concat_sha256"), qc.get("ordered_pcm_concat_sha256"))
            expected_composite = (
                FROZEN_PLAYLIST_PCM_COMPOSITE_SHA256
                if frozen_fixture
                else SUCCESSOR_PLAYLIST_PCM_COMPOSITE_SHA256
            )
            if (
                any(not _is_sha256(value) for value in claims)
                or set(claims) != {expected_composite}
                or composites != {expected_composite}
                or (frozen_fixture and vectors != {EXPECTED_PLAYLIST_PCM_TRACK_VECTOR})
            ):
                raise UploadReadyError("sequence 02: ordered PCM composite authority mismatch")
            if (
                derivation.get("decoded_total_samples") != PLAYLIST_DECODED_SAMPLES
                or qc.get("decoded_total_samples") != PLAYLIST_DECODED_SAMPLES
                or derivation.get("removed_internal_gap_samples") != PLAYLIST_REMOVED_GAP_SAMPLES
                or qc.get("removed_internal_gap_samples") != PLAYLIST_REMOVED_GAP_SAMPLES
            ):
                raise UploadReadyError("sequence 02: decoded sample/gap proof mismatch")
            _validate_encoder(derivation.get("encoder"), sequence, True)
            expected_kind = "approved-derivative"
        else:
            source_ref = artifact.get("source_audio")
            if type(source_ref) is not dict:
                raise UploadReadyError(f"sequence {sequence:02d}: approved source object missing")
            source_path = _resolve_child(root, source_ref.get("path"), f"sequence {sequence:02d} source")
            source_hash = _sha256(source_path)
            if source_hash != source_ref.get("sha256") or source_hash != locked.get("approved_source_audio_sha256") or source_hash != receipt.get("source_file_sha256"):
                raise UploadReadyError(f"sequence {sequence:02d}: approved source provenance mismatch")
            source_audio = _stream(_probe(ffprobe, source_path), "audio")
            source_payload = source_audio.get("tags", {}).get("payload_sha256")
            if derivation.get("source_audio_payload_sha256") != source_payload:
                raise UploadReadyError(f"sequence {sequence:02d}: source payload lineage mismatch")
            if sequence in STREAM_COPY:
                if source_audio.get("codec_name") != "aac" or source_audio.get("profile") != "LC":
                    raise UploadReadyError(f"sequence {sequence:02d}: stream-copy source is not AAC-LC")
                if derivation.get("mode") != "stream-copy" or derivation.get("encoder") is not None or source_payload != final_payload:
                    raise UploadReadyError(f"sequence {sequence:02d}: approved AAC was not stream-copied")
                expected_kind = "approved-source"
            else:
                if source_audio.get("codec_name") != "mp3" or derivation.get("mode") != "approved-transcode" or source_payload == final_payload:
                    raise UploadReadyError(f"sequence {sequence:02d}: MP3 derivative contract mismatch")
                _validate_encoder(derivation.get("encoder"), sequence, False)
                expected_kind = "approved-derivative"

        if derivation.get("output_audio_payload_sha256") != final_payload:
            raise UploadReadyError(f"sequence {sequence:02d}: output payload lineage mismatch")
        if sequence in TRANSCODE and (
            int(final_audio.get("bit_rate", 0)), int(final_audio.get("sample_rate", 0)), final_audio.get("channels")
        ) != (256000, 44100, 2):
            raise UploadReadyError(f"sequence {sequence:02d}: AAC derivative parameters mismatch")
        if (
            not {"kind", "artifact_audio_payload_sha256", "decision", "reviewer", "reviewed_at"} <= set(approval)
            or approval.get("kind") != expected_kind
            or approval.get("artifact_audio_payload_sha256") != final_payload
            or {key: approval.get(key) for key in ("reviewer", "decision", "reviewed_at")} != approval_authority
            or not _canonical_rfc3339_seconds(approval.get("reviewed_at"))
        ):
            raise UploadReadyError(f"sequence {sequence:02d}: exact audio approval missing")
        expected_qc = {
            "final_file_sha256": final_hash,
            "container": "mp4",
            "major_brand": str(final_probe["format"]["tags"]["major_brand"]).strip(),
            "audio_codec": "aac",
            "audio_profile": "LC",
            "sample_rate": int(final_audio["sample_rate"]),
            "channels": final_audio["channels"],
            "bit_rate": int(final_audio["bit_rate"]),
            "video_stream_fingerprint_sha256": locked.get("video_stream_fingerprint_sha256"),
            "frame_count": locked.get("frame_count"),
            "captions_sha256": locked.get("captions_sha256"),
            "boundaries_sha256": locked.get("boundaries_sha256"),
            "chapters_sha256": locked.get("chapters_sha256"),
        }
        if video.get("tags", {}).get("stream_fingerprint_sha256") != locked.get("video_stream_fingerprint_sha256"):
            raise UploadReadyError(f"sequence {sequence:02d}: video fingerprint differs from authority")
        for key, expected in expected_qc.items():
            if key not in qc or qc.get(key) != expected:
                raise UploadReadyError(f"sequence {sequence:02d}: QC {key} is not bound to actual/authority")
        tail = qc.get("real_time_tail_playback")
        if (
            qc.get("status") != "PASS"
            or qc.get("full_decode") != "PASS"
            or qc.get("avfoundation_decode") != "PASS"
            or type(tail) is not dict
            or tail.get("status") != "PASS"
            or not tail.get("reviewer")
            or float(tail.get("tail_seconds", 0)) <= 0
        ):
            raise UploadReadyError(f"sequence {sequence:02d}: full decode/player/tail QC incomplete")

    return {"status": "ok", "verified_sequences": [1, 2, 3, 4, 5, 6]}
