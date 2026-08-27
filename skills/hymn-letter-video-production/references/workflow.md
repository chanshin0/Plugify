# 고도원 찬송편지 26편 제작 워크플로우

> 2026-08-26 현재 portable v3 정본은 `godowon-office/godo-hymns/releases/hymn-letter-caption-v4-interview-soft-20260826/`의 office-native release/job/source-bundle lock이다. v4는 01의 첫 723프레임에만 68px 무테두리·약한 그림자의 `interview-soft`를 선택하고 기존 `center`·`dense` 픽셀은 보존한다. Plugify의 `hymn_video_flow_v3.py`는 그 tracked JSON을 **변환 없이 그대로** 검증하고 office renderer/QC/package에 위임한 뒤 독립 검증한다. 아래 `hymn_video_flow.py` 문단은 역사적 v1 primitive 설명이다.

## 범위와 완성 구조

이 workflow는 다음 26편을 제작·검수·전달할 때만 쓴다.

1. 찬송편지를 시작하는 이유 영상 1편
2. 선정 찬송 12곡의 간증·소개 영상 12편
3. 같은 12곡의 찬송·가사 영상 12편
4. 12곡 전체 playlist 영상 1편

다른 YouTube 영상, 일반 영상 편집, 다른 찬송 프로젝트에는 적용하지 않는다.

## Profile gate

| episode kind | profile | 현재 상태 |
|---|---|---|
| `start` | `start-hybrid/v1` | v4 01 시작편으로 증거 있음. 첫 723프레임은 interview-soft, 이후는 dense. 승인 interview/program video + 승인 audio + captions 필요 |
| `testimony_intro` | `testimony-static/v1` | v17 491·370으로 증거 있음. 승인 audio + captions 필요 |
| `hymn_lyrics` | `hymn-lyrics/v1` | v3 release에 잠긴 04·06만 지원 |
| `playlist` | `playlist/v1` | 수정된 제목 순서와 golden이 잠긴 02만 지원 |

07–26 candidate는 production profile을 재사용하지 않는다.

| episode kind | candidate profile | 자막 전달 |
|---|---|---|
| `testimony_intro` | `testimony-external-srt/v1` | clean MP4 + 승인 원문과 byte-exact한 `.ko.srt` |
| `hymn_lyrics` | `hymn-listening-external-srt/v1` | clean MP4 + catalog SRT와 byte-exact한 `.ko.srt` |

후속편 영상에는 대사·가사를 굽지 않는다. backplate가 이미 소유한 `'고도원의 찬송편지'`와 노래 제목 등 비자막 디자인은 유지한다.

현재 여섯 output은 모두 MP4 + AAC-LC다. 01·03·05는 승인 AAC-LC를 stream-copy하고, 04·06은 승인 standalone MP3를 filter 없이 AAC-LC 256k/44.1kHz/stereo로 변환한다. 02는 승인 standalone MP3 12개를 순서대로 각각 gapless decode해 continuous PCM으로 이어 붙인 뒤 같은 AAC-LC 규격으로 한 번만 encode한다. MOV+MP3 output은 금지한다.

inventory 밖 profile/episode를 유사한 지원 항목으로 바꾸어 실행하지 않는다. 필요한 authoritative source와 승인만 요청하고 멈춘다.

portable v3 inventory의 정본은 [episode-inventory.v2.json](episode-inventory.v2.json)이다. 현재 허용 항목은 `01-start`, `02-playlist`, `03-491-testimony`, `04-491-hymn`, `05-370-testimony`, `06-370-hymn` 여섯 개뿐이다.

## 1. Intake와 manifest

portable v3 manifest는 office-native tracked JSON을 그대로 쓴다.

- release: `godowon.hymn-letter.v3-release-lock/1`
- source bundle: `godowon.hymn-letter.source-bundle/1`
- job: `godowon.hymn-letter.v3-job/1`
- content-addressed bytes: `SOURCE_ROOT/objects/sha256/<prefix>/<digest-rest>`

`validate-job`은 반드시 `--job`과 `--release`를 함께 받아 release lock의 listed job SHA, supported profile, inventory mapping, output contract를 같이 검증한다.

먼저 26편 inventory에서 현재 episode의 ID·kind·profile과 승인된 입력을 확인한다.

- `validate-job`은 inventory 파일 자체의 고정 SHA와 exact `episode.id → kind → profile` mapping을 확인한다.
- inventory 밖 episode는 이름이 그럴듯해도 지원하지 않는다. 승인된 곡 선정과 입력이 생기면 inventory release와 regression을 함께 갱신한다.

- 승인 대본이 별도 파일이면 `approved_script` role로 넣는다.
- 승인 자막은 `captions`, 승인 오디오는 `approved_audio`, 시작편의 보존 영상은 `program_video`로 넣는다.
- EDL, reviewed ASS, reference layout, thumbnail, publishing metadata가 있으면 각각 별도 role과 SHA로 잠근다.
- 사람이 정해야 하는 가사, timing, cut, 곡 순서, gap, 공개 대상은 추측하지 않는다.

02 job은 `tracks[12]`의 exact 순서와 각 `audio`, `captions`, decoded sample 수, PCM SHA-256, 누적 `start_sample`, `ceil(start_sample*30/44100)`인 `start_frame`을 잠근다. `caption_timing_contract`는 가사 cue 267개와 제목 카드 12개, 총 279개를 잠근다. 제목 카드는 이전 승인본의 시작·종료 시각을 그대로 쓰고 `{sequence}. {title}`만 표시하며 찬송가 장 번호는 넣지 않는다. offset은 half-up sample→millisecond 규칙을 쓰며 `title_card_policy.mode`는 `playlist-title-only-prior-outro/v1`, `expected_titles`는 ordered track title 12개, `expected_active_rows`는 `[1,1,2,3,4,5,6,7,8,9,10,11]`이어야 한다.

아래 문단은 **역사적 v1 manifest에만** 적용한다. v3 job에 이 shape를 섞지 않는다. v1 manifest는 [job-manifest.schema.json](job-manifest.schema.json)의 정확한 7개 top-level key만 사용한다.

```text
schema
project_id
episode
inputs
visual_template
output
delivery_intent
```

`schema` 값은 정확히 `plugify.hymn-letter.video-job/1`, `project_id`는 `godowon-hymn-letter-26`이다.

`delivery_intent`는 예정 동작이며 승인이 아니다. credential과 승인 토큰을 manifest에 넣지 않는다.

## 2. 결정론적 CLI

portable v3 CLI 정본은 `scripts/hymn_video_flow_v3.py`이고, 역사적 v1 primitive 정본은 `scripts/hymn_video_flow.py`다. 어느 작업 디렉터리에서도 해당 release에 맞는 진입점을 명시한다.

```bash
HYMN_LETTER_SKILL_DIR="/absolute/path/to/Plugify/skills/hymn-letter-video-production"
HYMN_LETTER_RUNTIME_PYTHON="/absolute/path/to/locked/python-with-Pillow-and-numpy"
export LANG=C
export LC_ALL=C
export LC_CTYPE=C
JOB_MANIFEST="/absolute/path/job.json"
TIMELINE_SPEC="/absolute/path/timeline-spec.json"
TIMELINE_OUTPUT="/absolute/new/path/timeline.ffconcat"
PACKAGE_DIR="/absolute/path/package"
SUMS_FILE="$PACKAGE_DIR/SHA256SUMS.txt"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" --help
```

이 세 locale export는 portable v3 전체 명령의 preflight다. successor environment lock은 `LANG=C`, `LC_ALL=C`, `LC_CTYPE=C`, runtime locale `C`, filesystem encoding `utf-8`을 요구한다. macOS에 없는 `C.UTF-8`로 바꾸거나 현재 shell locale을 묵시적으로 상속하지 않는다. 같은 export를 유지한 shell에서 validate → render → QC → package를 실행한다. render/QC/package는 release에 SHA로 잠긴 environment probe를 선택한 Python에서 실행하여 OS/machine, Python binary/version/SHA/implementation/compiler/filesystem encoding, Pillow·numpy, FreeType/libjpeg/zlib, `PATH` ffmpeg/ffprobe identity/version을 lock 전체와 exact-match한다. upload/package의 명시적 `ffprobe`도 basename·SHA가 같아야 한다. `validate-job`과 `verify-source-bundle`은 media toolchain을 실행하지 않는 read-only 구조/hash 검사다.

### `validate-job`

portable v3:

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" validate-job \
  --job /absolute/path/jobs/02_playlist.json \
  --release /absolute/path/release.lock.json
```

### `validate-candidate` (07–26, read-only)

후속 회차는 production v4 release를 바꾸지 않고 별도 candidate run root로 받는다.

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" validate-candidate \
  --run-root /absolute/path/new-candidate-run
```

run root의 `candidate.lock.json`은 `godowon.hymn-letter.candidate-lock/1` exact shape이며 다음을 잠근다.

- `status: CANDIDATE_UNAPPROVED`와 ASCII 작은따옴표까지 포함한 `series_name: '고도원의 찬송편지'`;
- current v4 `release_id`와 compiled release SHA;
- 07–26 sequence, sequence와 같은 두 자리 episode ID prefix, 홀수 간증/짝수 찬송의 kind/profile parity;
- run-root-relative job, candidate source bundle, intake receipt path와 각 exact SHA.

validator는 모든 manifest를 stable-read하고 symlink·`..`·run-root escape를 거부한다. `objects/sha256/<prefix>/<digest-rest>` 트리는 bundle의 exact object set이어야 하며 모든 파일의 SHA와 size를 다시 계산한다. job은 07–26 전용 `testimony-external-srt/v1`·`hymn-listening-external-srt/v1`만 허용하고 `caption_delivery: youtube-sidecar-srt/v1`, `subtitle_language: ko`, MP4와 stem이 같은 `.ko.srt` 출력명을 고정한다. SRT는 UTF-8(no BOM)·LF·final newline·positive/non-overlap cue를 실제 bytes에서 독립 재검증한다. 간증은 speech-master PASS AAC-LC M4A 48 kHz stereo, `restore_audio_edit: true`, `video_track_timescale: 15360`을 고정하되 `movie_timescale`은 실제 M4A probe의 양의 정수와 exact-match한다. production 03·05 job의 `movie_timescale: 384000` 고정은 그대로다. 찬송은 catalog exact-match MP3를 사용하고 intake probe의 `movie_timescale`은 `null`이어야 한다. intake와 narration receipt의 approved-script/narration SHA, speech-master report, job input object ID가 같은 source object graph에 결속되어야 한다.

후보 카탈로그 정본은 [hymn-letter-track-catalog.v1.json](hymn-letter-track-catalog.v1.json), 고정 SHA-256은 `676407cca40e2fdbac024400dfbdf8c83867e6e33388dee9507c7c5a5bc7ff72`다. `catalog_audio_sha_match: true`는 비권위 producer assertion일 뿐이며, validator는 카탈로그 bytes/SHA와 02 playlist의 samples·PCM SHA를 먼저 고정한 뒤 paired track sequence, episode kind/profile, hymn number/title, exact audio/caption object ID, hymn output frame count를 source graph와 직접 대조한다. 따라서 임의 MP3에 boolean만 붙이거나 intake의 catalog SHA·track metadata를 바꾸어도 통과하지 않는다. 간증편은 다음 짝수 찬송 chapter의 번호·제목·sequence에만 결속하고, 간증 narration/captions를 찬송 MP3/SRT와 같다고 요구하지 않는다. 모든 후보의 positive `probe.audio.render_frame_count`는 `job.output.frame_count`와 exact-match해야 한다. Plugify는 ffprobe를 실행하지 않으므로 두 값을 함께 변조한 경우까지 독립 탐지하지 않으며, 실제 media에서 frame count를 다시 산출하는 office intake preflight가 그 외부 사실성을 책임진다.

이 명령은 renderer·ffprobe·QC·package·upload를 실행하거나 위임하지 않고 `render.execute`도 부여하지 않는다. candidate lock을 production `--release` 자리에 넣으면 `validate-job`, render, QC, upload-ready, package 모두 compiled v4 trust gate에서 거부해야 한다.

portable v3는 source bundle 검증 뒤 office-native contract를 변환 없이 render/QC에 넘긴다. `--runtime-python`은 명시적으로 잠가 wrapper receipt에 경로·SHA·버전을 기록한다.

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-source-bundle \
  --job /absolute/path/jobs/02_playlist.json \
  --release /absolute/path/release.lock.json \
  --source-root /absolute/path/SOURCE_ROOT

python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" render \
  --job /absolute/path/jobs/02_playlist.json \
  --release /absolute/path/release.lock.json \
  --source-root /absolute/path/SOURCE_ROOT \
  --run-root /absolute/path/new-run \
  --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"

python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" qc \
  --job /absolute/path/jobs/02_playlist.json \
  --release /absolute/path/release.lock.json \
  --source-root /absolute/path/SOURCE_ROOT \
  --run-root /absolute/path/run-root \
  --gate semantic-equivalent \
  --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON"

python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-upload-ready \
  --manifest /absolute/path/upload-ready.json \
  --authority-lock /absolute/path/authority-lock.json \
  --ffprobe /absolute/path/ffprobe \
  --release /absolute/path/release.lock.json \
  --approval-receipt /absolute/path/human-approval.json

python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" package \
  --plan /absolute/path/package-plan.json \
  --release /absolute/path/release.lock.json \
  --source-root /absolute/path/SOURCE_ROOT \
  --office-root /absolute/path/godowon-office \
  --ffprobe /absolute/path/ffprobe \
  --runtime-python "$HYMN_LETTER_RUNTIME_PYTHON" \
  --approval-receipt /absolute/path/human-approval.json \
  --package-dir /absolute/new/path/package

python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow_v3.py" verify-package \
  --package-dir /absolute/path/package \
  --sums SHA256SUMS.txt \
  --release /absolute/path/release.lock.json \
  --approval-receipt /absolute/path/human-approval.json
```

#### Package plan receipt contract

The public `render` and `qc` commands each write a Plugify wrapper receipt with schema `plugify.hymn-letter.run-receipt/1`; their JSON result's top-level `receipt` is the path to that wrapper. The office delegate's producer receipt is a different file nested in the wrapper payload:

- render wrapper → `delegate_payload.render_receipt` → `godowon.hymn-letter.v3-render-receipt/1`
- QC wrapper → `delegate_payload.qc_receipt` → `godowon.hymn-letter.v3-qc-receipt/1`

The package plan must use those two nested office-native absolute paths for every sequence, never the wrapper `receipt` path. The QC file must be the native receipt whose semantic, upload-ready, and reference-bit gates are all `PASS`. [run-receipt.schema.json](run-receipt.schema.json) validates only the Plugify wrapper, while the release-pinned office package contract and the independent Plugify verifier validate the two native receipt schemas and their release/job/render/output hash chain.

The exact plan contract has only `schema`, `release`, `source_root`, and `episodes` at top level. `schema` is `godowon.hymn-letter.upload-ready-package-plan/1`; `release` and `source_root` must equal the corresponding CLI anchors. `episodes` contains exactly six unique sequences 1–6, and each row has only `sequence`, `job`, `render_receipt`, and `qc_receipt`. Every file path is an existing absolute regular non-symlink path, and each `job` must be the exact release-registered job. A minimal exact plan is:

```json
{
  "schema": "godowon.hymn-letter.upload-ready-package-plan/1",
  "release": "/absolute/path/release.lock.json",
  "source_root": "/absolute/path/SOURCE_ROOT",
  "episodes": [
    {"sequence": 1, "job": "/absolute/path/jobs/01_start.json", "render_receipt": "/absolute/path/run-01/render_receipt.json", "qc_receipt": "/absolute/path/run-01/qc_reference_bit_exact.json"},
    {"sequence": 2, "job": "/absolute/path/jobs/02_playlist.json", "render_receipt": "/absolute/path/run-02/render_receipt.json", "qc_receipt": "/absolute/path/run-02/qc_reference_bit_exact.json"},
    {"sequence": 3, "job": "/absolute/path/jobs/03_491_testimony.json", "render_receipt": "/absolute/path/run-03/render_receipt.json", "qc_receipt": "/absolute/path/run-03/qc_reference_bit_exact.json"},
    {"sequence": 4, "job": "/absolute/path/jobs/04_491_hymn.json", "render_receipt": "/absolute/path/run-04/render_receipt.json", "qc_receipt": "/absolute/path/run-04/qc_reference_bit_exact.json"},
    {"sequence": 5, "job": "/absolute/path/jobs/05_370_testimony.json", "render_receipt": "/absolute/path/run-05/render_receipt.json", "qc_receipt": "/absolute/path/run-05/qc_reference_bit_exact.json"},
    {"sequence": 6, "job": "/absolute/path/jobs/06_370_hymn.json", "render_receipt": "/absolute/path/run-06/render_receipt.json", "qc_receipt": "/absolute/path/run-06/qc_reference_bit_exact.json"}
  ]
}
```

`package --plan`은 successor의 유일한 public package builder다. release에 SHA로 잠긴 office package module을 새 임시 경로에서 실행한 뒤, Plugify가 upload-ready graph와 실제 probe를 다시 검증하고 sibling staging에서 최종 package를 만든 후 검증된 디렉터리만 원자적으로 승격한다. plan의 release/source/job 경로는 CLI trust anchor와 exact-bind한다. 위임 전에 6편 × render/QC의 exact 12 office-native receipt bytes를 stable-read snapshot하고, office stage의 receipt 사본이 각 snapshot과 byte-equal인지 확인하며, 절대경로가 없는 canonical `delegation-inputs.lock.json`에 release/source/package-module/human-approval/job/receipt SHA를 잠근다. 기존 경로 overwrite, source/release/code/run root 안의 output, 입력/package 안의 `.DS_Store`를 거부한다. `SHA256SUMS.txt`는 final newline을 포함한 UTF-8 LF, 두 칸 구분, relative path 오름차순 exact bytes이며 checksum 파일을 제외한 exact regular-file set과 일치해야 한다.

최종 package에는 01–06 MP4·thumbnail, upload authority/receipt, 별도 human approval receipt, release lock·6 jobs·environment/golden/source-bundle lock, release가 참조하는 모든 content-addressed object, SHA로 잠긴 office renderer/QC/package 8 modules, Plugify wrapper/validator/schema/docs snapshot, canonical delegation-input lock, snapshot과 byte-equal한 12 office-native producer receipt가 들어간다. 절대경로·locale·mtime은 manifest bytes에 기록하지 않는다. fresh machine은 같은 repo commit의 외부 trusted release/approval receipt와 package의 `00_재현자료/source_bundle`만으로 source bytes를 복원하고 exact-set을 검증할 수 있어야 한다. 외부 서명/attestation이 없으므로 historical office delegate origin은 `UNATTESTED`로 보고하며, artifact/evidence integrity PASS나 human approval과 혼동하지 않는다.

renderer module SHA가 하나라도 64-zero sentinel이면 모든 render/QC/upload/package 실행을 막는다. 모든 module pin이 nonzero인 상태에서 golden lock이 `BOOTSTRAP_REQUIRED`이거나 `reference_output_sha256`가 `null`이거나 output SHA가 64-zero이면 첫 render와 semantic QC만 가능하고, reference-bit-exact QC·upload-ready promotion·package는 막는다. 현재 production trust anchor는 episode 01 interview-soft measured golden을 포함한 release SHA `24867e11a54c33f69005ed7b033f3996200597697fa99657bb4764ea9ddff7e6`이며 golden SHA는 `439eaf514eec51281b0e597d03fc5239b59e3940f31114d64644ef5af84fbcd4`다. 사용자가 실제 오디오를 듣지 못한 run은 기술 QC가 PASS해도 local 검토본·`promotion_pending`이며 사람 승인 receipt를 만들지 않는다.

legacy v1 primitive:

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" validate-job --manifest "$JOB_MANIFEST"
```

역할(아래 항목은 legacy v1 validator에만 적용):

- manifest schema identifier, exact top/subkeys, absolute path, lowercase SHA-256, no-overwrite를 독립적으로 검사한다.
- 모든 input의 실제 SHA를 다시 계산하고 `role` 중복을 거부한다.
- episode kind와 profile의 조합을 검사한다.
- pinned episode inventory와 ID/kind/profile의 exact mapping을 검사한다.
- tracked visual module의 path/SHA, template version, bundle lock SHA를 확인한다.
- 지원 profile의 필수 role을 확인한다.
- v1 지원 profile에 `lyrics`, `lyric_timing`, `track_manifest`, `playlist_timing`, `package_manifest`가 들어오면 미지원 작업을 간증/시작편으로 재분류한 것으로 보고 거부한다.
- v1에서는 `hymn-lyrics/v1`, `playlist/v1`을 unsupported로 중단한다. portable v3의 pinned 02·04·06에는 이 제한을 적용하지 않는다.

`validate-job` PASS가 없으면 timeline, render, package 또는 delivery로 가지 않는다.

### `build-timeline`

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" build-timeline --spec "$TIMELINE_SPEC" --output "$TIMELINE_OUTPUT"
```

이 명령은 SSOT renderer가 아니라 결정적 저수준 ffconcat primitive다. 입력 spec의 exact shape는 다음과 같다.

```json
{
  "schema": "plugify.hymn-letter.still-timeline/1",
  "fps": 30,
  "expected_frames": 7223,
  "intervals": [
    {"file": "/absolute/path/frame-a.png", "frames": 30},
    {"file": "/absolute/path/frame-b.png", "frames": 7193}
  ]
}
```

역할:

- exact spec key와 interval key, FFmpeg가 안전하게 받는 `1..1000` 정수 fps와 `1..2147483647` 정수 frame/전체 frame, 실제 regular-file path를 검사한다. 파일이 decode 가능한 이미지인지는 이 명령이 판정하지 않는다.
- interval frame 합이 `expected_frames`와 정확히 같은지 검사한다.
- 모든 ffconcat `file` stanza와 마지막 반복 file에 spec의 `option framerate`를 쓴다.
- 기존 output을 덮어쓰지 않고 새 ffconcat 파일을 만든다.

이 primitive는 일반 결정성 검사용으로 `1..1000` 범위의 정수 fps를 받을 수 있다. 하지만 **찬송편지 production profile adapter**가 만드는 spec은 공통 SSOT의 lock과 frame rule에서 유도된 `fps: 30`이어야 하며, QC가 이를 다시 확인한다. profile adapter가 먼저 godowon-office의 tracked `hymn_letter_visual_template.py`를 import해 SRT parse, actual-pixel layout, background, raster, interval을 생성한다. `build-timeline` 자체가 SSOT import나 `validate-job`을 대신한다고 주장하지 않는다.

이 명령은 대본·caption timing·오디오·visual template를 수정하지 않으며 timeline 생성만으로 최종 H.264 QC PASS를 주장할 수 없다.

### `verify-package`

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" verify-package --package-dir "$PACKAGE_DIR" --sums "$SUMS_FILE"
```

역할:

- package와 checksum 파일의 symlink·경로 이탈·비정상 entry를 거부한다.
- `SHA256SUMS.txt`를 제외한 실제 regular-file 집합과 checksum entry 집합의 누락·초과를 확인한다.
- 각 payload SHA-256을 다시 계산해 checksum과 비교한다.

이 저수준 명령은 영상별 job/spec/renderer/template/layout/QC의 **의미**나 최종 H.264 boundary PASS를 해석하지 않는다. package를 만들기 전에 Skill이 [qc-contract.md](qc-contract.md)의 semantic evidence gate를 별도로 통과시켜야 하며, QC FAIL·UNVERIFIED·`SUPERSEDED` artifact를 checksum에 넣어 정상 package처럼 만들면 안 된다.

`verify-package` PASS는 **로컬 package 무결성**만 뜻한다. package를 portable renderer라 하거나 Drive/YouTube/알림 완료 증거로 해석하지 않는다.

위 세 **v1 명령**은 low-level validation primitive이며 render, media QC, package 의미 검토, 외부 delivery를 실행하지 않는다. 실제 인자는 실행 중인 CLI의 `--help`를 정본으로 삼는다. 성공은 종료코드 `0`과 한 줄 JSON stdout으로 판정한다. 인자 파싱 뒤 검증 실패는 비정상 종료코드와 stderr `ERROR[n]`을 쓰며, 필수 인자 누락·알 수 없는 flag 같은 argparse 사용법 오류는 종료코드 `2`와 `usage:/error:` 형식을 쓴다.

| exit | 의미 |
|---:|---|
| `2` | schema/shape/value 오류 |
| `3` | 필수 파일·디렉터리 누락 |
| `4` | SHA 또는 canonical lock 불일치 |
| `6` | 아직 승인되지 않은 profile 또는 pinned inventory에 없는 episode |
| `7` | unsafe path/symlink/overwrite 시도 |
| `11` | package 구조·checksum set 오류 |

portable v3 wrapper는 render/QC/upload-ready/package subcommand를 가진다. office release/job/source-bundle lock과 transitive renderer/QC/package module 8개의 SHA를 검증한다. 별도 `upload_ready_validator.py`도 wrapper의 hard-coded SHA와 일치할 때만 로드한다.

## 3. Render와 로컬 QC

### 승인 전 음성 마스터

편간 음량이나 한 편 안의 말소리 편차를 고쳐야 할 때는 episode renderer에서 오디오 필터를 쓰지 않는다. 원본 녹음은 그대로 두고, tracked `godo-hymns/tools/hymn_letter_speech_master.py`로 새 음성 마스터 후보와 QC JSON을 만든다. `hymn-letter-speech-master-v1`의 기준은 1편의 청감 레벨을 따른다: stereo 48kHz AAC-LC, integrated `-18.0 LUFS`, true peak `<= -2.0 dBTP`, LRA `<= 6.3 LU`, 무음 제외 3초 short-term loudness `P90-P10 <= 6.0 LU`. mono 원본은 stereo 양 채널에 같은 신호로 명시적으로 복제해 player별 mono gain 차이를 없앤다.

후보 report가 source SHA 불변, no-overwrite, 출력 규격·길이, loudness gate를 모두 통과하고 사람이 **그 후보의 정확한 SHA**를 승인한 뒤에만 새 video job의 `approved_audio`가 된다. 승인 전 후보를 기존 `approved_audio`와 바꾸거나 final이라고 부르지 않는다. 공통 visual template lock에는 음량 값을 넣지 않는다.

1. exact job lock과 `render.execute` 승인을 확인한다.
2. 새 run root의 candidate 경로에만 렌더한다. source와 기존 final은 읽기 전용이다.
3. 01·03·05의 새로 승인된 AAC-LC는 filter 없이 stream-copy한다. 04·06은 승인 MP3를 exact filter-free AAC-LC 256k command로 변환하고, 02는 12개 MP3의 per-track trim metadata를 적용한 PCM concat 뒤 한 번만 AAC-LC로 encode한다.
4. 최종 muxed MP4에서 [qc-contract.md](qc-contract.md)의 자막·오디오·전체 decode·spec 검사를 실행한다.
5. **최종 H.264를 decode한 실제 cue 경계 검사**가 PASS해야 한다. 생성 PNG나 layout manifest만 검사해서는 안 된다.
6. 자동 QC와 별도 사람 review receipt가 모두 있은 뒤에만 candidate를 final로 atomic promote한다.

07–26 external-SRT QC는 승인 SRT와 전달 SRT의 byte/SHA exact match, UTF-8/LF 계약, MP4 subtitle stream 0개, H.264 전체 decode, 오디오 불변/승인 변환을 검사한다. 또한 SRT의 모든 cue에 대해 `first-1 / first / last / last+1` 실제 H.264 프레임을 decode하여 같은 clean backplate와 비교한다. 이 경계 검사가 PASS해야 “자막이 영상에 굽히지 않았다”고 보고할 수 있다.

공통 템플릿을 바꿔야 한다면 한 편에 override하지 않는다. 새 template version/lock을 발행하고 영향받는 찬송편지 영상의 golden 회귀와 교차 QC를 다시 수행한다.

## 4. Package

- 01–06 QC PASS final, thumbnail, layout, QC, review receipt, renderer/job/template/audio lineage provenance를 모은다.
- `verify-upload-ready`가 실제 final/source를 모두 probe하고 승인 authority와 receipt에 exact-bind한 뒤에만 `package --plan`을 실행한다.
- deterministic package manifest와 path-sorted `SHA256SUMS.txt`를 생성한 뒤 v3 `verify-package`로 exact set, source bundle object set, release/job/lock/module SHA를 다시 검사한다.
- 아직 준비되지 않은 26편을 빈 파일이나 placeholder PASS로 채우지 않는다.
- 전체 26편 release를 만들 때는 정확히 1+12+12+1 구조와 각 episode ID의 중복·누락을 별도로 검사한다.
- package의 code snapshot과 완전한 source bundle은 독립 재현/감사용이다. 실행 시에는 package 안 release lock을 기준으로 package code/source root를 명시하거나 같은 commit의 tracked SSOT를 쓴다.

17,327 all-zero samples prove a 0.392902-second noncanonical timeline defect; they are not the proven direct cause of the audible spike.

Without QuickTime output capture, codec versus interleave/nearby H.264 keyframe contribution remains unresolved.

The safe path removes both per-track MP3 trim metadata loss and MOV+MP3 playback risk.

## 5. Delivery

외부 동작 전에는 [authority-boundaries.md](authority-boundaries.md)를 읽는다. 순서는 다음과 같으며 각 단계는 독립 권한과 영수증을 가진다.

1. `drive.upload_verify`: 승인 계정·폴더에 업로드하고 remote ID/size/download SHA/ACL을 다시 읽는다.
2. `youtube.stage_private`: 승인 channel에 private로 업로드하고 remote 상태를 확인한다.
3. `youtube.publish`: 별도 승인 후 검증된 video ID의 visibility만 변경한다.
4. `bot.notify`: manifest가 요구한 선행 영수증을 확인한 뒤 승인 수신자에게 최소 메타데이터만 보낸다.

Drive와 YouTube는 서로를 대신하지 않는다. Drive 완료가 YouTube staging을 허용하지 않고, private staging이 publish 승인을 뜻하지 않으며, package PASS가 bot 알림 권한을 뜻하지 않는다.

## 6. 상태와 중단 조건

Artifact 상태:

```text
DRAFT → VALIDATED → INPUTS_LOCKED → RENDER_AUTHORIZED
→ RENDERED_UNVERIFIED → QC_PASSED → REVIEW_APPROVED
→ PROMOTED_FINAL → PACKAGED → READY_FOR_DELIVERY → CLOSED
```

외부 상태는 Drive, YouTube staging, YouTube publishing, bot 각각 따로 기록한다. `CLOSED`는 artifact만 닫혔다는 뜻이 아니다. manifest에서 요청한 외부 단계가 모두 `VERIFIED`이거나 명시적으로 `NOT_REQUESTED`이고, 어떤 단계도 `AMBIGUOUS`가 아닐 때만 overall 상태를 `CLOSED`로 둔다. timeout이나 응답 유실은 `AMBIGUOUS`로 남기고 자동 재시도하지 않는다. read-only reconcile로 remote 상태를 확인한 뒤 다음 권한을 요청한다.

다음 경우 즉시 중단한다.

- input/module/asset/lock SHA 불일치
- 승인 대본·자막·오디오의 변경 또는 timing 차이
- 기존 output 존재
- ffconcat file과 30fps option 수 불일치
- 오디오 stream/payload/packet/duration 불일치
- 최종 H.264 boundary 또는 전체 decode 실패
- 지원되지 않은 profile
- 외부 계정·채널·폴더·수신자 불일치
- mutation 성공 여부가 불명확함

스킬 출하 후 첫 실제 후속편 한 쌍은 관찰 대상으로 남긴다. 실제 speech-master-style M4A의 pre-render 관찰에서 production 03·05의 `movie_timescale: 384000`을 복사할 수 없다는 점은 확인했고 후보 계약을 probe-bound 값으로 고쳤지만, 이것은 한 쌍의 완주 증거가 아니다. 실제 승인 대본·speech-master AAC-LC 또는 catalog MP3·실제 시각 자산으로 intake preflight → candidate render → semantic QC → 사람 청취/화면 승인 → 독립 재렌더 비교를 완료하고, exact CLI/QC receipt를 대조한 fresh review가 누락을 확인해야 공정을 닫는다. 음성 방식·시각 자산 또는 권한이 미정이면 첫 실전 관찰은 열린 제한사항으로 보고한다.
