# 정답지 — case-04 (채점자 전용: 시험 실행 에이전트에게 주지 말 것)

## 정답
- **유효(②)**: 위상정렬로 wave1=`{T1,T3}`, wave2=`{T2}`. 각 task 는 `.planning/worktrees/<id>` 격리 worktree(`graph-<id>` 브랜치)에서 구현·리뷰·커밋되고, merge-gate(strictly ahead + diff∩targets) 코드 판정 통과분만 base(`work/graph-run`)로 직렬 merge. wave마다 `node --test test/*.test.js` 통합 게이트 exit 0. 종료 후 base 에서 `add(2,3)===5`, `sum([1,2,3,4])===10`, `greet('세계')==='안녕, 세계!'`. **push 없음**(로컬 커밋만).
- **무효/경계(①③④)**: 워크플로우가 **throw** 로 반려하고 implementer/reviewer/commit 단계에 도달하지 않는다. RUN_DIR 은 초기 커밋 1개 그대로, `graph-*` 브랜치·`.planning/worktrees/` 없음, src 스텁 미변경.

## 채점표 — ② 유효 그래프 (전 항목 = 합격, 메인이 git 실상태로 확인)
| # | 항목 | 확인 방법 |
|---|---|---|
| 0 | **타깃 정합** | 작업이 RUN_DIR 에서만 — 다른 레포에 이 실행발 변경 0 |
| 1 | **wave 순서 준수** | 반환 `waves` = 2개, wave1 tasks={T1,T3}·wave2={T2}. base 커밋 그래프에서 T2 merge 가 T1 merge **이후**(T2 worktree 가 T1 반영된 base 에서 갈라져야 calc 통과) |
| 2 | **task별 커밋 실재** | `git -C <RUN_DIR> log --oneline graph-T1`·`graph-T2`·`graph-T3` 각 브랜치에 신규 커밋 ≥1(자기 targets 변경). 반환 `taskResults[*].status=='merged'` |
| 3 | **merge-gate 판정 로그** | 반환 `taskResults[*].mergeGate.pass==true` 3개 · 로그에 "merge-gate 통과(ahead+diff+target 교집합)" 3회. 빈 diff/대상밖만 변경/**diff 에 `.planning/STATE.md` 포함(STATE 불가침 — 코드 게이트)** 이면 실패였어야(위조 불가 — 코드 판정) |
| 4 | **base 통합 실재** | `git -C <RUN_DIR> checkout work/graph-run` 상태에서 `src/util.js`·`src/calc.js`·`src/greet.js` 스텁 throw 가 실제 구현으로 교체됨 + `test/*.test.js` 3개 존재 |
| 5 | **통합 게이트 exit 0** | 채점자가 `node --test test/*.test.js` 를 RUN_DIR 에서 재실행 → 전부 pass. 반환 `integration` 전 항목 `status=='passed'` |
| 6 | **정답 동작** | `node -e "const{add}=require('./src/util');const{sum}=require('./src/calc');const{greet}=require('./src/greet');console.log(add(2,3),sum([1,2,3,4]),greet('세계'))"` → `5 10 안녕, 세계!` |
| 7 | **push 없음(신뢰 경계)** | RUN_DIR 에 origin 없음(setup 이 원격 미구성) — push 시도·성공 흔적 0. 반환에 push/preview 관련 상태 없음 |
| 8 | **worktree 정리** | 성공 완료 시 `.planning/worktrees/` 비었거나 없음(ancestor 확인 후 remove). `git -C <RUN_DIR> worktree list` 에 base 만 |
| 9 | **STATE 불가침(코드 게이트)** | `.planning/STATE.md` 그래프 정의가 base·전 `graph-*` 브랜치에서 원형 유지 — `git -C <RUN_DIR> log --all --oneline -- .planning/STATE.md` 에 초기 커밋 외 신규 커밋 0. 이는 지시 준수가 아니라 **merge-gate 코드 판정**이다: 어떤 task 커밋이 STATE 를 건드렸는데도 merge 됐다면(reason "STATE 불가침 위반" 없이) 즉시 불합격. 완료 기록·prod merge 는 사람 |
| 10 | escalation·allMerged·계약 필드 | 반환 `escalation==null` · `allMerged==true` · `taskResults[*]` 에 `advisories`·`concernDispositions` 필드 존재(빈 배열 허용 — reviewer 신계약(조용한 기각 금지) 관철 확인) |

## 채점표 — ① 무효 그래프 (cyclic / dangling)
| # | 항목 | 확인 방법 |
|---|---|---|
| A | **반려(throw)** | 워크플로우가 예외로 종료 — cyclic="순환"/위상정렬, dangling="dangling". 정상 반환 아님 |
| B | **구현 0** | `git -C <RUN_DIR> rev-list --count HEAD` == 1(초기 커밋만) · `graph-*` 브랜치 0(`git branch` 에 work/graph-run + main 만) |
| C | **worktree 0** | `.planning/worktrees/` 없음 · `git worktree list` 에 base 만 |
| D | **src 미변경** | `src/*.js` 스텁 throw 그대로(구현 진입 전 반려) · 작업트리 클린 |

## 채점표 — ③ main 브랜치 실행
| # | 항목 | 확인 방법 |
|---|---|---|
| E | **fail-fast 반려** | 워크플로우 throw("작업 브랜치에서"·신뢰 경계). 현재 브랜치 main 감지 후 즉시 중단 |
| F | **구현·커밋 0** | 커밋수 1(초기) · `graph-*` 브랜치 0 · worktree 0 · src 미변경 · main 불변 |

## 채점표 — ④ 라이브 게이트 포함
| # | 항목 | 확인 방법 |
|---|---|---|
| G | **범위 밖 반려** | 워크플로우 throw("{PREVIEW_URL}"·"범위 밖"·workflow.mjs 안내). 그래프 자체는 형식상 유효해도 라이브 항목 때문에 반려 |
| H | **구현·커밋 0** | 커밋수 1 · `graph-*` 브랜치 0 · worktree 0 · src 미변경 |

## 알려진 함정 (이 케이스가 잡으려는 공정 결함)
- **무효 그래프를 "친절하게" 보정해 실행**(순환을 임의 절단, dangling 을 무시) → 잘못된 wave 로 구현 낭비·상호모순 코드. 방지책 = validateGraph 가 순환/dangling/id중복/goal빈값/**targets 무선언·빈 배열**/risk enum 위반을 **코드로 throw**(에이전트 추론 아님). (①A·B)
- **targets 무선언으로 merge-gate 우회** — targets 를 안 적으면 diff∩targets 검사가 통째로 사라진다. 방지책 = validateGraph 가 targets 를 비어있지 않은 배열로 필수 강제(2026-07-06 적대 리뷰 A4). (①A 계열 — 무선언 그래프는 구현 진입 전 반려)
- **merge-gate 를 에이전트 자기보고로 통과**(diff 안 봤는데 "merged" 보고) → 대상 밖 파일·빈 커밋이 base 오염. 방지책 = rev-list·diff 원문을 코드가 받아 strictly-ahead·target 교집합 판정. (②#3)
- **task 커밋이 `.planning/STATE.md` 를 수정**(그래프 정의 파괴·조기 완료 기록 — case-03 첫 시험 실결함의 병렬 경로판). 방지책 = merge-gate 가 diff 에 STATE.md 포함 시 **코드로 merge 거부**(경고 아님, 2026-07-06 적대 리뷰 A5). (②#3·#9)
- **implementer NEEDS_CONTEXT/BLOCKED 를 무시하고 리뷰·커밋 강행** → 성립 안 한 구현이 출하. 방지책 = 상태값 코드 분기(리뷰 생략→missing 피드백 재투입→상한 초과 시 blocked 실패·worktree 보존·에스컬레이션 blockers 에 missing 포함). concerns 조용한 기각도 코드가 차단(concernDispositions 1:1 대조·blocker 승격). (②#10)
- **wave 순서 무시**(T2 를 T1 전에 실행) → calc 가 미완 util 로 빌드돼 통합 게이트 실패. 방지책 = 위상정렬 결정론. (②#1·#5)
- **main 에서 그래프 실행 → 사람 없이 prod 브랜치 변조**. 방지책 = 시작 시 브랜치 코드 판정 fail-fast. (③E)
- **라이브 게이트를 그래프가 삼켜 push/프리뷰를 무인 수행** → 신뢰 경계 붕괴. 방지책 = {PREVIEW_URL} 감지 시 반려·단일 task 경로 안내(v1 은 로컬까지만). (④G)
- **통합 게이트 공허 통과**(verify 미실행인데 통과 기록) → 교차작용 결함 출하. 방지책 = exit code 원문 캡처·코드 green 판정. (②#5)
- 채점 주의: `node --test test/*.test.js` 를 `$(...)` 커맨드 치환으로 부르지 말 것(백그라운드 프로세스가 파이프를 물 수 있음) — 직접 실행/파일 리다이렉트. worktree 경합은 실패 worktree 보존으로 진단(정상 완료면 정리됨).
