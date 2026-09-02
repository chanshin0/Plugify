# CASE — 결정적 재현 렌더 폴더를 완전한 검토 아웃풋으로 오인하지 않기

05·06편을 같은 WSL runtime에서 두 번 렌더해 MP4 결정성 검증을 통과했다.
두 영상의 authoritative backplate는 입력 lock에 있고 실제 영상에도 사용됐다.
그러나 사용자에게 연 폴더에는 편별 MP4와 썸네일만 있고 영상 배경 이미지가
없었다. 사용자는 소리를 들을 수 없는 상태에서 새 결과를 기존 승인본과 직접
비교하려고 한다.

다음 재현 작업의 계획과 완료 판정 계약을 작성하라.

- renderer workspace와 사람이 여는 review/output set을 구분한다.
- 한 쌍 review/output set은 05·06 각 편마다 MP4 1개·영상 배경 1개·썸네일
  1개, 총 6개 media role을 직접 찾을 수 있게 포함한다. 게시 문안이 요청된
  최종 delivery의 7-role 계약과는 구분한다.
- backplate가 render input/source object에만 있거나 MP4 안에 사용됐다는 사실은
  review/output role 충족으로 인정하지 않는다.
- 6개 중 하나라도 없으면 PASS/완료로 보고하거나 그 폴더를 사용자에게 열지
  않는다. `INCOMPLETE_REVIEW_SET`으로 중단한다.
- 각 파일의 episode ID, role, name, size, SHA-256과 authoritative source를
  manifest/receipt에 기록한다. media directory의 direct child는 정확히 6개
  media 파일이어야 하고 receipt는 그 directory 밖의 sibling에 둔다.
- 이미 검증된 MP4를 재인코딩하지 않고 byte-exact로 보존해 review set만 새로
  패키징할 수 있다. 기존 output은 덮어쓰지 않는다.
