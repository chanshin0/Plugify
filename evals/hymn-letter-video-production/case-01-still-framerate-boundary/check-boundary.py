#!/usr/bin/env python3
"""Deterministic actual-frame regression for ffconcat still-image timing."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixture" / "job.json"
EXPECTED_SIGNATURE = {722: "background", 723: "caption", 724: "caption", 767: "caption"}
LEGACY_SIGNATURE = {722: "background", 723: "background", 724: "caption", 767: "caption"}


def fail(message: str, code: int = 1) -> None:
    print(f"FAIL {message}", file=sys.stderr)
    raise SystemExit(code)


def run(command: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if expect_success and result.returncode != 0:
        fail(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def find_ffmpeg(argument: str | None) -> str:
    candidate = argument or os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not candidate or not Path(candidate).is_file():
        fail("FFmpeg not found; pass --ffmpeg or set FFMPEG", 2)
    return str(Path(candidate).resolve())


def write_ppm(path: Path, rgb: tuple[int, int, int]) -> None:
    width = height = 16
    pixels = " ".join("%d %d %d" % rgb for _ in range(width * height))
    path.write_text(f"P3\n{width} {height}\n255\n{pixels}\n", encoding="ascii")


def quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def write_reference_timeline(spec: dict, output: Path, *, fixed: bool) -> None:
    fps = int(spec["fps"])
    lines = ["ffconcat version 1.0"]
    base = Path(spec["_base"])
    for interval in spec["intervals"]:
        lines.append(f"file '{quote(base / interval['file'])}'")
        if fixed:
            lines.append(f"option framerate {fps}")
        lines.append(f"duration {interval['frames'] / fps:.9f}")
    last = spec["intervals"][-1]
    lines.append(f"file '{quote(base / last['file'])}'")
    if fixed:
        lines.append(f"option framerate {fps}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def classify_pixel(pixel: bytes) -> str:
    red, green, blue = pixel
    channels = {"background": red, "accent": green, "caption": blue}
    winner = max(channels, key=channels.get)
    others = [value for key, value in channels.items() if key != winner]
    if channels[winner] <= max(others) + 100:
        fail(f"unrecognized pixel: {(red, green, blue)}")
    return winner


def render_labels(
    ffmpeg: str,
    timeline: Path,
    work: Path,
    *,
    fps: int,
    expected_frames: int,
) -> list[str]:
    video = work / f"{timeline.stem}.mkv"
    all_raw = work / f"{timeline.stem}.all.rgb"
    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(timeline),
            "-vf",
            f"fps={fps}",
            "-an",
            "-frames:v",
            str(expected_frames),
            "-c:v",
            "ffv1",
            str(video),
        ]
    )
    run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(video),
            "-vf",
            "scale=1:1,format=rgb24",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            str(all_raw),
        ]
    )
    decoded_frames, remainder = divmod(len(all_raw.read_bytes()), 3)
    if remainder or decoded_frames != expected_frames:
        fail(
            f"expected exactly {expected_frames} decoded frames, "
            f"got {decoded_frames} remainder={remainder}"
        )
    data = all_raw.read_bytes()
    return [classify_pixel(data[index : index + 3]) for index in range(0, len(data), 3)]


def render_signature(ffmpeg: str, timeline: Path, work: Path) -> dict[int, str]:
    labels = render_labels(ffmpeg, timeline, work, fps=30, expected_frames=768)
    return {frame: labels[frame] for frame in (722, 723, 724, 767)}


def inspect_timeline(path: Path, spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    fps = spec["fps"]
    intervals = spec["intervals"]
    expected_frames = spec["expected_frames"]
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_line_count = 1 + len(intervals) * 3 + 2
    if len(lines) != expected_line_count or lines[0] != "ffconcat version 1.0":
        fail(f"candidate timeline grammar/line count mismatch: {len(lines)} != {expected_line_count}")
    cursor = 1
    durations: list[float] = []
    for interval in intervals:
        expected_file = f"file '{quote(spec_path.parent / interval['file'])}'"
        if lines[cursor] != expected_file:
            fail(f"unexpected file line: {lines[cursor]!r} != {expected_file!r}")
        if lines[cursor + 1] != f"option framerate {fps}":
            fail(f"file entry is not exactly locked to {fps} fps: {lines[cursor + 1]!r}")
        if not lines[cursor + 2].startswith("duration "):
            fail(f"missing duration after file/option: {lines[cursor + 2]!r}")
        try:
            duration = float(lines[cursor + 2].split(maxsplit=1)[1])
        except (IndexError, ValueError):
            fail(f"invalid duration: {lines[cursor + 2]!r}")
        if abs(duration - interval["frames"] / fps) > 5e-10:
            fail(f"duration does not preserve frames: {duration}, interval={interval}")
        durations.append(duration)
        cursor += 3
    terminal_file = f"file '{quote(spec_path.parent / intervals[-1]['file'])}'"
    if lines[cursor:] != [terminal_file, f"option framerate {fps}"]:
        fail(f"terminal repeat grammar mismatch: {lines[cursor:]!r}")
    if round(sum(durations) * fps) != expected_frames:
        fail(f"duration/frame sum mismatch: durations={durations}, fps={fps}")


def invoke_candidate(candidate: Path, spec: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, str(candidate), "build-timeline", "--spec", str(spec), "--output", str(output)]
    )


def write_spec(
    path: Path,
    *,
    fps: object,
    frames: list[object],
    files: list[str] | None = None,
    schema: object = "plugify.hymn-letter.still-timeline/1",
    expected_frames: object | None = None,
) -> None:
    names = files or ["background.ppm", "caption.ppm"]
    total = sum(frame for frame in frames if isinstance(frame, int) and not isinstance(frame, bool))
    payload = {
        "schema": schema,
        "fps": fps,
        "expected_frames": total if expected_frames is None else expected_frames,
        "intervals": [
            {"file": name, "frames": frame}
            for name, frame in zip(names, frames, strict=True)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test(ffmpeg: str) -> None:
    with tempfile.TemporaryDirectory(prefix="hymn-letter-eval-", dir="/tmp") as temporary:
        work = Path(temporary)
        shutil.copy2(FIXTURE, work / "job.json")
        write_ppm(work / "background.ppm", (255, 0, 0))
        write_ppm(work / "caption.ppm", (0, 0, 255))
        spec = json.loads((work / "job.json").read_text(encoding="utf-8"))
        spec["_base"] = str(work)
        legacy = work / "legacy.ffconcat"
        reference = work / "reference.ffconcat"
        write_reference_timeline(spec, legacy, fixed=False)
        write_reference_timeline(spec, reference, fixed=True)
        legacy_actual = render_signature(ffmpeg, legacy, work)
        reference_actual = render_signature(ffmpeg, reference, work)
        if legacy_actual != LEGACY_SIGNATURE:
            fail(f"legacy incident signature changed: {legacy_actual}")
        if reference_actual != EXPECTED_SIGNATURE:
            fail(f"reference signature changed: {reference_actual}")
        print(f"PASS legacy incident reproduced: {legacy_actual}")
        print(f"PASS reference boundary exact: {reference_actual}")
        print("SELF_TEST 2/2")


def candidate_test(ffmpeg: str, candidate: Path) -> None:
    if not candidate.is_file():
        fail(f"candidate not found: {candidate}", 2)
    with tempfile.TemporaryDirectory(prefix="hymn-letter-candidate-", dir="/tmp") as temporary:
        work = Path(temporary)
        spec_path = work / "job.json"
        shutil.copy2(FIXTURE, spec_path)
        write_ppm(work / "background.ppm", (255, 0, 0))
        write_ppm(work / "caption.ppm", (0, 0, 255))

        timeline = work / "candidate.ffconcat"
        invoke_candidate(candidate, spec_path, timeline)
        inspect_timeline(timeline, spec_path)
        actual = render_signature(ffmpeg, timeline, work)
        if actual != EXPECTED_SIGNATURE:
            fail(f"candidate actual-frame boundary mismatch: {actual}")
        print(f"PASS candidate actual-frame boundary: {actual}")

        before = timeline.read_bytes()
        overwrite = run(
            [sys.executable, str(candidate), "build-timeline", "--spec", str(spec_path), "--output", str(timeline)],
            expect_success=False,
        )
        if overwrite.returncode == 0 or timeline.read_bytes() != before:
            fail("candidate overwrote an existing timeline")
        print("PASS fail-closed existing output")

        invalid_payloads: list[tuple[str, dict]] = []
        base_payload = json.loads(spec_path.read_text(encoding="utf-8"))
        invalid_payloads.extend(
            [
                ("wrong-schema", {**base_payload, "schema": "wrong"}),
                ("missing-schema", {key: value for key, value in base_payload.items() if key != "schema"}),
                ("wrong-sum", {**base_payload, "expected_frames": 769}),
                (
                    "missing-expected-frames",
                    {key: value for key, value in base_payload.items() if key != "expected_frames"},
                ),
                ("boolean-expected-frames", {**base_payload, "expected_frames": True}),
                ("zero-fps", {**base_payload, "fps": 0}),
                ("negative-fps", {**base_payload, "fps": -30}),
                ("fractional-fps", {**base_payload, "fps": 29.97}),
                ("string-fps", {**base_payload, "fps": "30"}),
                ("boolean-fps", {**base_payload, "fps": True}),
                ("missing-fps", {key: value for key, value in base_payload.items() if key != "fps"}),
                ("empty-intervals", {**base_payload, "intervals": []}),
                ("missing-intervals", {key: value for key, value in base_payload.items() if key != "intervals"}),
                ("non-list-intervals", {**base_payload, "intervals": {}}),
                ("non-object-interval", {**base_payload, "intervals": [base_payload["intervals"][0], "bad"]}),
                (
                    "zero-frames",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"file": "caption.ppm", "frames": 0}]},
                ),
                (
                    "negative-frames",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"file": "caption.ppm", "frames": -1}]},
                ),
                (
                    "fractional-frames",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"file": "caption.ppm", "frames": 44.5}]},
                ),
                (
                    "boolean-frames",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"file": "caption.ppm", "frames": True}]},
                ),
                (
                    "missing-frames",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"file": "caption.ppm"}]},
                ),
                (
                    "missing-file",
                    {**base_payload, "intervals": [base_payload["intervals"][0], {"frames": 45}]},
                ),
            ]
        )
        for name, payload in invalid_payloads:
            invalid_path = work / f"invalid-{name}.json"
            invalid_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            invalid_result = run(
                [
                    sys.executable,
                    str(candidate),
                    "build-timeline",
                    "--spec",
                    str(invalid_path),
                    "--output",
                    str(work / f"invalid-{name}.ffconcat"),
                ],
                expect_success=False,
            )
            invalid_output = work / f"invalid-{name}.ffconcat"
            if invalid_result.returncode == 0 or invalid_output.exists():
                fail(f"candidate accepted or wrote output for invalid payload: {name}")
        print(f"PASS fail-closed invalid manifests: {len(invalid_payloads)}/{len(invalid_payloads)}")

        generic = work / "generic-24.json"
        write_spec(generic, fps=24, frames=[241, 47])
        generic_timeline = work / "generic-24.ffconcat"
        invoke_candidate(candidate, generic, generic_timeline)
        inspect_timeline(generic_timeline, generic)
        generic_labels = render_labels(
            ffmpeg, generic_timeline, work, fps=24, expected_frames=288
        )
        if generic_labels != ["background"] * 241 + ["caption"] * 47:
            fail("24fps generic actual-frame intervals mismatch")
        write_ppm(work / "accent.ppm", (0, 255, 0))
        generic_three = work / "generic-17-three.json"
        write_spec(
            generic_three,
            fps=17,
            frames=[19, 23, 37],
            files=["caption.ppm", "accent.ppm", "background.ppm"],
        )
        generic_three_timeline = work / "generic-17-three.ffconcat"
        invoke_candidate(candidate, generic_three, generic_three_timeline)
        inspect_timeline(generic_three_timeline, generic_three)
        generic_three_labels = render_labels(
            ffmpeg, generic_three_timeline, work, fps=17, expected_frames=79
        )
        if generic_three_labels != ["caption"] * 19 + ["accent"] * 23 + ["background"] * 37:
            fail("17fps three-interval actual-frame intervals mismatch")
        print("PASS generic fps/frame/interval rule")
        print("SUMMARY 5/5")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--candidate", type=Path)
    arguments = parser.parse_args()
    ffmpeg = find_ffmpeg(arguments.ffmpeg)
    if arguments.self_test == bool(arguments.candidate):
        fail("choose exactly one of --self-test or --candidate", 2)
    if arguments.self_test:
        self_test(ffmpeg)
    else:
        candidate_test(ffmpeg, arguments.candidate.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
