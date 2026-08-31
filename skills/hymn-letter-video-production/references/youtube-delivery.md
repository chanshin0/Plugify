# 찬송편지 YouTube 전달

YouTube 업로드·공개·엔드스크린 요청에서만 이 문서를 읽는다.

## 공식 CLI 가능 범위

YouTube Data API v3의 `videos.insert`와 resumable upload로 정확한 MP4를
`private` staging할 수 있다. 같은 요청에서 title, description, tags, category를
설정하고 `thumbnails.set`으로 사용자 썸네일을 붙인다. 반환 video ID로
`videos.list`의 snippet, status, contentDetails, processingDetails를 다시 읽어
channel ID, visibility, duration, processing 결과와 썸네일을 검증한다.

공식 근거:

- <https://developers.google.com/youtube/v3/guides/uploading_a_video>
- <https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol>
- <https://developers.google.com/youtube/v3/docs/thumbnails/set>
- <https://developers.google.com/youtube/v3/guides/implementation/videos>

CLI 실행 전 Google Cloud의 YouTube Data API v3 활성화, Desktop OAuth client,
정확한 채널 계정의 1회 동의와 repo 밖 token store가 필요하다. credential과
refresh token을 manifest·로그·레포에 넣지 않는다. `channels.list(mine=true)`로
실제 채널 ID를 읽어 승인 target과 다르면 멈춘다.

2020-07-28 이후 생성된 미검증 API 프로젝트의 `videos.insert` 결과는 감사
전까지 private로 제한될 수 있다. 이 제한은 private staging 성공과 publish
가능성을 구분하게 한다. 근거:
<https://developers.google.com/youtube/v3/revision_history>

첫 CLI는 `stage-private`만 구현한다. 한 manifest에 MP4·thumbnail·title·
description·tags·category, 크기·SHA, 목표 channel ID를 잠근다. 업로드하면서
읽은 MP4 SHA를 다시 계산하고, resumable session URI와 반환 video ID를 영수증에
남긴다. 처리상태는 하드 타임박스 안에서 폴링한다. timeout·응답 유실 때 같은
파일을 즉시 다시 올리지 말고 session과 최근 private video를 reconcile한다.

같은 명령에서 public/unlisted 전환, 엔드스크린, Drive 변경, 재생목록 공개,
업무봇 알림을 실행하지 않는다.

## 엔드스크린 템플릿

공식 Data API의 현재 resource/method에는 엔드스크린 편집 표면이 없다. 이는
공식 API 목록에 근거한 inference이며, Studio UI 자동화를 안정된 API로 가장하지
않는다. 엔드스크린은 YouTube Studio의 `템플릿 적용` 또는 `동영상에서 가져오기`
기능을 사용한다. 공식 UI 근거:
<https://support.google.com/youtube/answer/6388789>

1–8편은 사용자가 이미 수동 설정했다. 수정하지 않는다. 이후에는 홀수편이 7편,
짝수편이 8편의 엔드스크린을 가져온다. 두 새 video ID가 확인되고 대상 영상이
선택 가능해진 뒤 `특정 동영상`만 새 짝으로 바꾼다. 홀수→짝수와 짝수→홀수의
source template ID, target video ID, 표시 구간과 저장 시각을 각각 기록한다.

엔드스크린은 마지막 5–20초에 표시되므로 Studio 미리보기에서 현재 화면·자막·
인물과 충돌을 확인한다. 승인된 1–8편을 별도 end-card 화면이 없다는 이유만으로
재렌더하지 않는다. 이후 영상은 전용 안전 화면이 유리하지만, 영상 내용·길이를
바꾸는 별도 시각 결정으로 다룬다.
