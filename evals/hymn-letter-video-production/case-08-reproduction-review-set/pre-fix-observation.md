# 수정 전 관찰 — 2026-09-02

- 05·06 WSL 재현의 두 run은 MP4·AAC·decoded frame·runtime lock 결정성 PASS였다.
- 두 backplate는 authoritative input/source object에 있었고 영상 raster 생성에
  실제 사용됐다.
- 재현 job의 output 계약에는 `filename`과 `thumbnail_filename`만 있었고,
  renderer workspace도 썸네일만 episode root로 복사했다.
- 사용자가 연 `run_a/rendered`에는 MP4 2개와 썸네일 2개만 있고 영상 배경
  2개가 없었다.
- 따라서 미디어 생성 실패가 아니라 renderer workspace를 6-media review/output
  set으로 오인해 완료 폴더처럼 제시한 패키징·보고 경계 실패다.
