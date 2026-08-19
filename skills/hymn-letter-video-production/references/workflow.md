# 고도원 찬송편지 26편 제작 워크플로우

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
| `start` | `start-hybrid/v1` | v17 시작편으로 증거 있음. 승인 interview/program video + 승인 audio + captions 필요 |
| `testimony_intro` | `testimony-static/v1` | v17 491·370으로 증거 있음. 승인 audio + captions 필요 |
| `hymn_lyrics` | `hymn-lyrics/v1` | **차단**. 승인 노래 source, 가사 timing, golden fixture가 확정되기 전 렌더 금지 |
| `playlist` | `playlist/v1` | **차단**. 승인 12곡 순서·gap·chapter timing과 golden fixture가 확정되기 전 렌더 금지 |

차단 profile을 유사한 지원 profile로 바꾸어 실행하지 않는다. 필요한 authoritative source와 승인만 요청하고 멈춘다.

지원 episode의 의미 정본은 [episode-inventory.json](episode-inventory.json)이다. 현재 검증된 항목은 `start`, `hymn-491-testimony`, `hymn-370-testimony` 세 개뿐이다. 최신 12곡 선정은 아직 확정되지 않았으므로 나머지 23편의 ID를 이전 선정표나 대본 언급만으로 만들지 않는다.

## 1. Intake와 manifest

먼저 26편 inventory에서 현재 episode의 ID·kind·profile과 승인된 입력을 확인한다.

- `validate-job`은 inventory 파일 자체의 고정 SHA와 exact `episode.id → kind → profile` mapping을 확인한다.
- inventory 밖 episode는 이름이 그럴듯해도 지원하지 않는다. 승인된 곡 선정과 입력이 생기면 inventory release와 regression을 함께 갱신한다.

- 승인 대본이 별도 파일이면 `approved_script` role로 넣는다.
- 승인 자막은 `captions`, 승인 오디오는 `approved_audio`, 시작편의 보존 영상은 `program_video`로 넣는다.
- EDL, reviewed ASS, reference layout, thumbnail, publishing metadata가 있으면 각각 별도 role과 SHA로 잠근다.
- 사람이 정해야 하는 가사, timing, cut, 곡 순서, gap, 공개 대상은 추측하지 않는다.

Manifest는 [job-manifest.schema.json](job-manifest.schema.json)의 정확한 7개 top-level key만 사용한다.

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

CLI 정본은 `scripts/hymn_video_flow.py`다. 어느 작업 디렉터리에서도 같은 진입점을 사용한다.

```bash
HYMN_LETTER_SKILL_DIR="/mnt/c/Work/Plugify/skills/hymn-letter-video-production"
JOB_MANIFEST="/absolute/path/job.json"
TIMELINE_SPEC="/absolute/path/timeline-spec.json"
TIMELINE_OUTPUT="/absolute/new/path/timeline.ffconcat"
PACKAGE_DIR="/absolute/path/package"
SUMS_FILE="$PACKAGE_DIR/SHA256SUMS.txt"
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" --help
```

### `validate-job`

```bash
python3 "$HYMN_LETTER_SKILL_DIR/scripts/hymn_video_flow.py" validate-job --manifest "$JOB_MANIFEST"
```

역할:

- manifest schema identifier, exact top/subkeys, absolute path, lowercase SHA-256, no-overwrite를 독립적으로 검사한다.
- 모든 input의 실제 SHA를 다시 계산하고 `role` 중복을 거부한다.
- episode kind와 profile의 조합을 검사한다.
- pinned episode inventory와 ID/kind/profile의 exact mapping을 검사한다.
- tracked visual module의 path/SHA, template version, bundle lock SHA를 확인한다.
- 지원 profile의 필수 role을 확인한다.
- 현재 지원 profile에 `lyrics`, `lyric_timing`, `track_manifest`, `playlist_timing`, `package_manifest`가 들어오면 미지원 가사·playlist 작업을 간증/시작편으로 재분류한 것으로 보고 거부한다.
- `hymn-lyrics/v1`, `playlist/v1`은 승인 계약이 생기기 전 unsupported exit로 중단한다.

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

세 명령은 low-level validation primitive이며 render, media QC, package 의미 검토, 외부 delivery를 실행하지 않는다. 실제 인자는 실행 중인 CLI의 `--help`를 정본으로 삼는다. 성공은 종료코드 `0`과 한 줄 JSON stdout으로 판정한다. 인자 파싱 뒤 검증 실패는 비정상 종료코드와 stderr `ERROR[n]`을 쓰며, 필수 인자 누락·알 수 없는 flag 같은 argparse 사용법 오류는 종료코드 `2`와 `usage:/error:` 형식을 쓴다.

| exit | 의미 |
|---:|---|
| `2` | schema/shape/value 오류 |
| `3` | 필수 파일·디렉터리 누락 |
| `4` | SHA 또는 canonical lock 불일치 |
| `6` | 아직 승인되지 않은 profile 또는 pinned inventory에 없는 episode |
| `7` | unsafe path/symlink/overwrite 시도 |
| `11` | package 구조·checksum set 오류 |

현재 skill CLI에는 render나 실제 H.264/audio/caption QC subcommand가 없다. 따라서 승인된 project renderer/QC가 생성한 exact renderer SHA·명령·report를 [qc-contract.md](qc-contract.md)로 검토해야 한다. 그러한 결정론적 report가 없으면 `RENDERED_UNVERIFIED`에서 멈추며, 문서 규칙만으로 QC를 통과했다고 쓰지 않는다.

## 3. Render와 로컬 QC

1. exact job lock과 `render.execute` 승인을 확인한다.
2. 새 run root의 candidate 경로에만 렌더한다. source와 기존 final은 읽기 전용이다.
3. 승인 오디오는 filter 없이 stream copy한다.
4. 최종 muxed MP4에서 [qc-contract.md](qc-contract.md)의 자막·오디오·전체 decode·spec 검사를 실행한다.
5. **최종 H.264를 decode한 실제 cue 경계 검사**가 PASS해야 한다. 생성 PNG나 layout manifest만 검사해서는 안 된다.
6. 자동 QC와 별도 사람 review receipt가 모두 있은 뒤에만 candidate를 final로 atomic promote한다.

공통 템플릿을 바꿔야 한다면 한 편에 override하지 않는다. 새 template version/lock을 발행하고 영향받는 찬송편지 영상의 golden 회귀와 교차 QC를 다시 수행한다.

## 4. Package

- QC PASS final, thumbnail, layout, QC, review receipt, renderer/job/template provenance를 모은다.
- package manifest와 `SHA256SUMS.txt`를 생성한 뒤 `verify-package`를 실행한다.
- 아직 준비되지 않은 26편을 빈 파일이나 placeholder PASS로 채우지 않는다.
- 전체 26편 release를 만들 때는 정확히 1+12+12+1 구조와 각 episode ID의 중복·누락을 별도로 검사한다.
- template/module 사본은 감사 snapshot으로만 포함한다. runtime은 계속 tracked SSOT를 import한다.

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

스킬 출하 후 첫 실제 찬송편지 run은 관찰 대상으로 남긴다. 실제 CLI/QC/remote receipt를 대조하고 fresh review가 누락을 확인해야 공정을 닫는다.
