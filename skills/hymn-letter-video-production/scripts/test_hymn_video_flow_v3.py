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
INVENTORY = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["episodes"]
INVENTORY_BY_ID = {episode["episode_id"]: episode for episode in INVENTORY}
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
        "audio": "video/mp4",
        "captions": "text/plain",
        "chapters": "text/plain",
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


class V3FixtureMixin:
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hymn-flow-v3-")
        self.root = Path(self.temporary.name)
        self.release_root = self.root / "release"
        (self.release_root / "jobs").mkdir(parents=True)
        self.office_root = self.root / "godowon-office"
        (self.office_root / "godo-hymns" / "tools").mkdir(parents=True)
        self._write_stub(
            self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_profiles.py",
            "render",
        )
        self._write_stub(
            self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_qc.py",
            "qc",
        )
        for name in (
            "hymn_letter_caption_v3.py",
            "hymn_letter_v3_mp4.py",
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
            "import json, sys\n"
            f"print(json.dumps({{'delegate':'{stage}','status':'{status}','argv':sys.argv[1:]}}))\n",
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
            return {"intro_frames": 723, "intro_style": "center", "post_style": "dense"}
        if episode["profile"] == "playlist/v1":
            return {
                "style": "dense",
                "active_row_state": "yellow",
                "active_row_frame_boundaries": [0, 100, 200, 300],
                "title_card_policy": {
                    "mode": "playlist-prior-outro/v1",
                    "expected_titles": ["1장 첫 곡", "2장 둘째 곡", "3장 셋째 곡"],
                    "expected_active_rows": [1, 1, 2],
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
                for index in range(3):
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

        source_bundle = {
            "schema": "godowon.hymn-letter.source-bundle/1",
            "release_id": "hymn-letter-caption-v3-20260822",
            "storage_layout": "objects/sha256/<prefix>/<digest-rest>",
            "objects": object_entries,
        }
        source_bundle_path = self.release_root / "source-bundle.lock.json"
        write_json(source_bundle_path, source_bundle)
        source_bundle_sha = sha256(source_bundle_path)

        environment_lock = self.release_root / "environment.lock.json"
        golden_lock = self.release_root / "golden.lock.json"
        write_json(environment_lock, {"schema": "env/1", "release_id": "hymn-letter-caption-v3-20260822"})
        write_json(golden_lock, {"schema": "golden/1", "release_id": "hymn-letter-caption-v3-20260822"})

        settings = self._settings_for(episode)
        if episode["profile"] == "playlist/v1":
            settings["active_row_frame_boundaries"] = [0, 100, 200, episode["frame_count"]]

        job = {
            "schema": "godowon.hymn-letter.v3-job/1",
            "release_id": "hymn-letter-caption-v3-20260822",
            "episode_id": episode["episode_id"],
            "profile": episode["profile"],
            "inputs": inputs,
            "settings": settings,
            "output": {
                "filename": f"{episode['sequence']:02d}_{episode['episode_id']}.{episode['container']}",
                "thumbnail_filename": f"{episode['sequence']:02d}_thumb.jpg",
                "container": episode["container"],
                "frame_count": episode["frame_count"],
            },
        }
        job_path = self.release_root / "jobs" / f"{episode['sequence']:02d}.json"
        write_json(job_path, job)
        job_sha = sha256(job_path)

        renderer_modules = {}
        module_names = {
            "caption": "hymn_letter_caption_v3.py",
            "profiles": "hymn_letter_v3_profiles.py",
            "mp4": "hymn_letter_v3_mp4.py",
            "qc": "hymn_letter_v3_qc.py",
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
            "release_id": "hymn-letter-caption-v3-20260822",
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

    def test_rejects_playlist_title_card_row_regression(self) -> None:
        fixture = self.make_fixture("02-playlist")
        job = json.loads(fixture["job"].read_text(encoding="utf-8"))
        job["settings"]["title_card_policy"]["expected_active_rows"] = [1, 1, 1]
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
        self.assertEqual(payload["referenced_object_count"], 8)

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


class RenderAndQcV3Tests(V3FixtureMixin, PortableCliTestCase):
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
        qc_script = self.office_root / "godo-hymns" / "tools" / "hymn_letter_v3_qc.py"
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


class UsageTests(PortableCliTestCase):
    def test_argparse_usage_is_exit_two(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
