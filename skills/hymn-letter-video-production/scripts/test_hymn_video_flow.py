#!/usr/bin/env python3
"""Stdlib regression tests for hymn_video_flow.py."""

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
import time
import unittest


sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().with_name("hymn_video_flow.py")
CANONICAL_MODULE = Path(
    "/mnt/c/work/godowon-office/godo-hymns/tools/hymn_letter_visual_template.py"
)
CANONICAL_MODULE_SHA256 = (
    "0634d97c6eaa0a79f667108b551a7f65b0985bf810bd7e6ce9f950daab52cf80"
)
CANONICAL_BUNDLE = Path(
    "/mnt/c/work/godowon-office/output/"
    "찬송편지_시작영상_개선작업본_2026-08-18/02_project/"
    "v17_unified_template/common"
)
CANONICAL_LOCK_SHA256 = (
    "915c84bcb6d91b3d51fac77662baf10de9e6f51aed63784ab6a860f2a174698e"
)
EPISODE_INVENTORY = (
    SCRIPT.parent.parent / "references" / "episode-inventory.json"
)
EPISODE_INVENTORY_SHA256 = (
    "e03eb7974cd6f4726f0a07e8b64a0d128c95caf6b77e80d5e56b55742e50a711"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class CliTestCase(unittest.TestCase):
    def run_cli(self, *arguments: object) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
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


class BuildTimelineTests(CliTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-flow-timeline-")
        self.root = Path(self.temporary.name)
        (self.root / "background.ppm").write_bytes(b"background")
        (self.root / "caption's frame.ppm").write_bytes(b"caption")
        self.spec = {
            "schema": "plugify.hymn-letter.still-timeline/1",
            "fps": 30,
            "expected_frames": 768,
            "intervals": [
                {"file": "background.ppm", "frames": 723},
                {"file": "caption's frame.ppm", "frames": 45},
            ],
        }
        self.spec_path = self.root / "job.json"
        write_json(self.spec_path, self.spec)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, spec: Path | None = None, output: Path | None = None):
        return self.run_cli(
            "build-timeline",
            "--spec",
            spec or self.spec_path,
            "--output",
            output or self.root / "timeline.ffconcat",
        )

    def test_builds_absolute_frame_locked_timeline_and_refuses_overwrite(self) -> None:
        output = self.root / "timeline.ffconcat"
        result = self.invoke(output=output)
        payload = self.assert_success_json(result)
        self.assertEqual(payload["fps"], 30)
        self.assertEqual(payload["expected_frames"], 768)
        self.assertEqual(payload["interval_count"], 2)
        self.assertEqual(payload["spec_sha256"], sha256(self.spec_path))
        self.assertEqual(payload["output_sha256"], sha256(output))

        background = str((self.root / "background.ppm").resolve())
        caption = str((self.root / "caption's frame.ppm").resolve()).replace("'", "'\\''")
        expected = [
            "ffconcat version 1.0",
            f"file '{background}'",
            "option framerate 30",
            "duration 24.100000000",
            f"file '{caption}'",
            "option framerate 30",
            "duration 1.500000000",
            f"file '{caption}'",
            "option framerate 30",
        ]
        self.assertEqual(output.read_text(encoding="utf-8").splitlines(), expected)
        before = output.read_bytes()
        overwrite = self.invoke(output=output)
        self.assert_failure(overwrite, 7)
        self.assertEqual(output.read_bytes(), before)

    def test_rejects_strict_schema_and_numeric_failures_without_output(self) -> None:
        mutations: list[tuple[str, object]] = [
            ("wrong-schema", {**self.spec, "schema": "wrong"}),
            ("extra-top", {**self.spec, "extra": 1}),
            ("boolean-fps", {**self.spec, "fps": True}),
            ("zero-fps", {**self.spec, "fps": 0}),
            ("fractional-fps", {**self.spec, "fps": 29.97}),
            ("fps-above-supported-range", {**self.spec, "fps": 1001}),
            ("oversized-fps", {**self.spec, "fps": 1 << 63}),
            ("wrong-sum", {**self.spec, "expected_frames": 769}),
            ("boolean-total", {**self.spec, "expected_frames": True}),
            (
                "expected-frames-above-limit",
                {**self.spec, "expected_frames": 2_147_483_648},
            ),
            (
                "interval-frames-above-limit",
                {
                    **self.spec,
                    "expected_frames": 1,
                    "intervals": [
                        {"file": "background.ppm", "frames": 2_147_483_648}
                    ],
                },
            ),
            (
                "interval-sum-above-limit",
                {
                    **self.spec,
                    "expected_frames": 2_147_483_647,
                    "intervals": [
                        {"file": "background.ppm", "frames": 2_147_483_647},
                        {"file": "caption's frame.ppm", "frames": 1},
                    ],
                },
            ),
            ("empty", {**self.spec, "intervals": []}),
            (
                "extra-interval-key",
                {
                    **self.spec,
                    "intervals": [
                        self.spec["intervals"][0],
                        {**self.spec["intervals"][1], "duration": 1.5},
                    ],
                },
            ),
            (
                "zero-frames",
                {
                    **self.spec,
                    "intervals": [
                        self.spec["intervals"][0],
                        {"file": "caption's frame.ppm", "frames": 0},
                    ],
                },
            ),
        ]
        for name, payload in mutations:
            with self.subTest(name=name):
                spec_path = self.root / f"{name}.json"
                output = self.root / f"{name}.ffconcat"
                write_json(spec_path, payload)
                self.assert_failure(self.invoke(spec_path, output), 2)
                self.assertFalse(os.path.lexists(output))

    def test_rejects_duplicate_json_keys_missing_media_and_missing_output_parent(self) -> None:
        duplicate = self.root / "duplicate.json"
        duplicate.write_text(
            '{"schema":"plugify.hymn-letter.still-timeline/1",'
            '"schema":"plugify.hymn-letter.still-timeline/1",'
            '"fps":30,"expected_frames":1,'
            '"intervals":[{"file":"background.ppm","frames":1}]}\n',
            encoding="utf-8",
        )
        self.assert_failure(self.invoke(duplicate, self.root / "duplicate.ffconcat"), 2)

        missing_payload = copy.deepcopy(self.spec)
        missing_payload["intervals"][1]["file"] = "missing.ppm"
        missing_spec = self.root / "missing.json"
        write_json(missing_spec, missing_payload)
        self.assert_failure(self.invoke(missing_spec, self.root / "missing.ffconcat"), 3)

        output = self.root / "absent-parent" / "timeline.ffconcat"
        self.assert_failure(self.invoke(output=output), 3)
        self.assertFalse(os.path.lexists(output))

    def test_maximum_valid_fps_preserves_large_frame_duration(self) -> None:
        payload = {
            "schema": "plugify.hymn-letter.still-timeline/1",
            "fps": 1000,
            "expected_frames": 2_147_483_647,
            "intervals": [
                {"file": "background.ppm", "frames": 2_147_483_647}
            ],
        }
        spec = self.root / "large-fps.json"
        output = self.root / "large-fps.ffconcat"
        write_json(spec, payload)
        self.assert_success_json(self.invoke(spec, output))
        duration = next(
            line.split(maxsplit=1)[1]
            for line in output.read_text(encoding="utf-8").splitlines()
            if line.startswith("duration ")
        )
        self.assertEqual(duration, "2147483.647000000")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_dangling_output_symlink_without_creating_target(self) -> None:
        target = self.root / "must-not-be-created.ffconcat"
        output_link = self.root / "dangling-output.ffconcat"
        output_link.symlink_to(target)
        self.assert_failure(self.invoke(output=output_link), 7)
        self.assertTrue(output_link.is_symlink())
        self.assertFalse(target.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_output_parent_symlink_without_writing_through_alias(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.root / "output-alias"
        alias.symlink_to(outside, target_is_directory=True)
        escaped_output = outside / "escaped.ffconcat"
        self.assert_failure(self.invoke(output=alias / "escaped.ffconcat"), 7)
        self.assertFalse(escaped_output.exists())


class ValidateJobTests(CliTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-flow-job-")
        self.root = Path(self.temporary.name)
        self.assertTrue(CANONICAL_MODULE.is_file())
        self.assertEqual(sha256(CANONICAL_MODULE), CANONICAL_MODULE_SHA256)
        self.assertTrue((CANONICAL_BUNDLE / "template.lock.json").is_file())
        self.assertEqual(
            sha256(CANONICAL_BUNDLE / "template.lock.json"), CANONICAL_LOCK_SHA256
        )
        self.assertTrue(EPISODE_INVENTORY.is_file())
        self.assertEqual(sha256(EPISODE_INVENTORY), EPISODE_INVENTORY_SHA256)

        self.program = self.root / "program.mp4"
        self.audio = self.root / "approved.m4a"
        self.captions = self.root / "captions.srt"
        self.program.write_bytes(b"program-video")
        self.audio.write_bytes(b"approved-audio")
        self.captions.write_text("1\n00:00:00,000 --> 00:00:01,000\ntext\n", encoding="utf-8")
        self.run_root = self.root / "new-run"
        self.job = {
            "schema": "plugify.hymn-letter.video-job/1",
            "project_id": "godowon-hymn-letter-26",
            "episode": {
                "id": "start",
                "kind": "start",
                "profile": "start-hybrid/v1",
            },
            "inputs": [
                {
                    "role": "program_video",
                    "path": str(self.program.resolve()),
                    "sha256": sha256(self.program),
                },
                {
                    "role": "approved_audio",
                    "path": str(self.audio.resolve()),
                    "sha256": sha256(self.audio),
                },
                {
                    "role": "captions",
                    "path": str(self.captions.resolve()),
                    "sha256": sha256(self.captions),
                },
            ],
            "visual_template": {
                "module_path": str(CANONICAL_MODULE.resolve()),
                "module_sha256": CANONICAL_MODULE_SHA256,
                "bundle_path": str(CANONICAL_BUNDLE.resolve()),
                "lock_sha256": CANONICAL_LOCK_SHA256,
                "version": "hymn-letter-visual-v2",
            },
            "output": {
                "run_root": str(self.run_root.resolve()),
                "filename": "start-01.mp4",
                "overwrite": False,
            },
            "delivery_intent": {
                "render": True,
                "drive_upload": False,
                "youtube_private_stage": False,
                "youtube_publish": False,
                "bot_notify": False,
            },
        }
        self.manifest = self.root / "job.json"
        write_json(self.manifest, self.job)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, payload: dict | None = None, name: str = "job"):
        manifest = self.root / f"{name}.json"
        write_json(manifest, self.job if payload is None else payload)
        return self.run_cli("validate-job", "--manifest", manifest)

    def copy_locked_bundle(self, name: str) -> tuple[Path, dict]:
        destination = self.root / name
        destination.mkdir()
        lock = json.loads(
            (CANONICAL_BUNDLE / "template.lock.json").read_text(encoding="utf-8")
        )
        relative_files = [
            Path("template.lock.json"),
            Path("template_config.json"),
            *(Path(relative) for relative in lock["assets"]),
        ]
        for relative in relative_files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CANONICAL_BUNDLE / relative, target)
        return destination, lock

    def test_validates_start_and_testimony_profiles_with_hashes_and_lock(self) -> None:
        result = self.invoke()
        payload = self.assert_success_json(result)
        self.assertEqual(payload["profile"], "start-hybrid/v1")
        self.assertEqual(payload["input_count"], 3)
        self.assertEqual(payload["manifest_sha256"], sha256(self.root / "job.json"))
        self.assertEqual(
            payload["inputs"],
            [
                {
                    "role": item["role"],
                    "path": str(Path(item["path"]).resolve()),
                    "sha256": item["sha256"],
                }
                for item in self.job["inputs"]
            ],
        )
        self.assertEqual(
            payload["template"]["module_sha256"], CANONICAL_MODULE_SHA256
        )
        self.assertEqual(
            payload["episode_inventory"],
            {
                "path": str(EPISODE_INVENTORY.resolve()),
                "sha256": EPISODE_INVENTORY_SHA256,
            },
        )
        self.assertFalse(self.run_root.exists())

        for episode_id in ("hymn-491-testimony", "hymn-370-testimony"):
            with self.subTest(episode_id=episode_id):
                testimony = copy.deepcopy(self.job)
                testimony["episode"] = {
                    "id": episode_id,
                    "kind": "testimony_intro",
                    "profile": "testimony-static/v1",
                }
                testimony["inputs"] = [
                    item
                    for item in testimony["inputs"]
                    if item["role"] != "program_video"
                ]
                result = self.invoke(testimony, episode_id)
                payload = self.assert_success_json(result)
                self.assertEqual(payload["episode_id"], episode_id)
                self.assertEqual(payload["profile"], "testimony-static/v1")
                self.assertEqual(payload["input_count"], 2)

    @unittest.skipUnless(Path("/proc/self/fd").is_dir(), "/proc fd inspection unavailable")
    def test_rejects_manifest_changed_after_its_parsed_bytes_are_hashed(self) -> None:
        large_program = self.root / "large-program.mp4"
        with large_program.open("wb") as handle:
            handle.truncate(128 * 1024 * 1024)
        job = copy.deepcopy(self.job)
        job["inputs"][0]["path"] = str(large_program.resolve())
        job["inputs"][0]["sha256"] = sha256(large_program)
        manifest = self.root / "manifest-race.json"
        write_json(manifest, job)

        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "validate-job", "--manifest", str(manifest)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        replaced = False
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            try:
                descriptors = list(Path(f"/proc/{process.pid}/fd").iterdir())
            except OSError:
                descriptors = []
            for descriptor in descriptors:
                try:
                    opened_path = os.readlink(descriptor)
                except OSError:
                    continue
                if opened_path == str(large_program.resolve()):
                    changed_job = copy.deepcopy(job)
                    changed_job["delivery_intent"]["bot_notify"] = True
                    write_json(manifest, changed_job)
                    replaced = True
                    break
            if replaced:
                break
            time.sleep(0.001)
        stdout, stderr = process.communicate(timeout=60)
        self.assertTrue(replaced, "did not observe the large-input hash window")
        self.assertEqual(process.returncode, 7, stderr)
        self.assertEqual(stdout, "")
        self.assertIn("ERROR[7]", stderr)

    def test_rejects_schema_shape_roles_and_delivery_types(self) -> None:
        cases: list[tuple[str, dict]] = []
        cases.append(("extra-top", {**self.job, "extra": True}))

        extra_episode = copy.deepcopy(self.job)
        extra_episode["episode"]["title"] = "forbidden"
        cases.append(("extra-episode", extra_episode))

        duplicate_role = copy.deepcopy(self.job)
        duplicate_role["inputs"].append(copy.deepcopy(duplicate_role["inputs"][0]))
        cases.append(("duplicate-role", duplicate_role))

        unknown_role = copy.deepcopy(self.job)
        unknown_role["inputs"][0]["role"] = "unknown"
        cases.append(("unknown-role", unknown_role))

        missing_required = copy.deepcopy(self.job)
        missing_required["inputs"] = [
            item for item in missing_required["inputs"] if item["role"] != "program_video"
        ]
        cases.append(("missing-role", missing_required))

        wrong_kind = copy.deepcopy(self.job)
        wrong_kind["episode"]["kind"] = "testimony_intro"
        cases.append(("wrong-kind", wrong_kind))

        relative_input = copy.deepcopy(self.job)
        relative_input["inputs"][0]["path"] = "program.mp4"
        cases.append(("relative-input", relative_input))

        overwrite = copy.deepcopy(self.job)
        overwrite["output"]["overwrite"] = True
        cases.append(("overwrite", overwrite))

        nested_filename = copy.deepcopy(self.job)
        nested_filename["output"]["filename"] = "nested/video.mp4"
        cases.append(("nested-filename", nested_filename))

        bad_delivery = copy.deepcopy(self.job)
        bad_delivery["delivery_intent"]["render"] = 1
        cases.append(("bad-delivery", bad_delivery))

        publish_without_stage = copy.deepcopy(self.job)
        publish_without_stage["delivery_intent"]["youtube_publish"] = True
        cases.append(("publish-without-stage", publish_without_stage))

        for name, payload in cases:
            with self.subTest(name=name):
                self.assert_failure(self.invoke(payload, name), 2)

    def test_rejects_missing_and_hash_or_lock_mismatches(self) -> None:
        bad_hash = copy.deepcopy(self.job)
        bad_hash["inputs"][1]["sha256"] = "0" * 64
        self.assert_failure(self.invoke(bad_hash, "bad-input-hash"), 4)

        missing = copy.deepcopy(self.job)
        missing["inputs"][1]["path"] = str((self.root / "missing.m4a").resolve())
        self.assert_failure(self.invoke(missing, "missing-input"), 3)

        bad_module_hash = copy.deepcopy(self.job)
        bad_module_hash["visual_template"]["module_sha256"] = "0" * 64
        self.assert_failure(self.invoke(bad_module_hash, "bad-module-hash"), 4)

        drift_module = self.root / "drift-module.py"
        drift_module.write_bytes(CANONICAL_MODULE.read_bytes())
        bad_module_path = copy.deepcopy(self.job)
        bad_module_path["visual_template"]["module_path"] = str(drift_module.resolve())
        self.assert_failure(self.invoke(bad_module_path, "bad-module-path"), 7)

        alias_module_path = copy.deepcopy(self.job)
        alias_module_path["visual_template"]["module_path"] = (
            "/mnt/c/work/godowon-office/godo-hymns/tools/../tools/"
            "hymn_letter_visual_template.py"
        )
        self.assert_failure(self.invoke(alias_module_path, "alias-module-path"), 7)

        dot_alias_module_path = copy.deepcopy(self.job)
        dot_alias_module_path["visual_template"]["module_path"] = (
            "/mnt/c/work/godowon-office/godo-hymns/tools/./"
            "hymn_letter_visual_template.py"
        )
        self.assert_failure(
            self.invoke(dot_alias_module_path, "dot-alias-module-path"), 7
        )

        slash_alias_module_path = copy.deepcopy(self.job)
        slash_alias_module_path["visual_template"]["module_path"] = (
            "/mnt/c/work/godowon-office/godo-hymns//tools/"
            "hymn_letter_visual_template.py"
        )
        self.assert_failure(
            self.invoke(slash_alias_module_path, "slash-alias-module-path"), 7
        )

        non_string_module_path = copy.deepcopy(self.job)
        non_string_module_path["visual_template"]["module_path"] = 42
        self.assert_failure(
            self.invoke(non_string_module_path, "non-string-module-path"), 2
        )

        bad_lock_hash = copy.deepcopy(self.job)
        bad_lock_hash["visual_template"]["lock_sha256"] = "0" * 64
        self.assert_failure(self.invoke(bad_lock_hash, "bad-lock-hash"), 4)

        bad_version = copy.deepcopy(self.job)
        bad_version["visual_template"]["version"] = "hymn-letter-visual-v3"
        self.assert_failure(self.invoke(bad_version, "bad-version"), 4)

        bad_project = copy.deepcopy(self.job)
        bad_project["project_id"] = "different-project"
        self.assert_failure(self.invoke(bad_project, "bad-project"), 2)

    def test_returns_unsupported_profile_and_refuses_existing_target(self) -> None:
        unsupported = copy.deepcopy(self.job)
        unsupported["episode"] = {
            "id": "hymn-lyrics-001",
            "kind": "hymn_lyrics",
            "profile": "hymn-lyrics/v1",
        }
        self.assert_failure(self.invoke(unsupported, "unsupported"), 6)

        malformed_unsupported = copy.deepcopy(unsupported)
        del malformed_unsupported["delivery_intent"]["bot_notify"]
        self.assert_failure(
            self.invoke(malformed_unsupported, "malformed-unsupported"), 2
        )

        self.run_root.mkdir()
        target = self.run_root / self.job["output"]["filename"]
        target.write_bytes(b"existing")
        self.assert_failure(self.invoke(name="existing-target"), 7)
        self.assertEqual(target.read_bytes(), b"existing")

    def test_enforces_pinned_episode_map_and_rejects_profile_relabels(self) -> None:
        unknown_lyric_id_as_testimony = copy.deepcopy(self.job)
        unknown_lyric_id_as_testimony["episode"] = {
            "id": "hymn-491-lyrics",
            "kind": "testimony_intro",
            "profile": "testimony-static/v1",
        }
        unknown_lyric_id_as_testimony["inputs"] = [
            item
            for item in unknown_lyric_id_as_testimony["inputs"]
            if item["role"] != "program_video"
        ]
        result = self.invoke(
            unknown_lyric_id_as_testimony, "unknown-lyric-id-as-testimony"
        )
        self.assert_failure(result, 6)
        self.assertIn("UNSUPPORTED_EPISODE", result.stderr)

        known_testimony_as_lyrics = copy.deepcopy(self.job)
        known_testimony_as_lyrics["episode"] = {
            "id": "hymn-491-testimony",
            "kind": "hymn_lyrics",
            "profile": "hymn-lyrics/v1",
        }
        result = self.invoke(known_testimony_as_lyrics, "known-testimony-as-lyrics")
        self.assert_failure(result, 2)

        known_start_as_testimony = copy.deepcopy(self.job)
        known_start_as_testimony["episode"] = {
            "id": "start",
            "kind": "testimony_intro",
            "profile": "testimony-static/v1",
        }
        result = self.invoke(known_start_as_testimony, "known-start-as-testimony")
        self.assert_failure(result, 2)

    def test_rejects_missing_or_changed_locked_bundle_files(self) -> None:
        missing_config_bundle, _lock = self.copy_locked_bundle("missing-config-bundle")
        (missing_config_bundle / "template_config.json").unlink()
        missing_config = copy.deepcopy(self.job)
        missing_config["visual_template"]["bundle_path"] = str(
            missing_config_bundle.resolve()
        )
        self.assert_failure(self.invoke(missing_config, "missing-config"), 3)

        changed_config_bundle, _lock = self.copy_locked_bundle("changed-config-bundle")
        (changed_config_bundle / "template_config.json").write_bytes(b"changed")
        changed_config = copy.deepcopy(self.job)
        changed_config["visual_template"]["bundle_path"] = str(
            changed_config_bundle.resolve()
        )
        self.assert_failure(self.invoke(changed_config, "changed-config"), 4)

        missing_asset_bundle, lock = self.copy_locked_bundle("missing-asset-bundle")
        first_asset = Path(sorted(lock["assets"])[0])
        (missing_asset_bundle / first_asset).unlink()
        missing_asset = copy.deepcopy(self.job)
        missing_asset["visual_template"]["bundle_path"] = str(
            missing_asset_bundle.resolve()
        )
        self.assert_failure(self.invoke(missing_asset, "missing-asset"), 3)

        changed_asset_bundle, lock = self.copy_locked_bundle("changed-asset-bundle")
        first_asset = Path(sorted(lock["assets"])[0])
        changed_asset_path = changed_asset_bundle / first_asset
        changed_asset_path.unlink()
        changed_asset_path.write_bytes(b"changed")
        changed_asset = copy.deepcopy(self.job)
        changed_asset["visual_template"]["bundle_path"] = str(
            changed_asset_bundle.resolve()
        )
        self.assert_failure(self.invoke(changed_asset, "changed-asset"), 4)

    def test_supported_profiles_reject_lyrics_and_playlist_only_roles(self) -> None:
        extra = self.root / "forbidden-role.json"
        extra.write_text("{}\n", encoding="utf-8")

        start = copy.deepcopy(self.job)
        start["inputs"].append(
            {
                "role": "lyrics",
                "path": str(extra.resolve()),
                "sha256": sha256(extra),
            }
        )
        self.assert_failure(self.invoke(start, "start-with-lyrics"), 2)

        testimony = copy.deepcopy(self.job)
        testimony["episode"] = {
            "id": "hymn-491-testimony",
            "kind": "testimony_intro",
            "profile": "testimony-static/v1",
        }
        testimony["inputs"] = [
            item for item in testimony["inputs"] if item["role"] != "program_video"
        ]
        testimony["inputs"].append(
            {
                "role": "track_manifest",
                "path": str(extra.resolve()),
                "sha256": sha256(extra),
            }
        )
        self.assert_failure(self.invoke(testimony, "testimony-with-playlist"), 2)

    def test_rejects_filesystem_root_as_run_root(self) -> None:
        payload = copy.deepcopy(self.job)
        payload["output"]["run_root"] = "/"
        self.assert_failure(self.invoke(payload, "filesystem-root"), 7)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_run_root_with_symlink_ancestor(self) -> None:
        outside = self.root / "outside-run-root"
        outside.mkdir()
        alias = self.root / "run-root-alias"
        alias.symlink_to(outside, target_is_directory=True)
        payload = copy.deepcopy(self.job)
        payload["output"]["run_root"] = str(alias / "new-run")
        self.assert_failure(self.invoke(payload, "alias-run-root"), 7)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_symlink_input(self) -> None:
        link = self.root / "audio-link.m4a"
        link.symlink_to(self.audio)
        payload = copy.deepcopy(self.job)
        payload["inputs"][1]["path"] = str(link.absolute())
        self.assert_failure(self.invoke(payload, "symlink-input"), 7)


class VerifyPackageTests(CliTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-flow-package-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_package(self, name: str) -> tuple[Path, Path]:
        package = self.root / name
        (package / "QC").mkdir(parents=True)
        (package / "video.mp4").write_bytes(b"video")
        (package / "QC" / "report.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
        sums = package / "SHA256SUMS.txt"
        sums.write_text(
            f"{sha256(package / 'video.mp4')}  ./video.mp4\n"
            f"{sha256(package / 'QC' / 'report.json')}  ./QC/report.json\n",
            encoding="utf-8",
        )
        return package, sums

    def invoke(self, package: Path, sums: Path | str = "SHA256SUMS.txt"):
        return self.run_cli(
            "verify-package", "--package-dir", package, "--sums", sums
        )

    def test_verifies_exact_payload_set_and_hashes(self) -> None:
        package, sums = self.make_package("valid")
        payload = self.assert_success_json(self.invoke(package))
        self.assertEqual(payload["payload_count"], 2)
        self.assertEqual(payload["sums_sha256"], sha256(sums))
        self.assertEqual(Path(payload["package_dir"]), package.resolve())

        second, second_sums = self.make_package("valid-absolute")
        payload = self.assert_success_json(self.invoke(second, second_sums.resolve()))
        self.assertEqual(payload["payload_count"], 2)

    def test_rejects_hash_duplicate_and_non_exact_payload_set(self) -> None:
        package, _sums = self.make_package("hash-mismatch")
        (package / "video.mp4").write_bytes(b"changed")
        self.assert_failure(self.invoke(package), 4)

        package, sums = self.make_package("duplicate")
        first_line = sums.read_text(encoding="utf-8").splitlines()[0]
        sums.write_text(sums.read_text(encoding="utf-8") + first_line + "\n", encoding="utf-8")
        self.assert_failure(self.invoke(package), 11)

        package, _sums = self.make_package("extra")
        (package / "unlisted.txt").write_text("extra", encoding="utf-8")
        self.assert_failure(self.invoke(package), 11)

        package, sums = self.make_package("lists-sums")
        sums.write_text(
            sums.read_text(encoding="utf-8") + f"{'0' * 64}  ./SHA256SUMS.txt\n",
            encoding="utf-8",
        )
        self.assert_failure(self.invoke(package), 11)

    def test_rejects_traversal_outside_sums_and_missing_package(self) -> None:
        package, sums = self.make_package("traversal")
        sums.write_text(f"{'0' * 64}  ../outside.mp4\n", encoding="utf-8")
        self.assert_failure(self.invoke(package), 7)

        outside = self.root / "outside-sums.txt"
        outside.write_text(f"{'0' * 64}  ./video.mp4\n", encoding="utf-8")
        package, _ = self.make_package("outside")
        self.assert_failure(self.invoke(package, outside.resolve()), 7)

        self.assert_failure(self.invoke(self.root / "missing"), 3)

    @unittest.skipUnless(Path("/proc/self/fd").is_dir(), "/proc fd inspection unavailable")
    def test_rejects_payload_replaced_while_later_large_file_is_hashed(self) -> None:
        package = self.root / "race"
        package.mkdir()
        first = package / "a-first.bin"
        large = package / "z-large.bin"
        first.write_bytes(b"first-version")
        with large.open("wb") as handle:
            handle.truncate(256 * 1024 * 1024)
        sums = package / "SHA256SUMS.txt"
        sums.write_text(
            f"{sha256(first)}  ./a-first.bin\n"
            f"{sha256(large)}  ./z-large.bin\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "verify-package",
                "--package-dir",
                str(package),
                "--sums",
                str(sums),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        replaced = False
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            descriptor_dir = Path(f"/proc/{process.pid}/fd")
            try:
                descriptors = list(descriptor_dir.iterdir())
            except OSError:
                descriptors = []
            for descriptor in descriptors:
                try:
                    opened_path = os.readlink(descriptor)
                except OSError:
                    continue
                if opened_path == str(large.resolve()):
                    first.write_bytes(b"second-version")
                    replaced = True
                    break
            if replaced:
                break
            time.sleep(0.001)
        stdout, stderr = process.communicate(timeout=60)
        self.assertTrue(replaced, "did not observe the large-file hash window")
        self.assertEqual(process.returncode, 4, stderr)
        self.assertEqual(stdout, "")
        self.assertIn("ERROR[4]", stderr)

    @unittest.skipUnless(Path("/proc/self/fd").is_dir(), "/proc fd inspection unavailable")
    def test_rejects_early_payload_replaced_during_second_pass_large_hash(self) -> None:
        package = self.root / "second-pass-race"
        package.mkdir()
        first = package / "a-first.bin"
        large = package / "z-large.bin"
        with first.open("wb") as handle:
            handle.truncate(32 * 1024 * 1024)
        with large.open("wb") as handle:
            handle.truncate(256 * 1024 * 1024)
        sums = package / "SHA256SUMS.txt"
        sums.write_text(
            f"{sha256(first)}  ./a-first.bin\n"
            f"{sha256(large)}  ./z-large.bin\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "verify-package",
                "--package-dir",
                str(package),
                "--sums",
                str(sums),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        saw_first_large_open = False
        saw_gap_after_first_large = False
        replaced = False
        deadline = time.monotonic() + 30
        large_path = str(large.resolve())
        while process.poll() is None and time.monotonic() < deadline:
            try:
                descriptors = list(Path(f"/proc/{process.pid}/fd").iterdir())
            except OSError:
                descriptors = []
            large_is_open = False
            for descriptor in descriptors:
                try:
                    opened_path = os.readlink(descriptor)
                except OSError:
                    continue
                if opened_path == large_path:
                    large_is_open = True
                    break
            if large_is_open and not saw_first_large_open:
                saw_first_large_open = True
            elif saw_first_large_open and not large_is_open:
                saw_gap_after_first_large = True
            elif saw_gap_after_first_large and large_is_open:
                first.write_bytes(b"changed-after-second-pass-first-hash")
                replaced = True
                break
            time.sleep(0.001)
        stdout, stderr = process.communicate(timeout=60)
        self.assertTrue(replaced, "did not observe the second-pass large-file window")
        self.assertEqual(process.returncode, 4, stderr)
        self.assertEqual(stdout, "")
        self.assertIn("ERROR[4]", stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_rejects_symlink_payload_and_package_root(self) -> None:
        package, _sums = self.make_package("symlink-payload")
        (package / "linked.mp4").symlink_to(package / "video.mp4")
        self.assert_failure(self.invoke(package), 7)

        target, _target_sums = self.make_package("real-package")
        link = self.root / "package-link"
        link.symlink_to(target, target_is_directory=True)
        self.assert_failure(self.invoke(link), 7)


class UsageTests(CliTestCase):
    def test_argparse_usage_is_exit_two(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
