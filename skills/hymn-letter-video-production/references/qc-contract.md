# 찬송편지 QC 계약

이 계약은 고도원 찬송편지 26편에만 적용한다. “파일이 만들어졌다”와 “최종 영상이 승인 입력·공통 시각·프레임 경계를 보존했다”를 구분하며, 기계 검사가 하나라도 빠지면 fail closed한다.

## 현재 검증된 기준선

- tracked SSOT: `/mnt/c/work/godowon-office/godo-hymns/tools/hymn_letter_visual_template.py`
- module SHA-256: `0634d97c6eaa0a79f667108b551a7f65b0985bf810bd7e6ce9f950daab52cf80`
- template version: `hymn-letter-visual-v2`
- template lock SHA-256: `915c84bcb6d91b3d51fac77662baf10de9e6f51aed63784ab6a860f2a174698e`
- frame rule: `start=ceil(start_ms*30)`, `end=ceil(end_ms*30)-1`
- output baseline: 1920×1080, 30fps, H.264 High, yuv420p, Rec.709

이 값 중 하나를 바꾸는 것은 에피소드 설정 변경이 아니라 새 template release다. 새 version·lock과 영향받는 영상의 전체 회귀 검토가 필요하다.

## 필수 게이트

### 1. Job과 입력

- [job-manifest.schema.json](job-manifest.schema.json)으로 추가 필드까지 엄격히 검증한다.
- `inputs`의 각 `role`은 한 번만 나타나야 하며 모든 경로는 절대경로다.
- 현재 파일 SHA-256이 manifest와 같아야 한다. script, captions, audio, video, EDL, reference layout 중 하나라도 달라지면 중단한다.
- `references/episode-inventory.json`의 pinned SHA와 exact ID/kind/profile mapping이 일치해야 한다. inventory 밖 episode나 다른 kind/profile로 재분류한 episode는 거부한다.
- source와 output의 canonical path가 달라야 하고 `output.overwrite`는 반드시 `false`다.
- `hymn-lyrics/v1`과 `playlist/v1`은 승인된 source/timing/golden fixture가 아직 없으므로 profile gate에서 종료한다. 다른 profile로 우회하지 않는다.

### 2. 공통 시각 SSOT

- package 사본이 아니라 tracked module을 import한다.
- module path/SHA, template version, bundle lock SHA, config SHA, base/header/font asset SHA를 렌더 전에 확인한다.
- 자산이나 lock을 한 바이트라도 변조한 fixture가 거부되는지 회귀검사한다.
- 에피소드별 좌표, 폰트, safe area, 줄맞춤, framerate override는 허용하지 않는다.
- 자막 raster는 공통 모듈의 Pillow actual-pixel renderer로만 만든다. 최대 5줄, safe area, header 비겹침, 실제 glyph bbox를 검사한다.

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

- 승인 오디오는 filter 없이 stream copy한다. FFmpeg 계획에 audio filter나 audio re-encode가 있으면 실패한다.
- 최종 muxed MP4에서 source/output의 stream SHA와 container-independent payload SHA, packet 수, duration/time base, packet timestamp fingerprint를 비교한다.
- codec, sample rate, channel layout도 승인 입력과 같아야 한다.
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
| `hymn-lyrics/v1` | 미승인. lyric timing과 golden fixture가 승인되기 전 정책 없음으로 PASS하지 않음 |
| `playlist/v1` | 미승인. track order/gap/chapter/golden fixture가 승인되기 전 정책 없음으로 PASS하지 않음 |

MAE/PSNR threshold, crop, decode batch size는 versioned QC 구현이 소유한다. episode manifest가 완화할 수 없다.

### 7. 공통성·사람 검토

- 같은 release의 episode들이 같은 template version/lock, module SHA, Pillow renderer, safe area, 최대 줄 수를 쓰는지 교차 검사한다.
- 100px 대표 프레임 2장과 최장 cue 1장으로 contact sheet를 만들 수 있는 profile은 이를 생성한다.
- 사람 검토는 자동 QC JSON을 수정해 흉내 내지 않는다. reviewer, reviewed artifact SHA, decision, timestamp가 있는 별도 review receipt를 남긴다.
- 공통 템플릿 변경은 golden 370 layout exact match, compressed-boundary fixture, asset/lock 변조 거부, 기존 대표 영상 재렌더·교차 QC를 요구한다.

### 8. Package

- QC PASS 영상과 그 영상의 exact job/spec/renderer/template/layout/QC SHA가 모두 있어야 package 후보가 된다.
- package manifest와 `SHA256SUMS.txt`를 만들고 모든 payload를 다시 읽어 누락·초과·hash 불일치를 검사한다.
- `verify-package`는 checksum 파일을 제외한 local regular-file 집합과 checksum entry 집합의 exact match 및 payload SHA만 판정한다. semantic evidence 존재·PASS는 그 전에 별도 gate가 확인한다.
- package의 template/module 사본은 감사 snapshot이다. package 자체를 portable renderer라고 부르지 않는다.
- local package PASS는 Drive 업로드·원격 다시읽기·ACL·YouTube 상태·업무봇 알림을 입증하지 않는다. 그 증거는 [authority-boundaries.md](authority-boundaries.md)의 별도 receipt가 소유한다.

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
