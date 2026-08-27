#!/usr/bin/env python3
"""Regression tests for hymn_video_flow_v3.py."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().with_name("hymn_video_flow_v3.py")
INVENTORY_PATH = SCRIPT.parent.parent / "references" / "episode-inventory.v2.json"
INVENTORY_PAYLOAD = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
PRODUCTION_RELEASE_ID = INVENTORY_PAYLOAD["release_id"]
INVENTORY = INVENTORY_PAYLOAD["episodes"]
INVENTORY_BY_ID = {episode["episode_id"]: episode for episode in INVENTORY}
CANDIDATE_CATALOG_PATH = SCRIPT.parent.parent / "references" / "hymn-letter-track-catalog.v1.json"
CANDIDATE_CATALOG_SHA256 = "676407cca40e2fdbac024400dfbdf8c83867e6e33388dee9507c7c5a5bc7ff72"
CANDIDATE_CATALOG = json.loads(CANDIDATE_CATALOG_PATH.read_text(encoding="utf-8"))
CANDIDATE_TRACKS = {track["sequence"]: track for track in CANDIDATE_CATALOG["tracks"]}
APPROVED_SOURCE_ROOT = (
    SCRIPT.parents[4] / "godowon-office" / "godo-hymns" / "work" / "hymn-letter-v3-source"
)
JOB_FILENAMES = {
    1: "01_start.json",
    2: "02_playlist.json",
    3: "03_491_testimony.json",
    4: "04_491_hymn.json",
    5: "05_370_testimony.json",
    6: "06_370_hymn.json",
}
PROFILE_INPUTS = {
    "start-hybrid/v1": {
        "program_video": "video/mp4",
        "audio": "audio/mp4",
        "captions": "text/plain",
        "backplate": "image/jpeg",
        "font": "font/ttf",
        "thumbnail": "image/jpeg",
    },
    "playlist/v1": {
        "font": "font/ttf",
        "thumbnail": "image/jpeg",
        "active_rows": "image/png",
    },
    "testimony-static/v1": {
        "backplate": "image/jpeg",
        "audio": "video/mp4",
        "captions": "text/plain",
        "font": "font/ttf",
        "thumbnail": "image/jpeg",
    },
    "hymn-lyrics/v1": {
        "backplate": "image/jpeg",
        "audio": "audio/mpeg",
        "captions": "text/plain",
        "font": "font/ttf",
        "thumbnail": "image/jpeg",
    },
}
PRODUCTION_PCM_SHA256 = (
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
)
PRODUCTION_DISCARD_PADDING = (47, 713, 191, 119, 497, 155, 1091, 407, 551, 677, 677, 47)
PRODUCTION_ORDERED_PCM_SHA256 = "ba04e40ef9be81d73e7ada45d1213d8a6f2239b67ca794a384abb0a023964e57"
PRODUCTION_PLAYLIST_TRACKS = (
    (491, "저 높은 곳을 향하여", 17275392, 0, 0),
    (370, "주 안에 있는 나에게", 9718758, 17275392, 11752),
    (387, "멀리멀리 갔더니", 9024624, 26994150, 18364),
    (438, "내 영혼이 은총 입어", 8745912, 36018774, 24503),
    (458, "너희 마음에 슬픔이 가득 차도", 8148798, 44764686, 30453),
    (490, "주여 지난 밤 내 꿈에", 9336852, 52913484, 35996),
    (439, "십자가로 가까이", 10984428, 62250336, 42348),
    (540, "주의 음성을 내가 들으니", 9296280, 73234764, 49820),
    (394, "이 세상의 친구들", 7821576, 82531044, 56144),
    (382, "너 근심 걱정 말아라", 10143882, 90352620, 61465),
    (386, "만세반석 열린 곳에", 10369674, 100496502, 68365),
    (606, "날빛보다 더 밝은 천국", 10063872, 110866176, 75420),
)
PRODUCTION_PCM_CONCAT_SHA256 = "b88ceebf62e7dbdcfdd0c692a510d399b911f4be47e99e3d7b93c1a79634c5fe"
PRODUCTION_COMBINED_SRT_SHA256 = "85ac5c9af34472639ab66c0a403895a1a5de25cd7479a7e31a5d9d89bb4d0d02"
PRODUCTION_CHAPTERS_SHA256 = "cdf0986a950517085094975a33fb906962f52692002e12acb53262857a5a973e"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class PortableCliTestCase(unittest.TestCase):
    def run_cli(self, *arguments: object) -> subprocess.CompletedProcess[str]:
        rendered_arguments = [str(argument) for argument in arguments]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [sys.executable, str(SCRIPT), *rendered_arguments]
        if "--release" in rendered_arguments:
            release_index = rendered_arguments.index("--release") + 1
            if release_index < len(rendered_arguments):
                release_path = Path(rendered_arguments[release_index])
                if release_path.is_file():
                    # Production exposes no trust override. Fixture releases are admitted only by
                    # importing the module inside this test subprocess and replacing the compiled
                    # digest before calling main().
                    bootstrap = (
                        "import sys;"
                        f"sys.path.insert(0,{str(SCRIPT.parent)!r});"
                        "import hymn_video_flow_v3 as flow;"
                        f"flow.PROJECT_RELEASE_SHA256={sha256(release_path)!r};"
                        "raise SystemExit(flow.main(sys.argv[1:]))"
                    )
                    command = [sys.executable, "-c", bootstrap, *rendered_arguments]
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

    def assert_success_json(self, result: subprocess.CompletedProcess[str]) -> dict:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        payload = json.loads(result.stdout)
        self.assertIs(type(payload), dict)
        self.assertEqual(payload["status"], "ok")
        return payload

    def assert_failure(self, result: subprocess.CompletedProcess[str], code: int) -> None:
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(f"ERROR[{code}]", result.stderr)


class V3FixtureMixin:
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-flow-v3-")
        self.root = Path(self.temporary.name)
        self.release_root = self.root / "release"
        (self.release_root / "jobs").mkdir(parents=True)
        self.office_root = self.root / "godowon-office"
        (self.office_root / "godo-hymns" / "tools").mkdir(parents=True)
        self.runtime_python = Path(sys.executable).resolve()
        version_probe = subprocess.run(
            [str(self.runtime_python), "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
        self.runtime_python_version = (version_probe.stdout or version_probe.stderr).strip()
        self.path_ffmpeg = Path(shutil.which("ffmpeg") or "").resolve()
        if not self.path_ffmpeg.is_file():
            self.fail("test fixture requires ffmpeg on PATH")
        self.successor_ffprobe = self.root / "ffprobe"
        fixture_ffprobe = (
            SCRIPT.parents[3]
            / "evals"
            / "hymn-letter-video-production"
            / "case-02-upload-ready-aac-lc-provenance"
            / "fixture"
            / "ffprobe-stub.py"
        )
        shutil.copyfile(fixture_ffprobe, self.successor_ffprobe)
        self.successor_ffprobe.chmod(0o755)
        self._write_stub(
            self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_profiles_aac.py",
            "render",
        )
        self._write_stub(
            self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_qc_aac.py",
            "qc",
        )
        for name in (
            "hymn_letter_v3_aac_common.py",
            "hymn_letter_caption_v3.py",
            "hymn_letter_v3_mp4_aac.py",
            "hymn_letter_v3_package_aac.py",
            "hymn_letter_v3_playlist_active_rows.py",
            "hymn_letter_avfoundation_probe.m",
        ):
            path = self.office_root / "godo-hymns" / "tools" / name
            path.write_text(f"{name}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_stub(self, path: Path, stage: str) -> None:
        status = "PASS" if stage == "qc" else "ok"
        path.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            f"print(json.dumps({{'delegate':'{stage}','status':'{status}','argv':sys.argv[1:],"
            "'locale_environment':{key:os.environ.get(key) for key in ('LANG','LC_ALL','LC_CTYPE')}}))\n",
            encoding="utf-8",
        )
        path.chmod(0o755)

    def _bytes_for(self, episode_id: str, key: str, index: int | None = None) -> bytes:
        suffix = "" if index is None else f"-{index:02d}"
        if key in {"captions", "chapters"}:
            return (
                f"1\n00:00:00,000 --> 00:00:01,000\n{episode_id}-{key}{suffix}\n"
            ).encode("utf-8")
        return f"{episode_id}:{key}{suffix}".encode("utf-8")

    def _settings_for(self, episode: dict) -> dict:
        if episode["profile"] == "start-hybrid/v1":
            return {"intro_frames": 723, "intro_style": "interview-soft", "post_style": "dense"}
        if episode["profile"] == "playlist/v1":
            starts = [track[4] for track in PRODUCTION_PLAYLIST_TRACKS]
            return {
                "style": "dense",
                "active_row_state": "yellow",
                "active_row_frame_boundaries": [*starts, episode["frame_count"]],
                "title_card_policy": {
                    "mode": "playlist-title-only-prior-outro/v1",
                    "expected_titles": [track[1] for track in PRODUCTION_PLAYLIST_TRACKS],
                    "expected_active_rows": [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                },
                "movie_timescale": 44100,
                "video_track_timescale": 15360,
            }
        if episode["profile"] == "testimony-static/v1":
            return {
                "style": "center",
                "restore_audio_edit": True,
                "movie_timescale": 384000,
                "video_track_timescale": 15360,
            }
        return {"style": "center", "movie_timescale": 44100, "video_track_timescale": 15360}

    def make_fixture(
        self,
        episode_id: str,
        *,
        source_root: Path | None = None,
    ) -> dict[str, Path]:
        episode = copy.deepcopy(INVENTORY_BY_ID[episode_id])
        if source_root is None:
            source_root = self.root / "source-root"
        source_root.mkdir(parents=True, exist_ok=True)

        object_entries: dict[str, dict] = {}
        inputs: dict[str, object] = {}
        spec = PROFILE_INPUTS[episode["profile"]]
        for key, media_type in spec.items():
            if key == "active_rows":
                ids: list[str] = []
                for index in range(12):
                    payload = self._bytes_for(episode_id, key, index)
                    digest = hashlib.sha256(payload).hexdigest()
                    object_path = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
                    object_path.parent.mkdir(parents=True, exist_ok=True)
                    object_path.write_bytes(payload)
                    object_entries[f"sha256:{digest}"] = {
                        "sha256": digest,
                        "size": len(payload),
                        "filenames": [f"{key}_{index+1:02d}.png"],
                        "roles": [f"{episode['sequence']:02d}_{key}_{index+1:02d}"],
                    }
                    ids.append(f"sha256:{digest}")
                inputs[key] = ids
            else:
                payload = self._bytes_for(episode_id, key)
                digest = hashlib.sha256(payload).hexdigest()
                object_path = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
                object_path.parent.mkdir(parents=True, exist_ok=True)
                object_path.write_bytes(payload)
                object_entries[f"sha256:{digest}"] = {
                    "sha256": digest,
                    "size": len(payload),
                    "filenames": [f"{key}.bin"],
                    "roles": [f"{episode['sequence']:02d}_{key}"],
                }
                inputs[key] = f"sha256:{digest}"

        audio_policies = {
            "start-hybrid/v1": "stream-copy-approved-aac/v1",
            "playlist/v1": "gapless-track-concat-aac-lc-256k/v1",
            "testimony-static/v1": "stream-copy-approved-aac/v1",
            "hymn-lyrics/v1": "approved-mp3-to-aac-lc-256k/v1",
        }
        inputs["audio_policy"] = audio_policies[episode["profile"]]
        if episode["profile"] == "playlist/v1":
            tracks = []
            for index in range(12):
                audio_payload = self._bytes_for(episode_id, "track-audio", index)
                caption_payload = self._bytes_for(episode_id, "captions", index)
                hymn_number, title, samples, start_sample, start_frame = PRODUCTION_PLAYLIST_TRACKS[index]
                track = {"index": index + 1, "hymn_number": hymn_number, "title": title}
                for key, payload, suffix, role in (
                    ("audio", audio_payload, "mp3", "track_audio"),
                    ("captions", caption_payload, "srt", "track_captions"),
                ):
                    digest = hashlib.sha256(payload).hexdigest()
                    object_path = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
                    object_path.parent.mkdir(parents=True, exist_ok=True)
                    object_path.write_bytes(payload)
                    object_entries[f"sha256:{digest}"] = {
                        "sha256": digest,
                        "size": len(payload),
                        "filenames": [f"track-{index + 1:02d}.{suffix}"],
                        "roles": [f"02_{role}_{index + 1:02d}"],
                    }
                    track[key] = f"sha256:{digest}"
                track.update(
                    {
                        "samples": samples,
                        "pcm_f32le_sha256": PRODUCTION_PCM_SHA256[index],
                        "start_sample": start_sample,
                        "start_frame": start_frame,
                    }
                )
                tracks.append(track)
            inputs.update(
                {
                    "tracks": tracks,
                    "gapless_audio_contract": {
                        "mode": "decode-each-mp3-to-f32le-concat/v1",
                        "sample_rate": 44100,
                        "channels": 2,
                        "total_samples": 120930048,
                        "composite_pcm_f32le_sha256": PRODUCTION_PCM_CONCAT_SHA256,
                    },
                    "caption_timing_contract": {
                        "mode": "per-track-srt-offset-by-start-sample/v1",
                        "sample_rate": 44100,
                        "combined_srt_sha256": PRODUCTION_COMBINED_SRT_SHA256,
                        "cue_count": 279,
                        "lyric_cue_count": 267,
                        "title_card_cue_count": 12,
                        "title_card_text_policy": "sequence-numbered-title-only/v1",
                        "offset_rounding": "half-up-samples-to-ms/v1",
                        "title_card_serialization": "{sequence}. {title}",
                        "title_card_placement": "initial-title-then-next-title-in-prior-track-outro/v1",
                    },
                    "chapter_contract": {
                        "mode": "track-start-sample/v1",
                        "sample_rate": 44100,
                        "ffmetadata_sha256": PRODUCTION_CHAPTERS_SHA256,
                    },
                }
            )

        source_bundle = {
            "schema": "godowon.hymn-letter.source-bundle/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "storage_layout": "objects/sha256/<prefix>/<digest-rest>",
            "objects": object_entries,
        }
        source_bundle_path = self.release_root / "source-bundle.lock.json"
        write_json(source_bundle_path, source_bundle)
        source_bundle_sha = sha256(source_bundle_path)

        environment_lock = self.release_root / "environment.lock.json"
        golden_lock = self.release_root / "golden.lock.json"
        environment_payload = {
                "schema": "godowon.hymn-letter.environment-lock/1",
                "platform": "macOS-test-arm64",
                "system": "Darwin",
                "release": "test",
                "machine": "arm64",
                "python_binary_name": self.runtime_python.name,
                "python_version": self.runtime_python_version.removeprefix("Python "),
                "python_sha256": sha256(self.runtime_python),
                "python_implementation": "CPython",
                "python_compiler": "Clang test",
                "python_filesystem_encoding": "utf-8",
                "runtime_locale": "C",
                "locale_environment": {"LANG": "C", "LC_ALL": "C", "LC_CTYPE": "C"},
                "ffmpeg_binary_name": "ffmpeg",
                "ffmpeg_sha256": sha256(self.path_ffmpeg),
                "ffmpeg_version_line": "ffmpeg version test",
                "ffmpeg_build": "configuration: test",
                "ffprobe_binary_name": "ffprobe",
                "ffprobe_sha256": sha256(self.successor_ffprobe),
                "ffprobe_version_line": "ffprobe version test",
                "libx264_core": "x264 core test",
                "libx264_threads": 18,
                "libx264_lookahead_threads": 3,
                "python_packages": {"Pillow": "test", "numpy": "test"},
                "pillow_native_libraries": {
                    "freetype2": "test",
                    "libjpeg": "test",
                    "libjpeg_turbo": "test",
                    "zlib": "test",
                    "zlib_ng": "test",
                },
            }
        write_json(
            environment_lock,
            environment_payload,
        )
        mp4_probe_module = (
            self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_mp4_aac.py"
        )
        mp4_probe_module.write_text(
            "def environment_fingerprint():\n"
            f"    return {environment_payload!r}\n",
            encoding="utf-8",
        )
        golden_episodes = {}
        for inventory_episode in INVENTORY:
            golden_episode = {
                "output_sha256": hashlib.sha256(
                    f"golden:{inventory_episode['episode_id']}".encode("utf-8")
                ).hexdigest(),
                "filename": (
                    f"{inventory_episode['sequence']:02d}_{inventory_episode['episode_id']}."
                    f"{inventory_episode['container']}"
                ),
                "frame_count": inventory_episode["frame_count"],
                "container": inventory_episode["container"],
                "audio_codec": inventory_episode["audio_codec"],
                "audio_profile": inventory_episode["audio_profile"],
                "profile": inventory_episode["profile"],
            }
            if inventory_episode["episode_id"] == "02-playlist":
                golden_episode.update(
                    {
                        "composite_pcm_f32le_sha256": PRODUCTION_PCM_CONCAT_SHA256,
                        "combined_srt_sha256": PRODUCTION_COMBINED_SRT_SHA256,
                        "chapters_sha256": PRODUCTION_CHAPTERS_SHA256,
                    }
                )
            golden_episodes[inventory_episode["episode_id"]] = golden_episode
        write_json(
            golden_lock,
            {
                "schema": "godowon.hymn-letter.v3-golden-lock/1",
                "release_id": PRODUCTION_RELEASE_ID,
                "episodes": golden_episodes,
            },
        )

        settings = self._settings_for(episode)
        job = {
            "schema": "godowon.hymn-letter.v3-job/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "episode_id": episode["episode_id"],
            "profile": episode["profile"],
            "inputs": inputs,
            "settings": settings,
            "output": {
                "filename": f"{episode['sequence']:02d}_{episode['episode_id']}.{episode['container']}",
                "thumbnail_filename": f"{episode['sequence']:02d}_thumb.jpg",
                "container": episode["container"],
                "audio_codec": "aac",
                "audio_profile": "LC",
                "frame_count": episode["frame_count"],
            },
        }
        job_path = self.release_root / "jobs" / JOB_FILENAMES[episode["sequence"]]
        write_json(job_path, job)
        job_sha = sha256(job_path)

        renderer_modules = {}
        module_names = {
            "aac_common": "hymn_letter_v3_aac_common.py",
            "caption": "hymn_letter_caption_v3.py",
            "profiles": "hymn_letter_v3_profiles_aac.py",
            "mp4": "hymn_letter_v3_mp4_aac.py",
            "package": "hymn_letter_v3_package_aac.py",
            "qc": "hymn_letter_v3_qc_aac.py",
            "playlist_active_rows": "hymn_letter_v3_playlist_active_rows.py",
            "avfoundation_probe_source": "hymn_letter_avfoundation_probe.m",
        }
        for key, filename in module_names.items():
            module_path = self.office_root / "godo-hymns" / "tools" / filename
            renderer_modules[key] = {
                "path": f"godo-hymns/tools/{filename}",
                "sha256": sha256(module_path),
            }

        release = {
            "schema": "godowon.hymn-letter.v3-release-lock/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "created_at": "2026-08-22",
            "source_bundle_lock": "source-bundle.lock.json",
            "environment_lock": "environment.lock.json",
            "golden_lock": "golden.lock.json",
            "jobs": [{"path": f"jobs/{job_path.name}", "sha256": job_sha}],
            "renderer_modules": renderer_modules,
            "supported_profiles": [episode["profile"]],
            "notes": ["fixture"],
            "source_bundle_lock_sha256": source_bundle_sha,
            "environment_lock_sha256": sha256(environment_lock),
            "golden_lock_sha256": sha256(golden_lock),
        }
        release_path = self.release_root / "release.lock.json"
        write_json(release_path, release)
        return {
            "job": job_path,
            "release": release_path,
            "run_root": self.root / f"run-{episode_id}",
            "source_root": source_root,
            "source_bundle": source_bundle_path,
        }


class ValidateJobV3Tests(V3FixtureMixin, PortableCliTestCase):
    def test_production_cli_rejects_same_id_release_without_compiled_trust_pin(self) -> None:
        fixture = self.make_fixture("01-start")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "validate-job",
                "--job",
                str(fixture["job"]),
                "--release",
                str(fixture["release"]),
            ],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assert_failure(result, 4)
        self.assertIn("compiled production trust pin", result.stderr)

    def test_accepts_all_six_episode_contracts(self) -> None:
        for episode in INVENTORY:
            with self.subTest(episode_id=episode["episode_id"]):
                fixture = self.make_fixture(episode["episode_id"])
                payload = self.assert_success_json(
                    self.run_cli(
                        "validate-job",
                        "--job",
                        fixture["job"],
                        "--release",
                        fixture["release"],
                    )
                )
                self.assertEqual(payload["episode_id"], episode["episode_id"])
                self.assertEqual(payload["output_container"], episode["container"])
                self.assertEqual(payload["output_audio_codec"], episode["audio_codec"])

    def test_rejects_playlist_title_card_regression(self) -> None:
        fixture = self.make_fixture("02-playlist")
        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        job["settings"]["title_card_policy"]["expected_titles"][0] = "491장 저 높은 곳을 향하여"
        write_json(fixture["job"], job)
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["jobs"][0]["sha256"] = sha256(fixture["job"])
        write_json(fixture["release"], release)
        self.assert_failure(
            self.run_cli(
                "validate-job",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
            ),
            2,
        )

    def test_rejects_episode_01_legacy_outline_style(self) -> None:
        fixture = self.make_fixture("01-start")
        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        job["settings"]["intro_style"] = "center"
        write_json(fixture["job"], job)
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["jobs"][0]["sha256"] = sha256(fixture["job"])
        write_json(fixture["release"], release)
        self.assert_failure(
            self.run_cli(
                "validate-job",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
            ),
            2,
        )

    def test_production_testimony_still_requires_locked_movie_timescale(self) -> None:
        for episode_id in ("03-491-testimony", "05-370-testimony"):
            with self.subTest(episode_id=episode_id):
                fixture = self.make_fixture(episode_id)
                job = json.loads(fixture["job"].read_text(encoding="utf-8"))
                job["settings"]["movie_timescale"] = 1000
                write_json(fixture["job"], job)
                release = json.loads(fixture["release"].read_text(encoding="utf-8"))
                release["jobs"][0]["sha256"] = sha256(fixture["job"])
                write_json(fixture["release"], release)
                self.assert_failure(
                    self.run_cli(
                        "validate-job",
                        "--job",
                        fixture["job"],
                        "--release",
                        fixture["release"],
                    ),
                    2,
                )


class SchemaLockShapeV3Tests(unittest.TestCase):
    def test_release_jobs_and_playlist_vector_use_closed_prefix_items(self) -> None:
        references = SCRIPT.parent.parent / "references"
        release_schema = json.loads(
            (references / "release-lock.schema.json").read_text(encoding="utf-8")
        )
        jobs = release_schema["properties"]["jobs"]
        self.assertIs(jobs["items"], False)
        self.assertEqual(len(jobs["prefixItems"]), 6)
        self.assertEqual(
            [item["properties"]["path"]["const"] for item in jobs["prefixItems"]],
            [f"jobs/{JOB_FILENAMES[index]}" for index in range(1, 7)],
        )
        for item in jobs["prefixItems"]:
            self.assertEqual(item["type"], "object")
            self.assertIs(item["additionalProperties"], False)
            self.assertEqual(item["required"], ["path", "sha256"])
            self.assertEqual(item["properties"]["sha256"]["pattern"], "^[0-9a-f]{64}$")

        job_schema = json.loads(
            (references / "job-manifest.v2.schema.json").read_text(encoding="utf-8")
        )
        variants = job_schema["allOf"][0]["oneOf"]
        self.assertEqual(len(variants), 6)
        self.assertEqual(
            [variant["properties"]["episode_id"]["const"] for variant in variants],
            [episode["episode_id"] for episode in INVENTORY],
        )
        start_branch = next(
            branch
            for branch in job_schema["allOf"]
            if branch.get("if", {}).get("properties", {}).get("profile", {}).get("const")
            == "start-hybrid/v1"
        )
        self.assertEqual(
            start_branch["then"]["properties"]["settings"]["properties"]["intro_style"]["const"],
            "interview-soft",
        )
        playlist_branch = next(
            branch
            for branch in job_schema["allOf"]
            if branch.get("if", {}).get("properties", {}).get("profile", {}).get("const")
            == "playlist/v1"
        )
        tracks = playlist_branch["then"]["properties"]["inputs"]["properties"]["tracks"]
        self.assertIs(tracks["items"], False)
        self.assertEqual(len(tracks["prefixItems"]), 12)
        for index, item in enumerate(tracks["prefixItems"]):
            generic, exact = item["allOf"]
            hymn_number, title, samples, start_sample, start_frame = PRODUCTION_PLAYLIST_TRACKS[index]
            properties = exact["properties"]
            self.assertEqual(generic["$ref"], "#/$defs/playlist_track")
            self.assertEqual(properties["index"]["const"], index + 1)
            self.assertEqual(properties["hymn_number"]["const"], hymn_number)
            self.assertEqual(properties["title"]["const"], title)
            self.assertEqual(properties["samples"]["const"], samples)
            self.assertEqual(properties["pcm_f32le_sha256"]["const"], PRODUCTION_PCM_SHA256[index])
            self.assertEqual(properties["start_sample"]["const"], start_sample)
            self.assertEqual(properties["start_frame"]["const"], start_frame)
            self.assertNotIn("audio", properties)
            self.assertNotIn("captions", properties)

    def test_candidate_schemas_bind_dynamic_testimony_movie_timescale(self) -> None:
        references = SCRIPT.parent.parent / "references"
        candidate_job = json.loads(
            (references / "candidate-job.schema.json").read_text(encoding="utf-8")
        )
        testimony_job = next(
            branch
            for branch in candidate_job["allOf"]
            if branch["if"]["properties"]["profile"]["const"] == "testimony-external-srt/v1"
        )
        testimony_settings = testimony_job["then"]["properties"]["settings"]["properties"]
        self.assertEqual(testimony_settings["movie_timescale"], {"type": "integer", "minimum": 1})
        self.assertIs(testimony_settings["restore_audio_edit"]["const"], True)
        hymn_job = next(
            branch
            for branch in candidate_job["allOf"]
            if branch["if"]["properties"]["profile"]["const"] == "hymn-listening-external-srt/v1"
        )
        self.assertEqual(
            hymn_job["then"]["properties"]["settings"]["properties"]["movie_timescale"]["const"],
            44100,
        )

        candidate_intake = json.loads(
            (references / "candidate-intake.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sha256(CANDIDATE_CATALOG_PATH), CANDIDATE_CATALOG_SHA256)
        self.assertEqual(
            candidate_intake["properties"]["catalog"]["properties"]["sha256"]["const"],
            CANDIDATE_CATALOG_SHA256,
        )
        self.assertEqual(
            [track["sequence"] for track in CANDIDATE_CATALOG["tracks"]],
            list(range(8, 27, 2)),
        )
        audio_probe = candidate_intake["properties"]["probe"]["properties"]["audio"]
        self.assertIn("movie_timescale", audio_probe["required"])
        self.assertIn("render_frame_count", audio_probe["required"])
        self.assertEqual(
            audio_probe["properties"]["render_frame_count"],
            {"type": "integer", "minimum": 1},
        )
        testimony_intake = next(
            branch
            for branch in candidate_intake["allOf"]
            if branch["if"]["properties"]["episode"]["properties"]["profile"]["const"]
            == "testimony-external-srt/v1"
        )
        self.assertEqual(
            testimony_intake["then"]["properties"]["probe"]["properties"]["audio"]
            ["properties"]["movie_timescale"],
            {"type": "integer", "minimum": 1},
        )
        hymn_intake = next(
            branch
            for branch in candidate_intake["allOf"]
            if branch["if"]["properties"]["episode"]["properties"]["profile"]["const"]
            == "hymn-listening-external-srt/v1"
        )
        self.assertEqual(
            hymn_intake["then"]["properties"]["probe"]["properties"]["audio"]
            ["properties"]["movie_timescale"],
            {"type": "null"},
        )


class VerifySourceBundleV3Tests(V3FixtureMixin, PortableCliTestCase):
    def test_verifies_bundle_and_normalizes_tmp_alias(self) -> None:
        alias_root = Path(tempfile.mkdtemp(prefix="hymn-flow-v3-alias-", dir="/tmp"))
        self.addCleanup(lambda: shutil.rmtree(alias_root, ignore_errors=True))
        fixture = self.make_fixture("02-playlist", source_root=alias_root)
        payload = self.assert_success_json(
            self.run_cli(
                "verify-source-bundle",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                alias_root,
            )
        )
        self.assertEqual(payload["episode_id"], "02-playlist")
        self.assertEqual(Path(payload["source_root"]), alias_root.resolve())
        self.assertEqual(payload["referenced_object_count"], 38)

    def test_rejects_mutated_missing_and_release_mismatch(self) -> None:
        fixture = self.make_fixture("04-491-hymn")
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["jobs"][0]["sha256"] = "0" * 64
        write_json(fixture["release"], release)
        self.assert_failure(
            self.run_cli(
                "verify-source-bundle",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
            ),
            4,
        )

        fixture = self.make_fixture("06-370-hymn")
        source_bundle = json.loads(fixture["source_bundle"].read_text(encoding="utf-8"))
        object_id = next(iter(source_bundle["objects"]))
        digest = object_id.split(":", 1)[1]
        object_path = fixture["source_root"] / "objects" / "sha256" / digest[:2] / digest[2:]
        object_path.write_bytes(b"mutated")
        self.assert_failure(
            self.run_cli(
                "verify-source-bundle",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
            ),
            4,
        )

        fixture = self.make_fixture("01-start")
        source_bundle = json.loads(fixture["source_bundle"].read_text(encoding="utf-8"))
        object_id = next(iter(source_bundle["objects"]))
        digest = object_id.split(":", 1)[1]
        object_path = fixture["source_root"] / "objects" / "sha256" / digest[:2] / digest[2:]
        object_path.unlink()
        self.assert_failure(
            self.run_cli(
                "verify-source-bundle",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
            ),
            3,
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_symlink_escape(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        source_bundle = json.loads(fixture["source_bundle"].read_text(encoding="utf-8"))
        object_id = next(iter(source_bundle["objects"]))
        digest = object_id.split(":", 1)[1]
        object_path = fixture["source_root"] / "objects" / "sha256" / digest[:2] / digest[2:]
        outside = self.root / "outside.bin"
        outside.write_bytes(b"outside")
        object_path.unlink()
        object_path.symlink_to(outside)
        self.assert_failure(
            self.run_cli(
                "verify-source-bundle",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
            ),
            7,
        )


class UploadReadyV3Tests(PortableCliTestCase):
    @property
    def frozen_fixture(self) -> Path:
        return (
            SCRIPT.parents[3]
            / "evals"
            / "hymn-letter-video-production"
            / "case-02-upload-ready-aac-lc-provenance"
            / "fixture"
        )

    def test_verifies_frozen_six_episode_upload_contract(self) -> None:
        fixture = self.frozen_fixture
        payload = self.assert_success_json(
            self.run_cli(
                "verify-upload-ready",
                "--manifest",
                fixture / "upload-ready.json",
                "--authority-lock",
                fixture / "authority-lock.json",
                "--ffprobe",
                fixture / "ffprobe-stub.py",
            )
        )
        self.assertEqual(payload["verified_sequences"], [1, 2, 3, 4, 5, 6])

    def test_rejects_drifted_upload_validator_before_reading_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hymn-validator-drift-") as temporary:
            copied_skill = Path(temporary) / "hymn-letter-video-production"
            shutil.copytree(SCRIPT.parent.parent, copied_skill)
            copied_validator = copied_skill / "scripts" / "upload_ready_validator.py"
            copied_validator.write_text(
                copied_validator.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_skill / "scripts" / "hymn_video_flow_v3.py"),
                    "verify-upload-ready",
                    "--manifest",
                    str(Path(temporary) / "missing.json"),
                    "--authority-lock",
                    str(Path(temporary) / "missing-authority.json"),
                    "--ffprobe",
                    sys.executable,
                ],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assert_failure(result, 4)

    def test_rejects_drifted_imported_legacy_helper_before_cli_dispatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hymn-legacy-drift-") as temporary:
            copied_skill = Path(temporary) / "hymn-letter-video-production"
            shutil.copytree(SCRIPT.parent.parent, copied_skill)
            copied_helper = copied_skill / "scripts" / "hymn_video_flow.py"
            copied_helper.write_text(
                copied_helper.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(copied_skill / "scripts" / "hymn_video_flow_v3.py"), "--help"],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assert_failure(result, 4)


class PackageV3Tests(V3FixtureMixin, PortableCliTestCase):
    def package_release_for_test(
        self,
        upload_root: Path,
        release_fixture: dict[str, Path],
        package_dir: Path,
    ) -> dict:
        """Exercise the production package builder without restoring removed CLI flags."""
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        previous_pin = flow.PROJECT_RELEASE_SHA256
        if release_fixture["release"].is_file():
            flow.PROJECT_RELEASE_SHA256 = sha256(release_fixture["release"])
        try:
            if not release_fixture["release"].is_file():
                return flow.package_release(
                    upload_root / "upload-ready.json",
                    upload_root / "authority-lock.json",
                    self.successor_ffprobe,
                    release_fixture["release"],
                    release_fixture["source_root"],
                    self.office_root,
                    release_fixture["approval"],
                    package_dir,
                    self.root / "missing-delegation-inputs.lock.json",
                    {},
                )
            release = json.loads(release_fixture["release"].read_text(encoding="utf-8"))
            release_sha256 = sha256(release_fixture["release"])
            upload_manifest = json.loads(
                (upload_root / "upload-ready.json").read_text(encoding="utf-8")
            )
            upload_by_sequence = {
                artifact["sequence"]: artifact for artifact in upload_manifest["artifacts"]
            }
            staged_receipts = upload_root / "00_재현자료" / "receipts"
            staged_receipts.mkdir(parents=True, exist_ok=True)
            snapshot_hashes: dict[int, dict[str, str]] = {}
            lock_episodes = []
            for sequence in range(1, 7):
                job_path = release_fixture["release"].parent / "jobs" / JOB_FILENAMES[sequence]
                job = json.loads(job_path.read_text(encoding="utf-8"))
                thumbnail_sha256 = job["inputs"]["thumbnail"].split(":", 1)[1]
                render_receipt = staged_receipts / f"{sequence:02d}-render_receipt.json"
                qc_receipt = staged_receipts / f"{sequence:02d}-qc_receipt.json"
                write_json(
                    render_receipt,
                    {
                        "schema": "godowon.hymn-letter.v3-render-receipt/1",
                        "job_sha256": sha256(job_path),
                        "release_sha256": release_sha256,
                        "output": {
                            "sha256": upload_by_sequence[sequence]["final_media"]["sha256"],
                            "frame_count": job["output"]["frame_count"],
                        },
                        "thumbnail": {"sha256": thumbnail_sha256},
                    },
                )
                write_json(
                    qc_receipt,
                    {
                        "schema": "godowon.hymn-letter.v3-qc-receipt/1",
                        "job_sha256": sha256(job_path),
                        "release_sha256": release_sha256,
                        "render_receipt_sha256": sha256(render_receipt),
                        "semantic_equivalent": {"status": "PASS"},
                        "reference_bit_exact": {"status": "PASS"},
                    },
                )
                snapshot_hashes[sequence] = {
                    "render": sha256(render_receipt),
                    "qc": sha256(qc_receipt),
                }
                lock_episodes.append(
                    {
                        "sequence": sequence,
                        "episode_id": job["episode_id"],
                        "job_sha256": sha256(job_path),
                        "render_receipt_sha256": snapshot_hashes[sequence]["render"],
                        "qc_receipt_sha256": snapshot_hashes[sequence]["qc"],
                    }
                )
            delegation_lock = upload_root / "delegation-inputs.lock.json"
            delegation_lock.write_text(
                json.dumps(
                    {
                    "schema": "plugify.hymn-letter.delegation-inputs-lock/1",
                    "release_id": release["release_id"],
                    "release_sha256": release_sha256,
                    "source_bundle_sha256": release["source_bundle_lock_sha256"],
                    "package_module_sha256": release["renderer_modules"]["package"]["sha256"],
                    "human_approval_sha256": sha256(release_fixture["approval"]),
                    "episodes": lock_episodes,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            return flow.package_release(
                upload_root / "upload-ready.json",
                upload_root / "authority-lock.json",
                self.successor_ffprobe,
                release_fixture["release"],
                release_fixture["source_root"],
                self.office_root,
                release_fixture["approval"],
                package_dir,
                delegation_lock,
                snapshot_hashes,
            )
        finally:
            flow.PROJECT_RELEASE_SHA256 = previous_pin

    def assert_package_release_failure(self, code: int, callback: object) -> None:
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        with self.assertRaises(flow.FlowError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def rewrite_package_hashes(self, package: Path, manifest: dict) -> None:
        manifest_path = package / "PACKAGE-MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        rows = []
        for path in sorted(package.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS.txt":
                rows.append(f"{sha256(path)}  {path.relative_to(package).as_posix()}")
        (package / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def verify_built_package(self, package: Path) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            "verify-package", "--package-dir", package,
            "--release", self.package_trust["release"],
            "--approval-receipt", self.package_trust["approval"],
        )

    def make_full_release(self, upload_root: Path) -> dict[str, Path]:
        source_root = self.root / "source-root-full"
        all_objects: dict[str, dict] = {}
        last_fixture: dict[str, Path] | None = None
        for episode in INVENTORY:
            last_fixture = self.make_fixture(episode["episode_id"], source_root=source_root)
            source_bundle = json.loads(last_fixture["source_bundle"].read_text(encoding="utf-8"))
            all_objects.update(source_bundle["objects"])
        assert last_fixture is not None

        upload_manifest = json.loads((upload_root / "upload-ready.json").read_text(encoding="utf-8"))
        golden_path = self.release_root / "golden.lock.json"
        golden = json.loads(golden_path.read_text(encoding="utf-8"))

        def install_upload_source(path: Path) -> str:
            digest = sha256(path)
            object_id = f"sha256:{digest}"
            destination = source_root / "objects" / "sha256" / digest[:2] / digest[2:]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(path, destination)
            all_objects[object_id] = {
                "sha256": digest,
                "size": destination.stat().st_size,
                "filenames": [path.name],
                "roles": ["approved-audio"],
            }
            return object_id

        for artifact in upload_manifest["artifacts"]:
            sequence = artifact["sequence"]
            job_path = self.release_root / "jobs" / JOB_FILENAMES[sequence]
            job = json.loads(job_path.read_text(encoding="utf-8"))
            if sequence == 2:
                for index, (track, source_ref) in enumerate(
                    zip(job["inputs"]["tracks"], artifact["source_audio"])
                ):
                    track["audio"] = install_upload_source(upload_root / source_ref["path"])
                    track["pcm_f32le_sha256"] = PRODUCTION_PCM_SHA256[index]
            else:
                job["inputs"]["audio"] = install_upload_source(
                    upload_root / artifact["source_audio"]["path"]
                )
            write_json(job_path, job)
            golden["episodes"][job["episode_id"]]["output_sha256"] = artifact["final_media"]["sha256"]
            golden["episodes"][job["episode_id"]]["filename"] = job["output"]["filename"]
        write_json(golden_path, golden)

        referenced_ids: set[str] = set()

        def collect_ids(value: object) -> None:
            if type(value) is str and value.startswith("sha256:"):
                referenced_ids.add(value)
            elif type(value) is list:
                for item in value:
                    collect_ids(item)
            elif type(value) is dict:
                for item in value.values():
                    collect_ids(item)

        jobs: list[dict[str, str]] = []
        for episode in INVENTORY:
            job_path = self.release_root / "jobs" / JOB_FILENAMES[episode["sequence"]]
            collect_ids(json.loads(job_path.read_text(encoding="utf-8"))["inputs"])
            jobs.append({"path": f"jobs/{job_path.name}", "sha256": sha256(job_path)})
        source_bundle = {
            "schema": "godowon.hymn-letter.source-bundle/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "storage_layout": "objects/sha256/<prefix>/<digest-rest>",
            "objects": {object_id: all_objects[object_id] for object_id in sorted(referenced_ids)},
        }
        write_json(last_fixture["source_bundle"], source_bundle)
        release = json.loads(last_fixture["release"].read_text(encoding="utf-8"))
        release["jobs"] = jobs
        release["supported_profiles"] = [
            "start-hybrid/v1",
            "playlist/v1",
            "testimony-static/v1",
            "hymn-lyrics/v1",
        ]
        release["source_bundle_lock_sha256"] = sha256(last_fixture["source_bundle"])
        release["golden_lock_sha256"] = sha256(golden_path)
        write_json(last_fixture["release"], release)
        return {
            "release": last_fixture["release"],
            "source_root": source_root,
            "approval": upload_root / "human-approval.json",
        }

    def make_successor_upload_fixture(self, name: str) -> Path:
        frozen = (
            SCRIPT.parents[3]
            / "evals"
            / "hymn-letter-video-production"
            / "case-02-upload-ready-aac-lc-provenance"
            / "fixture"
        )
        target = self.root / name
        shutil.copytree(frozen, target)
        release_id = PRODUCTION_RELEASE_ID
        authority = json.loads((target / "authority-lock.json").read_text(encoding="utf-8"))
        receipts = json.loads((target / "receipts.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "upload-ready.json").read_text(encoding="utf-8"))
        authority["release_id"] = release_id
        receipts["release_id"] = release_id
        manifest["release_id"] = release_id
        authority_playlist = next(item for item in authority["episodes"] if item["sequence"] == 2)
        receipt_playlist = next(item for item in receipts["entries"] if item["sequence"] == 2)
        artifact_playlist = next(item for item in manifest["artifacts"] if item["sequence"] == 2)
        for index, (source_ref, locked_track, decoded, boundary) in enumerate(
            zip(
                artifact_playlist["source_audio"],
                authority_playlist["approved_source_tracks"],
                receipt_playlist["derivation"]["track_decodes"],
                receipt_playlist["qc"]["track_boundaries"],
            )
        ):
            media_path = target / source_ref["path"]
            tokens = dict(
                token.split("=", 1)
                for token in media_path.read_text(encoding="utf-8").strip().split()
            )
            tokens["skip_samples"] = "1105"
            tokens["discard_padding"] = str(PRODUCTION_DISCARD_PADDING[index])
            tokens["decoded_pcm"] = PRODUCTION_PCM_SHA256[index]
            media_path.write_text(
                " ".join(f"{key}={value}" for key, value in tokens.items()) + "\n",
                encoding="utf-8",
            )
            source_hash = sha256(media_path)
            source_ref["sha256"] = source_hash
            locked_track.update(
                {
                    "sha256": source_hash,
                    "skip_samples": 1105,
                    "discard_padding": PRODUCTION_DISCARD_PADDING[index],
                    "decoded_pcm_sha256": PRODUCTION_PCM_SHA256[index],
                }
            )
            decoded.update(
                {
                    "skip_samples": 1105,
                    "discard_padding": PRODUCTION_DISCARD_PADDING[index],
                    "decoded_pcm_sha256": PRODUCTION_PCM_SHA256[index],
                }
            )
            boundary["decoded_pcm_sha256"] = PRODUCTION_PCM_SHA256[index]
            receipt_playlist["source_track_sha256"][index] = source_hash
        authority_playlist["ordered_pcm_concat_sha256"] = PRODUCTION_ORDERED_PCM_SHA256
        receipt_playlist["derivation"]["ordered_pcm_concat_sha256"] = PRODUCTION_ORDERED_PCM_SHA256
        receipt_playlist["qc"]["ordered_pcm_concat_sha256"] = PRODUCTION_ORDERED_PCM_SHA256
        authority_playlist["captions_sha256"] = PRODUCTION_COMBINED_SRT_SHA256
        authority_playlist["chapters_sha256"] = PRODUCTION_CHAPTERS_SHA256
        receipt_playlist["qc"]["captions_sha256"] = PRODUCTION_COMBINED_SRT_SHA256
        receipt_playlist["qc"]["chapters_sha256"] = PRODUCTION_CHAPTERS_SHA256
        write_json(target / "authority-lock.json", authority)
        write_json(target / "receipts.json", receipts)
        manifest["authority_lock"]["sha256"] = sha256(target / "authority-lock.json")
        manifest["receipts"]["sha256"] = sha256(target / "receipts.json")
        write_json(target / "upload-ready.json", manifest)
        approval = {
            "schema": "godowon.hymn-letter.human-approval-receipt/1",
            "release_id": release_id,
            "episodes": [],
        }
        for artifact, locked, receipt in zip(
            manifest["artifacts"], authority["episodes"], receipts["entries"]
        ):
            approval["episodes"].append(
                {
                    "sequence": artifact["sequence"],
                    "episode_id": artifact["episode_id"],
                    "profile": artifact["profile"],
                    "reviewer": locked["approval_authority"]["reviewer"],
                    "decision": locked["approval_authority"]["decision"],
                    "reviewed_at": locked["approval_authority"]["reviewed_at"],
                    "final_file_sha256": artifact["final_media"]["sha256"],
                    "artifact_audio_payload_sha256": receipt["approval"][
                        "artifact_audio_payload_sha256"
                    ],
                }
            )
        write_json(target / "human-approval.json", approval)
        return target

    def build_test_package(self, package_dir: Path) -> dict:
        upload = self.make_successor_upload_fixture(f"upload-{package_dir.name}")
        release_fixture = self.make_full_release(upload)
        self.package_trust = release_fixture
        result = self.package_release_for_test(upload, release_fixture, package_dir)
        self.assertEqual(result["status"], "ok")
        return result

    def test_package_refuses_existing_output_before_delegate_or_copy(self) -> None:
        package = self.root / "already-exists"
        package.mkdir()
        missing = {
            "release": self.root / "missing-release.json",
            "source_root": self.root,
            "approval": self.root / "missing-approval.json",
        }
        self.assert_package_release_failure(
            7,
            lambda: self.package_release_for_test(self.root, missing, package),
        )

    def test_successor_upload_requires_external_human_approval_and_production_pcm_vector(self) -> None:
        upload = self.make_successor_upload_fixture("upload-approval-gate")
        release_fixture = self.make_full_release(upload)
        missing_approval = self.run_cli(
            "verify-upload-ready",
            "--manifest", upload / "upload-ready.json",
            "--authority-lock", upload / "authority-lock.json",
            "--ffprobe", self.successor_ffprobe,
            "--release", release_fixture["release"],
        )
        self.assert_failure(missing_approval, 2)
        self.assertIn("external --approval-receipt", missing_approval.stderr)

        frozen_relabel = self.root / "frozen-relabel"
        shutil.copytree(
            SCRIPT.parents[3] / "evals" / "hymn-letter-video-production"
            / "case-02-upload-ready-aac-lc-provenance" / "fixture",
            frozen_relabel,
        )
        for filename in ("upload-ready.json", "authority-lock.json", "receipts.json"):
            path = frozen_relabel / filename
            value = json.loads(path.read_text(encoding="utf-8"))
            value["release_id"] = PRODUCTION_RELEASE_ID
            write_json(path, value)
        manifest = json.loads((frozen_relabel / "upload-ready.json").read_text(encoding="utf-8"))
        manifest["authority_lock"]["sha256"] = sha256(frozen_relabel / "authority-lock.json")
        manifest["receipts"]["sha256"] = sha256(frozen_relabel / "receipts.json")
        write_json(frozen_relabel / "upload-ready.json", manifest)
        # Exercise the pinned validator directly here: the production wrapper
        # correctly refuses every successor graph before probe execution unless
        # its external release/approval trust anchors are present.
        wrong_vector = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util,sys;from pathlib import Path;"
                    "p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('v',p);"
                    "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                    "m.validate_upload_ready(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]))"
                ),
                str(SCRIPT.with_name("upload_ready_validator.py")),
                str(frozen_relabel / "upload-ready.json"),
                str(frozen_relabel / "authority-lock.json"),
                str(frozen_relabel / "ffprobe-stub.py"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(wrong_vector.returncode, 0)
        self.assertIn("ordered PCM composite authority mismatch", wrong_vector.stderr)

    def test_successor_upload_rejects_wrong_ffprobe_and_receipt_contract_drift(self) -> None:
        def verify(upload: Path, release_fixture: dict[str, Path], ffprobe: Path) -> subprocess.CompletedProcess[str]:
            return self.run_cli(
                "verify-upload-ready",
                "--manifest", upload / "upload-ready.json",
                "--authority-lock", upload / "authority-lock.json",
                "--ffprobe", ffprobe,
                "--release", release_fixture["release"],
                "--approval-receipt", release_fixture["approval"],
            )

        upload = self.make_successor_upload_fixture("upload-wrong-ffprobe")
        release_fixture = self.make_full_release(upload)
        wrong_ffprobe = self.root / "ffprobe-wrong"
        shutil.copyfile(self.successor_ffprobe, wrong_ffprobe)
        wrong_ffprobe.chmod(0o755)
        self.assert_failure(verify(upload, release_fixture, wrong_ffprobe), 4)

        upload = self.make_successor_upload_fixture("upload-authority-schema")
        release_fixture = self.make_full_release(upload)
        authority_path = upload / "authority-lock.json"
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        authority["schema"] = "invalid-authority-schema"
        write_json(authority_path, authority)
        manifest_path = upload / "upload-ready.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["authority_lock"]["sha256"] = sha256(authority_path)
        write_json(manifest_path, manifest)
        self.assert_failure(verify(upload, release_fixture, self.successor_ffprobe), 2)

    def test_successor_never_executes_probe_before_release_trust(self) -> None:
        upload = self.make_successor_upload_fixture("upload-untrusted-probe")
        marker = self.root / "untrusted-probe-executed"
        untrusted_probe = self.root / "untrusted-ffprobe"
        untrusted_probe.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
            "print('{}')\n",
            encoding="utf-8",
        )
        untrusted_probe.chmod(0o755)
        result = self.run_cli(
            "verify-upload-ready",
            "--manifest", upload / "upload-ready.json",
            "--authority-lock", upload / "authority-lock.json",
            "--ffprobe", untrusted_probe,
        )
        self.assert_failure(result, 2)
        self.assertIn("requires --release", result.stderr)
        self.assertFalse(marker.exists(), "untrusted ffprobe ran before release trust validation")

        def verify(upload: Path, release_fixture: dict[str, Path], ffprobe: Path) -> subprocess.CompletedProcess[str]:
            return self.run_cli(
                "verify-upload-ready",
                "--manifest", upload / "upload-ready.json",
                "--authority-lock", upload / "authority-lock.json",
                "--ffprobe", ffprobe,
                "--release", release_fixture["release"],
                "--approval-receipt", release_fixture["approval"],
            )

        upload = self.make_successor_upload_fixture("upload-receipt-schema")
        release_fixture = self.make_full_release(upload)
        receipt_path = upload / "receipts.json"
        receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipts["schema"] = "invalid-receipt-schema"
        write_json(receipt_path, receipts)
        manifest_path = upload / "upload-ready.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["receipts"]["sha256"] = sha256(receipt_path)
        write_json(manifest_path, manifest)
        self.assert_failure(verify(upload, release_fixture, self.successor_ffprobe), 2)

        upload = self.make_successor_upload_fixture("upload-approval-timestamp")
        release_fixture = self.make_full_release(upload)
        approval_path = release_fixture["approval"]
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["episodes"][0]["reviewed_at"] = "2026-08-22"
        write_json(approval_path, approval)
        self.assert_failure(verify(upload, release_fixture, self.successor_ffprobe), 2)

    def test_package_rejects_output_inside_locked_source_root(self) -> None:
        upload = self.make_successor_upload_fixture("upload-disjoint")
        release_fixture = self.make_full_release(upload)
        output = release_fixture["source_root"] / "MUTATES_LOCKED_SOURCE"
        self.assert_package_release_failure(
            7,
            lambda: self.package_release_for_test(upload, release_fixture, output),
        )
        self.assertFalse(output.exists())

    def test_package_plan_builds_unattested_evidence_and_rejects_staged_mutation(self) -> None:
        upload = self.make_successor_upload_fixture("upload-plan-smoke")
        release_fixture = self.make_full_release(upload)
        marker = self.root / "delegate-argv.json"
        mutation_flag = self.root / "mutate-staged-receipt"
        package_script = self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_package_aac.py"
        package_script.write_text(
            "#!/usr/bin/env python3\n"
            "import hashlib, json, pathlib, shutil, sys\n"
            "argv = sys.argv[1:]\n"
            "plan = json.loads(pathlib.Path(argv[argv.index('--plan') + 1]).read_text(encoding='utf-8'))\n"
            "output = pathlib.Path(argv[argv.index('--output-dir') + 1])\n"
            f"shutil.copytree(pathlib.Path({str(upload)!r}), output)\n"
            "observed = {}\n"
            "for episode in plan['episodes']:\n"
            "    for stage in ('render', 'qc'):\n"
            "        source = pathlib.Path(episode[f'{stage}_receipt'])\n"
            "        content = source.read_bytes()\n"
            "        observed[f\"{episode['sequence']:02d}-{stage}\"] = hashlib.sha256(content).hexdigest()\n"
            "        target = output / '00_재현자료' / 'receipts' / f\"{episode['sequence']:02d}-{stage}_receipt.json\"\n"
            "        target.parent.mkdir(parents=True, exist_ok=True)\n"
            "        target.write_bytes(content)\n"
            f"if pathlib.Path({str(mutation_flag)!r}).exists():\n"
            "    (output / '00_재현자료' / 'receipts' / '01-render_receipt.json').write_bytes(b'mutated')\n"
            f"pathlib.Path({str(marker)!r}).write_text(json.dumps({{'argv': argv, 'plan': plan, 'receipt_sha256': observed}}), encoding='utf-8')\n"
            "print(json.dumps({'status':'ok'}))\n",
            encoding="utf-8",
        )
        package_script.chmod(0o755)
        release = json.loads(release_fixture["release"].read_text(encoding="utf-8"))
        release["renderer_modules"]["package"]["sha256"] = sha256(package_script)
        write_json(release_fixture["release"], release)
        release_sha256 = sha256(release_fixture["release"])
        upload_manifest = json.loads((upload / "upload-ready.json").read_text(encoding="utf-8"))
        upload_by_sequence = {
            artifact["sequence"]: artifact for artifact in upload_manifest["artifacts"]
        }
        receipt_root = self.root / "plan-receipts"
        receipt_root.mkdir()
        plan_episodes = []
        source_receipt_sha256 = {}
        for sequence in range(1, 7):
            render_receipt = receipt_root / f"{sequence:02d}-render.json"
            qc_receipt = receipt_root / f"{sequence:02d}-qc.json"
            job_path = self.release_root / "jobs" / JOB_FILENAMES[sequence]
            job = json.loads(job_path.read_text(encoding="utf-8"))
            thumbnail_sha256 = job["inputs"]["thumbnail"].split(":", 1)[1]
            write_json(
                render_receipt,
                {
                    "schema": "godowon.hymn-letter.v3-render-receipt/1",
                    "job_sha256": sha256(job_path),
                    "release_sha256": release_sha256,
                    "output": {
                        "sha256": upload_by_sequence[sequence]["final_media"]["sha256"],
                        "frame_count": job["output"]["frame_count"],
                    },
                    "thumbnail": {"sha256": thumbnail_sha256},
                },
            )
            write_json(
                qc_receipt,
                {
                    "schema": "godowon.hymn-letter.v3-qc-receipt/1",
                    "job_sha256": sha256(job_path),
                    "release_sha256": release_sha256,
                    "render_receipt_sha256": sha256(render_receipt),
                    "semantic_equivalent": {"status": "PASS"},
                    "reference_bit_exact": {"status": "PASS"},
                },
            )
            source_receipt_sha256[f"{sequence:02d}-render"] = sha256(render_receipt)
            source_receipt_sha256[f"{sequence:02d}-qc"] = sha256(qc_receipt)
            plan_episodes.append(
                {
                    "sequence": sequence,
                    "job": str((self.release_root / "jobs" / JOB_FILENAMES[sequence]).resolve()),
                    "render_receipt": str(render_receipt.resolve()),
                    "qc_receipt": str(qc_receipt.resolve()),
                }
            )
        plan = self.root / "package-plan.json"
        write_json(
            plan,
            {
                "schema": "godowon.hymn-letter.upload-ready-package-plan/1",
                "release": str(release_fixture["release"].resolve()),
                "source_root": str(release_fixture["source_root"].resolve()),
                "episodes": plan_episodes,
            },
        )
        package_output = self.root / "package-plan-output"
        result = self.assert_success_json(self.run_cli(
            "package",
            "--plan", plan,
            "--ffprobe", self.successor_ffprobe,
            "--release", release_fixture["release"],
            "--source-root", release_fixture["source_root"],
            "--office-root", self.office_root,
            "--runtime-python", sys.executable,
            "--approval-receipt", release_fixture["approval"],
            "--package-dir", package_output,
        ))
        self.assertEqual(result["delegation_origin"], "UNATTESTED")
        observed = json.loads(marker.read_text(encoding="utf-8"))
        argv = observed["argv"]
        approval_index = argv.index("--approval-receipt")
        self.assertEqual(Path(argv[approval_index + 1]), release_fixture["approval"].resolve())
        self.assertEqual(observed["receipt_sha256"], source_receipt_sha256)
        self.assertTrue(
            all(
                Path(episode["render_receipt"]).parent != receipt_root
                and Path(episode["qc_receipt"]).parent != receipt_root
                for episode in observed["plan"]["episodes"]
            )
        )
        package_manifest = json.loads(
            (package_output / "PACKAGE-MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(package_manifest["build_mode"], "office-plan-delegate-unattested/v1")
        delegation_entry = next(
            entry
            for entry in package_manifest["entries"]
            if entry["role"] == "delegation-inputs-lock"
        )
        delegation_lock = json.loads(
            (package_output / delegation_entry["path"]).read_text(encoding="utf-8")
        )
        self.assertNotIn(str(self.root), json.dumps(delegation_lock, ensure_ascii=False))
        self.assertEqual(
            [episode["render_receipt_sha256"] for episode in delegation_lock["episodes"]],
            [source_receipt_sha256[f"{sequence:02d}-render"] for sequence in range(1, 7)],
        )

        mutation_flag.touch()
        mutated_result = self.run_cli(
            "package",
            "--plan", plan,
            "--ffprobe", self.successor_ffprobe,
            "--release", release_fixture["release"],
            "--source-root", release_fixture["source_root"],
            "--office-root", self.office_root,
            "--runtime-python", sys.executable,
            "--approval-receipt", release_fixture["approval"],
            "--package-dir", self.root / "package-plan-mutated-output",
        )
        self.assert_failure(mutated_result, 4)

    def test_verify_package_rejects_ds_store_and_unlisted_payload(self) -> None:
        package = self.root / "package"
        package.mkdir()
        payload = package / "payload.bin"
        payload.write_bytes(b"payload")
        sums = package / "SHA256SUMS.txt"
        sums.write_text(f"{sha256(payload)}  payload.bin\n", encoding="utf-8")
        (package / ".DS_Store").write_bytes(b"finder")
        self.assert_failure(
            self.run_cli(
                "verify-package", "--package-dir", package, "--sums", sums,
                "--release", self.root / "missing-release.json",
                "--approval-receipt", self.root / "missing-approval.json",
            ),
            7,
        )
        (package / ".DS_Store").unlink()
        (package / "extra.bin").write_bytes(b"extra")
        self.assert_failure(
            self.run_cli(
                "verify-package", "--package-dir", package, "--sums", sums,
                "--release", self.root / "missing-release.json",
                "--approval-receipt", self.root / "missing-approval.json",
            ),
            11,
        )

    def test_package_is_repeatable_and_binds_canonical_media_after_full_rehash(self) -> None:
        first = self.root / "package-a"
        second = self.root / "package-b"
        first_result = self.build_test_package(first)
        second_result = self.build_test_package(second)
        self.assertEqual(first_result["verified_sequences"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            (first / "PACKAGE-MANIFEST.json").read_bytes(),
            (second / "PACKAGE-MANIFEST.json").read_bytes(),
        )
        self.assertEqual(
            (first / "SHA256SUMS.txt").read_bytes(),
            (second / "SHA256SUMS.txt").read_bytes(),
        )
        package_manifest_path = first / "PACKAGE-MANIFEST.json"
        package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
        media_entry = next(item for item in package_manifest["entries"] if item["role"] == "episode-media:01")
        media_path = first / media_entry["path"]
        media_path.write_bytes(b"self-consistent-but-not-approved")
        media_entry["sha256"] = sha256(media_path)
        media_entry["size"] = media_path.stat().st_size
        package_manifest_path.write_text(
            json.dumps(package_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        checksum_rows = []
        for path in sorted(first.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS.txt":
                checksum_rows.append(f"{sha256(path)}  {path.relative_to(first).as_posix()}")
        (first / "SHA256SUMS.txt").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
        self.assert_failure(
            self.run_cli(
                "verify-package", "--package-dir", first,
                "--release", self.package_trust["release"],
                "--approval-receipt", self.package_trust["approval"],
            ),
            4,
        )

    def test_verify_package_rejects_rehashed_code_release_and_noncanonical_sums(self) -> None:
        package = self.root / "package-provenance"
        self.build_test_package(package)
        manifest_path = package / "PACKAGE-MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        code_entry = next(item for item in manifest["entries"] if item["role"] == "plugify-code")
        code_path = package / code_entry["path"]
        code_path.write_bytes(b"forged plugify code\n")
        code_entry["sha256"] = sha256(code_path)
        code_entry["size"] = code_path.stat().st_size
        self.rewrite_package_hashes(package, manifest)
        self.assert_failure(self.verify_built_package(package), 4)

        package = self.root / "package-release-trust"
        self.build_test_package(package)
        manifest_path = package / "PACKAGE-MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        release_entry = next(item for item in manifest["entries"] if item["role"] == "release-lock")
        release_path = package / release_entry["path"]
        release = json.loads(release_path.read_text(encoding="utf-8"))
        release["notes"].append("self-signed mutation")
        write_json(release_path, release)
        release_entry["sha256"] = sha256(release_path)
        release_entry["size"] = release_path.stat().st_size
        manifest["release_sha256"] = release_entry["sha256"]
        self.rewrite_package_hashes(package, manifest)
        self.assert_failure(self.verify_built_package(package), 4)

        package = self.root / "package-sums-canonical"
        self.build_test_package(package)
        sums = package / "SHA256SUMS.txt"
        sums.write_bytes(sums.read_bytes().removesuffix(b"\n"))
        self.assert_failure(self.verify_built_package(package), 2)

        package = self.root / "package-direct-repack-mode"
        self.build_test_package(package)
        manifest_path = package / "PACKAGE-MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["build_mode"] = "verified-upload-ready-repack/v1"
        self.rewrite_package_hashes(package, manifest)
        self.assert_failure(self.verify_built_package(package), 2)

    def test_package_retracts_when_promoted_tree_changes_before_final_verify(self) -> None:
        upload = self.make_successor_upload_fixture("upload-promoted-mutation")
        release_fixture = self.make_full_release(upload)
        package = self.root / "package-promoted-mutation"
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        original_promote = flow._atomic_promote_new_directory

        def promote_then_mutate(source: Path, destination: Path) -> tuple[int, int]:
            identity = original_promote(source, destination)
            (destination / ".DS_Store").write_bytes(b"late incidental metadata")
            return identity

        flow._atomic_promote_new_directory = promote_then_mutate
        try:
            self.assert_package_release_failure(
                7,
                lambda: self.package_release_for_test(upload, release_fixture, package),
            )
        finally:
            flow._atomic_promote_new_directory = original_promote
        self.assertFalse(package.exists(), "failed promoted package was not retracted")

        upload = self.make_successor_upload_fixture("upload-promotion-postcheck-failure")
        release_fixture = self.make_full_release(upload)
        package = self.root / "package-promotion-postcheck-failure"

        def promote_then_raise(source: Path, destination: Path) -> tuple[int, int]:
            original_promote(source, destination)
            raise flow.FlowError(7, "injected post-rename identity failure")

        flow._atomic_promote_new_directory = promote_then_raise
        try:
            self.assert_package_release_failure(
                7,
                lambda: self.package_release_for_test(upload, release_fixture, package),
            )
        finally:
            flow._atomic_promote_new_directory = original_promote
        self.assertFalse(package.exists(), "post-rename failure left a final directory")

        upload = self.make_successor_upload_fixture("upload-promotion-interrupt")
        release_fixture = self.make_full_release(upload)
        package = self.root / "package-promotion-interrupt"
        original_verify = flow.verify_deterministic_package
        verify_calls = 0

        def interrupt_second_verify(*args: object, **kwargs: object) -> dict:
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls == 2:
                raise KeyboardInterrupt("injected post-promotion interrupt")
            return original_verify(*args, **kwargs)

        flow.verify_deterministic_package = interrupt_second_verify
        try:
            with self.assertRaises(KeyboardInterrupt):
                self.package_release_for_test(upload, release_fixture, package)
        finally:
            flow.verify_deterministic_package = original_verify
        self.assertEqual(verify_calls, 2)
        self.assertFalse(package.exists(), "interrupted post-promotion verify left a final directory")

    def test_verify_package_rejects_ds_store_added_after_final_exact_set_scan(self) -> None:
        package = self.root / "package-late-ds-store"
        self.build_test_package(package)
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        original_closed_verify = flow.verify_closed_package
        previous_pin = flow.PROJECT_RELEASE_SHA256
        closed_verify_calls = 0

        def final_scan_then_add_metadata(*args: object, **kwargs: object) -> dict:
            nonlocal closed_verify_calls
            result = original_closed_verify(*args, **kwargs)
            closed_verify_calls += 1
            if closed_verify_calls == 2:
                (package / ".DS_Store").write_bytes(b"metadata added after final exact-set scan")
            return result

        flow.verify_closed_package = final_scan_then_add_metadata
        flow.PROJECT_RELEASE_SHA256 = sha256(self.package_trust["release"])
        try:
            self.assert_package_release_failure(
                7,
                lambda: flow.verify_deterministic_package(
                    package,
                    package / "SHA256SUMS.txt",
                    self.package_trust["release"],
                    self.package_trust["approval"],
                ),
            )
        finally:
            flow.verify_closed_package = original_closed_verify
            flow.PROJECT_RELEASE_SHA256 = previous_pin
        self.assertEqual(closed_verify_calls, 2)


class RenderAndQcV3Tests(V3FixtureMixin, PortableCliTestCase):
    def test_runtime_probe_imports_actual_pinned_office_dataclass_module(self) -> None:
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        workspace = SCRIPT.parents[4]
        office_root = workspace / "godowon-office"
        release_path = (
            office_root
            / "godo-hymns"
            / "releases"
            / PRODUCTION_RELEASE_ID
            / "release.lock.json"
        )
        runtime_python = Path("/Users/admin/venvs/hymn-letter-v3-runtime-copies/bin/python3.12")
        if not release_path.is_file() or not runtime_python.is_file():
            self.skipTest("actual pinned office release/runtime is unavailable")
        normalized_release_path, release_sha256, release = flow._load_release(release_path)
        self.assertEqual(release_sha256, flow.PROJECT_RELEASE_SHA256)
        mp4_module = office_root / release["renderer_modules"]["mp4"]["path"]
        self.assertTrue(mp4_module.is_file())
        self.assertIn("@dataclass", mp4_module.read_text(encoding="utf-8"))
        self.assertEqual(
            sha256(mp4_module),
            release["renderer_modules"]["mp4"]["sha256"],
        )
        resolved_runtime, runtime_metadata = flow._resolve_runtime_python(runtime_python)
        flow._require_locked_runtime_environment(
            normalized_release_path,
            release,
            office_root,
            resolved_runtime,
            runtime_metadata,
        )

    def test_runtime_fingerprint_rejects_pillow_native_drift(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        environment_path = self.release_root / "environment.lock.json"
        environment = json.loads(environment_path.read_text(encoding="utf-8"))
        environment["pillow_native_libraries"]["freetype2"] = "drifted"
        write_json(environment_path, environment)
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["environment_lock_sha256"] = sha256(environment_path)
        write_json(fixture["release"], release)
        result = self.run_cli(
            "render",
            "--job", fixture["job"],
            "--release", fixture["release"],
            "--source-root", fixture["source_root"],
            "--run-root", fixture["run_root"],
            "--office-root", self.office_root,
            "--runtime-python", sys.executable,
        )
        self.assert_failure(result, 4)
        self.assertIn("runtime/Pillow/FFmpeg environment", result.stderr)

    def test_zero_renderer_module_pin_blocks_execution(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["renderer_modules"]["profiles"]["sha256"] = "0" * 64
        write_json(fixture["release"], release)
        result = self.run_cli(
            "render",
            "--job", fixture["job"],
            "--release", fixture["release"],
            "--source-root", fixture["source_root"],
            "--run-root", fixture["run_root"],
            "--office-root", self.office_root,
            "--runtime-python", sys.executable,
        )
        self.assert_failure(result, 6)
        self.assertIn("renderer module pins are BOOTSTRAP_REQUIRED", result.stderr)

    def test_runtime_lock_rejects_wrong_executable(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        wrong_runtime = self.root / "wrong-python"
        wrong_runtime.write_text("#!/bin/sh\necho 'Python 0.0.0'\n", encoding="utf-8")
        wrong_runtime.chmod(0o755)
        result = self.run_cli(
            "render",
            "--job", fixture["job"],
            "--release", fixture["release"],
            "--source-root", fixture["source_root"],
            "--run-root", fixture["run_root"],
            "--office-root", self.office_root,
            "--runtime-python", wrong_runtime,
        )
        self.assert_failure(result, 4)
        self.assertIn("runtime Python does not match environment lock", result.stderr)

    def test_render_and_qc_write_wrapper_receipts(self) -> None:
        fixture = self.make_fixture("05-370-testimony")
        render_payload = self.assert_success_json(
            self.run_cli(
                "render",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
                "--run-root",
                fixture["run_root"],
                "--office-root",
                self.office_root,
                "--runtime-python",
                sys.executable,
            )
        )
        render_receipt = Path(render_payload["receipt"])
        render_data = json.loads(render_receipt.read_text(encoding="utf-8"))
        self.assertEqual(render_data["stage"], "render")
        self.assertEqual(render_data["delegate_payload"]["argv"][0], "render")
        self.assertEqual(
            render_data["delegate_payload"]["locale_environment"],
            {"LANG": "C", "LC_ALL": "C", "LC_CTYPE": "C"},
        )
        self.assertEqual(render_data["runtime_python"]["sha256"], sha256(Path(sys.executable).resolve()))
        self.assertIn("05-370-testimony", render_receipt.name)

        qc_payload = self.assert_success_json(
            self.run_cli(
                "qc",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
                "--run-root",
                fixture["run_root"],
                "--gate",
                "semantic-equivalent",
                "--office-root",
                self.office_root,
                "--runtime-python",
                sys.executable,
            )
        )
        qc_receipt = Path(qc_payload["receipt"])
        qc_data = json.loads(qc_receipt.read_text(encoding="utf-8"))
        self.assertEqual(qc_data["stage"], "qc")
        self.assertEqual(qc_data["gate"], "semantic-equivalent")
        self.assertEqual(qc_data["delegate_payload"]["argv"][0], "qc")
        self.assertIn("05-370-testimony", qc_receipt.name)
        self.assertEqual(qc_payload["gate_status"], "PASS")

    def test_qc_fail_is_reported_as_json_and_exit_twelve_with_receipt(self) -> None:
        fixture = self.make_fixture("05-370-testimony")
        self.assert_success_json(
            self.run_cli(
                "render",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
                "--run-root",
                fixture["run_root"],
                "--office-root",
                self.office_root,
                "--runtime-python",
                sys.executable,
            )
        )
        qc_script = self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_qc_aac.py"
        qc_script.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "print(json.dumps({'delegate':'qc','status':'FAIL','argv':sys.argv[1:]}))\n",
            encoding="utf-8",
        )
        qc_script.chmod(0o755)

        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["renderer_modules"]["qc"]["sha256"] = sha256(qc_script)
        write_json(fixture["release"], release)

        result = self.run_cli(
            "qc",
            "--job",
            fixture["job"],
            "--release",
            fixture["release"],
            "--source-root",
            fixture["source_root"],
            "--run-root",
            fixture["run_root"],
            "--gate",
            "reference-bit-exact",
            "--office-root",
            self.office_root,
            "--runtime-python",
            sys.executable,
        )
        self.assertEqual(result.returncode, 12, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "qc")
        self.assertEqual(payload["gate"], "reference-bit-exact")
        self.assertEqual(payload["gate_status"], "FAIL")
        self.assertEqual(payload["status"], "failed")

        receipt_path = Path(payload["receipt"])
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["stage"], "qc")
        self.assertEqual(receipt["gate"], "reference-bit-exact")
        self.assertEqual(receipt["delegate_payload"]["status"], "FAIL")
        delegate_stdout = (
            json.dumps(
                {
                    "delegate": "qc",
                    "status": "FAIL",
                    "argv": receipt["delegate_payload"]["argv"],
                }
            )
            + "\n"
        )
        self.assertEqual(
            receipt["delegate_stdout_sha256"],
            hashlib.sha256(delegate_stdout.encode("utf-8")).hexdigest(),
        )

    def test_new_literal_tmp_run_root_is_canonicalized(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        alias_parent = Path("/tmp")
        run_root = alias_parent / f"hymn-flow-v3-run-{os.getpid()}-{id(self)}"
        self.addCleanup(lambda: shutil.rmtree(run_root.resolve(), ignore_errors=True))
        payload = self.assert_success_json(
            self.run_cli(
                "render",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
                "--run-root",
                run_root,
                "--office-root",
                self.office_root,
                "--runtime-python",
                sys.executable,
            )
        )
        receipt = json.loads(Path(payload["receipt"]).read_text(encoding="utf-8"))
        self.assertEqual(Path(receipt["run_root"]), run_root.resolve())

    def test_rejects_renderer_module_mutation_during_delegate(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        profiles = self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_profiles.py"
        caption = self.office_root / "godo-hymns" / "tools" / "hymn_letter_caption_v3.py"
        profiles.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "from pathlib import Path\n"
            f"Path({str(caption)!r}).write_text('mutated\\n', encoding='utf-8')\n"
            "print(json.dumps({'delegate':'render','status':'ok','argv':sys.argv[1:]}))\n",
            encoding="utf-8",
        )
        profiles.chmod(0o755)
        release = json.loads(fixture["release"].read_text(encoding="utf-8"))
        release["renderer_modules"]["profiles"]["sha256"] = sha256(profiles)
        write_json(fixture["release"], release)
        result = self.run_cli(
            "render",
            "--job",
            fixture["job"],
            "--release",
            fixture["release"],
            "--source-root",
            fixture["source_root"],
            "--run-root",
            fixture["run_root"],
            "--office-root",
            self.office_root,
            "--runtime-python",
            sys.executable,
        )
        self.assert_failure(result, 4)
        self.assertFalse((fixture["run_root"] / "plugify-render-wrapper-receipt-03-491-testimony.json").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_existing_run_root_beneath_arbitrary_symlink(self) -> None:
        fixture = self.make_fixture("03-491-testimony")
        real_parent = self.root / "real-runs"
        real_parent.mkdir()
        alias_parent = self.root / "aliased-runs"
        alias_parent.symlink_to(real_parent, target_is_directory=True)
        run_root = alias_parent / "existing-run"
        run_root.mkdir()
        self.assert_failure(
            self.run_cli(
                "render",
                "--job",
                fixture["job"],
                "--release",
                fixture["release"],
                "--source-root",
                fixture["source_root"],
                "--run-root",
                run_root,
                "--office-root",
                self.office_root,
                "--runtime-python",
                sys.executable,
            ),
            7,
        )


class CandidateFixtureMixin:
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-candidate-v1-")
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _json_bytes(payload: object) -> bytes:
        return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def make_candidate(self, sequence: int, *, approved_hymn: bool = False) -> dict[str, Path]:
        testimony = sequence % 2 == 1
        track_sequence = sequence + 1 if testimony else sequence
        approved_track = CANDIDATE_TRACKS.get(track_sequence)
        episode = {
            "sequence": sequence,
            "episode_id": f"{sequence:02d}-387-{'testimony' if testimony else 'hymn'}",
            "kind": "testimony_intro" if testimony else "hymn_lyrics",
            "profile": "testimony-external-srt/v1" if testimony else "hymn-listening-external-srt/v1",
            "hymn_number": approved_track["hymn_number"] if approved_track else 387,
            "title": approved_track["title"] if approved_track else "멀리멀리 갔더니",
        }
        run_root = self.root / f"candidate-{sequence:02d}"
        run_root.mkdir()
        object_entries: dict[str, dict] = {}
        object_paths: dict[str, Path] = {}
        input_metadata: dict[str, dict] = {}

        def add_object(key: str, filename: str, payload: bytes) -> dict:
            digest = hashlib.sha256(payload).hexdigest()
            object_id = f"sha256:{digest}"
            object_path = run_root / "objects" / "sha256" / digest[:2] / digest[2:]
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_path.write_bytes(payload)
            object_entries[object_id] = {
                "sha256": digest,
                "size": len(payload),
                "filenames": [filename],
                "roles": [key],
            }
            object_paths[key] = object_path
            metadata = {
                "object_id": object_id,
                "sha256": digest,
                "size": len(payload),
                "original_filename": filename,
            }
            input_metadata[key] = metadata
            return metadata

        approved_audio_bytes: bytes | None = None
        approved_captions_bytes: bytes | None = None
        if approved_hymn:
            if testimony or approved_track is None:
                raise ValueError("approved_hymn requires a registered even sequence")
            audio_digest = approved_track["audio_object_id"].removeprefix("sha256:")
            captions_digest = approved_track["captions_object_id"].removeprefix("sha256:")
            approved_audio_path = (
                APPROVED_SOURCE_ROOT / "objects" / "sha256" / audio_digest[:2] / audio_digest[2:]
            )
            approved_captions_path = (
                APPROVED_SOURCE_ROOT
                / "objects" / "sha256" / captions_digest[:2] / captions_digest[2:]
            )
            approved_audio_bytes = approved_audio_path.read_bytes()
            approved_captions_bytes = approved_captions_path.read_bytes()

        caption_payload = (
            approved_captions_bytes
            if approved_captions_bytes is not None
            else (
                b"1\n00:00:00,000 --> 00:00:01,000\napproved script\n"
                if testimony
                else b"1\n00:00:00,000 --> 00:00:01,000\ntext\n"
            )
        )
        common_payloads = {
            "captions": ("captions.srt", caption_payload),
            "backplate": ("backplate.jpg", b"candidate-backplate"),
            "thumbnail": ("thumbnail.jpg", b"candidate-thumbnail"),
        }
        for key, (filename, payload) in common_payloads.items():
            add_object(key, filename, payload)

        if testimony:
            add_object("approved_script", "approved-script.txt", b"approved script\n")
            narration = add_object("narration_audio", "narration.m4a", b"aac-lc-48k-candidate")
            narration_receipt = {
                "schema": "godowon.hymn-letter.narration-receipt/1",
                "narration_mode": "recorded",
                "approved_script_sha256": input_metadata["approved_script"]["sha256"],
                "result_sha256": narration["sha256"],
                "script_approved": True,
                "human_approval_receipt": True,
                "human_listening_approved": True,
            }
            add_object(
                "narration_receipt",
                "narration-receipt.json",
                self._json_bytes(narration_receipt),
            )
            speech_master_report = {
                "schema": "godowon.hymn-letter.speech-master-report/1",
                "status": "PASS",
                "profile": {
                    "id": "hymn-letter-speech-master-v1",
                    "output": {
                        "container": "M4A",
                        "codec": "AAC-LC",
                        "sample_rate": 48000,
                        "channels": 2,
                        "bitrate": "192k",
                    },
                },
                "artifacts": {"output": {"sha256": narration["sha256"]}},
                "qc": {"pass": True},
            }
            add_object(
                "speech_master_report",
                "speech-master-report.json",
                self._json_bytes(speech_master_report),
            )
            audio_metadata = narration
            approvals = {
                "narration_mode": "recorded",
                "script_approved": True,
                "human_approval_receipt": True,
                "human_listening_approved": True,
            }
            audio_probe = {
                "codec_name": "aac",
                "profile": "LC",
                "sample_rate": 48000,
                "channels": 2,
                "duration_ms": 3000,
                "movie_timescale": 1000,
            }
            settings = {
                "caption_delivery": "youtube-sidecar-srt/v1",
                "subtitle_language": "ko",
                "restore_audio_edit": True,
                "movie_timescale": 1000,
                "video_track_timescale": 15360,
            }
            audio_policy = "stream-copy-approved-aac/v1"
        else:
            audio_metadata = add_object(
                "audio",
                "hymn.mp3",
                approved_audio_bytes
                if approved_audio_bytes is not None
                else b"arbitrary-mp3-with-untrusted-catalog-assertion",
            )
            approvals = {"catalog_audio_sha_match": True}
            audio_probe = {
                "codec_name": "mp3",
                "profile": "unknown",
                "sample_rate": 44100,
                "channels": 2,
                "duration_ms": (
                    (approved_track["samples"] * 1000 + 44099) // 44100
                    if approved_hymn and approved_track
                    else 5000
                ),
                "movie_timescale": None,
            }
            settings = {
                "caption_delivery": "youtube-sidecar-srt/v1",
                "subtitle_language": "ko",
                "movie_timescale": 44100,
                "video_track_timescale": 15360,
            }
            audio_policy = "approved-mp3-to-aac-lc-256k/v1"

        job_frame_count = (
            90
            if testimony
            else approved_track["frame_count"] if approved_hymn else 150
        )
        audio_probe["render_frame_count"] = job_frame_count

        job_inputs = {
            "audio_policy": audio_policy,
            "backplate": input_metadata["backplate"]["object_id"],
            "audio": audio_metadata["object_id"],
            "captions": input_metadata["captions"]["object_id"],
            "thumbnail": input_metadata["thumbnail"]["object_id"],
        }
        job = {
            "schema": "godowon.hymn-letter.v3-job/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "episode_id": episode["episode_id"],
            "profile": episode["profile"],
            "inputs": job_inputs,
            "settings": settings,
            "output": {
                "filename": f"{sequence:02d}_candidate.mp4",
                "captions_filename": f"{sequence:02d}_candidate.ko.srt",
                "thumbnail_filename": f"{sequence:02d}_thumbnail.jpg",
                "container": "mp4",
                "audio_codec": "aac",
                "audio_profile": "LC",
                "frame_count": job_frame_count,
            },
        }
        job_path = run_root / "job.json"
        write_json(job_path, job)

        intake_inputs = (
            {
                key: input_metadata[key]
                for key in (
                    "approved_script", "narration_audio", "captions", "backplate",
                    "thumbnail", "narration_receipt", "speech_master_report",
                )
            }
            if testimony
            else {
                key: input_metadata[key]
                for key in ("audio", "captions", "backplate", "thumbnail")
            }
        )
        base_release = {
            "release_id": PRODUCTION_RELEASE_ID,
            "release_lock_sha256": "24867e11a54c33f69005ed7b033f3996200597697fa99657bb4764ea9ddff7e6",
        }
        caption_blocks = caption_payload.decode("utf-8").strip().split("\n\n")
        last_timing = next(line for line in caption_blocks[-1].splitlines() if "-->" in line)
        last_end = last_timing.split("-->", 1)[1].strip().replace(".", ",")
        hours, minutes, seconds_ms = last_end.split(":")
        seconds, milliseconds = seconds_ms.split(",")
        caption_last_end_ms = (
            ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000
            + int(milliseconds)
        )
        intake = {
            "schema": "godowon.hymn-letter.episode-intake/1",
            "status": "CANDIDATE_UNAPPROVED",
            "series_name": "'고도원의 찬송편지'",
            "base_release": base_release,
            "episode": episode,
            "inputs": intake_inputs,
            "approvals": approvals,
            "probe": {
                "ffprobe_sha256": "1" * 64,
                "ffprobe_version": "fixture ffprobe (must not execute)",
                "audio": audio_probe,
                "captions": {
                    "format": "SubRip",
                    "encoding": "UTF-8",
                    "bom": False,
                    "line_endings": "LF",
                    "ends_with_newline": True,
                    "cue_count": len(caption_blocks),
                    "last_end_ms": caption_last_end_ms,
                },
            },
            "catalog": {
                "schema": "godowon.hymn-letter.track-catalog/1",
                "sha256": CANDIDATE_CATALOG_SHA256,
                "track_sequence": sequence + 1 if testimony else sequence,
            },
        }
        intake_path = run_root / "intake-receipt.json"
        write_json(intake_path, intake)

        source_bundle = {
            "schema": "godowon.hymn-letter.candidate-source-bundle/1",
            "release_id": PRODUCTION_RELEASE_ID,
            "storage_layout": "objects/sha256/<prefix>/<digest-rest>",
            "objects": object_entries,
        }
        source_bundle_path = run_root / "source-bundle.lock.json"
        write_json(source_bundle_path, source_bundle)
        candidate_lock = {
            "schema": "godowon.hymn-letter.candidate-lock/1",
            "status": "CANDIDATE_UNAPPROVED",
            "series_name": "'고도원의 찬송편지'",
            "base_release": base_release,
            "episode": episode,
            "job": {"path": "job.json", "sha256": sha256(job_path)},
            "source_bundle": {
                "path": "source-bundle.lock.json",
                "sha256": sha256(source_bundle_path),
            },
            "intake_receipt": {
                "path": "intake-receipt.json",
                "sha256": sha256(intake_path),
            },
        }
        lock_path = run_root / "candidate.lock.json"
        write_json(lock_path, candidate_lock)
        return {
            "run_root": run_root,
            "lock": lock_path,
            "job": job_path,
            "source_bundle": source_bundle_path,
            "intake": intake_path,
            "objects": object_paths,
        }

    def refresh_reference(self, fixture: dict[str, Path], key: str, path_key: str) -> None:
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock[key]["sha256"] = sha256(fixture[path_key])
        write_json(fixture["lock"], lock)

    def run_candidate(self, fixture: dict[str, Path], **environment: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "validate-candidate", "--run-root", str(fixture["run_root"])],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **environment},
        )


class CandidateValidationV3Tests(CandidateFixtureMixin, PortableCliTestCase):
    def test_rejects_missing_blank_line_between_srt_cues(self) -> None:
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        captions = self.root / "missing-separator.srt"
        captions.write_bytes(
            b"1\n00:00:00,000 --> 00:00:01,000\nfirst\n"
            b"2\n00:00:01,000 --> 00:00:02,000\nsecond\n"
        )
        with self.assertRaises(flow.FlowError) as raised:
            flow._candidate_srt_observation(captions)
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("cues must be separated by a blank line", str(raised.exception))

    def test_accepts_testimony_without_running_media_tools(self) -> None:
        marker = self.root / "media-tool-ran"
        tool_root = self.root / "tools"
        tool_root.mkdir()
        for tool_name in ("ffprobe", "ffmpeg"):
            tool = tool_root / tool_name
            tool.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
            tool.chmod(0o755)
        fixture = self.make_candidate(7)
        payload = self.assert_success_json(self.run_candidate(fixture, PATH=str(tool_root)))
        self.assertEqual(payload["candidate_status"], "CANDIDATE_UNAPPROVED")
        self.assertEqual(payload["sequence"], 7)
        self.assertEqual(payload["catalog_track_sequence"], 8)
        self.assertEqual(payload["expected_pcm_f32le_sha256"], PRODUCTION_PCM_SHA256[2])
        self.assertFalse(payload["execution_authorized"])
        self.assertFalse(marker.exists(), "validate-candidate executed a media tool")

    def test_accepts_actual_approved_387_hymn_objects(self) -> None:
        track = CANDIDATE_TRACKS[8]
        required_paths = []
        for key in ("audio_object_id", "captions_object_id"):
            digest = track[key].removeprefix("sha256:")
            required_paths.append(
                APPROVED_SOURCE_ROOT / "objects" / "sha256" / digest[:2] / digest[2:]
            )
        if not all(path.is_file() for path in required_paths):
            self.skipTest("approved 387 source objects are unavailable")
        fixture = self.make_candidate(8, approved_hymn=True)
        payload = self.assert_success_json(self.run_candidate(fixture))
        self.assertEqual(payload["catalog_sha256"], CANDIDATE_CATALOG_SHA256)
        self.assertEqual(payload["catalog_track_sequence"], 8)
        self.assertEqual(payload["approved_frame_count"], 6140)
        self.assertEqual(payload["expected_pcm_f32le_sha256"], PRODUCTION_PCM_SHA256[2])
        self.assertFalse(payload["execution_authorized"])

        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        job["output"]["frame_count"] = 6139
        write_json(fixture["job"], job)
        self.refresh_reference(fixture, "job", "job")
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        intake["probe"]["audio"]["render_frame_count"] = 6139
        write_json(fixture["intake"], intake)
        self.refresh_reference(fixture, "intake_receipt", "intake")
        mismatch = self.run_candidate(fixture)
        self.assert_failure(mismatch, 4)
        self.assertIn("frame count differs from approved track", mismatch.stderr)

    def test_rejects_arbitrary_mp3_even_when_catalog_assertion_is_true(self) -> None:
        fixture = self.make_candidate(8)
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        self.assertIs(intake["approvals"]["catalog_audio_sha_match"], True)
        result = self.run_candidate(fixture)
        self.assert_failure(result, 4)
        self.assertIn("audio object differs from approved track", result.stderr)

    def test_rejects_mutated_immutable_catalog(self) -> None:
        if str(SCRIPT.parent) not in sys.path:
            sys.path.insert(0, str(SCRIPT.parent))
        import hymn_video_flow_v3 as flow

        mutated_catalog = self.root / "mutated-track-catalog.json"
        catalog = copy.deepcopy(CANDIDATE_CATALOG)
        catalog["tracks"][0]["title"] = "변조된 제목"
        write_json(mutated_catalog, catalog)
        previous_path = flow.CANDIDATE_TRACK_CATALOG_PATH
        flow.CANDIDATE_TRACK_CATALOG_PATH = mutated_catalog
        try:
            with self.assertRaises(flow.FlowError) as raised:
                flow._load_candidate_track_catalog()
            self.assertEqual(raised.exception.code, 4)
        finally:
            flow.CANDIDATE_TRACK_CATALOG_PATH = previous_path

    def test_rejects_episode_title_drift_from_paired_catalog_track(self) -> None:
        fixture = self.make_candidate(7)
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        intake["episode"]["title"] = "임의 제목"
        write_json(fixture["intake"], intake)
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock["episode"]["title"] = "임의 제목"
        lock["intake_receipt"]["sha256"] = sha256(fixture["intake"])
        write_json(fixture["lock"], lock)
        result = self.run_candidate(fixture)
        self.assert_failure(result, 4)
        self.assertIn("hymn number/title differs from approved track", result.stderr)

    def test_rejects_unregistered_sequence_and_kind_profile_parity(self) -> None:
        fixture = self.make_candidate(7)
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock["episode"]["sequence"] = 27
        lock["episode"]["episode_id"] = "27-387-testimony"
        write_json(fixture["lock"], lock)
        self.assert_failure(self.run_candidate(fixture), 6)

        fixture = self.make_candidate(9)
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock["episode"]["sequence"] = 8
        lock["episode"]["episode_id"] = "08-387-testimony"
        write_json(fixture["lock"], lock)
        self.assert_failure(self.run_candidate(fixture), 6)

    def test_rejects_relative_path_escape(self) -> None:
        fixture = self.make_candidate(8)
        outside = self.root / "outside-job.json"
        shutil.copyfile(fixture["job"], outside)
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock["job"] = {"path": "../outside-job.json", "sha256": sha256(outside)}
        write_json(fixture["lock"], lock)
        self.assert_failure(self.run_candidate(fixture), 7)

    def test_rejects_symlinked_reference(self) -> None:
        fixture = self.make_candidate(8)
        outside = self.root / "outside-job.json"
        shutil.copyfile(fixture["job"], outside)
        fixture["job"].unlink()
        fixture["job"].symlink_to(outside)
        self.assert_failure(self.run_candidate(fixture), 7)

    def test_rejects_content_hash_mismatch(self) -> None:
        fixture = self.make_candidate(8)
        fixture["objects"]["audio"].write_bytes(b"mutated catalog audio")
        self.assert_failure(self.run_candidate(fixture), 4)

    def test_rejects_missing_job_input_object(self) -> None:
        fixture = self.make_candidate(7)
        fixture["objects"]["narration_audio"].unlink()
        self.assert_failure(self.run_candidate(fixture), 3)

    def test_rejects_candidate_status_drift_in_lock_or_intake(self) -> None:
        fixture = self.make_candidate(8)
        lock = json.loads(fixture["lock"].read_text(encoding="utf-8"))
        lock["status"] = "APPROVED"
        write_json(fixture["lock"], lock)
        self.assert_failure(self.run_candidate(fixture), 6)

        fixture = self.make_candidate(7)
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        intake["status"] = "APPROVED"
        write_json(fixture["intake"], intake)
        self.refresh_reference(fixture, "intake_receipt", "intake")
        self.assert_failure(self.run_candidate(fixture), 6)

    def test_candidate_movie_timescale_must_match_audio_probe_contract(self) -> None:
        fixture = self.make_candidate(7)
        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        job["settings"]["movie_timescale"] = 2000
        write_json(fixture["job"], job)
        self.refresh_reference(fixture, "job", "job")
        result = self.run_candidate(fixture)
        self.assert_failure(result, 2)
        self.assertIn("does not match the audio probe", result.stderr)

        fixture = self.make_candidate(8)
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        intake["probe"]["audio"]["movie_timescale"] = 44100
        write_json(fixture["intake"], intake)
        self.refresh_reference(fixture, "intake_receipt", "intake")
        result = self.run_candidate(fixture)
        self.assert_failure(result, 2)
        self.assertIn("must be null", result.stderr)

    def test_candidate_job_frame_count_must_match_audio_probe(self) -> None:
        fixture = self.make_candidate(7)
        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        intake = json.loads(fixture["intake"].read_text(encoding="utf-8"))
        self.assertEqual(job["output"]["frame_count"], 90)
        self.assertEqual(intake["probe"]["audio"]["render_frame_count"], 90)

        job["output"]["frame_count"] = 1
        write_json(fixture["job"], job)
        self.refresh_reference(fixture, "job", "job")
        result = self.run_candidate(fixture)
        self.assert_failure(result, 2)
        self.assertIn("does not match the intake audio probe", result.stderr)

    def test_production_commands_reject_candidate_lock_as_release(self) -> None:
        fixture = self.make_candidate(8)
        regular_executable = Path(sys.executable).resolve()
        upload_manifest = fixture["run_root"] / "upload-ready.json"
        authority = fixture["run_root"] / "authority-lock.json"
        write_json(upload_manifest, {"release_id": PRODUCTION_RELEASE_ID})
        write_json(authority, {})
        package_output = self.root / "production-package-must-not-exist"
        commands = {
            "validate": [
                "validate-job", "--job", fixture["job"], "--release", fixture["lock"],
            ],
            "render": [
                "render", "--job", fixture["job"], "--release", fixture["lock"],
                "--source-root", fixture["run_root"], "--run-root", self.root / "render-run",
                "--runtime-python", regular_executable,
            ],
            "qc": [
                "qc", "--job", fixture["job"], "--release", fixture["lock"],
                "--source-root", fixture["run_root"], "--run-root", self.root / "qc-run",
                "--gate", "semantic-equivalent", "--runtime-python", regular_executable,
            ],
            "package": [
                "package", "--plan", fixture["job"], "--ffprobe", regular_executable,
                "--release", fixture["lock"], "--source-root", fixture["run_root"],
                "--runtime-python", regular_executable, "--approval-receipt", fixture["intake"],
                "--package-dir", package_output,
            ],
            "upload": [
                "verify-upload-ready", "--manifest", upload_manifest,
                "--authority-lock", authority, "--ffprobe", regular_executable,
                "--release", fixture["lock"], "--approval-receipt", fixture["intake"],
            ],
        }
        for name, arguments in commands.items():
            with self.subTest(command=name):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *map(str, arguments)],
                    text=True,
                    capture_output=True,
                    check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assert_failure(result, 4)
                self.assertIn("compiled production trust pin", result.stderr)
        self.assertFalse(package_output.exists())


class UsageTests(PortableCliTestCase):
    def test_successor_docs_export_portable_c_locale(self) -> None:
        for relative in ("SKILL.md", "references/workflow.md"):
            document = (SCRIPT.parent.parent / relative).read_text(encoding="utf-8")
            self.assertIn("export LANG=C", document)
            self.assertIn("export LC_ALL=C", document)
            self.assertIn("export LC_CTYPE=C", document)
            self.assertIn("filesystem encoding `utf-8`", document)

    def test_argparse_usage_is_exit_two(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)

    def test_public_package_command_is_plan_only(self) -> None:
        result = self.run_cli("package", "--manifest", "removed-direct-package.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("--plan", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
