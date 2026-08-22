#!/usr/bin/env python3
"""Regression contract for upload-ready MP4/AAC-LC and audio lineage."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixture"
SEQUENCES = set(range(1, 7))
TRANSCODE = {2, 4, 6}
STREAM_COPY = {1, 3, 5}
SINGLE_TRANSCODE = {4, 6}
MP4_MAJOR_BRANDS = {"isom", "iso2", "mp41", "mp42", "avc1", "dash", "mmp4"}
AUDIO_FILTER_ATTACK_OPTIONS = (
    "-af",
    "-af:a:0",
    "-filter:a",
    "-filter:a:0",
    "-filter:a:7",
    "-filter:a:m:language:eng",
    "-filter:1",
    "-filter_script:a",
    "-filter_script:a:0",
    "-/filter:a",
    "-/filter:a:0",
    "-/af",
    "-/af:0",
    "-filter_complex_script",
    "-/filter_complex",
    "-lavfi",
    "-/lavfi",
)
FORBIDDEN_PROCESSING_OPTIONS = (*AUDIO_FILTER_ATTACK_OPTIONS, "-shortest")
EXPECTED_ATTACK_COUNT = 355
APPROVAL_AUTHORITY_FIELDS = ("reviewer", "decision", "reviewed_at")
EXPECTED_APPROVAL_AUTHORITIES = {
    sequence: {
        "reviewer": "fixture-reviewer",
        "decision": "APPROVED",
        "reviewed_at": f"2026-08-22T09:{0 if sequence == 1 else sequence:02d}:00+09:00",
    }
    for sequence in range(1, 7)
}
PCM_COMPOSITE_DOMAIN = b"plugify.hymn-letter.ordered-pcm-manifest/v1\0"
EXPECTED_PLAYLIST_PCM_COMPOSITE_SHA256 = "dc3d9fd41fdf445d30e6da054fa42e0a33f5f23ba247522aa88248b38174e6cb"
PLAYLIST_DISCARD_PADDING = (47, 23, 11, 29, 7, 31, 13, 19, 5, 37, 17, 41)
EXPECTED_PLAYLIST_PCM_TRACK_VECTOR = tuple(
    (track, 1105, PLAYLIST_DISCARD_PADDING[track - 1], f"d2{track:02d}" * 16)
    for track in range(1, 13)
)
REQUIRED_INCIDENT_STATEMENTS = (
    "17,327 all-zero samples prove a 0.392902-second noncanonical timeline defect; they are not the proven direct cause of the audible spike.",
    "Without QuickTime output capture, codec versus interleave/nearby H.264 keyframe contribution remains unresolved.",
    "The safe path removes both per-track MP3 trim metadata loss and MOV+MP3 playback risk.",
)
ADVERSARIAL_INCIDENT_OVERCLAIMS = (
    "The audible spike was directly caused by the 17,327 silent samples.",
    "The 17,327 silent samples directly caused the audible spike.",
    "The direct cause of the audible spike was the 17,327 silent samples.",
    "17,327개의 무음 샘플이 가청 튐을 직접 일으켰다.",
)
RFC3339_SECONDS_RE = re.compile(
    r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T"
    r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)"
)
TRANSCODE_FLAG_PAIRS = (
    ("-c:v", "copy"),
    ("-c:a", "aac"),
    ("-profile:a", "aac_low"),
    ("-b:a", "256k"),
    ("-ar", "44100"),
    ("-ac", "2"),
)
PLAYLIST_DECODED_SAMPLES = 120_930_048
PLAYLIST_REMOVED_GAP_SAMPLES = 17_327
PLAYLIST_FILTER_GRAPH = (
    ";".join(
        f"[{index}:a]asetpts=PTS-STARTPTS[a{index}]"
        for index in range(1, 13)
    )
    + ";"
    + "".join(f"[a{index}]" for index in range(1, 13))
    + "concat=n=12:v=0:a=1[aout]"
)
EXPECTED_PROFILES = {
    "start-hybrid/v1",
    "playlist/v1",
    "testimony-static/v1",
    "hymn-lyrics/v1",
}
MOV_MP3_RE = re.compile(r"MOV\s*\+\s*MP3", flags=re.IGNORECASE)
PROHIBITION_RE = re.compile(
    r"forbid|prohibit|reject|disallow|unsupported|must\s+not|never|not\s+allowed|"
    r"not\s+support(?:ed)?|do\s+not\s+use|don['’]t\s+use|should\s+not\s+use|"
    r"not\s+permit(?:ted)?|do\s+not\s+allow|no\s+longer\s+support(?:ed)?|"
    r"금지|거부|불가|허용하지|허용\s*안(?:\s*함)?|지원하지|지원\s*안(?:\s*함)?|"
    r"사용하지|사용\s*금지",
    flags=re.IGNORECASE,
)
CLAUSE_SPLIT_RE = re.compile(r"[.;]|\s+(?:but|however|yet)\s+|\s*(?:하지만|그러나)\s*", re.IGNORECASE)
PERMISSION_RE = re.compile(
    r"allow|permit|support|may\s+use|can\s+use|허용|지원|사용\s*가능|쓸\s*수",
    flags=re.IGNORECASE,
)


class ContractError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256_value(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_canonical_rfc3339_seconds(value: object) -> bool:
    if type(value) is not str or RFC3339_SECONDS_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    if parsed.utcoffset() is None:
        return False
    if value.endswith("Z"):
        canonical = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        canonical = parsed.isoformat(timespec="seconds")
    if value != canonical:
        return False
    offset = parsed.utcoffset()
    return offset is not None and abs(offset.total_seconds()) <= 14 * 60 * 60


def pcm_track_vector(items: list[dict]) -> tuple[tuple[object, object, object, object], ...]:
    return tuple(
        (
            item.get("track") if type(item) is dict else None,
            item.get("skip_samples") if type(item) is dict else None,
            item.get("discard_padding") if type(item) is dict else None,
            item.get("decoded_pcm_sha256") if type(item) is dict else None,
        )
        for item in items
    )


def ordered_pcm_composite_sha256(items: list[dict]) -> str:
    records: list[dict[str, object]] = []
    for expected_track, item in enumerate(items, start=1):
        if type(item) is not dict:
            raise ContractError("sequence 02: PCM evidence record must be an object")
        record = {
            "track": item.get("track"),
            "decoded_pcm_sha256": item.get("decoded_pcm_sha256"),
            "skip_samples": item.get("skip_samples"),
            "discard_padding": item.get("discard_padding"),
        }
        if (
            record["track"] != expected_track
            or not is_sha256_value(record["decoded_pcm_sha256"])
            or type(record["skip_samples"]) is not int
            or record["skip_samples"] < 0
            or type(record["discard_padding"]) is not int
            or record["discard_padding"] < 0
        ):
            raise ContractError(f"sequence 02 track {expected_track}: invalid PCM composite evidence")
        records.append(record)
    if len(records) != 12:
        raise ContractError("sequence 02: PCM composite requires exact ordered 12-track evidence")
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(PCM_COMPOSITE_DOMAIN + canonical).hexdigest()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load JSON {path}: {exc}") from exc
    if type(value) is not dict:
        raise ContractError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def expected_incident_contract() -> dict:
    return {
        "schema": "plugify.hymn-letter.codec-incident/1",
        "observed_at": "2026-08-22",
        "episode_id": "02-playlist",
        "expected_candidate_statements": list(REQUIRED_INCIDENT_STATEMENTS),
        "adversarial_overclaim_corpus": list(ADVERSARIAL_INCIDENT_OVERCLAIMS),
        "selected_tracks": {
            "ordered_paths": [f"media/02-track-{track:02d}.mp3" for track in range(1, 13)],
            "observed_real_time_playback": "clean",
            "gapless_rule": "decode-each-standalone-track-honoring-skip-samples-and-discard-padding-before-pcm-concat",
        },
        "forbidden_preconcatenated_source": {
            "path": "media/02-approved-source.mp3",
            "reason": "per-track MP3 priming/padding side-data is absent at internal boundaries",
            "measured_internal_trim_loss_samples": 17327,
            "measured_noncanonical_timeline_seconds": 0.392902,
            "measured_samples_character": "all-zero-silence-in-mp3float-and-audiotoolbox",
            "causality_limit": "silent extra samples prove a noncanonical timeline defect but are not asserted as the direct cause of the audible spike",
        },
        "final_artifact": {
            "path": "media/02-legacy-playlist.mov",
            "observed_real_time_tail": "end-note-glitch",
            "immediate_mechanism_status": "unresolved-without-quicktime-output-capture",
            "remaining_risk": "long MOV+MP3 playback path; codec versus interleave/large-nearby-H264-keyframe contribution is not differentiated",
        },
        "rename_control": {
            "path": "media/02-renamed-only.mp4",
            "expect_same_bytes_as_final_artifact": True,
            "expected_result": "reject",
        },
    }


def validate_incident_contract(incident: dict) -> None:
    if incident != expected_incident_contract():
        raise ContractError("incident schema/evidence/causality statements differ from the exact frozen contract")


def incident_documentation_failures(text: str) -> list[str]:
    failures = [
        f"candidate documentation lacks exact incident statement: {statement}"
        for statement in REQUIRED_INCIDENT_STATEMENTS
        if statement not in text
    ]
    normalized_text = " ".join(text.split()).casefold()
    overclaims = [
        statement
        for statement in ADVERSARIAL_INCIDENT_OVERCLAIMS
        if " ".join(statement.split()).casefold() in normalized_text
    ]
    if overclaims:
        failures.append("candidate documentation overclaims silent-sample causality: " + " | ".join(overclaims))
    return failures


def mutate_stream_copy_source_to_mp3(fixture: Path) -> None:
    """Keep sequence 01's payload tag but make its actual source probe MP3/unknown."""
    source = fixture / "media" / "01-approved-audio.m4a"
    source.write_text(
        "kind=source sequence=01 container=mp3 major_brand=none codec=mp3 profile=unknown "
        "sample_rate=48000 channels=2 bit_rate=192000 "
        "audio_payload=1111111111111111111111111111111111111111111111111111111111111111\n",
        encoding="utf-8",
    )
    source_hash = sha256(source)
    authority = load_json(fixture / "authority-lock.json")
    authority["episodes"][0]["approved_source_audio_sha256"] = source_hash
    write_json(fixture / "authority-lock.json", authority)
    receipts = load_json(fixture / "receipts.json")
    receipts["entries"][0]["source_file_sha256"] = source_hash
    write_json(fixture / "receipts.json", receipts)
    manifest = load_json(fixture / "upload-ready.json")
    manifest["artifacts"][0]["source_audio"]["sha256"] = source_hash
    manifest["authority_lock"]["sha256"] = sha256(fixture / "authority-lock.json")
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def resolve_child(root: Path, raw: str) -> Path:
    if type(raw) is not str or not raw or Path(raw).is_absolute():
        raise ContractError(f"unsafe relative path: {raw!r}")
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractError(f"path escapes fixture: {raw!r}") from exc
    if not candidate.is_file() or candidate.is_symlink():
        raise ContractError(f"missing/non-regular fixture path: {raw!r}")
    return candidate


def probe(ffprobe: Path | None, media: Path, env: dict[str, str] | None = None) -> dict:
    if ffprobe is None:
        return trusted_probe_media(media)
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise ContractError(f"probe failed for {media}: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"probe returned invalid JSON for {media}") from exc
    return value


def trusted_probe_media(media: Path) -> dict:
    """Parse immutable text media in the trusted runner process."""
    values: dict[str, str] = {}
    for token in media.read_text(encoding="utf-8").strip().split():
        if "=" not in token:
            raise ContractError(f"invalid trusted media token: {token!r}")
        key, value = token.split("=", 1)
        values[key] = value
    required = {
        "kind", "sequence", "container", "major_brand", "codec", "profile",
        "sample_rate", "channels", "bit_rate", "audio_payload",
    }
    if not required <= set(values):
        raise ContractError(f"trusted media keys missing: {sorted(required - set(values))}")
    streams: list[dict[str, object]] = []
    if values["kind"] == "final":
        if not {"video_fingerprint", "frame_count"} <= set(values):
            raise ContractError("trusted final lacks video fingerprint/frame count")
        streams.append(
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "profile": "High",
                "nb_frames": values["frame_count"],
                "tags": {"stream_fingerprint_sha256": values["video_fingerprint"]},
            }
        )
    audio: dict[str, object] = {
        "index": len(streams),
        "codec_type": "audio",
        "codec_name": values["codec"],
        "profile": values["profile"],
        "sample_rate": values["sample_rate"],
        "channels": int(values["channels"]),
        "bit_rate": values["bit_rate"],
        "tags": {"payload_sha256": values["audio_payload"]},
    }
    if "track" in values:
        if not {"skip_samples", "discard_padding", "decoded_pcm"} <= set(values):
            raise ContractError("trusted track lacks gapless/PCM evidence")
        audio["tags"]["decoded_pcm_sha256"] = values["decoded_pcm"]
        audio["side_data_list"] = [
            {
                "side_data_type": "Skip Samples",
                "skip_samples": int(values["skip_samples"]),
                "discard_padding": int(values["discard_padding"]),
            }
        ]
    streams.append(audio)
    container = values["container"]
    if container == "mp3":
        format_name = "mp3"
    elif container in {"mp4", "mov", "m4a"}:
        format_name = "mov,mp4,m4a,3gp,3g2,mj2"
    else:
        format_name = container
    return {
        "streams": streams,
        "format": {
            "filename": str(media.resolve()),
            "format_name": format_name,
            "tags": {"major_brand": values["major_brand"]},
        },
    }


def snapshot_tree(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = "symlink:" + os.readlink(path)
        elif path.is_file():
            snapshot[relative] = sha256(path)
    return snapshot


class ProbeBroker:
    """Trusted in-memory probe attestation broker; candidate never receives its HMAC key."""

    def __init__(self, fixture: Path):
        self.fixture = fixture.resolve()
        self.media_root = (self.fixture / "media").resolve()
        self.secret = secrets.token_bytes(32)
        self.run_id = secrets.token_hex(16)
        self.entries: list[dict[str, str]] = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.temporary: tempfile.TemporaryDirectory[str] | None = None
        self.server: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.wrapper: Path | None = None

    def __enter__(self) -> "ProbeBroker":
        self.temporary = tempfile.TemporaryDirectory(prefix="hp-", dir="/tmp")
        root = Path(self.temporary.name)
        socket_path = root / "p.sock"
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(socket_path))
        self.server.listen()
        self.server.settimeout(0.1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.wrapper = root / (secrets.token_hex(8) + "-ffprobe")
        self.wrapper.write_text(
            "#!/usr/bin/env python3\n"
            "import json, socket, sys\n"
            f"s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect({str(socket_path)!r})\n"
            "s.sendall((json.dumps({'argv':sys.argv[1:]})+'\\n').encode())\n"
            "data=b''\n"
            "while True:\n"
            "    chunk=s.recv(65536)\n"
            "    if not chunk: break\n"
            "    data+=chunk\n"
            "reply=json.loads(data.decode())\n"
            "if not reply.get('ok'):\n"
            "    print(reply.get('error','probe failed'),file=sys.stderr); raise SystemExit(2)\n"
            "print(json.dumps(reply['probe'],sort_keys=True))\n",
            encoding="utf-8",
        )
        self.wrapper.chmod(0o755)
        return self

    def _serve(self) -> None:
        assert self.server is not None
        while not self.stop_event.is_set():
            try:
                connection, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                try:
                    raw = b""
                    while b"\n" not in raw and len(raw) < 1024 * 1024:
                        chunk = connection.recv(65536)
                        if not chunk:
                            break
                        raw += chunk
                    request = json.loads(raw.decode("utf-8").splitlines()[0])
                    argv = request.get("argv")
                    if type(argv) is not list or not argv:
                        raise ContractError("probe broker requires argv")
                    media = Path(argv[-1]).resolve()
                    try:
                        media.relative_to(self.media_root)
                    except ValueError as exc:
                        raise ContractError("probe path outside fixture media") from exc
                    if not media.is_file() or media.is_symlink():
                        raise ContractError("probe path is not regular media")
                    payload = trusted_probe_media(media)
                    probe_sha = hashlib.sha256(
                        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    entry = {
                        "run_id": self.run_id,
                        "path": str(media),
                        "file_sha256": sha256(media),
                        "probe_sha256": probe_sha,
                        "nonce": secrets.token_hex(16),
                    }
                    message = "\0".join(entry[key] for key in ("run_id", "path", "file_sha256", "probe_sha256", "nonce"))
                    entry["signature"] = hmac.new(self.secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
                    with self.lock:
                        self.entries.append(entry)
                    response = {"ok": True, "probe": payload}
                except Exception as exc:  # trusted broker converts malformed requests to probe failure
                    response = {"ok": False, "error": str(exc)}
                connection.sendall(json.dumps(response, sort_keys=True).encode("utf-8"))

    def verified_paths(self) -> set[str]:
        verified: set[str] = set()
        with self.lock:
            entries = list(self.entries)
        for entry in entries:
            message = "\0".join(entry[key] for key in ("run_id", "path", "file_sha256", "probe_sha256", "nonce"))
            expected = hmac.new(self.secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
            if entry["run_id"] != self.run_id or not hmac.compare_digest(entry["signature"], expected):
                raise ContractError("unauthenticated probe broker entry")
            verified.add(entry["path"])
        return verified

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop_event.set()
        if self.server is not None:
            self.server.close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        if self.temporary is not None:
            self.temporary.cleanup()


def stream(probe_value: dict, kind: str) -> dict:
    matches = [item for item in probe_value.get("streams", []) if item.get("codec_type") == kind]
    if len(matches) != 1:
        raise ContractError(f"expected one {kind} stream, got {len(matches)}")
    return matches[0]


def assert_final_probe(value: dict, sequence: int) -> tuple[dict, dict]:
    video = stream(value, "video")
    audio = stream(value, "audio")
    formats = {
        item.strip().lower()
        for item in str(value.get("format", {}).get("format_name", "")).split(",")
        if item.strip()
    }
    brand = str(value.get("format", {}).get("tags", {}).get("major_brand", "")).strip().lower()
    if "mp4" not in formats or brand not in MP4_MAJOR_BRANDS:
        raise ContractError(
            f"sequence {sequence:02d}: actual container is not allowlisted MP4 "
            f"(formats={sorted(formats)}, major_brand={brand!r})"
        )
    if audio.get("codec_name") != "aac" or audio.get("profile") != "LC":
        raise ContractError(f"sequence {sequence:02d}: actual final audio is not AAC-LC")
    if video.get("codec_name") != "h264":
        raise ContractError(f"sequence {sequence:02d}: actual final video is not H.264")
    return video, audio


def permissive_mov_mp3_lines(text: str) -> list[str]:
    """Return only present-tense/contract-shaped MOV+MP3 allowance claims."""
    offending: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if MOV_MP3_RE.search(line) is None:
            continue
        for clause in CLAUSE_SPLIT_RE.split(line):
            match = MOV_MP3_RE.search(clause)
            if match is None or PROHIBITION_RE.search(clause):
                continue
            prefix = clause[: match.start()]
            contract_shaped = ":" in prefix or line.startswith(("|", "-", "*"))
            if PERMISSION_RE.search(clause) or contract_shaped:
                offending.append(line)
                break
    return offending


def profile_contract_failures(contracts: dict) -> list[str]:
    failures: list[str] = []
    actual_profiles = set(contracts)
    if actual_profiles != EXPECTED_PROFILES:
        failures.append(
            "PROFILE_CONTRACTS must contain exact four profiles; "
            f"missing={sorted(EXPECTED_PROFILES - actual_profiles)}, "
            f"extra={sorted(actual_profiles - EXPECTED_PROFILES)}"
        )
    for profile in sorted(EXPECTED_PROFILES & actual_profiles):
        value = contracts[profile]
        if type(value) is not dict or value.get("container") != "mp4" or value.get("audio_codec") != "aac":
            failures.append(
                f"PROFILE_CONTRACTS {profile} still permits "
                f"{value.get('container') if type(value) is dict else None}+"
                f"{value.get('audio_codec') if type(value) is dict else None}"
            )
    return failures


def command_has_pair(command: list[str], flag: str, value: str) -> bool:
    return any(command[index:index + 2] == [flag, value] for index in range(len(command) - 1))


def expected_playlist_command() -> list[str]:
    command = ["ffmpeg", "-i", "<video-only>"]
    for track in range(1, 13):
        command.extend(["-i", f"<track-{track:02d}>"])
    command.extend(
        [
            "-filter_complex", PLAYLIST_FILTER_GRAPH,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-profile:a", "aac_low",
            "-b:a", "256k", "-ar", "44100", "-ac", "2",
            "<new-output>.mp4",
        ]
    )
    return command


def expected_single_transcode_command() -> list[str]:
    return [
        "ffmpeg", "-i", "<approved-source>",
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "aac", "-profile:a", "aac_low",
        "-b:a", "256k", "-ar", "44100", "-ac", "2",
        "<new-output>.mp4",
    ]


def is_forbidden_audio_processing_option(token: str) -> bool:
    """Recognize FFmpeg audio-filter aliases with arbitrary stream specifiers."""
    option = token.strip().lower().split("=", 1)[0]
    if option == "-shortest":
        return True
    if option == "-af" or option.startswith("-af:"):
        return True
    if option in {"-filter_audio", "-audio_filter"}:
        return True
    if option.startswith("-filter:"):
        stream_specifier = option.removeprefix("-filter:").split(":")
        return any(component in {"a", "audio"} for component in stream_specifier)
    if option.startswith("-filter_script:"):
        stream_specifier = option.removeprefix("-filter_script:").split(":")
        return any(component in {"a", "audio"} for component in stream_specifier)
    return False


def validate_encoder(encoder: object, sequence: int, *, playlist: bool) -> None:
    if type(encoder) is not dict or not re.fullmatch(r"[0-9a-f]{64}", str(encoder.get("binary_sha256", ""))):
        raise ContractError(f"sequence {sequence:02d}: encoder binary provenance missing")
    command = encoder.get("normalized_command")
    if type(command) is not list or not all(type(item) is str for item in command):
        raise ContractError(f"sequence {sequence:02d}: normalized encoder command missing")
    for flag, value in TRANSCODE_FLAG_PAIRS:
        if not command_has_pair(command, flag, value):
            raise ContractError(f"sequence {sequence:02d}: encoder command missing {flag} {value}")
    if any(is_forbidden_audio_processing_option(token) for token in command):
        raise ContractError(f"sequence {sequence:02d}: audio filter/shortest shortcut forbidden")
    joined = " ".join(command)
    if playlist:
        if encoder.get("gapless_decode_policy") != "honor-skip-samples-and-discard-padding-per-track":
            raise ContractError("sequence 02: per-track gapless decode policy missing")
        if command != expected_playlist_command():
            raise ContractError(
                "sequence 02: encoder must use the exact ordered 12-input "
                "asetpts/concat graph with no other audio processing"
            )
        if "02-approved-source.mp3" in joined or "concatenated-mp3" in joined:
            raise ContractError("sequence 02: pre-concatenated MP3 derivative input is forbidden")
    elif command != expected_single_transcode_command():
        raise ContractError(
            f"sequence {sequence:02d}: individual MP3 transcode command must match the exact filter-free contract"
        )


def validate_fixture(root: Path, ffprobe: Path | None) -> None:
    manifest = load_json(root / "upload-ready.json")
    if manifest.get("schema") != "plugify.hymn-letter.upload-ready/1":
        raise ContractError("invalid upload-ready schema")
    authority_ref, receipt_ref = manifest.get("authority_lock", {}), manifest.get("receipts", {})
    authority_path = resolve_child(root, authority_ref.get("path"))
    receipt_path = resolve_child(root, receipt_ref.get("path"))
    if sha256(authority_path) != authority_ref.get("sha256"):
        raise ContractError("authority lock hash mismatch")
    if sha256(receipt_path) != receipt_ref.get("sha256"):
        raise ContractError("receipt hash mismatch")
    authority, receipts = load_json(authority_path), load_json(receipt_path)
    artifacts, locks, receipt_entries = manifest.get("artifacts"), authority.get("episodes"), receipts.get("entries")
    if any(type(items) is not list or len(items) != 6 for items in (artifacts, locks, receipt_entries)):
        raise ContractError("exact six artifact/authority/receipt entries are required")
    by_artifact = {item.get("sequence"): item for item in artifacts}
    by_lock = {item.get("sequence"): item for item in locks}
    by_receipt = {item.get("sequence"): item for item in receipt_entries}
    if any(set(mapping) != SEQUENCES for mapping in (by_artifact, by_lock, by_receipt)):
        raise ContractError("exact unique sequence set 01-06 is required")
    for sequence in sorted(SEQUENCES):
        artifact, locked, receipt = by_artifact[sequence], by_lock[sequence], by_receipt[sequence]
        identity = (artifact.get("episode_id"), artifact.get("profile"))
        if identity != (locked.get("episode_id"), locked.get("profile")) or identity != (receipt.get("episode_id"), receipt.get("profile")):
            raise ContractError(f"sequence {sequence:02d}: identity/profile mismatch")
        authority_required = {
            "sequence", "episode_id", "profile", "frame_count", "captions_sha256",
            "boundaries_sha256", "chapters_sha256", "video_stream_fingerprint_sha256",
            "approval_authority",
        }
        if not authority_required <= set(locked):
            raise ContractError(
                f"sequence {sequence:02d}: authority schema fields missing "
                f"{sorted(authority_required - set(locked))}"
            )
        if type(locked["frame_count"]) is not int or locked["frame_count"] <= 0:
            raise ContractError(f"sequence {sequence:02d}: authority frame count invalid")
        approval_authority = locked["approval_authority"]
        if (
            type(approval_authority) is not dict
            or approval_authority != EXPECTED_APPROVAL_AUTHORITIES[sequence]
            or not is_canonical_rfc3339_seconds(approval_authority.get("reviewed_at"))
        ):
            raise ContractError(f"sequence {sequence:02d}: exact approval authority is invalid")
        for authority_field in (
            "captions_sha256", "boundaries_sha256", "video_stream_fingerprint_sha256",
        ):
            if not is_sha256_value(locked[authority_field]):
                raise ContractError(f"sequence {sequence:02d}: authority {authority_field} invalid")
        if sequence == 2:
            if not is_sha256_value(locked["chapters_sha256"]):
                raise ContractError("sequence 02: applicable chapters authority must be a SHA-256")
        elif locked["chapters_sha256"] is not None:
            raise ContractError(
                f"sequence {sequence:02d}: non-applicable chapters authority must be explicit null"
            )
        derivation, approval, qc = receipt.get("derivation"), receipt.get("approval"), receipt.get("qc")
        if any(type(item) is not dict for item in (derivation, approval, qc)):
            raise ContractError(f"sequence {sequence:02d}: explicit derivation, approval, and QC are required")

        final_ref = artifact.get("final_media", {})
        final_path = resolve_child(root, final_ref.get("path"))
        if final_path.suffix.lower() != ".mp4":
            raise ContractError(f"sequence {sequence:02d}: final filename is not .mp4")
        final_hash = sha256(final_path)
        if final_hash != final_ref.get("sha256") or final_hash != receipt.get("final_file_sha256"):
            raise ContractError(f"sequence {sequence:02d}: final hash binding mismatch")
        final_probe = probe(ffprobe, final_path)
        video, final_audio = assert_final_probe(final_probe, sequence)
        final_payload = final_audio.get("tags", {}).get("payload_sha256")
        if int(video.get("nb_frames", 0)) != locked.get("frame_count"):
            raise ContractError(f"sequence {sequence:02d}: actual frame count differs from authority")

        if sequence == 2:
            source_refs = artifact.get("source_audio")
            locked_tracks = locked.get("approved_source_tracks")
            receipt_hashes = receipt.get("source_track_sha256")
            track_decodes = derivation.get("track_decodes")
            source_payloads = derivation.get("source_audio_payload_sha256")
            boundary_qc = qc.get("track_boundaries")
            actual_pcm_evidence: list[dict[str, object]] = []
            if any(type(items) is not list or len(items) != 12 for items in (source_refs, locked_tracks, receipt_hashes, track_decodes, source_payloads, boundary_qc)):
                raise ContractError("sequence 02: exact ordered 12-track lineage is required")
            if [item.get("track") for item in source_refs] != list(range(1, 13)) or [item.get("track") for item in locked_tracks] != list(range(1, 13)):
                raise ContractError("sequence 02: track order must be exact 1..12")
            for index, (source_ref, locked_track, decoded, boundary) in enumerate(zip(source_refs, locked_tracks, track_decodes, boundary_qc)):
                track = index + 1
                source_path = resolve_child(root, source_ref.get("path"))
                if source_path.name == "02-approved-source.mp3":
                    raise ContractError("sequence 02: pre-concatenated MP3 is forbidden as derivative source")
                source_hash = sha256(source_path)
                if source_hash != source_ref.get("sha256") or source_hash != locked_track.get("sha256") or source_hash != receipt_hashes[index]:
                    raise ContractError(f"sequence 02 track {track}: source authority/hash mismatch")
                source_audio = stream(probe(ffprobe, source_path), "audio")
                side_data = source_audio.get("side_data_list")
                if source_audio.get("codec_name") != "mp3" or type(side_data) is not list or len(side_data) != 1:
                    raise ContractError(f"sequence 02 track {track}: standalone MP3 gapless probe missing")
                side = side_data[0]
                decoded_pcm = source_audio.get("tags", {}).get("decoded_pcm_sha256")
                actual = (track, side.get("skip_samples"), side.get("discard_padding"), decoded_pcm)
                expected = (locked_track.get("track"), locked_track.get("skip_samples"), locked_track.get("discard_padding"), locked_track.get("decoded_pcm_sha256"))
                if actual != expected or (decoded.get("track"), decoded.get("skip_samples"), decoded.get("discard_padding"), decoded.get("decoded_pcm_sha256")) != expected:
                    raise ContractError(f"sequence 02 track {track}: priming/padding/decoded PCM lineage mismatch")
                if source_audio.get("tags", {}).get("payload_sha256") != source_payloads[index]:
                    raise ContractError(f"sequence 02 track {track}: source payload order mismatch")
                if boundary != {"track": track, "decoded_pcm_sha256": decoded_pcm, "start": "PASS", "tail": "PASS"}:
                    raise ContractError(f"sequence 02 track {track}: PCM boundary/tail QC missing")
                actual_pcm_evidence.append(
                    {
                        "track": track,
                        "skip_samples": side.get("skip_samples"),
                        "discard_padding": side.get("discard_padding"),
                        "decoded_pcm_sha256": decoded_pcm,
                    }
                )
            if derivation.get("mode") != "approved-trackwise-gapless-pcm-concat-transcode":
                raise ContractError("sequence 02: trackwise gapless PCM concat derivation required")
            computed_composites = {
                ordered_pcm_composite_sha256(actual_pcm_evidence),
                ordered_pcm_composite_sha256(locked_tracks),
                ordered_pcm_composite_sha256(track_decodes),
            }
            computed_vectors = {
                pcm_track_vector(actual_pcm_evidence),
                pcm_track_vector(locked_tracks),
                pcm_track_vector(track_decodes),
            }
            claimed_composites = (
                locked.get("ordered_pcm_concat_sha256"),
                derivation.get("ordered_pcm_concat_sha256"),
                qc.get("ordered_pcm_concat_sha256"),
            )
            if (
                any(not is_sha256_value(value) for value in claimed_composites)
                or set(claimed_composites) != {EXPECTED_PLAYLIST_PCM_COMPOSITE_SHA256}
                or computed_composites != {EXPECTED_PLAYLIST_PCM_COMPOSITE_SHA256}
                or computed_vectors != {EXPECTED_PLAYLIST_PCM_TRACK_VECTOR}
            ):
                raise ContractError(
                    "sequence 02: ordered PCM composite must be the exact recomputed domain-separated authority proof"
                )
            if (
                derivation.get("decoded_total_samples") != PLAYLIST_DECODED_SAMPLES
                or qc.get("decoded_total_samples") != PLAYLIST_DECODED_SAMPLES
                or derivation.get("removed_internal_gap_samples") != PLAYLIST_REMOVED_GAP_SAMPLES
                or qc.get("removed_internal_gap_samples") != PLAYLIST_REMOVED_GAP_SAMPLES
            ):
                raise ContractError(
                    "sequence 02: decoded sample total/internal gap removal proof mismatch"
                )
            validate_encoder(derivation.get("encoder"), sequence, playlist=True)
            expected_kind = "approved-derivative"
        else:
            source_ref = artifact.get("source_audio")
            if type(source_ref) is not dict:
                raise ContractError(f"sequence {sequence:02d}: one approved source object required")
            source_path = resolve_child(root, source_ref.get("path"))
            source_hash = sha256(source_path)
            if source_hash != source_ref.get("sha256") or source_hash != locked.get("approved_source_audio_sha256") or source_hash != receipt.get("source_file_sha256"):
                raise ContractError(f"sequence {sequence:02d}: approved source provenance mismatch")
            source_audio = stream(probe(ffprobe, source_path), "audio")
            source_payload = source_audio.get("tags", {}).get("payload_sha256")
            if derivation.get("source_audio_payload_sha256") != source_payload:
                raise ContractError(f"sequence {sequence:02d}: source payload lineage mismatch")
            if sequence in STREAM_COPY:
                if source_audio.get("codec_name") != "aac" or source_audio.get("profile") != "LC":
                    raise ContractError(f"sequence {sequence:02d}: stream-copy source probe is not AAC-LC")
                if derivation.get("mode") != "stream-copy" or derivation.get("encoder") is not None or source_payload != final_payload:
                    raise ContractError(f"sequence {sequence:02d}: approved AAC must be stream-copied")
                expected_kind = "approved-source"
            else:
                if source_audio.get("codec_name") != "mp3" or derivation.get("mode") != "approved-transcode" or source_payload == final_payload:
                    raise ContractError(f"sequence {sequence:02d}: individual MP3 must have a distinct approved derivative")
                validate_encoder(derivation.get("encoder"), sequence, playlist=False)
                expected_kind = "approved-derivative"

        if derivation.get("output_audio_payload_sha256") != final_payload:
            raise ContractError(f"sequence {sequence:02d}: output audio payload lineage mismatch")
        if sequence in TRANSCODE and (int(final_audio.get("bit_rate", 0)), int(final_audio.get("sample_rate", 0)), final_audio.get("channels")) != (256000, 44100, 2):
            raise ContractError(f"sequence {sequence:02d}: AAC derivative parameters mismatch")
        approval_required = {
            "kind", "artifact_audio_payload_sha256", "decision", "reviewer", "reviewed_at",
        }
        if (
            not approval_required <= set(approval)
            or approval.get("kind") != expected_kind
            or approval.get("artifact_audio_payload_sha256") != final_payload
            or {key: approval.get(key) for key in APPROVAL_AUTHORITY_FIELDS} != approval_authority
            or not is_canonical_rfc3339_seconds(approval.get("reviewed_at"))
        ):
            raise ContractError(f"sequence {sequence:02d}: exact audio approval missing")
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
            raise ContractError(f"sequence {sequence:02d}: actual video fingerprint differs from authority")
        for key, expected in expected_qc.items():
            if key not in qc or qc.get(key) != expected:
                raise ContractError(f"sequence {sequence:02d}: QC {key} not bound to actual/authority")
        tail = qc.get("real_time_tail_playback")
        if qc.get("status") != "PASS" or qc.get("full_decode") != "PASS" or qc.get("avfoundation_decode") != "PASS" or type(tail) is not dict or tail.get("status") != "PASS" or not tail.get("reviewer") or float(tail.get("tail_seconds", 0)) <= 0:
            raise ContractError(f"sequence {sequence:02d}: full decode/player/tail QC is incomplete")


def write_test_candidate(skill_dir: Path, script_source: str) -> None:
    """Create static-contract-compliant assets around an intentionally bad verifier."""
    scripts = skill_dir / "scripts"
    references = skill_dir / "references"
    scripts.mkdir(parents=True)
    references.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "All four profiles use MP4 + AAC-LC. MOV+MP3 is forbidden.\n"
        + "\n".join(REQUIRED_INCIDENT_STATEMENTS)
        + "\n",
        encoding="utf-8",
    )
    (references / "qc-contract.md").write_text(
        "Upload-ready output is MP4 + AAC-LC; MOV+MP3 is prohibited.\n"
        + "\n".join(REQUIRED_INCIDENT_STATEMENTS)
        + "\n",
        encoding="utf-8",
    )
    write_json(
        references / "episode-inventory.v2.json",
        {
            "episodes": [
                {"sequence": sequence, "episode_id": f"{sequence:02d}-fixture", "container": "mp4", "audio_codec": "aac"}
                for sequence in sorted(SEQUENCES)
            ]
        },
    )
    write_json(
        references / "job-manifest.v2.schema.json",
        {
            "properties": {
                "output": {
                    "properties": {
                        "filename": {"pattern": r"^[^/\\]+\.mp4$"},
                        "container": {"const": "mp4"},
                    }
                }
            }
        },
    )
    script = scripts / "hymn_video_flow_v3.py"
    script.write_text(script_source, encoding="utf-8")
    script.chmod(0o755)


def write_partial_contract_candidate(skill_dir: Path) -> None:
    """Probe all inputs but enforce only final MP4/AAC and final-tail status."""
    write_test_candidate(
        skill_dir,
        '''#!/usr/bin/env python3
import argparse, json, os, subprocess, sys
from pathlib import Path

PROFILE_CONTRACTS = {
    "start-hybrid/v1": {"container": "mp4", "audio_codec": "aac"},
    "playlist/v1": {"container": "mp4", "audio_codec": "aac"},
    "testimony-static/v1": {"container": "mp4", "audio_codec": "aac"},
    "hymn-lyrics/v1": {"container": "mp4", "audio_codec": "aac"},
}

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="command", required=True)
verify = sub.add_parser("verify-upload-ready")
verify.add_argument("--manifest", required=True, type=Path)
verify.add_argument("--authority-lock", required=True, type=Path)
verify.add_argument("--ffprobe", required=True, type=Path)
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
root = args.manifest.parent
receipts = json.loads((root / manifest["receipts"]["path"]).read_text(encoding="utf-8"))
for receipt in receipts["entries"]:
    if receipt.get("qc", {}).get("real_time_tail_playback", {}).get("status") != "PASS":
        raise SystemExit(2)
for artifact in manifest["artifacts"]:
    sources = artifact["source_audio"] if isinstance(artifact["source_audio"], list) else [artifact["source_audio"]]
    references = [(source, False) for source in sources] + [(artifact["final_media"], True)]
    for reference, is_final in references:
        media = root / reference["path"]
        result = subprocess.run(
            [str(args.ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media)],
            text=True, capture_output=True, check=False, env=os.environ.copy(),
        )
        if result.returncode:
            raise SystemExit(2)
        probed = json.loads(result.stdout)
        if is_final:
            audio = [stream for stream in probed["streams"] if stream.get("codec_type") == "audio"]
            video = [stream for stream in probed["streams"] if stream.get("codec_type") == "video"]
            formats = {part.strip().lower() for part in str(probed.get("format", {}).get("format_name", "")).split(",")}
            brand = str(probed.get("format", {}).get("tags", {}).get("major_brand", "")).strip().lower()
            if len(audio) != 1 or len(video) != 1 or "mp4" not in formats or brand not in {"isom", "iso2", "mp41", "mp42", "avc1", "dash", "mmp4"} or audio[0].get("codec_name") != "aac" or audio[0].get("profile") != "LC":
                raise SystemExit(2)
# BUG: authenticated probes happen, but source codec/profile, lineage, authority,
# frame identity, encoder contract, approval, and trackwise gapless proof are ignored.
print(json.dumps({"status": "ok", "verified_sequences": [1, 2, 3, 4, 5, 6]}))
''',
    )


def write_spoof_candidate(skill_dir: Path) -> None:
    """Model the rejected rev3 exploit: forge a known log and never call ffprobe."""
    write_test_candidate(
        skill_dir,
        '''#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path

PROFILE_CONTRACTS = {
    "start-hybrid/v1": {"container": "mp4", "audio_codec": "aac"},
    "playlist/v1": {"container": "mp4", "audio_codec": "aac"},
    "testimony-static/v1": {"container": "mp4", "audio_codec": "aac"},
    "hymn-lyrics/v1": {"container": "mp4", "audio_codec": "aac"},
}

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="command", required=True)
verify = sub.add_parser("verify-upload-ready")
verify.add_argument("--manifest", required=True, type=Path)
verify.add_argument("--authority-lock", required=True, type=Path)
verify.add_argument("--ffprobe", required=True, type=Path)
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
# Old runner exposed FFPROBE_LOG. Forge it if present and branch on predictable names.
log_path = os.environ.get("FFPROBE_LOG")
if log_path:
    paths = []
    for artifact in manifest["artifacts"]:
        sources = artifact["source_audio"] if isinstance(artifact["source_audio"], list) else [artifact["source_audio"]]
        paths.extend(str((args.manifest.parent / item["path"]).resolve()) for item in sources)
        paths.append(str((args.manifest.parent / artifact["final_media"]["path"]).resolve()))
    Path(log_path).write_text("\\n".join(paths) + "\\n", encoding="utf-8")
_predictable_attack = any(part in {"baseline", "renamed", "bad-stream-source"} for part in args.manifest.parts)
# Deliberately never execute --ffprobe.
print(json.dumps({"status": "ok", "verified_sequences": [1, 2, 3, 4, 5, 6]}))
''',
    )


def self_test() -> None:
    ffprobe = FIXTURE / "ffprobe-stub.py"
    # Exercise both the executable public stub and fast trusted in-process parsing.
    validate_fixture(FIXTURE, ffprobe)
    validate_fixture(FIXTURE, None)
    incident = load_json(FIXTURE / "incident.json")
    validate_incident_contract(incident)
    overclaimed_incident = json.loads(json.dumps(incident))
    overclaimed_incident["forbidden_preconcatenated_source"]["causality_limit"] = (
        "the 17,327 silent samples directly caused the audible spike"
    )
    try:
        validate_incident_contract(overclaimed_incident)
    except ContractError:
        pass
    else:
        raise ContractError("incident causality overclaim was accepted by the exact schema contract")
    if not all(
        is_canonical_rfc3339_seconds(value["reviewed_at"])
        for value in EXPECTED_APPROVAL_AUTHORITIES.values()
    ) or any(
        is_canonical_rfc3339_seconds(value)
        for value in (
            "2026-02-30T09:00:00+09:00",
            "2026-08-22 09:00:00+09:00",
            "2026-08-22T09:00:00",
            "2026-08-22T09:00:00+14:30",
        )
    ):
        raise ContractError("approval reviewed_at canonical RFC3339-seconds validator is unsound")
    legacy = resolve_child(FIXTURE, incident["final_artifact"]["path"])
    renamed = resolve_child(FIXTURE, incident["rename_control"]["path"])
    if sha256(legacy) != sha256(renamed):
        raise ContractError("rename control must have byte-identical legacy MOV bytes")
    try:
        assert_final_probe(probe(None, renamed), 2)
    except ContractError:
        pass
    else:
        raise ContractError("extension-only rename was incorrectly accepted")

    with tempfile.TemporaryDirectory(prefix="hymn-aac-eval-matrix-") as temporary:
        attacks = build_attacks(Path(temporary))
        names = [name for name, _fixture in attacks]
        critical_names: set[str] = set()
        for sequence in sorted(SEQUENCES):
            critical_names.update(
                {
                    f"{sequence:02d} approval artifact binding mutation",
                    f"{sequence:02d} approval decision mutation",
                    f"{sequence:02d} approval reviewer mutation",
                    f"{sequence:02d} approval valid-looking timestamp mutation",
                    f"{sequence:02d} approval invalid RFC3339 date mutation",
                    f"{sequence:02d} approval authority echo/rebinding mutation",
                    f"{sequence:02d} authority identity binding mutation",
                    f"{sequence:02d} authority video fingerprint binding mutation",
                    f"{sequence:02d} manifest exact final SHA mutation",
                    f"{sequence:02d} receipt exact final SHA mutation",
                    f"{sequence:02d} final QC exact SHA mutation",
                    f"{sequence:02d} full decode QC mutation",
                    f"{sequence:02d} AVFoundation QC mutation",
                    f"{sequence:02d} captions authority/QC binding mutation",
                    f"{sequence:02d} boundaries authority/QC binding mutation",
                    f"{sequence:02d} chapters canonical authority/QC mutation",
                }
            )
            if sequence != 2:
                critical_names.update(
                    {
                        f"{sequence:02d} missing canonical authority chapters key",
                        f"{sequence:02d} missing canonical QC chapters key",
                    }
                )
        for sequence in sorted(TRANSCODE):
            critical_names.update(
                f"{sequence:02d} forbidden encoder processing {option}"
                for option in FORBIDDEN_PROCESSING_OPTIONS
            )
            critical_names.update(
                {
                    f"{sequence:02d} encoder input argv order mutation",
                    f"{sequence:02d} encoder map argv order mutation",
                    f"{sequence:02d} encoder map argv value mutation",
                    f"{sequence:02d} encoder output argv mutation",
                    f"{sequence:02d} encoder arbitrary extra argv mutation",
                    f"{sequence:02d} encoder filter graph mutation",
                }
            )
            critical_names.update(
                f"{sequence:02d} duplicate encoder pair {flag} {value}"
                for flag, value in TRANSCODE_FLAG_PAIRS
            )
        for sequence in sorted(STREAM_COPY):
            critical_names.add(f"{sequence:02d} stream-copy non-applicable encoder mutation")
        critical_names.update(
            {
                "02 ordered PCM composite claim echo/rebinding mutation",
            }
        )
        critical_names.update(
            f"02 track {track:02d} PCM evidence full echo/rebinding mutation"
            for track in range(1, 13)
        )
        missing_critical = critical_names - set(names)
        if len(names) != len(set(names)) or len(attacks) != EXPECTED_ATTACK_COUNT or missing_critical:
            raise ContractError("attack matrix is incomplete or has duplicate labels")
        accepted: list[str] = []
        for name, attack in attacks:
            try:
                validate_fixture(attack, None)
            except ContractError:
                continue
            accepted.append(name)
        if accepted:
            raise ContractError("reference validator accepted attacks: " + " | ".join(accepted))

    safe_docs = (
        "MOV+MP3 is forbidden.\nMOV + MP3는 허용하지 않는다.\n"
        "MOV+MP3 is not supported.\nDo not use MOV+MP3.\n"
        "MOV+MP3 is not permitted.\nDo not allow MOV+MP3.\n"
        "MOV+MP3 is no longer supported.\nMOV+MP3 지원 안 함.\n"
        "2026-08-22 MOV+MP3 사고."
    )
    unsafe_docs = (
        "- playlist/v1: MOV + MP3.\nMOV+MP3 is allowed for upload.\n"
        "Do not use MOV+MP3, but MOV+MP3 is allowed for legacy uploads."
    )
    if permissive_mov_mp3_lines(safe_docs) or len(permissive_mov_mp3_lines(unsafe_docs)) != 3:
        raise ContractError("MOV+MP3 allowance/prohibition classifier is not context-sensitive")
    exact_incident_docs = "\n".join(REQUIRED_INCIDENT_STATEMENTS)
    if incident_documentation_failures(exact_incident_docs):
        raise ContractError("exact uncertainty statements were rejected")
    reviewer_overclaim = ADVERSARIAL_INCIDENT_OVERCLAIMS[0]
    for overclaim in ADVERSARIAL_INCIDENT_OVERCLAIMS:
        overclaim_docs = exact_incident_docs + "\n" + overclaim
        if not any("overclaims" in failure for failure in incident_documentation_failures(overclaim_docs)):
            raise ContractError(f"explicit incident overclaim corpus entry was not rejected: {overclaim}")
    valid_profiles = {
        profile: {"container": "mp4", "audio_codec": "aac"}
        for profile in EXPECTED_PROFILES
    }
    missing_lyrics = {key: value for key, value in valid_profiles.items() if key != "hymn-lyrics/v1"}
    if profile_contract_failures(valid_profiles) or not profile_contract_failures(missing_lyrics):
        raise ContractError("exact four-profile set checker does not reject a missing profile")

    with tempfile.TemporaryDirectory(prefix="hymn-aac-eval-doc-overclaim-") as temporary:
        mutated_skill = Path(temporary) / "hymn-letter-video-production"
        write_partial_contract_candidate(mutated_skill)
        if static_candidate_failures(mutated_skill):
            raise ContractError("safe incident-documentation test candidate unexpectedly failed static checks")
        skill_doc = mutated_skill / "SKILL.md"
        skill_doc.write_text(
            skill_doc.read_text(encoding="utf-8")
            + reviewer_overclaim
            + "\n",
            encoding="utf-8",
        )
        if not any("overclaims" in failure for failure in static_candidate_failures(mutated_skill)):
            raise ContractError("adversarial candidate documentation overclaim was accepted")

    with tempfile.TemporaryDirectory(prefix="hymn-aac-eval-spoof-") as temporary:
        temporary_root = Path(temporary)
        spoof_skill = temporary_root / "hymn-letter-video-production"
        write_spoof_candidate(spoof_skill)
        spoof_fixture = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, spoof_fixture)
        spoof_ok, spoof_evidence = invoke_candidate(spoof_skill, spoof_fixture, True)
        if spoof_ok or "authenticated_probe_count=0" not in spoof_evidence or "lacks authenticated" not in spoof_evidence:
            raise ContractError("log-forging/no-probe candidate escaped authenticated broker gate")

    with tempfile.TemporaryDirectory(prefix="hymn-aac-eval-partial-") as temporary:
        temporary_root = Path(temporary)
        partial_skill = temporary_root / "hymn-letter-video-production"
        write_partial_contract_candidate(partial_skill)
        partial_baseline = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, partial_baseline)
        partial_ok, partial_evidence = invoke_candidate(partial_skill, partial_baseline, True)
        if not partial_ok:
            raise ContractError("partial candidate must first satisfy authenticated baseline probes: " + partial_evidence)
        ignored_source = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, ignored_source)
        mutate_stream_source_probe(ignored_source, 3, profile="unknown")
        rejected, evidence = invoke_candidate(partial_skill, ignored_source, False)
        if rejected:
            raise ContractError("partial candidate unexpectedly rejected ignored source-profile mutation: " + evidence)
        ignored_gapless = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, ignored_gapless)
        mutate_playlist_actual_track(ignored_gapless, 7, skip_samples=0)
        rejected, evidence = invoke_candidate(partial_skill, ignored_gapless, False)
        if rejected:
            raise ContractError("partial candidate unexpectedly rejected ignored per-track trim mutation: " + evidence)
        ignored_contracts = (
            (
                "01 approval",
                lambda root: mutate_receipt_entry(
                    root,
                    1,
                    lambda receipt: receipt["approval"].__setitem__("artifact_audio_payload_sha256", "0" * 64),
                ),
            ),
            (
                "03 full decode",
                lambda root: mutate_receipt_entry(
                    root,
                    3,
                    lambda receipt: receipt["qc"].__setitem__("full_decode", "FAIL"),
                ),
            ),
            ("05 canonical chapters", lambda root: mutate_chapters_binding(root, 5)),
            ("04 stream-specified audio filter", lambda root: add_forbidden_encoder_flag(root, 4, "-filter:a:0")),
        )
        for contract_name, mutate in ignored_contracts:
            ignored = temporary_root / secrets.token_hex(16)
            shutil.copytree(FIXTURE, ignored)
            mutate(ignored)
            rejected, evidence = invoke_candidate(partial_skill, ignored, False)
            if rejected:
                raise ContractError(
                    f"partial candidate unexpectedly rejected ignored {contract_name} mutation: " + evidence
                )

    print("PASS reference six-profile MP4/AAC-LC bundle")
    print("PASS MP3-in-MOV survives extension rename and is rejected by actual probe")
    print(f"PASS independent approval/authority/composite matrix rejected ({len(attacks)} mutations)")
    print("PASS prohibitive wording and exact incident uncertainty pass while causal overclaim fails")
    print("PASS exact four-profile set rejects a missing playlist/hymn contract")
    print("PASS 01/03/05 source probes require AAC-LC independently of payload tags")
    print("PASS runner-owned authenticated broker rejects forged logs and zero-probe candidates")
    print("PASS probing partial candidate is exposed by cross-sequence approval/QC/filter mutations")
    print("PASS 02 exact 12-track gapless proof recomputes the fixed domain-separated PCM composite")
    print("SELF_TEST 9/9")


def extract_profile_contracts(script: Path) -> dict:
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PROFILE_CONTRACTS" for target in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "PROFILE_CONTRACTS":
            return ast.literal_eval(node.value)
    raise ContractError("PROFILE_CONTRACTS literal not found")


def static_candidate_failures(skill_dir: Path) -> list[str]:
    failures: list[str] = []
    script = skill_dir / "scripts" / "hymn_video_flow_v3.py"
    inventory_path = skill_dir / "references" / "episode-inventory.v2.json"
    schema_path = skill_dir / "references" / "job-manifest.v2.schema.json"
    skill_path = skill_dir / "SKILL.md"
    qc_path = skill_dir / "references" / "qc-contract.md"
    for path in (script, inventory_path, schema_path, skill_path, qc_path):
        if not path.is_file():
            failures.append(f"missing candidate asset: {path}")
    if failures:
        return failures
    try:
        contracts = extract_profile_contracts(script)
        failures.extend(profile_contract_failures(contracts))
    except (ContractError, SyntaxError, ValueError) as exc:
        failures.append(f"cannot inspect PROFILE_CONTRACTS: {exc}")
    try:
        episodes = load_json(inventory_path).get("episodes", [])
        if {item.get("sequence") for item in episodes} != SEQUENCES:
            failures.append("inventory does not contain exact sequences 01-06")
        for item in episodes:
            if item.get("container") != "mp4" or item.get("audio_codec") != "aac":
                failures.append(f"inventory {item.get('episode_id')} still permits {item.get('container')}+{item.get('audio_codec')}")
    except ContractError as exc:
        failures.append(str(exc))
    try:
        output = load_json(schema_path)["properties"]["output"]["properties"]
        containers = set(output["container"].get("enum", [output["container"].get("const")]))
        pattern = output["filename"].get("pattern", "")
        if containers != {"mp4"} or re.fullmatch(pattern, "candidate.mov") or not re.fullmatch(pattern, "candidate.mp4"):
            failures.append("job schema does not lock output to .mp4/container mp4")
    except (ContractError, KeyError, re.error, TypeError) as exc:
        failures.append(f"cannot inspect job output schema: {exc}")
    docs = (skill_path.read_text(encoding="utf-8") + "\n" + qc_path.read_text(encoding="utf-8"))
    permissive_claims = permissive_mov_mp3_lines(docs)
    if permissive_claims:
        failures.append(
            "candidate documentation still allows MOV+MP3: "
            + " | ".join(permissive_claims)
        )
    if "AAC-LC" not in docs or "MP4" not in docs:
        failures.append("candidate documentation lacks explicit MP4 + AAC-LC upload-ready rule")
    failures.extend(incident_documentation_failures(docs))
    return failures


def required_probe_paths(fixture: Path) -> set[str]:
    manifest = load_json(fixture / "upload-ready.json")
    paths: set[str] = set()
    for artifact in manifest.get("artifacts", []):
        sources = artifact.get("source_audio")
        source_refs = sources if type(sources) is list else [sources]
        for reference in [*source_refs, artifact.get("final_media")]:
            if type(reference) is dict:
                paths.add(str(resolve_child(fixture, reference.get("path"))))
    return paths


def invoke_candidate(skill_dir: Path, fixture: Path, expect_success: bool) -> tuple[bool, str]:
    script = skill_dir / "scripts" / "hymn_video_flow_v3.py"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("FFPROBE_LOG", None)
    before = snapshot_tree(fixture)
    with ProbeBroker(fixture) as broker:
        assert broker.wrapper is not None
        command = [
            sys.executable, str(script), "verify-upload-ready",
            "--manifest", str(fixture / "upload-ready.json"),
            "--authority-lock", str(fixture / "authority-lock.json"),
            "--ffprobe", str(broker.wrapper),
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=environment)
        authenticated_paths = broker.verified_paths()
    after = snapshot_tree(fixture)
    mutated = before != after
    command = [
        sys.executable, str(script), "verify-upload-ready", "--manifest", "<fixture>",
        "--authority-lock", "<authority>", "--ffprobe", "<authenticated-broker>",
    ]
    rendered = (
        f"command={' '.join(command)}\nexit={result.returncode}\n"
        f"authenticated_probe_count={len(authenticated_paths)} fixture_mutated={mutated}\n"
        f"stdout:\n{result.stdout}stderr:\n{result.stderr}"
    )
    if mutated:
        return False, rendered + "candidate mutated eval fixture\n"
    if expect_success:
        if result.returncode != 0:
            return False, rendered
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, rendered + "invalid success JSON\n"
        if payload.get("status") != "ok" or payload.get("verified_sequences") != [1, 2, 3, 4, 5, 6]:
            return False, rendered + "success JSON lacks exact verified_sequences\n"
        required = required_probe_paths(fixture)
        if not required <= authenticated_paths:
            return False, rendered + f"candidate lacks authenticated source/final probes: {sorted(required - authenticated_paths)}\n"
        return True, rendered
    return result.returncode != 0, rendered


def mutate_receipts(fixture: Path, mutate) -> None:
    receipts = load_json(fixture / "receipts.json")
    mutate(receipts)
    write_json(fixture / "receipts.json", receipts)
    manifest = load_json(fixture / "upload-ready.json")
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def entry_for(document: dict, collection: str, sequence: int) -> dict:
    matches = [item for item in document[collection] if item.get("sequence") == sequence]
    if len(matches) != 1:
        raise ContractError(f"attack fixture lacks unique sequence {sequence:02d} in {collection}")
    return matches[0]


def refresh_document_refs(fixture: Path, *, authority: dict | None = None, receipts: dict | None = None) -> None:
    if authority is not None:
        write_json(fixture / "authority-lock.json", authority)
    if receipts is not None:
        write_json(fixture / "receipts.json", receipts)
    manifest = load_json(fixture / "upload-ready.json")
    manifest["authority_lock"]["sha256"] = sha256(fixture / "authority-lock.json")
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def media_tokens(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in path.read_text(encoding="utf-8").strip().split():
        key, separator, value = token.partition("=")
        if not separator:
            raise ContractError(f"invalid attack media token {token!r}")
        values[key] = value
    return values


def rewrite_media(path: Path, **updates: object) -> None:
    values = media_tokens(path)
    for key, value in updates.items():
        if key not in values:
            raise ContractError(f"cannot mutate absent media token {key!r}")
        values[key] = str(value)
    path.write_text(" ".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")


def rebind_final_hash(fixture: Path, sequence: int) -> None:
    manifest = load_json(fixture / "upload-ready.json")
    artifact = entry_for(manifest, "artifacts", sequence)
    final_path = resolve_child(fixture, artifact["final_media"]["path"])
    final_hash = sha256(final_path)
    artifact["final_media"]["sha256"] = final_hash
    receipts = load_json(fixture / "receipts.json")
    receipt = entry_for(receipts, "entries", sequence)
    receipt["final_file_sha256"] = final_hash
    receipt["qc"]["final_file_sha256"] = final_hash
    write_json(fixture / "receipts.json", receipts)
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def mutate_final(fixture: Path, sequence: int, **updates: object) -> None:
    manifest = load_json(fixture / "upload-ready.json")
    final_ref = entry_for(manifest, "artifacts", sequence)["final_media"]
    rewrite_media(resolve_child(fixture, final_ref["path"]), **updates)
    rebind_final_hash(fixture, sequence)


def mutate_stream_source_probe(fixture: Path, sequence: int, **updates: object) -> None:
    manifest = load_json(fixture / "upload-ready.json")
    artifact = entry_for(manifest, "artifacts", sequence)
    source = resolve_child(fixture, artifact["source_audio"]["path"])
    rewrite_media(source, **updates)
    source_hash = sha256(source)
    artifact["source_audio"]["sha256"] = source_hash
    authority = load_json(fixture / "authority-lock.json")
    entry_for(authority, "episodes", sequence)["approved_source_audio_sha256"] = source_hash
    receipts = load_json(fixture / "receipts.json")
    entry_for(receipts, "entries", sequence)["source_file_sha256"] = source_hash
    write_json(fixture / "authority-lock.json", authority)
    write_json(fixture / "receipts.json", receipts)
    manifest["authority_lock"]["sha256"] = sha256(fixture / "authority-lock.json")
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def mutate_receipt_entry(fixture: Path, sequence: int, mutate) -> None:
    receipts = load_json(fixture / "receipts.json")
    mutate(entry_for(receipts, "entries", sequence))
    refresh_document_refs(fixture, receipts=receipts)


def mutate_authority_entry(fixture: Path, sequence: int, mutate) -> None:
    authority = load_json(fixture / "authority-lock.json")
    mutate(entry_for(authority, "episodes", sequence))
    refresh_document_refs(fixture, authority=authority)


def mutate_manifest_final_sha(fixture: Path, sequence: int) -> None:
    manifest = load_json(fixture / "upload-ready.json")
    entry_for(manifest, "artifacts", sequence)["final_media"]["sha256"] = "0" * 64
    write_json(fixture / "upload-ready.json", manifest)


def mutate_chapters_binding(fixture: Path, sequence: int) -> None:
    if sequence == 2:
        mutate_receipt_entry(
            fixture,
            sequence,
            lambda receipt: receipt["qc"].__setitem__("chapters_sha256", "0" * 64),
        )
        return
    # For a non-applicable field, mutate authority and QC together. This catches
    # candidates that merely compare the two while ignoring canonical explicit null.
    authority = load_json(fixture / "authority-lock.json")
    receipts = load_json(fixture / "receipts.json")
    entry_for(authority, "episodes", sequence)["chapters_sha256"] = "0" * 64
    entry_for(receipts, "entries", sequence)["qc"]["chapters_sha256"] = "0" * 64
    refresh_document_refs(fixture, authority=authority, receipts=receipts)


def mutate_approval_authority_rebinding(fixture: Path, sequence: int) -> None:
    attacker_authority = {
        "reviewer": "attacker-reviewer",
        "decision": "REJECTED",
        "reviewed_at": "2026-08-22T10:00:00+09:00",
    }
    authority = load_json(fixture / "authority-lock.json")
    receipts = load_json(fixture / "receipts.json")
    entry_for(authority, "episodes", sequence)["approval_authority"] = dict(attacker_authority)
    entry_for(receipts, "entries", sequence)["approval"].update(attacker_authority)
    refresh_document_refs(fixture, authority=authority, receipts=receipts)


def corrupt_encoder_pair(fixture: Path, sequence: int, flag: str, _value: str) -> None:
    def mutate(receipt: dict) -> None:
        command = receipt["derivation"]["encoder"]["normalized_command"]
        index = command.index(flag)
        command[index + 1] = "BROKEN"

    mutate_receipt_entry(fixture, sequence, mutate)


def mutate_encoder_argv(fixture: Path, sequence: int, mutate) -> None:
    def mutate_receipt(receipt: dict) -> None:
        mutate(receipt["derivation"]["encoder"]["normalized_command"])

    mutate_receipt_entry(fixture, sequence, mutate_receipt)


def mutate_encoder_input_order(fixture: Path, sequence: int) -> None:
    def mutate(command: list[str]) -> None:
        inputs = [index for index, token in enumerate(command) if token == "-i"]
        if len(inputs) > 1:
            first, second = inputs[:2]
            command[first + 1], command[second + 1] = command[second + 1], command[first + 1]
            return
        index = inputs[0]
        pair = command[index:index + 2]
        del command[index:index + 2]
        command[command.index("-c:v"):command.index("-c:v")] = pair

    mutate_encoder_argv(fixture, sequence, mutate)


def mutate_encoder_map_order(fixture: Path, sequence: int) -> None:
    def mutate(command: list[str]) -> None:
        maps = [index for index, token in enumerate(command) if token == "-map"]
        command[maps[0] + 1], command[maps[1] + 1] = command[maps[1] + 1], command[maps[0] + 1]

    mutate_encoder_argv(fixture, sequence, mutate)


def mutate_encoder_map_value(fixture: Path, sequence: int) -> None:
    def mutate(command: list[str]) -> None:
        command[command.index("-map") + 1] = "9:a:0"

    mutate_encoder_argv(fixture, sequence, mutate)


def mutate_encoder_output(fixture: Path, sequence: int) -> None:
    mutate_encoder_argv(fixture, sequence, lambda command: command.__setitem__(-1, "<wrong-output>.mov"))


def mutate_encoder_duplicate_pair(fixture: Path, sequence: int, flag: str, value: str) -> None:
    mutate_encoder_argv(
        fixture,
        sequence,
        lambda command: command.__setitem__(slice(-1, -1), [flag, value]),
    )


def mutate_encoder_extra_token(fixture: Path, sequence: int) -> None:
    mutate_encoder_argv(
        fixture,
        sequence,
        lambda command: command.__setitem__(slice(-1, -1), ["-metadata", "comment=unexpected"]),
    )


def mutate_encoder_filter_graph(fixture: Path, sequence: int) -> None:
    def mutate(command: list[str]) -> None:
        if sequence == 2:
            index = command.index("-filter_complex") + 1
            command[index] = PLAYLIST_FILTER_GRAPH.replace(
                "[6:a]asetpts=PTS-STARTPTS",
                "[6:a]volume=1,asetpts=PTS-STARTPTS",
            )
        else:
            command[-1:-1] = ["-filter_complex", "[0:a]anull[aout]"]

    mutate_encoder_argv(fixture, sequence, mutate)


def add_forbidden_encoder_flag(fixture: Path, sequence: int, flag: str) -> None:
    def mutate(receipt: dict) -> None:
        command = receipt["derivation"]["encoder"]["normalized_command"]
        insertion = [flag] if flag == "-shortest" or "=" in flag else [flag, "volume=1"]
        command[-1:-1] = insertion

    mutate_receipt_entry(fixture, sequence, mutate)


def mutate_source_replacement(fixture: Path, sequence: int) -> None:
    """Rebind manifest/receipt derivation to replacement bytes, but not authority."""
    manifest = load_json(fixture / "upload-ready.json")
    artifact = entry_for(manifest, "artifacts", sequence)
    receipts = load_json(fixture / "receipts.json")
    receipt = entry_for(receipts, "entries", sequence)
    replacement_payload = (f"{7 + sequence:x}" * 64)[:64]
    if sequence == 2:
        source_ref = artifact["source_audio"][0]
        source = resolve_child(fixture, source_ref["path"])
        replacement_pcm = "f201" * 16
        rewrite_media(source, audio_payload=replacement_payload, decoded_pcm=replacement_pcm)
        source_hash = sha256(source)
        source_ref["sha256"] = source_hash
        receipt["source_track_sha256"][0] = source_hash
        receipt["derivation"]["source_audio_payload_sha256"][0] = replacement_payload
        receipt["derivation"]["track_decodes"][0]["decoded_pcm_sha256"] = replacement_pcm
        receipt["qc"]["track_boundaries"][0]["decoded_pcm_sha256"] = replacement_pcm
    else:
        source_ref = artifact["source_audio"]
        source = resolve_child(fixture, source_ref["path"])
        rewrite_media(source, audio_payload=replacement_payload)
        source_hash = sha256(source)
        source_ref["sha256"] = source_hash
        receipt["source_file_sha256"] = source_hash
        receipt["derivation"]["source_audio_payload_sha256"] = replacement_payload
    write_json(fixture / "receipts.json", receipts)
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def mutate_playlist_actual_track(fixture: Path, track: int, **updates: object) -> None:
    """Change actual track bytes and rebind object hashes, retaining locked semantics."""
    manifest = load_json(fixture / "upload-ready.json")
    artifact = entry_for(manifest, "artifacts", 2)
    source_ref = artifact["source_audio"][track - 1]
    source = resolve_child(fixture, source_ref["path"])
    rewrite_media(source, **updates)
    source_hash = sha256(source)
    source_ref["sha256"] = source_hash
    receipts = load_json(fixture / "receipts.json")
    receipt = entry_for(receipts, "entries", 2)
    receipt["source_track_sha256"][track - 1] = source_hash
    authority = load_json(fixture / "authority-lock.json")
    entry_for(authority, "episodes", 2)["approved_source_tracks"][track - 1]["sha256"] = source_hash
    write_json(fixture / "receipts.json", receipts)
    write_json(fixture / "authority-lock.json", authority)
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    manifest["authority_lock"]["sha256"] = sha256(fixture / "authority-lock.json")
    write_json(fixture / "upload-ready.json", manifest)


def mutate_pcm_composite_claim_rebinding(fixture: Path) -> None:
    fake_composite = "not-a-sha256"
    authority = load_json(fixture / "authority-lock.json")
    receipts = load_json(fixture / "receipts.json")
    entry_for(authority, "episodes", 2)["ordered_pcm_concat_sha256"] = fake_composite
    receipt = entry_for(receipts, "entries", 2)
    receipt["derivation"]["ordered_pcm_concat_sha256"] = fake_composite
    receipt["qc"]["ordered_pcm_concat_sha256"] = fake_composite
    refresh_document_refs(fixture, authority=authority, receipts=receipts)


def mutate_playlist_pcm_with_full_rebinding(fixture: Path, track: int) -> None:
    """Change one actual PCM proof and consistently echo it through every mutable claim."""
    replacement_pcm = f"9f{track:02x}" * 16
    manifest = load_json(fixture / "upload-ready.json")
    authority = load_json(fixture / "authority-lock.json")
    receipts = load_json(fixture / "receipts.json")
    artifact = entry_for(manifest, "artifacts", 2)
    locked = entry_for(authority, "episodes", 2)
    receipt = entry_for(receipts, "entries", 2)
    source_ref = artifact["source_audio"][track - 1]
    source = resolve_child(fixture, source_ref["path"])
    rewrite_media(source, decoded_pcm=replacement_pcm)
    source_hash = sha256(source)
    source_ref["sha256"] = source_hash
    receipt["source_track_sha256"][track - 1] = source_hash
    locked_track = locked["approved_source_tracks"][track - 1]
    locked_track["sha256"] = source_hash
    locked_track["decoded_pcm_sha256"] = replacement_pcm
    receipt["derivation"]["track_decodes"][track - 1]["decoded_pcm_sha256"] = replacement_pcm
    receipt["qc"]["track_boundaries"][track - 1]["decoded_pcm_sha256"] = replacement_pcm
    echoed_composite = ordered_pcm_composite_sha256(locked["approved_source_tracks"])
    locked["ordered_pcm_concat_sha256"] = echoed_composite
    receipt["derivation"]["ordered_pcm_concat_sha256"] = echoed_composite
    receipt["qc"]["ordered_pcm_concat_sha256"] = echoed_composite
    write_json(fixture / "authority-lock.json", authority)
    write_json(fixture / "receipts.json", receipts)
    manifest["authority_lock"]["sha256"] = sha256(fixture / "authority-lock.json")
    manifest["receipts"]["sha256"] = sha256(fixture / "receipts.json")
    write_json(fixture / "upload-ready.json", manifest)


def build_attacks(temporary_root: Path) -> list[tuple[str, Path]]:
    """Build independently mutated fixtures in randomized opaque directories."""
    attacks: list[tuple[str, Path]] = []

    def add(name: str, mutate) -> None:
        destination = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, destination)
        mutate(destination)
        attacks.append((name, destination))

    # Every upload-ready file must prove its actual container, brand, audio codec,
    # audio profile, video identity, frame identity, and tail review independently.
    for sequence in sorted(SEQUENCES):
        add(
            f"{sequence:02d} actual final format_name mutation",
            lambda root, sequence=sequence: mutate_final(root, sequence, container="matroska"),
        )
        add(
            f"{sequence:02d} actual final major_brand mutation",
            lambda root, sequence=sequence: mutate_final(root, sequence, major_brand="qt"),
        )
        add(
            f"{sequence:02d} actual final audio codec mutation",
            lambda root, sequence=sequence: mutate_final(root, sequence, codec="mp3"),
        )
        add(
            f"{sequence:02d} actual final audio profile mutation",
            lambda root, sequence=sequence: mutate_final(root, sequence, profile="HE-AAC"),
        )
        add(
            f"{sequence:02d} actual video fingerprint mutation",
            lambda root, sequence=sequence: mutate_final(root, sequence, video_fingerprint="f" * 64),
        )
        add(
            f"{sequence:02d} actual frame identity mutation",
            lambda root, sequence=sequence: mutate_final(
                root,
                sequence,
                frame_count=int(media_tokens(resolve_child(
                    root,
                    entry_for(load_json(root / "upload-ready.json"), "artifacts", sequence)["final_media"]["path"],
                ))["frame_count"]) + 1,
            ),
        )
        add(
            f"{sequence:02d} failed real-time tail QC",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"]["real_time_tail_playback"].__setitem__("status", "FAIL"),
            ),
        )
        add(
            f"{sequence:02d} approval artifact binding mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["approval"].__setitem__("artifact_audio_payload_sha256", "0" * 64),
            ),
        )
        add(
            f"{sequence:02d} approval decision mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["approval"].__setitem__("decision", "REJECTED"),
            ),
        )
        add(
            f"{sequence:02d} approval reviewer mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["approval"].__setitem__("reviewer", "attacker-reviewer"),
            ),
        )
        add(
            f"{sequence:02d} approval valid-looking timestamp mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["approval"].__setitem__("reviewed_at", "2026-08-22T10:00:00+09:00"),
            ),
        )
        add(
            f"{sequence:02d} approval invalid RFC3339 date mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["approval"].__setitem__("reviewed_at", "2026-02-30T09:00:00+09:00"),
            ),
        )
        add(
            f"{sequence:02d} approval authority echo/rebinding mutation",
            lambda root, sequence=sequence: mutate_approval_authority_rebinding(root, sequence),
        )
        add(
            f"{sequence:02d} authority identity binding mutation",
            lambda root, sequence=sequence: mutate_authority_entry(
                root,
                sequence,
                lambda locked: locked.__setitem__("episode_id", "tampered-authority"),
            ),
        )
        add(
            f"{sequence:02d} authority video fingerprint binding mutation",
            lambda root, sequence=sequence: mutate_authority_entry(
                root,
                sequence,
                lambda locked: locked.__setitem__("video_stream_fingerprint_sha256", "e" * 64),
            ),
        )
        add(
            f"{sequence:02d} manifest exact final SHA mutation",
            lambda root, sequence=sequence: mutate_manifest_final_sha(root, sequence),
        )
        add(
            f"{sequence:02d} receipt exact final SHA mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt.__setitem__("final_file_sha256", "0" * 64),
            ),
        )
        add(
            f"{sequence:02d} final QC exact SHA mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"].__setitem__("final_file_sha256", "0" * 64),
            ),
        )
        add(
            f"{sequence:02d} full decode QC mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"].__setitem__("full_decode", "FAIL"),
            ),
        )
        add(
            f"{sequence:02d} AVFoundation QC mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"].__setitem__("avfoundation_decode", "FAIL"),
            ),
        )
        add(
            f"{sequence:02d} captions authority/QC binding mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"].__setitem__("captions_sha256", "0" * 64),
            ),
        )
        add(
            f"{sequence:02d} boundaries authority/QC binding mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["qc"].__setitem__("boundaries_sha256", "0" * 64),
            ),
        )
        add(
            f"{sequence:02d} chapters canonical authority/QC mutation",
            lambda root, sequence=sequence: mutate_chapters_binding(root, sequence),
        )
        if sequence != 2:
            add(
                f"{sequence:02d} missing canonical authority chapters key",
                lambda root, sequence=sequence: mutate_authority_entry(
                    root,
                    sequence,
                    lambda locked: locked.pop("chapters_sha256"),
                ),
            )
            add(
                f"{sequence:02d} missing canonical QC chapters key",
                lambda root, sequence=sequence: mutate_receipt_entry(
                    root,
                    sequence,
                    lambda receipt: receipt["qc"].pop("chapters_sha256"),
                ),
            )

    def extension_only_rename(root: Path) -> None:
        shutil.copy2(root / "media" / "02-renamed-only.mp4", root / "media" / "02-final.mp4")
        rebind_final_hash(root, 2)

    add("02 extension-only MP3-in-MOV rename", extension_only_rename)

    # Stream-copy safety cannot be inferred from payload tags: probe codec and LC profile.
    for sequence in sorted(STREAM_COPY):
        add(
            f"{sequence:02d} stream-copy source codec mutation",
            lambda root, sequence=sequence: mutate_stream_source_probe(root, sequence, codec="mp3"),
        )
        add(
            f"{sequence:02d} stream-copy source profile mutation",
            lambda root, sequence=sequence: mutate_stream_source_probe(root, sequence, profile="unknown"),
        )
        add(
            f"{sequence:02d} stream-copy non-applicable encoder mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["derivation"].__setitem__("encoder", {"unexpected": True}),
            ),
        )

    # Each transcode profile independently locks derivation, binary provenance,
    # every required encoder pair, and every forbidden processing shortcut.
    for sequence in sorted(TRANSCODE):
        add(
            f"{sequence:02d} missing derivation provenance",
            lambda root, sequence=sequence: mutate_receipt_entry(root, sequence, lambda receipt: receipt.pop("derivation")),
        )
        add(
            f"{sequence:02d} encoder binary provenance mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["derivation"]["encoder"].__setitem__("binary_sha256", "unverified"),
            ),
        )
        add(
            f"{sequence:02d} derivation output payload binding mutation",
            lambda root, sequence=sequence: mutate_receipt_entry(
                root,
                sequence,
                lambda receipt: receipt["derivation"].__setitem__("output_audio_payload_sha256", "0" * 64),
            ),
        )
        for flag, value in TRANSCODE_FLAG_PAIRS:
            add(
                f"{sequence:02d} encoder pair {flag} {value} mutation",
                lambda root, sequence=sequence, flag=flag, value=value: corrupt_encoder_pair(root, sequence, flag, value),
            )
            add(
                f"{sequence:02d} duplicate encoder pair {flag} {value}",
                lambda root, sequence=sequence, flag=flag, value=value: mutate_encoder_duplicate_pair(root, sequence, flag, value),
            )
        add(
            f"{sequence:02d} encoder input argv order mutation",
            lambda root, sequence=sequence: mutate_encoder_input_order(root, sequence),
        )
        add(
            f"{sequence:02d} encoder map argv order mutation",
            lambda root, sequence=sequence: mutate_encoder_map_order(root, sequence),
        )
        add(
            f"{sequence:02d} encoder map argv value mutation",
            lambda root, sequence=sequence: mutate_encoder_map_value(root, sequence),
        )
        add(
            f"{sequence:02d} encoder output argv mutation",
            lambda root, sequence=sequence: mutate_encoder_output(root, sequence),
        )
        add(
            f"{sequence:02d} encoder arbitrary extra argv mutation",
            lambda root, sequence=sequence: mutate_encoder_extra_token(root, sequence),
        )
        add(
            f"{sequence:02d} encoder filter graph mutation",
            lambda root, sequence=sequence: mutate_encoder_filter_graph(root, sequence),
        )
        for forbidden in FORBIDDEN_PROCESSING_OPTIONS:
            add(
                f"{sequence:02d} forbidden encoder processing {forbidden}",
                lambda root, sequence=sequence, forbidden=forbidden: add_forbidden_encoder_flag(root, sequence, forbidden),
            )
        add(
            f"{sequence:02d} source replacement/hash rebinding",
            lambda root, sequence=sequence: mutate_source_replacement(root, sequence),
        )

    add(
        "02 forbidden single pre-concatenated MP3 derivative source",
        lambda root: entry_for(load_json(root / "upload-ready.json"), "artifacts", 2),
    )
    # The pre-concatenated attack needs the manifest write kept explicit.
    preconcat_name, preconcat_root = attacks.pop()
    preconcat_manifest = load_json(preconcat_root / "upload-ready.json")
    preconcat_artifact = entry_for(preconcat_manifest, "artifacts", 2)
    preconcat_path = preconcat_root / "media" / "02-approved-source.mp3"
    preconcat_artifact["source_audio"] = {
        "path": "media/02-approved-source.mp3",
        "sha256": sha256(preconcat_path),
    }
    write_json(preconcat_root / "upload-ready.json", preconcat_manifest)
    attacks.append((preconcat_name, preconcat_root))

    def swap_playlist_order(root: Path) -> None:
        manifest = load_json(root / "upload-ready.json")
        sources = entry_for(manifest, "artifacts", 2)["source_audio"]
        sources[0], sources[1] = sources[1], sources[0]
        write_json(root / "upload-ready.json", manifest)

    add("02 approved track order mutation", swap_playlist_order)

    add(
        "02 decoded total sample proof mutation",
        lambda root: mutate_receipt_entry(root, 2, lambda receipt: receipt["derivation"].__setitem__("decoded_total_samples", PLAYLIST_DECODED_SAMPLES + 1)),
    )
    add(
        "02 removed internal gap sample proof mutation",
        lambda root: mutate_receipt_entry(root, 2, lambda receipt: receipt["qc"].__setitem__("removed_internal_gap_samples", PLAYLIST_REMOVED_GAP_SAMPLES - 1)),
    )
    add("02 ordered PCM composite claim echo/rebinding mutation", mutate_pcm_composite_claim_rebinding)
    for track in range(1, 13):
        add(
            f"02 track {track:02d} PCM evidence full echo/rebinding mutation",
            lambda root, track=track: mutate_playlist_pcm_with_full_rebinding(root, track),
        )
    for track in range(1, 13):
        add(
            f"02 track {track:02d} actual priming trim mutation",
            lambda root, track=track: mutate_playlist_actual_track(root, track, skip_samples=0),
        )
        add(
            f"02 track {track:02d} actual padding trim mutation",
            lambda root, track=track: mutate_playlist_actual_track(root, track, discard_padding=0),
        )
        add(
            f"02 track {track:02d} actual decoded PCM provenance mutation",
            lambda root, track=track: mutate_playlist_actual_track(root, track, decoded_pcm=(f"{track:x}" * 64)[:64]),
        )
        add(
            f"02 track {track:02d} boundary start QC mutation",
            lambda root, track=track: mutate_receipt_entry(
                root,
                2,
                lambda receipt: receipt["qc"]["track_boundaries"][track - 1].__setitem__("start", "FAIL"),
            ),
        )
        add(
            f"02 track {track:02d} boundary tail QC mutation",
            lambda root, track=track: mutate_receipt_entry(
                root,
                2,
                lambda receipt: receipt["qc"]["track_boundaries"][track - 1].__setitem__("tail", "FAIL"),
            ),
        )

    random.SystemRandom().shuffle(attacks)
    return attacks


def evaluate_candidate(skill_dir: Path) -> list[str]:
    failures = static_candidate_failures(skill_dir)
    with tempfile.TemporaryDirectory(prefix="hymn-aac-eval-candidate-") as temporary:
        temporary_root = Path(temporary)
        baseline = temporary_root / secrets.token_hex(16)
        shutil.copytree(FIXTURE, baseline)
        ok, evidence = invoke_candidate(skill_dir, baseline, True)
        if not ok:
            failures.append("verify-upload-ready baseline failed\n" + evidence)
        else:
            for name, attack in build_attacks(temporary_root):
                rejected, attack_evidence = invoke_candidate(skill_dir, attack, False)
                if not rejected:
                    failures.append(f"candidate accepted {name}\n{attack_evidence}")
    return failures


def candidate_test(skill_dir: Path) -> None:
    failures = evaluate_candidate(skill_dir)
    if failures:
        for item in failures:
            print(f"FAIL {item}", file=sys.stderr)
        print(f"SUMMARY 0/1 candidate contract; failures={len(failures)}", file=sys.stderr)
        raise SystemExit(1)
    print("PASS candidate locks 01-06 to MP4 + AAC-LC")
    print("PASS candidate rejects every independent actual-probe, lineage, encoder, authority, and QC mutation")
    print("SUMMARY 1/1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--candidate", type=Path, help="candidate hymn-letter-video-production skill directory")
    args = parser.parse_args()
    if args.self_test == bool(args.candidate):
        parser.error("choose exactly one of --self-test or --candidate")
    if args.self_test:
        self_test()
    else:
        candidate_test(args.candidate.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
