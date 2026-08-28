#!/usr/bin/env python3
"""Check a planning response, never media quality or completion."""
import json
import sys
from pathlib import Path


def check(plan):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    require(plan.get("episode_sequences") == [7, 8], "scope must include 07 and 08")
    paths = plan.get("evidence_paths", [])
    require(isinstance(paths, list) and len(paths) >= 3, "missing inspected prior evidence")
    steps = plan.get("steps", [])
    expected = ["source-check", "prior-evidence-review", "script-audio-compare", "new-edl", "trim-concat", "speech-master", "edited-audio-srt", "listening-review", "pair-render-qc", "pair-delivery"]
    require(isinstance(steps, list) and all(s in steps for s in expected), "missing production stages")
    if isinstance(steps, list) and all(s in steps for s in expected):
        require([steps.index(s) for s in expected] == sorted(steps.index(s) for s in expected), "production stage order is invalid")
    for key in ("reuse_previous_cut_timestamps", "tts", "change_speech_speed", "transcription_is_final_audio", "pair_complete"):
        require(plan.get(key) is False, f"{key} must remain false in this case")
    require(plan.get("transcription_progress_basis") == "saved-completed-chunks", "ASR progress needs completed saved chunks")
    require(plan.get("episode8_audio_source") == "approved-hymn-catalog", "08 must use the approved hymn source")
    deliverables = plan.get("deliverables", {})
    for episode in ("7", "8"):
        roles = deliverables.get(episode, []) if isinstance(deliverables, dict) else []
        require(isinstance(roles, list) and {"audio", "mp4", "ko.srt", "thumbnail", "backplate", "qc", "metadata"}.issubset(roles), f"episode {episode} delivery is incomplete")
    require(isinstance(deliverables, dict) and "edit-log" in deliverables.get("7", []), "07 needs an edit log")
    require(isinstance(plan.get("missing_inputs"), list) and len(plan["missing_inputs"]) > 0, "unavailable inputs must stay visible")
    require(plan.get("external_actions") == [], "no external mutation is authorized")
    return errors


if __name__ == "__main__":
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        failures = check(data)
    except (IndexError, OSError, ValueError, TypeError, AttributeError) as exc:
        failures = [f"invalid response: {exc}"]
    print(json.dumps({"scope": "planning-only", "passed": not failures, "failures": failures}, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)
