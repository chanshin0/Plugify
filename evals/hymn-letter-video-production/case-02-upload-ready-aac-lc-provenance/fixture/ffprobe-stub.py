#!/usr/bin/env python3
"""Hermetic ffprobe-shaped probe for text media fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    if len(sys.argv) < 2:
        fail("fixture ffprobe requires a media path")
    path = Path(sys.argv[-1]).resolve()
    if not path.is_file():
        fail(f"fixture media missing: {path}")
    values: dict[str, str] = {}
    for token in path.read_text(encoding="utf-8").strip().split():
        if "=" not in token:
            fail(f"invalid fixture token: {token!r}")
        key, value = token.split("=", 1)
        values[key] = value
    required = {
        "kind", "sequence", "container", "major_brand", "codec", "profile",
        "sample_rate", "channels", "bit_rate", "audio_payload",
    }
    optional = {
        "video_fingerprint", "frame_count", "track", "skip_samples",
        "discard_padding", "decoded_pcm",
    }
    if set(values) - (required | optional) or not required <= set(values):
        fail(f"invalid fixture media keys: {sorted(values)}")
    if values["kind"] == "final" and not {"video_fingerprint", "frame_count"} <= set(values):
        fail("final fixture requires video_fingerprint and frame_count")
    if "track" in values and not {"skip_samples", "discard_padding", "decoded_pcm"} <= set(values):
        fail("track fixture requires gapless/PCM fields")
    log_path = os.environ.get("FFPROBE_LOG")
    if log_path:
        with Path(log_path).open("a", encoding="utf-8") as handle:
            handle.write(str(path) + "\n")
    streams: list[dict[str, object]] = []
    if values["kind"] == "final":
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
    streams.append(
        {
            "index": len(streams),
            "codec_type": "audio",
            "codec_name": values["codec"],
            "profile": values["profile"],
            "sample_rate": values["sample_rate"],
            "channels": int(values["channels"]),
            "bit_rate": values["bit_rate"],
            "tags": {
                "payload_sha256": values["audio_payload"],
                **({"decoded_pcm_sha256": values["decoded_pcm"]} if "decoded_pcm" in values else {}),
            },
            **(
                {
                    "side_data_list": [
                        {
                            "side_data_type": "Skip Samples",
                            "skip_samples": int(values["skip_samples"]),
                            "discard_padding": int(values["discard_padding"]),
                        }
                    ]
                }
                if "track" in values
                else {}
            ),
        }
    )
    container = values["container"]
    if container == "mp3":
        format_name = "mp3"
    elif container in {"mp4", "mov", "m4a"}:
        format_name = "mov,mp4,m4a,3gp,3g2,mj2"
    else:
        format_name = container
    payload = {
        "streams": streams,
        "format": {
            "filename": str(path),
            "format_name": format_name,
            "tags": {"major_brand": values["major_brand"]},
        },
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
