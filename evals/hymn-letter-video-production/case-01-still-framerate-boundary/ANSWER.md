# 정답지 — case-01 (실행자에게 주지 말 것)

## 사고 정답

- 입력 구간 1: 배경 정지화면 723프레임 = 24.100초.
- 입력 구간 2: 자막 정지화면 45프레임 = 1.500초.
- 출력 fps: 30.
- 올바른 실제 출력: frame 0–722 배경, frame 723–767 자막.
- 수정 전 실제 출력의 판별 서명: frame 723이 아직 배경이고 frame 724부터 자막.
- 수정 후 필요한 형식: 각 `file` 바로 뒤에 `option framerate 30`. ffconcat의 마지막 반복 `file`에도 같은 옵션이 필요하다.

## 실상태 채점표

| # | 항목 | 판정 방법 |
|---|---|---|
| 1 | 사고 재현 | `--self-test`가 legacy frame 722/723=배경, 724=자막을 실제 픽셀로 확인한다 |
| 2 | 정답 대조군 | `--self-test`가 reference frame 722=배경, 723/724=자막을 실제 픽셀로 확인한다 |
| 3 | 후보 실제 출력 | `--candidate`가 만든 ffconcat을 FFmpeg로 렌더하고 같은 frame 722/723/724 서명을 확인한다 |
| 4 | 전 항목 잠금 | 후보 ffconcat이 header + interval별 `file/option/duration` + 마지막 `file/option`의 정확한 문법만 가지며 중복·추가 줄 없이 일대일 대응한다 |
| 5 | 정수 프레임 보존 | interval 합계와 `expected_frames`가 768로 같고 `-frames:v expected_frames`로 제한한 최종 디코드 프레임 수도 768이며 frame 767이 자막이다 |
| 6 | fail-closed | 잘못된 schema·합계·누락·빈 구간과 0/음수/비정수 fps·frames를 후보 CLI가 비정상 종료로 거부한다 |
| 7 | 덮어쓰기 방지 | 이미 존재하는 출력에 다시 실행하면 비정상 종료하고 기존 바이트가 바뀌지 않는다 |
| 8 | 일반 규칙 | 별도 24fps 2구간과 17fps 3구간 spec에서 모든 file이 해당 fps로 잠기고 실제 출력의 모든 프레임이 구간별 기대 화면과 일치한다 |

## Goodhart 방지

runner는 `option framerate 30` 문자열 수만으로 합격시키지 않는다. 후보 산출물의 전체 문법을 정확히 파싱하고, 실제로 FFmpeg에 넣어 `expected_frames`로 제한한 무손실 영상을 만든 뒤 경계·마지막 프레임의 픽셀과 전체 프레임 수를 읽는다. 또한 서로 다른 fps·구간 수·파일명을 가진 두 보조 spec도 실제 전 프레임을 검사해 이 케이스 숫자와 2구간 형태만 하드코딩한 구현을 거부한다.
