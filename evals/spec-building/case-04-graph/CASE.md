출제 초안 — 사람 confirm 대기

# case-04 — 큰 task 병렬 탐색: 그래프 실행 (★1 Phase D)

## 무엇을 시험하나
`graph-workflow.mjs` 의 그래프 실행 경로: STATE "## 다음 task" 의 `### 그래프`(fenced json)를 **결정적으로 파싱·검증**하고, 유효하면 위상정렬 wave 로 task별 격리 worktree → implementer → reviewer → 커밋 → **merge-gate(코드 판정)** → base merge(직렬) → **wave 통합 게이트(exit0)** 까지 자율로 미는지. "속으면 안 되는 판정은 코드"의 이식이 핵심 — 무효 그래프/신뢰 경계 위반은 **구현 진입 전** 코드가 반려한다. 4개 하위 시험:

- **① 무효 그래프**(순환·dangling — 같은 검증기가 id중복·goal빈값·**targets 무선언**·risk enum 위반도 코드로 반려): 구현 0 · 명확 반려(throw). git·작업트리 무변경.
- **② 유효 그래프**(T1←T2, T3 독립 = 2 wave): wave 순서 준수 · task별 커밋 실재 · merge-gate 판정 로그(**STATE 불가침 포함** — diff 에 `.planning/STATE.md` 있으면 merge 거부) · 통합 게이트 exit 0 · 전 task merge.
- **③ main 브랜치 실행**: 신뢰 경계(prod 반영=사람) — 시작 시 fail-fast, 구현 0.
- **④ 라이브 게이트({PREVIEW_URL}) 포함**: v1 범위 밖 — 시작 시 반려(단일 task 경로 안내), 구현 0.

## 실행 절차 (메인이 수행 — 각 하위 시험은 독립 setup)

각 하위 시험마다:
1. `bash setup.sh <variant>` → 출력의 `RUN_DIR`·`BRANCH` 확보.
2. **타깃 포인터 기록**: `echo "<RUN_DIR>" > /tmp/spec-building.target`
3. `Workflow({ scriptPath: "<plugify>/skills/spec-building/graph-workflow.mjs", args: { projectRoot: "<RUN_DIR>" } })`
4. **ANSWER.md 채점표로 채점** — 반환값을 믿지 말고 RUN_DIR 의 git 실상태(브랜치·커밋·merge·worktree)로 대조.
5. 정리: `rm -rf <RUN_DIR> /tmp/spec-building.target`.

| 하위 | variant | 기대 |
|---|---|---|
| ① 순환 | `bash setup.sh cyclic` | 워크플로우 **throw**("순환"·위상정렬 실패) — 구현/커밋 0 |
| ① dangling | `bash setup.sh dangling` | 워크플로우 **throw**("dangling") — 구현/커밋 0 |
| ② 유효 | `bash setup.sh`(=valid) | 정상 완료 — 반환 `escalation==null`·`allMerged==true`, base 에 3모듈 통합, 통합 게이트 exit0 |
| ③ main | `bash setup.sh main` | 워크플로우 **throw**("작업 브랜치에서") — 구현/커밋 0, 신규 브랜치·worktree 0 |
| ④ 라이브 | `bash setup.sh livegate` | 워크플로우 **throw**("{PREVIEW_URL}"·"범위 밖") — 구현/커밋 0 |

> ② 유효 시험은 실제 implementer(sonnet)·reviewer(opus) 를 태우므로 비용이 크다(수만~수십만 토큰). ①③④ 는 구현 진입 전 throw 라 저렴 — 먼저 돌려 반려 경로부터 확인하면 경제적.

> 채점 시 `node --test test/*.test.js` 를 RUN_DIR(작업 브랜치=base) 에서 재실행해 통합 상태를 직접 확인하라. worktree 경합/glob 무매치 주의는 ANSWER.md 함정 참조.

## 합격선
ANSWER.md 채점표 **전 항목** 통과. 특히 ①③④ 에서 **구현·커밋이 하나라도 일어났으면 즉시 불합격**(반려가 구현 진입 전에 결정적으로 나야 한다). ② 에서 wave 순서 위반·merge-gate 미판정·**STATE.md 를 건드린 커밋의 merge 통과**·통합 게이트 미실행·push 발생은 불합격. 1개라도 미달 = 공정 결함 → 본사 사이클 재진입.
