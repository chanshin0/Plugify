# 찬송편지 외부 동작 권한 경계

이 문서는 고도원 찬송편지 26편 공정에서 로컬 산출물 생성과 외부 상태 변경을 분리한다. `delivery_intent`는 희망 동작을 적는 필드일 뿐 권한이 아니다.

## 공통 승인 영수증

각 mutation은 그 동작 전용의 명시적 승인 영수증을 요구한다. 한 영수증으로 다음 동작을 묵시적으로 허용하지 않는다.

필수 필드:

- `action`: 아래 표의 정확한 권한 이름
- `subject_sha256`: 선택한 경로의 job/candidate lock, 영상 또는 package manifest의 정확한 SHA-256
- `target`: output root, Drive folder, YouTube channel/video, bot recipient처럼 실제 변경 대상
- `actor`와 `authorized_at`
- `expires_at`
- 한 번만 쓸 수 있는 `nonce`
- YouTube 동작이면 허용 visibility

credential, OAuth token, cookie는 manifest·영수증·로그에 넣지 않는다. 실행 직전 connector가 보고하는 실제 계정·채널·폴더·수신자를 영수증의 `target`과 비교한다.

## 권한 표

| 경계 | 권한 이름 | 선행 증거 | 허용되는 일 | 성공 영수증 |
|---|---|---|---|---|
| 로컬 렌더 | `render.execute` | legacy는 `validate-job` PASS; 후속편은 현재 project prepare + 독립 `verify-run` PASS. 두 경로 모두 해당 template/release/runtime lock PASS와 새 output 경로 | 승인된 exact job/candidate lock으로 candidate와 QC 자산 생성 | candidate path/SHA, renderer·job/candidate·template/release SHA |
| Drive 업로드+다시읽기 | `drive.upload_verify` | QC PASS package와 `verify-package` PASS | 승인된 계정의 정확한 폴더에 업로드하고 다시 내려받아 확인 | remote file IDs, size, download SHA, ACL snapshot, verified time |
| YouTube 비공개 staging | `youtube.stage_private` | QC PASS 영상·thumbnail·metadata hash | 승인 channel에 `private`로만 업로드 | video ID, channel ID, visibility=`private`, duration/processing read-back |
| YouTube 공개 전환 | `youtube.publish` | 검증된 private video ID와 별도 publish 승인 | 영수증에 적힌 visibility로만 변경 | video ID, 최종 visibility, published/read-back time |
| YouTube 엔드스크린 | `youtube.end_screen_configure` | 두 영상의 검증된 video ID, 선택 가능한 visibility, 승인된 홀수/짝수 Studio 원형과 별도 승인 | 승인된 한 쌍에 홀수→짝수·짝수→홀수 특정 동영상 요소를 복사·저장 | source template video ID, target video IDs, 방향, 표시 구간, saved/read-back time |
| 업무봇 알림 | `bot.notify` | manifest가 요구한 Drive/YouTube 영수증과 최소 메타데이터 payload | 승인 수신자에게 1회 알림 | channel/recipient, message ID, sent time, payload SHA |

로컬 read-only 검사와 원격 read-only `reconcile`에는 mutation 권한이 필요하지 않지만, 범위를 벗어난 파일·계정은 읽지 않는다.

후속편은 프로젝트의 잠긴 prepare/verify 계약을 사용하며 구형 `validate-job`
PASS를 대신 만들어 제출하지 않는다. prepare·독립 verify 통과는 실행 가능성
증거일 뿐 `render.execute` 승인이나 사람 검수·외부 전달 권한이 아니다.
후속편에도 위 승인 영수증과 외부 동작 분리는 그대로 적용한다.

## 단계별 규칙

### 렌더

- 기존 파일을 덮어쓰지 않고 새 run root의 candidate에만 쓴다.
- 렌더 완료는 QC PASS가 아니다. 최종 H.264 경계 QC와 오디오·자막 보존 검사가 끝난 뒤에만 final로 승격한다.
- 승인된 대본, 자막, 오디오, EDL 또는 시각 template를 바꾸면 영수증과 run을 새로 만든다.

### Drive

- 로컬 package 검증은 Drive 업로드 증거가 아니다.
- 업로드 직전에 같은 package에서 `verify-package`를 다시 실행하고, 가능하면 content-addressed 읽기 전용 snapshot을 만든 뒤 그 snapshot만 전송한다. 검증 뒤 원래 경로가 그대로라는 가정으로 업로드하지 않는다.
- uploader는 전송하면서 읽은 각 파일 바이트도 hash해 검증 receipt의 payload hash와 같음을 확인한다.
- 업로드 API 성공 응답만으로 완료 처리하지 않는다. remote ID를 다시 읽고 가능한 경우 내려받아 package manifest의 크기·SHA와 비교한다.
- ACL을 읽어 승인된 공유 범위인지 확인한다. 대상 폴더 문구나 예정 경로만으로 `VERIFIED`라 하지 않는다.
- 검증이 끝나기 전 업무봇 알림의 Drive 완료 문구를 만들지 않는다.

### YouTube

- staging은 항상 `private`다. `delivery_intent.youtube_publish=true`여도 별도 `youtube.publish` 승인이 없으면 visibility를 높이지 않는다.
- staging 직전에 영상·thumbnail·metadata의 SHA를 다시 확인하고, 실제 업로드 스트림에서 계산한 영상 hash를 승인 receipt의 subject와 대조한다.
- private staging 후 실제 channel ID, video ID, visibility, duration, processing state, thumbnail 적용 상태를 다시 읽는다.
- 공식 YouTube Data API v3 CLI는 resumable private upload, metadata, custom
  thumbnail과 processing/status read-back까지만 기본 자동화한다. API에 없는
  엔드스크린을 업로드 성공으로 추론하지 않는다.
- publish 영수증은 검증된 remote video ID와 정확한 최종 visibility에 결박한다. 다른 영상이나 다른 채널에 재사용하지 않는다.
- 엔드스크린은 두 video ID가 모두 확인된 뒤 별도 권한으로 설정한다. 1–8편의
  사용자 수동 설정은 덮어쓰지 않는다. 이후 홀수편은 7편, 짝수편은 8편에서
  Studio `동영상에서 가져오기`로 배치·시간을 복사하고 `특정 동영상` 대상만
  새 짝으로 바꾼다. 홀수→짝수와 짝수→홀수를 각각 미리보기·저장·기록한다.

### 업무봇

- `bot_notify=true`는 전송 승인이 아니다. prerequisite receipt가 모두 verified이고 `bot.notify` 영수증이 있어야 한다.
- 메시지는 편 ID, 검증 상태, 안전한 링크 같은 최소 메타데이터만 포함한다. 대본·전체 자막·로컬 절대경로·계정정보·credential은 보내지 않는다.
- message ID가 없는 성공 보고는 `SENT_UNVERIFIED`로 남긴다.

## 실패·불명확 상태

- timeout이나 응답 유실로 성공 여부가 불명확하면 `AMBIGUOUS`로 기록한다.
- `AMBIGUOUS`에서는 같은 mutation을 자동 재시도하지 않는다. remote ID와 상태를 read-only로 reconcile해 중복 업로드·중복 공개·중복 알림 가능성을 먼저 제거한다.
- 실패 영수증과 부분 성공 remote ID를 지우지 않는다. 새 시도는 새 nonce와 명시적 승인 범위 안에서만 한다.

## 증거 해석 제한

v17 로컬 review package는 40개 payload 해시와 세 영상의 로컬 QC를 입증한다. 그러나 package 안의 renderer는 외부 작업공간 입력과 이전 renderer에 의존하므로 **portable renderer가 아니다**. 또한 대상 Drive 폴더 문구만 있고 remote file ID·다운로드 SHA·ACL·message ID가 없으므로 **Drive 업로드나 알림 완료 증거도 아니다**. 이 두 주장을 package 존재만으로 확대하지 않는다.
