---
name: hymn-letter-video-production
description: "Produce, review, package, and route delivery for the 26-video Godowon Hymn Letter series with its locked visual template and approved scripts, captions, and audio. Use only for 고도원 찬송편지 start, testimony-introduction, hymn-lyrics, or 12-song playlist work; do not use for general video editing or unrelated hymn projects."
---

# 고도원 찬송편지 영상 제작

## Purpose

Run the evidence-backed production, review, packaging, and delivery flow for the single Godowon Hymn Letter project. The intended release has exactly 26 videos:

- one video explaining why the Hymn Letter begins;
- twelve hymn testimony/introduction videos;
- twelve matching hymn/lyrics videos;
- one playlist containing all twelve hymns.

Do not route ordinary YouTube editing, unrelated hymn videos, or general media work through this skill.

## Load the right reference

- Read [references/workflow.md](references/workflow.md) for any production, review, package, or delivery task.
- For the portable v3 path, read [references/job-manifest.v2.schema.json](references/job-manifest.v2.schema.json), [references/episode-inventory.v2.json](references/episode-inventory.v2.json), [references/source-bundle.schema.json](references/source-bundle.schema.json), [references/release-lock.schema.json](references/release-lock.schema.json), and [references/run-receipt.schema.json](references/run-receipt.schema.json). The Plugify filenames stay the same, but the actual producer schemas are office-native: `godowon.hymn-letter.v3-job/1`, `godowon.hymn-letter.v3-release-lock/1`, and `godowon.hymn-letter.source-bundle/1`.
- Keep [references/job-manifest.schema.json](references/job-manifest.schema.json) and [references/episode-inventory.json](references/episode-inventory.json) only for the historical v1 primitive path and already-built legacy review packages.
- Read [references/qc-contract.md](references/qc-contract.md) before rendering, reviewing, promoting, or packaging media.
- Read [references/authority-boundaries.md](references/authority-boundaries.md) before any render execution or external mutation.

## Non-negotiable invariants

- Preserve approved script, caption text and timing, and audio. Do not rewrite, split, trim, normalize, retime, or “improve” them without a newly approved source.
- For portable v3, load the sibling `godowon-office` release lock and use only the repo-relative renderer modules whose SHA-256 values it pins. The historical WSL v2 module is legacy-only.
- Never copy visual coordinates, font sizes, fitting logic, safe area, or still-image framerate into an episode-specific renderer or manifest.
- Never overwrite an existing output. Render to a new run/candidate and promote only after QC PASS.
- A generated layout or PNG is not sufficient QC. Decode the actual final H.264 and verify its cue/interval boundary frames.
- A local review package is not a portable renderer and is not evidence of Drive upload, YouTube state, or bot delivery.

## Profile gate

Only these profiles may appear in a portable v3 job:

- `start-hybrid/v1`: sequence 01, MP4 + AAC.
- `playlist/v1`: sequence 02, MOV + MP3.
- `testimony-static/v1`: sequences 03 and 05, MP4 + AAC.
- `hymn-lyrics/v1`: sequences 04 and 06, MOV + MP3.

The current v3 inventory is deliberately narrow: `01-start`, `02-playlist`, `03-491-testimony`, `04-491-hymn`, `05-370-testimony`, and `06-370-hymn`. Adding another episode still requires an approved inventory update, a new inventory hash, and regression validation.

## Operating workflow

1. Confirm that the request belongs to this 26-video project and identify the exact episode kind/profile.
2. Inventory approved inputs and ask only for missing human-owned choices or authority. Do not ask the user to perform routine checks the CLI can perform.
3. Create a manifest with the exact schema, hash every input, and run `validate-job`.
4. For v3 work, verify the content-addressed source bundle and release lock first. The renderer/QC wrapper is portable; the actual office renderer/QC remains tracked in the sibling `godowon-office` repository.
5. For portable v3, invoke `hymn_video_flow_v3.py render`; it verifies the release, job, content objects, runtime, and tracked office renderer before producing the 30fps raster timeline and final media. Use legacy `build-timeline` only for historical v1 jobs.
6. Render only with `render.execute` authority, stream-copy approved audio, then run the full QC contract against the final muxed H.264.
7. Require separate automated QC and human visual-review receipts before final promotion.
8. Build a review package only from qualified artifacts and run `verify-package`.
9. Treat Drive upload+readback, YouTube private staging, YouTube publication, and business-bot notification as four separate external authority boundaries.

CLI entrypoints:

```bash
HYMN_LETTER_SKILL_DIR="/absolute/path/to/Plugify/skills/hymn-letter-video-production"
HYMN_LETTER_RUNTIME_PYTHON="/absolute/path/to/locked/python-with-Pillow-and-numpy"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" validate-job --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-source-bundle --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" render --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT --run-root /absolute/path/new-run --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" qc --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT --run-root /absolute/path/run-root --gate semantic-equivalent --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"

# Historical v1 primitives only:
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" validate-job --manifest /absolute/path/legacy-job.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" build-timeline --spec /absolute/path/timeline-spec.json --output /absolute/new/path/timeline.ffconcat
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" verify-package --package-dir /absolute/path/package --sums /absolute/path/package/SHA256SUMS.txt
```

Use each command's JSON result and artifact hashes as evidence. A process exit, an MP4/MOV's existence, a contact sheet, or a verbal completion report does not replace the required checks.

The three legacy v1 commands are low-level primitives. The v3 `render` and `qc` commands do execute the tracked office producer and create hash-bound receipts; neither command grants external delivery authority.

## Authority boundaries

Keep these permissions distinct:

- `render.execute` — create a new local candidate for one exact job lock.
- `drive.upload_verify` — upload one exact verified package and read remote IDs, size, hashes, and ACL back.
- `youtube.stage_private` — upload one exact video to one exact channel as private.
- `youtube.publish` — change the verified staged video to the explicitly approved visibility.
- `bot.notify` — send an approved minimal-metadata message after required remote receipts exist.

`delivery_intent` records requested stages but grants none of these permissions. Never infer an account, folder, channel, visibility, recipient, or approval from a previous episode.

## Stop and report

Stop fail-closed when an input/template hash differs, an output exists, a required role is missing, a profile is unsupported, caption/audio invariants fail, final H.264 boundary QC fails, package evidence is incomplete, an external identity differs, or a remote mutation is ambiguous.

Report the exact failed gate, current verified boundary, evidence path/SHA, and the smallest missing approval or authoritative input. Do not mark later states complete.
