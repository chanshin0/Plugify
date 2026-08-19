# case-01 — 30fps 정지화면 타임라인의 자막 경계를 실제 출력 프레임으로 보장한다

## 사용자 요구에서 역산한 시험

찬송편지의 공통 배경·큰 자막 영상은 최종 30fps 프레임 번호를 정본으로 삼는다. 24.100초 뒤 시작하도록 계산한 첫 공통 화면은 0부터 셌을 때 정확히 **frame 723**에서 보여야 한다. ffconcat에 정지 이미지를 넣으면서 각 `file`의 입력 프레임레이트를 고정하지 않으면 image2의 25fps 기본값이 24.100초를 양자화해 실제 출력 전환이 frame 724로 한 프레임 늦어진다.

따라서 제작 모듈은 manifest의 정수 프레임 구간을 ffconcat으로 바꿀 때 모든 `file` 항목(마지막 반복 항목 포함)에 해당 작업의 fps를 입력 옵션으로 기록해야 한다. 합격 여부는 문자열 존재만이 아니라 FFmpeg로 렌더한 실제 frame 722·723·724의 픽셀로 판정한다.

## 실행 과제

후보 모듈은 다음 CLI를 제공한다.

```bash
python3 skills/hymn-letter-video-production/scripts/hymn_video_flow.py \
  build-timeline --spec <job.json> --output <timeline.ffconcat>
```

`job.json`은 `plugify.hymn-letter.still-timeline/1` 스키마이며 `fps`, `expected_frames`, `intervals[].file`, `intervals[].frames`를 가진다. 파일 경로는 spec 파일의 디렉터리를 기준으로 해석한다. 후보는 기존 출력을 덮어쓰지 않고, 잘못된 스키마·합계 프레임·0 이하 구간을 거부해야 한다.

## 결정적 사전검사

아래에서 `<FFMPEG>`는 FFmpeg 실행 파일이다. 이 워크스페이스의 번들 경로는 `/mnt/c/work/godowon-office/output/찬송편지_시작영상_개선작업본_2026-08-18/.tools/ffmpeg/bin/ffmpeg`이다.

```bash
python3 evals/hymn-letter-video-production/case-01-still-framerate-boundary/check-boundary.py \
  --self-test --ffmpeg <FFMPEG>

python3 evals/hymn-letter-video-production/case-01-still-framerate-boundary/check-boundary.py \
  --candidate skills/hymn-letter-video-production/scripts/hymn_video_flow.py \
  --ffmpeg <FFMPEG>
```

## 합격선

- self-test가 수정 전 형식을 실제 frame 724 전환으로 재현하고, 정답 형식을 frame 723 전환으로 판정한다.
- 후보가 만든 타임라인을 실제 렌더했을 때 frame 722는 배경색, frame 723·724는 자막색이다.
- 모든 ffconcat `file` 항목에 `option framerate 30`이 정확히 하나씩 대응하며, 마지막 반복 항목도 빠지지 않는다.
- 구간 프레임 합계가 768이고 제작 명령의 `-frames:v expected_frames` 계약으로 렌더한 최종 결과가 정확히 768프레임이며 frame 767도 올바른 화면이다. ffconcat 자체는 마지막 정지화면의 종료 시각을 보존하려고 마지막 `file`을 한 번 반복하므로, 옵션 없는 native 길이가 아니라 이 제한된 최종 출력이 판정 대상이다.
- 잘못된 schema, 누락·빈 구간, 0/음수/비정수 fps·frames, 합계 불일치를 모두 fail-closed로 거부한다.
- 후보는 spec의 문구·파일명·두 구간 형태에 맞춘 특례가 아니라 서로 다른 fps와 3개 이상 구간에도 같은 규칙을 적용하며, 보조 spec도 실제 출력 전 프레임을 검사한다.
- 합격은 runner 종료코드 0과 ANSWER.md 채점표를 모두 만족해야 한다.
