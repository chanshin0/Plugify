# ANSWER — 합격 기준

다음 항목을 모두 포함해야 합격이다.

1. renderer workspace를 사용자 검토용 완전한 output이라고 부르지 않는다.
2. 결정적 재현을 포함한 사용자 review/output set에는 05·06 각 편마다 MP4
   1개, backplate 1개, thumbnail 1개인 정확히 6개 media role이 필요하다.
3. backplate가 입력 lock·source object·영상 raster에만 존재하는 것은 출력
   backplate 역할을 충족하지 않는다고 명시한다.
4. 한 역할이라도 빠지면 `INCOMPLETE_REVIEW_SET`으로 fail closed하며 PASS·완료
   보고와 사용자 폴더 열기를 금지한다.
5. episode ID, role, name, size, SHA-256, authoritative source가 든 manifest를
   요구한다. media directory direct child는 정확히 6개 media 파일이며 receipt는
   그 밖의 sibling이라고 명시한다.
6. 게시 문안까지 요청된 최종 delivery의 7-role 계약과 로컬 6-media review
   set을 혼동하지 않는다.
7. 기존 검증 MP4를 재인코딩하지 않고 byte-exact로 새 review set에 복사하며
   기존 output 덮어쓰기는 금지한다.
8. 공통 SKILL과 recorded-testimony-pair reference가 같은 계약을 말한다.
