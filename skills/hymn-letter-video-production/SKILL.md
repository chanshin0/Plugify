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
- For the portable v3 path, read [references/job-manifest.v2.schema.json](references/job-manifest.v2.schema.json), [references/episode-inventory.v2.json](references/episode-inventory.v2.json), [references/source-bundle.schema.json](references/source-bundle.schema.json), [references/release-lock.schema.json](references/release-lock.schema.json), and [references/run-receipt.schema.json](references/run-receipt.schema.json). The Plugify filenames stay the same, but the actual producer schemas are office-native: `godowon.hymn-letter.v3-job/1`, `godowon.hymn-letter.v3-release-lock/1`, and `godowon.hymn-letter.source-bundle/1`. `run-receipt.schema.json` describes only the Plugify invocation wrapper `plugify.hymn-letter.run-receipt/1`; it does not replace the office-native render/QC receipt schemas `godowon.hymn-letter.v3-render-receipt/1` and `godowon.hymn-letter.v3-qc-receipt/1`.
- For an unapproved 07–26 episode candidate, also read [references/candidate-lock.schema.json](references/candidate-lock.schema.json), [references/candidate-job.schema.json](references/candidate-job.schema.json), [references/candidate-intake.schema.json](references/candidate-intake.schema.json), [references/candidate-source-bundle.schema.json](references/candidate-source-bundle.schema.json), and the immutable [references/hymn-letter-track-catalog.v1.json](references/hymn-letter-track-catalog.v1.json). This is a separate, read-only admission contract; it does not extend or rewrite the production v4 release.
- Keep [references/job-manifest.schema.json](references/job-manifest.schema.json) and [references/episode-inventory.json](references/episode-inventory.json) only for the historical v1 primitive path and already-built legacy review packages.
- Read [references/qc-contract.md](references/qc-contract.md) before rendering, reviewing, promoting, or packaging media.
- Read [references/authority-boundaries.md](references/authority-boundaries.md) before any render execution or external mutation.

## Non-negotiable invariants

- Preserve approved script, caption text and timing, and audio. Do not rewrite, split, trim, normalize, retime, or “improve” them without a newly approved source.
- For portable v3, load the sibling `godowon-office` release lock and use only the repo-relative renderer modules whose SHA-256 values it pins. The historical WSL v2 module is legacy-only.
- Never copy visual coordinates, font sizes, fitting logic, safe area, or still-image framerate into an episode-specific renderer or manifest.
- Never overwrite an existing output. Render to a new run/candidate and promote only after QC PASS.
- A generated layout or PNG is not sufficient QC. Decode the actual final H.264 and verify its cue/interval boundary frames.
- A v3 package must carry the locked release/jobs, complete referenced content-addressed source bundle, renderer/QC/package code snapshots, approval/QC receipts, and exact sorted checksums. It is reproducible evidence, but it is not evidence of Drive upload, YouTube state, or bot delivery.

## Profile gate

Only these profiles may appear in a portable v3 job:

- `start-hybrid/v1`: sequence 01, MP4 + AAC-LC; approved AAC-LC stream copy.
- `playlist/v1`: sequence 02, MP4 + AAC-LC; ordered 12-track standalone MP3 gapless decode → continuous PCM concat → AAC-LC 256k. Keep 267 lyric cues plus 12 title cards at the original locked intervals; serialize each card as `{sequence}. {title}` and never include a hymn chapter number.
- `testimony-static/v1`: sequences 03 and 05, MP4 + AAC-LC; approved AAC-LC stream copy.
- `hymn-lyrics/v1`: sequences 04 and 06, MP4 + AAC-LC; approved standalone MP3 → AAC-LC 256k.

The current v3 production inventory is deliberately narrow: `01-start`, `02-playlist`, `03-491-testimony`, `04-491-hymn`, `05-370-testimony`, and `06-370-hymn`. Adding another episode to that production release still requires an approved inventory update, a new inventory hash, and regression validation. The separate 07–26 `validate-candidate` path does not add an episode to that release or bypass this gate.

The approved 07–26 candidate contract uses separate profiles so it cannot silently change 01–06 pixels:

- `testimony-external-srt/v1`: odd sequences 07–25, clean backplate MP4 + byte-exact Korean `.ko.srt`; approved AAC-LC stream copy.
- `hymn-listening-external-srt/v1`: even sequences 08–26, clean backplate MP4 + byte-exact Korean `.ko.srt`; approved standalone MP3 → AAC-LC 256k.

Both profiles require `caption_delivery: youtube-sidecar-srt/v1` and `subtitle_language: ko`. They never rasterize dialogue or lyrics into video frames. The approved backplate may still contain non-caption design elements such as the exact series constant `'고도원의 찬송편지'` and the song title.

## Operating workflow

1. Confirm that the request belongs to this 26-video project and identify the exact episode kind/profile.
2. Inventory approved inputs and ask only for missing human-owned choices or authority. Do not ask the user to perform routine checks the CLI can perform.
3. Create a manifest with the exact schema, hash every input, and run `validate-job`.
   For a prepared 07–26 run, run `validate-candidate --run-root` instead. It admits only `CANDIDATE_UNAPPROVED`, exact-binds the current v4 base release, job, intake receipt, and complete content-addressed object tree, and never grants render or delivery authority.
4. For v3 work, verify the content-addressed source bundle and release lock first. The renderer/QC wrapper is portable; the actual office renderer/QC remains tracked in the sibling `godowon-office` repository.
5. For the exact production release, invoke `hymn_video_flow_v3.py render`; it verifies the release, job, content objects, runtime, and tracked office renderer before producing the 30fps raster timeline and final media. Never pass a candidate lock as `--release`; candidate rendering requires its own authorized handoff after read-only admission. Use legacy `build-timeline` only for historical v1 jobs.
6. Render only with `render.execute` authority and the profile's explicit `audio_policy`, then run the full QC contract against the final muxed H.264 MP4 + AAC-LC.
7. Require separate automated QC and human visual-review receipts before final promotion.
8. Run `verify-upload-ready`, then build a new deterministic package from the approved office package plan and run v3 `verify-package`.
9. Treat Drive upload+readback, YouTube private staging, YouTube publication, and business-bot notification as four separate external authority boundaries.

CLI entrypoints:

```bash
HYMN_LETTER_SKILL_DIR="/absolute/path/to/Plugify/skills/hymn-letter-video-production"
HYMN_LETTER_RUNTIME_PYTHON="/absolute/path/to/locked/python-with-Pillow-and-numpy"
export LANG=C
export LC_ALL=C
export LC_CTYPE=C
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" validate-job --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" validate-candidate --run-root /absolute/path/new-candidate-run
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-source-bundle --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" render --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT --run-root /absolute/path/new-run --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" qc --job /absolute/path/jobs/02_playlist.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT --run-root /absolute/path/run-root --gate semantic-equivalent --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-upload-ready --manifest /absolute/path/upload-ready.json --authority-lock /absolute/path/authority-lock.json --ffprobe /absolute/path/ffprobe --release /absolute/path/release.lock.json --approval-receipt /absolute/path/human-approval.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" package --plan /absolute/path/package-plan.json --release /absolute/path/release.lock.json --source-root /absolute/path/SOURCE_ROOT --ffprobe /absolute/path/ffprobe --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON" --approval-receipt /absolute/path/human-approval.json --package-dir /absolute/new/path/package
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-package --package-dir /absolute/path/package --sums SHA256SUMS.txt --release /absolute/path/release.lock.json --approval-receipt /absolute/path/human-approval.json

# Historical v1 primitives only:
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" validate-job --manifest /absolute/path/legacy-job.json
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" build-timeline --spec /absolute/path/timeline-spec.json --output /absolute/new/path/timeline.ffconcat
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" verify-package --package-dir /absolute/path/package --sums /absolute/path/package/SHA256SUMS.txt
```

Run the complete v3 validate/render/QC/package sequence in that exported locale. The successor environment lock requires `LANG=C`, `LC_ALL=C`, `LC_CTYPE=C`, and filesystem encoding `utf-8`; do not substitute `C.UTF-8` on macOS. Execution preflight runs the release-pinned environment probe under the selected Python and exact-matches the full lock: OS/machine, Python binary/version/SHA/implementation/compiler, Pillow·numpy versions, Pillow FreeType/libjpeg/zlib native fingerprints, and `PATH` ffmpeg/ffprobe identity/version. Upload/package also exact-match the explicit `ffprobe`. `validate-job` and `verify-source-bundle` remain read-only structural/hash checks and do not execute the media toolchain.

Use each command's JSON result and artifact hashes as evidence. A process exit, an MP4's existence, a contact sheet, or a verbal completion report does not replace the required checks.

`hymn-letter-caption-v4-interview-soft-20260826` is the only current release ID, and the wrapper compiles its exact release SHA as the production trust anchor. The v4 template adds `interview-soft` only for episode 01's first 723 frames: 68px, zero outline, and the locked subtle shadow; `center` and `dense` retain their previous pixels. A 64-zero renderer-module SHA blocks render, every QC mode, upload-ready verification, and packaging. Once all renderer modules are nonzero and pinned, `status: BOOTSTRAP_REQUIRED`, `reference_output_sha256: null`, or a 64-zero golden output SHA permits only the first render and semantic QC; it still blocks reference-bit-exact QC, upload-ready promotion, and packaging. The current tracked release has measured nonzero output hashes; episode 01 interview-soft has semantic-equivalent and independent reference-bit-exact PASS evidence. Release-wide promotion still requires all required QC evidence and a person who actually listened to issue the separate six-row `godowon.hymn-letter.human-approval-receipt/1`. Without it the result remains a local review package with `promotion_pending`; the CLI must not synthesize `APPROVED` from reviewer/time fields in a plan.

The successor public package builder is plan-only. It snapshots the exact twelve office-native render/QC receipt byte streams before delegation, makes the office stage reproduce those bytes, and packages a canonical path-free `delegation-inputs.lock.json`. Because there is no external signature for historical process origin, a delegated package reports `delegation_origin: UNATTESTED`; that label is separate from the independently verified artifact/evidence integrity and from the external human approval receipt.

The package plan schema is exactly `godowon.hymn-letter.upload-ready-package-plan/1`, with exact top-level keys `schema`, `release`, `source_root`, and `episodes`. Its six episode rows have only `sequence`, `job`, `render_receipt`, and `qc_receipt`. The public `render`/`qc` command result's top-level `receipt` points to the Plugify wrapper; do not put that path in the plan. Open that wrapper JSON and use the office-native path in `delegate_payload.render_receipt` or `delegate_payload.qc_receipt`, respectively. Packaging requires those native receipts, including semantic, upload-ready, and reference-bit PASS evidence for QC.

17,327 all-zero samples prove a 0.392902-second noncanonical timeline defect; they are not the proven direct cause of the audible spike.

Without QuickTime output capture, codec versus interleave/nearby H.264 keyframe contribution remains unresolved.

The safe path removes both per-track MP3 trim metadata loss and MOV+MP3 playback risk.

The three legacy v1 commands are low-level primitives. The v3 `render` and `qc` commands do execute the tracked office producer and create hash-bound receipts; neither command grants external delivery authority.

`validate-candidate` is different from every production release command. It is read-only and never invokes a renderer, ffprobe, QC, package builder, or uploader. It pins the immutable track catalog to SHA-256 `676407cca40e2fdbac024400dfbdf8c83867e6e33388dee9507c7c5a5bc7ff72`; the intake `catalog_audio_sha_match` boolean is only a producer assertion. The validator itself binds the paired track sequence, hymn number/title, approved audio and caption object IDs, production PCM anchor, and hymn frame count to that catalog. Every candidate also exact-binds positive `intake.probe.audio.render_frame_count` to `job.output.frame_count`; the office intake preflight remains responsible for deriving that probe value from the real media. Candidate SRT must be plain UTF-8 without BOM, use LF, end in a newline, contain non-overlapping positive cues, and declare the exact MP4-matching `.ko.srt` sidecar basename. A candidate testimony keeps `restore_audio_edit: true` but binds its positive `settings.movie_timescale` to the already-recorded `intake.probe.audio.movie_timescale`; do not copy production 03/05's `384000` onto a fresh M4A. Hymn candidates record probe `movie_timescale: null`. Production `validate-job`, `render`, `qc`, `verify-upload-ready`, `package`, and `verify-package` remain bound to the exact six-episode v4 release and reject a candidate lock passed as `--release`.

The candidate contract now includes one real speech-master-style M4A pre-render observation: it exposed that a fresh file's movie timescale cannot be copied from production 03/05 and must be probe-bound. That is not a completed pair observation. Do not call it production-ready from `validate-candidate` alone: the first real pair must still complete intake preflight, candidate render, semantic QC, human listening/visual approval, and an independent re-render comparison under fresh review. Missing real inputs, visual-asset choice, or voice authority means this observation remains open rather than silently assumed.

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
