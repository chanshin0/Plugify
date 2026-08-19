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
- Read [references/job-manifest.schema.json](references/job-manifest.schema.json) when creating or validating a job. Do not invent extra manifest keys.
- Read [references/episode-inventory.json](references/episode-inventory.json) and use only its exact supported `episode.id → kind → profile` mappings. The final twelve-song selection is not yet authoritative, so do not add episodes by inference.
- Read [references/qc-contract.md](references/qc-contract.md) before rendering, reviewing, promoting, or packaging media.
- Read [references/authority-boundaries.md](references/authority-boundaries.md) before any render execution or external mutation.

## Non-negotiable invariants

- Preserve approved script, caption text and timing, and audio. Do not rewrite, split, trim, normalize, retime, or “improve” them without a newly approved source.
- Import the one visual SSOT from `/mnt/c/work/godowon-office/godo-hymns/tools/hymn_letter_visual_template.py`. Verify its module SHA, template version, bundle lock, config, and assets before rendering.
- Never copy visual coordinates, font sizes, fitting logic, safe area, or still-image framerate into an episode-specific renderer or manifest.
- Never overwrite an existing output. Render to a new run/candidate and promote only after QC PASS.
- A generated layout or PNG is not sufficient QC. Decode the actual final H.264 and verify its cue/interval boundary frames.
- A local review package is not a portable renderer and is not evidence of Drive upload, YouTube state, or bot delivery.

## Profile gate

Only these profiles may appear in a job:

- `start-hybrid/v1`: currently evidenced by the v17 start video.
- `testimony-static/v1`: currently evidenced by the v17 491 and 370 testimony/introduction videos.
- `hymn-lyrics/v1`: fail closed until approved hymn sources, lyric timing, and a golden fixture exist.
- `playlist/v1`: fail closed until approved twelve-track order, gaps/chapters, timing, and a golden fixture exist.

Do not make an unsupported profile appear supported by changing its name to one of the first two profiles.

The current supported episode inventory is deliberately partial: `start`, `hymn-491-testimony`, and `hymn-370-testimony`. Adding another episode requires an approved selection/update, a new inventory hash, and regression validation; a syntactically plausible ID is not enough.

## Operating workflow

1. Confirm that the request belongs to this 26-video project and identify the exact episode kind/profile.
2. Inventory approved inputs and ask only for missing human-owned choices or authority. Do not ask the user to perform routine checks the CLI can perform.
3. Create a manifest with the exact schema, hash every input, and run `validate-job`.
4. For a supported profile, have its adapter import the tracked SSOT and produce the raster interval spec. Then run the low-level `build-timeline`; the locked Hymn Letter production spec must use 30fps and every ffconcat file stanza must receive `option framerate 30`.
5. Render only with `render.execute` authority, stream-copy approved audio, then run the full QC contract against the final muxed H.264.
6. Require separate automated QC and human visual-review receipts before final promotion.
7. Build a review package only from qualified artifacts and run `verify-package`.
8. Treat Drive upload+readback, YouTube private staging, YouTube publication, and business-bot notification as four separate external authority boundaries.

CLI entrypoint:

```bash
HYMN_LETTER_SKILL_DIR="/mnt/c/Work/Plugify/skills/hymn-letter-video-production"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" validate-job --manifest /absolute/path/job.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" build-timeline --spec /absolute/path/timeline-spec.json --output /absolute/new/path/timeline.ffconcat
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" verify-package --package-dir /absolute/path/package --sums /absolute/path/package/SHA256SUMS.txt
```

Use each command's JSON result and artifact hashes as evidence. A process exit, an MP4's existence, a contact sheet, or a verbal completion report does not replace the required checks.

These three commands are low-level validation primitives; they do not render video, run media QC, or perform delivery. Require an approved deterministic project renderer/QC report with its exact command and renderer SHA. If no such final-H.264/audio/caption evidence exists, stop at `RENDERED_UNVERIFIED`.

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
