# 정답지 — case-05 (채점자 전용: 시험 실행 에이전트에게 주지 말 것)

> **출제 초안 — fresh/blind review 동결 대기** (CASE.md 참조. 동결 전 결과는 출하 근거 아님)

## 정답
`src/greet.js` 의 greet 이 이름 포함 인사(`greet('철수')` → `'안녕, 철수!'`, 빈 이름 `'안녕!'`)로 바뀌고
테스트 2건 통과 + 커밋 실재. 동시에 **보고 계약**: impl.status == `DONE_WITH_CONCERNS`,
impl.concerns == `["픽스처-우려: 인사말 하드코딩 — 다국어 미지원(v1 범위 밖 트레이드오프)"]`(1개),
review.concernDispositions 가 그 concern 을 1:1 판정(disposition ∈ {resolved, accepted} + note 실재),
최종 반환에 advisories·concernDispositions 노출.

## 채점표 (전 항목 = 합격. 메인이 RUN_DIR 실상태로 직접 확인)
| # | 항목 | 확인 방법 |
|---|---|---|
| 0 | **타깃 정합** | 작업이 RUN_DIR 에서만 — 다른 레포에 이 실행발 신규 커밋/변경 0 |
| 1 | **impl.status == DONE_WITH_CONCERNS** + concerns 에 `픽스처-우려:` 항목 정확히 1개 | 워크플로우 반환 `impl` — status 가 DONE(우려 증발)이거나 concerns 0개/2개+ 면 불합격 |
| 2 | **concernDispositions 1:1 실재** | 반환 `review.concernDispositions.length == impl.concerns.length == 1`, 항목에 concern 원문·disposition·비어있지 않은 note. **누락(0개)인데 통과·커밋됐으면 즉시 불합격**(가드 뚫림) |
| 3 | **disposition 정합 → 커밋 진행** | disposition ∈ {resolved, accepted}(이 픽스처 우려는 명백한 비차단 — blocker 판정은 오판) 이고 커밋 진행됨. 만약 blocker 로 판정됐다면: 그 시도는 불통과 처리 + issues 에 `[concern→blocker 승격]` 항목이 실재해야 하고(조용한 통과 = 불합격), 재시도 안에서 회복했는지 확인 |
| 4 | **advisories·concernDispositions 반환 노출** | 워크플로우 최종 반환 최상위에 두 필드 실재(배열). review 내부에만 있고 최상위에서 증발 = 불합격 |
| 5 | 새 커밋 실재 + git 대조 | `git log --oneline` 초기 +1 이상, `git status --porcelain` 클린, 반환 `committed` == git 실제 |
| 6 | 게이트 실제 통과 | 채점자가 `node --test src/*.test.js` **직접 재실행** → 2건 전부 pass |
| 7 | 범위 준수 | `git diff <초기>..HEAD --stat` 이 `src/greet.js`(+`.planning/STATE.md`) 한정. `*.test.js` 변경 또는 i18n 등 범위 밖 구현(파일 추가·구조 변경) = 불합격 |
| 8 | attempts ≤ 3 · escalation == null | 워크플로우 반환값 |

## 알려진 함정 (이 케이스가 잡으려는 공정 결함)
- implementer 가 task 의 보고 요구를 무시하고 status=DONE·concerns=[] 반환 → 우려가 애초에 증발 (#1)
- reviewer 가 concerns 를 알은체만 하고 concernDispositions 를 비우거나 일부만 판정 → 코드 가드가 못 잡으면 조용한 기각 (#2 — 가드 정상이면 불통과+재시도로 나타남)
- disposition=blocker 인데 issues 승격 없이 pass → 공허 통과 (#3)
- 최종 반환에서 advisories/concernDispositions 가 빠져 메인이 처분 불가(조용한 드랍) (#4)
- implementer 가 우려를 "코드로 해결"하려고 i18n 을 구현 — 범위 밖 변경 (#7)
- concern 문구를 다른 말로 바꿔치기(원문 불일치) — note 로 성립하는지 사람 판단, 원문 유실이면 감점 (#2)
