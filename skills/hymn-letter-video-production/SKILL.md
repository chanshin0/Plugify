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

## Route before selecting a renderer

- For raw recorded testimony, reuse of episodes 01–06, or follow-up episodes 07–26,
  read [references/recorded-testimony-pair.md](references/recorded-testimony-pair.md)
  first. It routes to the project's current preparation/render contracts and the
  proven upstream narration-editing procedure. Do not feed these jobs to this
  skill's legacy `validate-job` CLI or relabel them as an older episode.
- For a requested testimony/listening pair, record both episode IDs and their
  deliverables before work. Finishing the narration or the odd episode alone
  does not complete the pair. Respect an explicit narrower or paused scope.
- For every hymn-listening episode, keep both added leading silence and any
  source-audio leading silence free of captions. Show the locked song title
  from the first audible accompaniment frame until the first sung lyric frame,
  then hand off to the first lyric with zero gap or overlap. Record the measured
  music onset, title interval, and lyric handoff in the render receipt. This is
  a required display cue, separate from the source-lyric preservation check.
- For the two thumbnails of one hymn pair, keep the song title, the white context
  line above it, and the final emotional copy exactly identical. Only the kind
  label differs, and both kind labels are fixed constants. Therefore author one
  shared emotional sentence (or one shared A/B/C/D candidate set) per pair.
  Derive it from the testimony script's central message and key lines, not from
  unrelated lyric copy or generic clickbait. The same candidate ID must preserve
  exact line breaks and placement across both thumbnails.
  Present exactly four integrated emotional-copy candidates for the pair, not
  four duplicated candidates per episode. After the user selects one, render the
  two final thumbnails and both video backplates as still images. Do not start a
  full-length MP4 render until the user approves those exact images. A short
  technical probe is not that approval.
- For publishing copy after episodes 01–06, give the testimony and listening
  episodes separate titles but one shared body derived from the approved
  testimony script. Match the 01–06 body structure by adding bracketed section
  subtitles (`[부제목]`) at the testimony's real topic transitions; a raw script
  pasted after the common introduction is incomplete. Require at least four
  section subtitles, preserve the approved script exactly when those inserted
  subtitles are removed, including leading and trailing line breaks, and share
  the subtitles and body across both episodes.
  Append the locked production/contact notice only to the listening episode.
  For current and future delivery, include one paired title/body UTF-8 TXT as a
  required delivery role; do not create or deliver RTF. Put exactly three blank
  lines (four newline characters) between the preceding body sentence and every
  bracketed section subtitle, and verify the TXT's remote bytes with the rest of
  the exact set.
  The selected shared emotional copy is also the testimony episode's title hook:
  join its locked thumbnail lines with one space immediately after the series
  name. Do not invent a separate paraphrase for the testimony title. Keep the
  listening episode's established song-title-led format. The publishing-copy
  generator must fail when the selected emotional copy and testimony title do
  not match.
  Count each video's complete YouTube description separately and fail before
  delivery when either exceeds 5,000 characters. The testimony count covers the
  shared body; the listening count also includes its production/contact notice.
  Exclude the video title from the 5,000-character description count.
  Do not treat a paired TXT's combined file length or a copy-instruction marker
  as either video's description length. Record the 5,000-character maximum and
  both final per-video counts in the publishing receipt.
  When the faithful body exceeds the limit, stop delivery and report both counts;
  do not use an LLM to summarize, paraphrase, or silently shorten the approved
  script. The user may explicitly approve a manual omission in the final
  publishing copy. Mark each such omission exactly as `[중략...]`; treat it as a
  reserved omission marker, not a bracketed section subtitle. Re-read the edited
  TXT, keep the locked titles, thumbnail copy, title block, and common intro
  unchanged, and require both final descriptions to pass 5,000 characters. Hash
  the final TXT only after that edit; hashes identify one final artifact and are
  not constants shared across episodes.
- For the current follow-up Drive delivery, keep production/audit audio, SRT,
  EDL, and QC locally. The final pair folder has exactly seven publishing roles:
  two burned-caption MP4s, two backplates, two thumbnails, and one paired UTF-8
  TXT. Review candidates may temporarily share the folder, but final promotion
  removes candidates, comparisons, stale versions, and RTF before exact-set
  verification.
- The legacy profile inventory and operating workflow below govern only the
  evidenced legacy renderer. They do not declare the current project follow-up
  flow unavailable, nor prove that its runtime/assets exist on this device.

## Load the right reference

- For legacy production, review, package, or delivery, read [references/workflow.md](references/workflow.md). For follow-ups, use the project references selected above instead of mixing legacy and current locks.
- Read [references/job-manifest.schema.json](references/job-manifest.schema.json) when creating or validating a legacy job. Follow-ups use the project's current prepare/verify schema and candidate lock. Do not mix schemas or invent extra manifest keys.
- For the legacy CLI, read [references/episode-inventory.json](references/episode-inventory.json) and use only its exact supported `episode.id → kind → profile` mappings. For follow-ups, use the project's current locked catalog; never invent a mapping.
- Read [references/qc-contract.md](references/qc-contract.md) before legacy media work; follow-up media uses its project's locked QC. Neither route permits omitted checks to become PASS.
- Read [references/authority-boundaries.md](references/authority-boundaries.md) before any render execution or external mutation.
- For YouTube CLI upload, publication, or end-screen work, also read
  [references/youtube-delivery.md](references/youtube-delivery.md).

## Non-negotiable invariants

- Preserve approved script, caption text and timing, and audio. User-authorized raw-recording cleanup is a separate upstream candidate stage: preserve the original, create a new EDL and derived audio, then obtain exact-candidate approval. Never edit an already approved source in place.
- Import the locked visual SSOT for the selected route. The legacy module is `godo-hymns/tools/hymn_letter_visual_template.py`; follow-ups use the project's release-bound adapter. Verify module SHA, template version, bundle lock, config, and assets before rendering.
- Never copy visual coordinates, font sizes, fitting logic, safe area, or still-image framerate into an episode-specific renderer or manifest.
- Never overwrite an existing output. Render to a new run/candidate and promote only after QC PASS.
- A generated layout or PNG is not sufficient QC. Decode the actual final H.264 and verify its cue/interval boundary frames.
- A local review package is not a portable renderer and is not evidence of Drive upload, YouTube state, or bot delivery.
- Before any delivery mutation, lock the current request as an exact role-aware
  delivery manifest: episode ID, role, target name, size, and SHA-256 for every
  required payload. Existing target files count only when their role and exact
  bytes match that manifest.
- An adjunct-only success (thumbnail, comparison sheet, SRT, audio, or metadata)
  never proves the episode or requested pair was delivered. A missing current
  burned-caption MP4 or any stale same-episode MP4 makes the target
  `PARTIAL_STALE_TARGET`, not complete.

## Legacy CLI profile gate

Only these profiles may appear in a job:

- `start-hybrid/v1`: currently evidenced by the v17 start video.
- `testimony-static/v1`: currently evidenced by the v17 491 and 370 testimony/introduction videos.
- `hymn-lyrics/v1`: fail closed until approved hymn sources, lyric timing, and a golden fixture exist.
- `playlist/v1`: fail closed until approved twelve-track order, gaps/chapters, timing, and a golden fixture exist.

Do not make an unsupported profile appear supported by changing its name to one of the first two profiles.

The current supported episode inventory is deliberately partial: `start`, `hymn-491-testimony`, and `hymn-370-testimony`. Adding another episode requires an approved selection/update, a new inventory hash, and regression validation; a syntactically plausible ID is not enough.

## Legacy operating workflow

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

For a Drive replacement/reorganization receipt, verify the exact role set before
reporting completion:

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/verify_delivery_set.py" \
  --manifest /absolute/path/delivery-manifest.json \
  --receipt /absolute/path/drive-receipt.json
```

The receipt must be bound to the current manifest hash and prove exact remote
children, non-local remote IDs, remote sizes, DriveFS readback hashes, and either
declared stale-ID cleanup or exact replacement of superseded bytes when Drive
retains the remote IDs. Name only the roles actually verified in the user
report. If this command fails, report the verified subset and reconciliation
needed; do not say the pair or folder is delivered.

These three commands are low-level validation primitives; they do not render video, run media QC, or perform delivery. Require an approved deterministic project renderer/QC report with its exact command and renderer SHA. If no such final-H.264/audio/caption evidence exists, stop at `RENDERED_UNVERIFIED`.

## Authority boundaries

Keep these permissions distinct:

- `render.execute` — create a new local candidate for one exact job lock.
- `drive.upload_verify` — upload one exact verified package and read remote IDs, size, hashes, and ACL back.
- `youtube.stage_private` — upload one exact video to one exact channel as private.
- `youtube.publish` — change the verified staged video to the explicitly approved visibility.
- `youtube.end_screen_configure` — after both paired video IDs exist and the
  target videos are selectable, copy the approved odd/even Studio layout and
  point each video to its exact counterpart.
- `bot.notify` — send an approved minimal-metadata message after required remote receipts exist.

`delivery_intent` records requested stages but grants none of these permissions. Never infer an account, folder, channel, visibility, recipient, or approval from a previous episode.

## Stop and report

Stop fail-closed when an input/template hash differs, an output exists, a required role is missing, a profile is unsupported, caption/audio invariants fail, final H.264 boundary QC fails, package evidence is incomplete, an external identity differs, or a remote mutation is ambiguous.

Report the exact failed gate, current verified boundary, evidence path/SHA, and the smallest missing approval or authoritative input. Do not mark later states complete.
