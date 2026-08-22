# 찬송편지 QC 계약

> 2026-08-22 현재 portable v3 QC는 `godowon.hymn-letter.v3-release-lock/1`, `godowon.hymn-letter.v3-job/1`, `godowon.hymn-letter.source-bundle/1`을 그대로 입력으로 받는다. Plugify wrapper는 schema inventing이 아니라 release/job/source-root/module SHA 검증과 wrapper receipt 추가만 한다.

이 계약은 고도원 찬송편지 26편에만 적용한다. “파일이 만들어졌다”와 “최종 영상이 승인 입력·공통 시각·프레임 경계를 보존했다”를 구분하며, 기계 검사가 하나라도 빠지면 fail closed한다.

## 현재 portable v3 기준선

- tracked release: sibling `godowon-office/godo-hymns/releases/hymn-letter-caption-v3-gapless-aac-20260822/release.lock.json`
- renderer modules: release lock의 repo-relative path와 SHA-256을 매 실행 전에 재검산
- template version: `godowon-hymn-caption-v3/1`
- styles: center 68px·최대 2줄, dense 60px·최대 3줄
- frame rule: `start=ceil(start_ms*30/1000)`, `end=ceil(end_ms*30/1000)-1`
- output baseline: MP4 + AAC-LC, 1920×1080, 30fps, H.264 High, yuv420p, Rec.709

이 값 중 하나를 바꾸는 것은 에피소드 설정 변경이 아니라 새 template release다. 새 version·lock과 영향받는 영상의 전체 회귀 검토가 필요하다.

## 필수 게이트

### 1. Job과 입력

- portable v3 job/release/source-bundle lock의 SHA가 서로 정확히 결박되어야 한다.
- release lock의 listed job SHA, source bundle lock SHA, environment lock SHA, golden lock SHA가 모두 다시 계산되어야 한다.
- portable v3 execution preflight는 release-pinned environment probe를 선택한 Python에서 실행해 `LANG=C`, `LC_ALL=C`, `LC_CTYPE=C`, runtime locale `C`, filesystem encoding `utf-8`뿐 아니라 OS/machine, Python binary/version/SHA/implementation/compiler, Pillow·numpy, FreeType/libjpeg/zlib, `PATH` ffmpeg/ffprobe identity/version을 environment lock 전체와 exact-match한다. upload/package에 명시한 `ffprobe` basename/SHA도 같아야 한다. macOS에서 `C.UTF-8`를 대용하거나 locale을 묵시적으로 상속하면 environment match가 아니다. `validate-job`·`verify-source-bundle`은 toolchain을 실행하지 않는 read-only 구조/hash 검사다.
- reference-bit-exact는 `environment.lock.json`이 exact match일 때만 `PASS`가 가능하다. 그렇지 않으면 `NOT_APPLICABLE`이며 semantic PASS로 둔갑시키지 않는다.
- renderer module SHA가 하나라도 64-zero sentinel이면 render와 모든 QC/upload/package가 실패해야 한다. 모든 module pin이 nonzero인 상태에서 golden이 `status: BOOTSTRAP_REQUIRED`이거나 `reference_output_sha256: null`이거나 output SHA가 64-zero이면 첫 render와 semantic QC만 가능하다. reference-bit-exact, upload-ready promotion, package는 실패해야 한다. 현재 compiled production release와 measured golden은 nonzero지만, 별도 human approval receipt가 없으면 promotion/package 권한은 여전히 없다.
- 02 playlist의 canonical captions는 2026-08-22 제목 순서 수정본을 가리킨다. 제목 카드는 1번을 시작에 한 번, 2–12번을 직전 곡의 outro에 한 번씩 둔다.
- 02의 12 track rows는 누적 sample 기준이며 `start_frame=ceil(start_sample*30/44100)`이다. combined SRT는 half-up `(samples*1000+22050)//44100` offset, lyric cue 267개, title cue 12개, 총 279개를 가져야 한다. title 직렬화는 `"{sequence}. {hymn_number}장  {title}"`처럼 `장` 뒤 두 칸이며, 표시용 expected title은 한 칸이다.

- [job-manifest.v2.schema.json](job-manifest.v2.schema.json)과 [episode-inventory.v2.json](episode-inventory.v2.json)으로 office-native v3 job을 엄격히 검증한다.
- 입력은 절대경로가 아니라 `sha256:<64hex>` object ID이며, `SOURCE_ROOT/objects/sha256/<prefix>/<rest>` 아래 bytes·size를 다시 검산한다.
- source와 output은 분리하고 기존 output을 덮어쓰지 않는다.
- `hymn-lyrics/v1`과 `playlist/v1`은 현재 release에 잠긴 04·06 및 02에 한해 지원한다. inventory 밖 항목은 다른 profile로 우회하지 않는다.

### 2. 공통 시각 SSOT

- package 사본이 아니라 tracked module을 import한다.
- module path/SHA, template version, bundle lock SHA, config SHA, base/header/font asset SHA를 렌더 전에 확인한다.
- 자산이나 lock을 한 바이트라도 변조한 fixture가 거부되는지 회귀검사한다.
- 에피소드별 좌표, 폰트, safe area, 줄맞춤, framerate override는 허용하지 않는다.
- 자막 raster는 공통 모듈의 Pillow actual-pixel renderer로만 만든다. center 최대 2줄, dense 최대 3줄, safe area, 배경 비겹침, 실제 glyph bbox를 검사한다.

### 3. 대본·자막 불변

- 승인 script와 captions 원본 SHA를 기록한다. script가 별도 파일이면 `approved_script` role로 함께 잠근다.
- SRT cue 수와 순서, 빈 cue, overlap, 각 cue의 원문, 시작·종료 millisecond를 검사한다.
- 렌더 전후 canonical text hash와 timing hash를 비교한다. 표시용 줄바꿈 외 문자 변경, cue 분할·병합, 시간 이동을 허용하지 않는다.
- 공통 모듈의 `assert_layout_preserves_cues`를 통과해야 한다.
- 수정이 필요하면 manifest 옵션으로 고치지 않고 새 승인 source와 새 run을 만든다.

### 4. 타임라인

- 모든 ffconcat `file` stanza마다 `option framerate 30`이 있어야 한다. 마지막 반복 file도 예외가 아니다.
- `file` 수와 30fps option 수가 같아야 한다.
- interval이 겹치거나 비면 실패하고 각 frame 수와 전체 frame 수는 `1..2147483647` 범위여야 하며, 합이 기대 전체 frame 수와 정확히 같아야 한다.
- production profile adapter가 공통 모듈의 frame rule과 raster builder로 image interval spec을 만든다. 저수준 `build-timeline`은 그 spec을 검증해 ffconcat만 쓰며 SSOT를 import하거나 layout을 만들지 않는다.
- `build-timeline` primitive는 테스트 가능한 일반 규칙으로 `1..1000` 범위의 정수 fps를 받지만, 찬송편지 production spec은 template lock에 따라 반드시 30fps여야 한다. QC에서 이를 다시 검사한다.
- v16은 정지 PNG가 25fps로 해석되어 cue 경계가 이동한 폐기본이다. 뒤에서 `fps=30`만 거는 방식으로 복구됐다고 간주하지 않는다.

### 5. 오디오 보존

- 음량 보정이 필요하면 renderer 밖의 승인 전 단계에서 tracked `godo-hymns/tools/hymn_letter_speech_master.py`로 새 후보를 만든다. `hymn-letter-speech-master-v1` report는 source SHA 전후 일치, 새 출력/no-overwrite, stereo 48kHz AAC-LC, `-18.0 LUFS ±0.3`, true peak `<= -2.0 dBTP`, LRA `<= 6.3 LU`, 무음 제외 3초 short-term `P90-P10 <= 6.0 LU`, 원본 대비 길이 차 `<= 1 AAC frame`을 모두 증명해야 한다.
- mono 원본은 master 단계에서 명시적으로 dual-channel stereo로 복제하고, 그 뒤의 loudness 측정은 stereo 출력 기준으로 한다. source recording은 수정하지 않는다.
- 사람 review receipt에는 master 후보 SHA, reviewer, decision, timestamp가 있어야 한다. 그 승인이 생기기 전에는 후보를 manifest의 `approved_audio`로 잠그거나 final로 승격하지 않는다.
- 같은 시리즈의 speech master batch는 각 후보의 post-encode integrated loudness를 교차 비교해 최대 차이가 `0.5 LU` 이하여야 한다. 기준 1편을 다시 인코딩하지 않으며, 현재 잠금 기준은 `-18.01 LUFS`다. 개별 후보 PASS만 있고 편간 비교 보고가 없으면 batch QC는 미완료다.
- 01·03·05의 승인 AAC-LC는 filter 없이 stream-copy한다. source/final audio payload가 exact match하고 encoder는 explicit null이어야 한다.
- 04·06은 승인 standalone MP3에서 `-c:v copy -c:a aac -profile:a aac_low -b:a 256k -ar 44100 -ac 2`로 변환한다. audio filter, trim, resample shortcut, `-shortest`, extra argv는 금지한다.
- 02는 승인 standalone MP3 12개를 exact order로 각각 skip-samples/discard-padding을 적용해 decode하고, `[i:a]asetpts=PTS-STARTPTS` 12개와 exact `concat=n=12:v=0:a=1` graph로 continuous PCM을 만든 뒤 AAC-LC 256k로 한 번 encode한다. 과거 pre-concatenated MP3를 derivative input으로 쓰는 것은 금지한다.
- 02 authority/derivation/QC는 각 track의 source SHA, skip/discard, decoded PCM SHA, ordered domain-separated PCM composite, decoded total samples, 제거된 internal gap samples, start/tail PASS를 서로 exact-bind한다.
- 02 production raw concatenated f32le PCM SHA는 `2e3e983f5a71aa775bd0360bc29efa229d3656e6ff52c981236fc776fc3f9f63`, 실제 skip/discard+decoded-PCM vector의 domain-manifest SHA는 `a18ae5063bb626971bdb1897a311b79b145a679655b089f588cfa1af6b5cbf76`다. `dc3d9f…`는 fake vector를 쓰는 frozen evaluator 전용이며 successor authority로 허용하지 않는다.
- 최종 muxed MP4에서 source/output의 container-independent audio payload SHA와 실제 probe를 비교한다. 01·03·05는 payload 동일, 02·04·06은 승인 derivative payload와 final payload 동일이어야 한다.
- 파일 전체 SHA나 청취 확인만으로 오디오 불변을 주장하지 않는다.

### 6. 최종 비디오와 실제 압축 경계

- candidate가 아니라 최종 muxed H.264 MP4의 video+audio 전체 decode를 실행한다.
- resolution, fps, pix_fmt, codec/profile, Rec.709 metadata, frame 수와 presentation PTS sequence를 확인한다.
- H.264 B-frame의 packet-order PTS 재정렬을 오류로 오판하지 않는다. DTS 엄격 증가와 presentation-order PTS 연속성을 별도로 본다.
- 생성 PNG나 layout manifest만 보지 않고 **최종 H.264에서 실제 프레임을 decode**해 기대 Pillow PNG와 비교한다.

Profile별 경계 정책:

| profile | 필수 실제 출력 검사 |
|---|---|
| `start-hybrid/v1` | source-video→공통화면 전환의 직전/첫/title 마지막/첫 caption 프레임과, 공통화면 전 구간 frame 단위 PSNR |
| `testimony-static/v1` | 모든 interval의 first/last endpoint와 가능한 각 cue의 `first-1 / first / last / last+1` reference 비교 |
| `hymn-lyrics/v1` | center style, MP4 + AAC-LC, 모든 interval의 first/last endpoint와 cue boundary 비교 |
| `playlist/v1` | dense style, active-row PNG state + chapter/gap/title-card timing + actual H.264 boundary 비교 |

MAE/PSNR threshold, crop, decode batch size는 versioned QC 구현이 소유한다. episode manifest가 완화할 수 없다.

### 7. 공통성·사람 검토

- 같은 release의 episode들이 같은 template version/lock, module SHA, Pillow renderer, safe area, 최대 줄 수를 쓰는지 교차 검사한다.
- 100px 대표 프레임 2장과 최장 cue 1장으로 contact sheet를 만들 수 있는 profile은 이를 생성한다.
- 사람 검토는 자동 QC JSON을 수정해 흉내 내지 않는다. reviewer, reviewed artifact SHA, decision, timestamp가 있는 별도 review receipt를 남긴다.
- upload 승인에는 별도 `godowon.hymn-letter.human-approval-receipt/1`의 exact 01–06 rows가 필요하다. 각 row는 `decision: APPROVED`, reviewer/reviewed_at, exact `final_file_sha256`, exact `artifact_audio_payload_sha256`를 함께 잠근다. package plan의 이름/시간만으로 이 receipt를 합성하지 않는다. 사람이 실제 오디오를 듣지 못했으면 기술 QC 결과는 local 검토본·`promotion_pending`으로 남긴다.
- 공통 템플릿 변경은 golden 370 layout exact match, compressed-boundary fixture, asset/lock 변조 거부, 기존 대표 영상 재렌더·교차 QC를 요구한다.

### 8. Package

- QC PASS 영상과 그 영상의 exact job/spec/renderer/template/layout/QC SHA가 모두 있어야 package 후보가 된다.
- `verify-upload-ready`는 외부 trusted release lock과 별도 human approval receipt를 요구한다. final 6개와 승인 source 17개를 실제 probe하고 MP4 major brand/H.264/AAC-LC, job/golden frame·final SHA, 02 production source/PCM/SRT/chapter vector, source/derivative payload, exact human approval, full decode/AVFoundation/real-time tail PASS를 검사한다.
- [run-receipt.schema.json](run-receipt.schema.json)의 `plugify.hymn-letter.run-receipt/1`은 public `render`/`qc` 호출을 기록하는 Plugify wrapper receipt일 뿐 package evidence용 producer receipt가 아니다. Package plan의 `render_receipt`와 `qc_receipt`에는 각 wrapper의 `delegate_payload.render_receipt`와 `delegate_payload.qc_receipt`가 가리키는 office-native `godowon.hymn-letter.v3-render-receipt/1`·`godowon.hymn-letter.v3-qc-receipt/1` 절대경로를 넣는다. Wrapper의 top-level `receipt` 경로를 넣으면 안 된다.
- Exact plan은 schema `godowon.hymn-letter.upload-ready-package-plan/1`과 top-level `schema`/`release`/`source_root`/`episodes`만 가지며, exact 01–06 각 row는 `sequence`/`job`/`render_receipt`/`qc_receipt`만 가진다. Native QC receipt는 semantic, upload-ready, reference-bit gate가 모두 `PASS`이고 같은 native render receipt의 SHA를 결박해야 한다. 최소 유효 JSON은 [workflow.md](workflow.md#package-plan-receipt-contract)를 따른다.
- `package --plan`은 successor의 유일한 public builder다. release에 SHA로 잠긴 office package module을 새 경로에서 실행한 뒤 Plugify가 독립적으로 검증·재구성한다. 위임 전 exact 12 office-native render/QC receipt bytes를 stable snapshot하고 office stage의 사본이 byte-equal인지 확인하며, path-free canonical `delegation-inputs.lock.json`에 release/source/package-module/human-approval/job/receipt SHA를 잠근다. package 안에 release/jobs/locks, 모든 참조 source object, office 8 modules, Plugify wrapper/validator/schema/docs, receipts를 포함한다.
- deterministic package manifest와 path-sorted `SHA256SUMS.txt` exact bytes(LF/final newline/two-space)를 만들고 모든 payload를 다시 읽어 누락·초과·hash 불일치를 검사한다. input과 output root를 분리하고 sibling stage를 검증한 뒤에만 원자 승격하며 overwrite와 `.DS_Store`는 거부한다.
- v3 `verify-package`는 package 밖의 compiled-SHA trusted release lock과 human approval receipt를 입력받아 packaged copies와 exact SHA를 비교한다. regular-file/checksum exact set뿐 아니라 source bundle object exact set, release job/lock SHA, renderer/QC/package module exact path/SHA, Plugify code snapshot bytes, 01–06 media/thumbnail, delegation input lock과 12 render/QC receipt chain을 판정하고 마지막에 exact-set을 다시 스캔한다. 외부 delegate attestation이 없으므로 historical origin은 정직하게 `UNATTESTED`; artifact/evidence integrity와 human approval은 별도 판정이다.
- local package PASS는 Drive 업로드·원격 다시읽기·ACL·YouTube 상태·업무봇 알림을 입증하지 않는다. 그 증거는 [authority-boundaries.md](authority-boundaries.md)의 별도 receipt가 소유한다.

17,327 all-zero samples prove a 0.392902-second noncanonical timeline defect; they are not the proven direct cause of the audible spike.

Without QuickTime output capture, codec versus interleave/nearby H.264 keyframe contribution remains unresolved.

The safe path removes both per-track MP3 trim metadata loss and MOV+MP3 playback risk.

## 통과 보고의 최소 필드

QC 보고에는 다음을 빠뜨리지 않는다.

- job manifest SHA와 profile
- renderer path/SHA 및 normalized command/FFmpeg version
- tracked module path/SHA, template version/lock/config/assets SHA
- 각 입력 path/role/SHA
- captions cue/text/timing 보존 결과
- audio stream/payload/packet/duration 보존 결과
- timeline frame 합, ffconcat file/30fps option 수
- 최종 output path/SHA/probe/full-decode 결과
- actual final H.264 boundary method, 검사 frame 수, 최악 점수, threshold, PASS/FAIL
- contact sheet와 별도 human-review receipt SHA(필요한 경우)

위 필드가 없는 기존 QC를 추정으로 채우지 않는다. provenance가 부족하면 그대로 `UNVERIFIED`로 보고한다.
