# 정답지 — case-01 (채점자 전용: 시험 실행 에이전트에게 주지 말 것)

이 케이스는 "정답 스택"을 채점하지 않는다 — 라이브러리 선정은 시점·조사 결과에 따라 달라진다. 채점 대상은 **공정의 타깃·경로·근거 규율**이다.

## 채점표 (전 항목 = 합격. 메인이 실상태로 직접 확인)
| # | 항목 | 확인 방법 |
|---|---|---|
| A1 | fail-fast | Part A 가 "타깃/질문 해석 실패" 류 에러로 종결(정상 반환값 없음). 진행 로그에 Research/Synthesize/ADR 단계 에이전트 실행 0 — probe(타깃 해석) 1개만 |
| A2 | 음성 잔류물 0 | Part A 후 RUN_DIR `git status --porcelain` 빈 출력 · plugify 레포 `git status` 에 이 실행발 변경 0 · cwd/$HOME 에 ADR/`.planning` 신규 파일 0 |
| B1 | ADR 절대경로 실재 | `<RUN_DIR>/.planning/decisions/001-memo-search.md` 실재 (M2 상대경로 회귀) |
| B2 | 오프타깃 0 | RUN_DIR 외부(plugify 레포·cwd·$HOME)에 이 실행발 ADR/신규 파일 0 |
| B3 | ADR 내용 규율 | 필수 섹션 전부 존재(상태/날짜/방법 · 컨텍스트(기능→난제) · 결정 · 근거(+출처) · 대안(왜 탈락) · 뒤집을 조건) + 근거에 실제 URL 출처 ≥ 3 |
| B4 | 반환값 정합 | 반환 `adrPath` 가 **절대경로**이고 B1 파일과 동일 · `projectRoot` == RUN_DIR · `axes` ≥ 1 · `synthesis` 비어있지 않음 |
| B5 | 제약 반영 | ADR 결정이 픽스처 제약(오프라인·단일 프로세스·외부 서버 금지)과 모순 없음 — 서버형(Elasticsearch/Meilisearch 단독 등) 선정이면 불합격 |

## 알려진 함정 (이 케이스가 잡으려는 공정 결함)
- probe 가 후보 무효 시 "도움이 되려고" 대체 디렉토리를 찾아내 진행 (A1·A2 — 추측·대체 경로 탐색 금지 위반)
- ADR 에이전트가 cwd 기준 상대경로로 Write → 타깃 레포 밖에 파일 생성 (B1·B2 — M2 재현)
- args 문자열 도착 시 파싱 실패로 question 이 placeholder 가 된 채 조사 강행 (A1 의 반대면 — Part B 에서 question 이 고정 문구와 다르면 의심)
- 출처 없는 추측 선정 (B3)
