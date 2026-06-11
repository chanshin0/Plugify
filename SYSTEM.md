# SYSTEM — 개발 루프 시스템 구조 (이어가기 앵커)

> 새 세션에서 시스템 개선을 이어갈 때 이 문서부터 읽는다. 규칙의 정본은 각 SKILL/AGENTS — 이 문서는 **지도 + 현재 위치 + 열린 개선**만 담는다(중복 금지).
> 마지막 갱신: 2026-06-11 (본사 루프 완성 — evals 문제집 + 첫 canary 사이클 완주)

## 1. 2층 구조 — 본사/지점

```
[본사 = 이 레포(plugify)]                      [지점 = 각 프로젝트 레포]
공정을 만든다. 커밋 = 출시                      공정으로 제품을 만든다
├── AGENTS.md   ← 헌법(설계 원칙·출하 조건)      ├── AGENTS.md   ← "공정을 따르라" + 가게 고유 사실
├── skills/     ← 공정 정본(평면)                └── .planning/STATE.md ← 주문 대장("## 다음 task" = 표준 인터페이스)
├── evals/      ← 문제집(본사 루프의 종료조건)
├── agents/     ← 스킬 독립 에이전트(debugger·design-explorer)
└── scripts/install.sh ← 배포(~/.claude 심링크 + 에이전트 dual-block 생성)
```
- **모드 스위치 = 어느 레포에서 일하는가.** 지점 작업 중 사고가 나면 응급처치만 하고, 공정 수정은 본사 사이클로 넘긴다(영업 중 라인 뜯기 금지).
- 현재 지점: `~/Projects/niche-market` (유일 — 라이브 https://niche-market.vercel.app, push=자동배포).

## 2. 지점 루프 (제품 개발 파이프라인)

```
service-planning → tech-deciding → spec-building ─→ live-verify ─→ (통과) 보고
   (기획서)          (ADR)        │ implementer(sonnet)   │ 실패: 표준 버그 블록을
                                  │ → reviewer(opus)+Codex │ STATE "다음 task"에 append
                                  │ → commit(git상태 판정) │ → spec-building 재투입
                                  └ 최대 3회→에스컬레이션  └ 3바퀴 상한·동일증상 2회→debugger
위성: perf-review(성능 진단, 분석3+judge) · debugger(라이브 증거 진단) · design-explorer(UI 톤)
```
- **루프 종결 신호 = 라이브 동작**(게이트 통과 아님) — live-verify 가 닫는다. 표준 버그 블록 양식 = live-verify SKILL 내(진단→구현 공용 인터페이스).
- 워크플로우 호출 규약: **포인터 파일 먼저** `echo <레포절대경로> > /tmp/spec-building.target` → Workflow 실행 (spec-building SKILL "실행" 참조).

## 3. 본사 루프 (공정 개선 — 메타)

```
트리거(사고/신규 공정/정기) → 공정 수정 → evals 문제집 실행 → ANSWER 채점(실상태 대조)
                                   ↑                                │
                                   └── 불합격: 결함 수정 ←──────────┘  합격 → 커밋(출시) + canary 선언
```
- 종료조건 = **문제집 통과**(1사례 검증 금지). 출제·합격선 = 사람(굿하트 차단). 사고 → 회귀 케이스 추가(incident-protocol 절차 4).
- 문제집 현황: `evals/spec-building/case-01`(경계 버그픽스 — 타깃정합·committed 실재·범위·게이트 8항목) ✅ 1회 합격(2026-06-11) / `evals/perf-review/case-01`(심은 버그 3+오탐 함정 1) — **미실행**(perf-review 다음 수정 시 첫 실행).

## 4. 하니스 사실 (실증된 것 — 추측 아님)

| 사실 | 실증 |
|---|---|
| Workflow args 는 **JSON 문자열로 도착** | canary 로그 `args 수신: "{\"projectRoot\"...}"` → workflow.mjs 가 JSON.parse 정규화. 포인터 파일이 정본 채널(이중화) |
| agentType 레지스트리는 세션 시작에 고정 | 신규 에이전트는 재시작 후 유효. 미등록 세션 폴백 = general-purpose + .md 본문 인라인 + model 파라미터 |
| SessionStart 훅은 메인 세션만 | 서브에이전트에 wiki/컨텍스트 자동 주입 없음 — spawn 프롬프트에 명시 전달 |
| 커밋 실재는 git 상태로만 판정 | committed 오보고 사고(2026-06-11) → workflow.mjs 가 headLog+porcelain 으로 판정, 메인도 push 전 git 직접 확인 |
| node --test 디렉토리 인자 미동작(v22.22) | 글롭(`src/*.test.js`) 사용 |

## 5. 2026-06-11 확립된 룰 (정본 위치만 — 내용은 그 파일)

- 버그픽스 수용 기준 = 실코드 경로 실증 + 라이브 닫기 → `skills/spec-building/SKILL.md` "수용 기준 작성 룰"
- reviewer: 재현 실경로성 검증 + **리뷰 대상 레포 git 변조 금지** → `skills/spec-building/agents/reviewer.md`
- 타깃 해석 fail-fast(조용한 폴백 금지) → `skills/spec-building/workflow.mjs`
- 사고→자산 반영→회귀 케이스→canary → `skills/incident-protocol/SKILL.md`

## 6. 열린 개선 (다음 세션 백로그)

1. **perf-review eval 첫 실행** — case-01 미실행 상태. perf-review 를 다음에 손댈 때 함께.
2. **commit 원자성** — canary 관찰: implementer 가 픽스 직접 커밋 + commit 에이전트가 STATE 별도 커밋(2분할). implementer.md 에 "커밋은 commit 단계 소관" 명시 검토.
3. **풀체인 모드**(사람은 최종 보고만) — STATE task 큐 자동 순회(spec-building→live-verify→다음). **선행: 프리뷰 배포**(push=즉시 prod 라 완전 무인 불가). 검수자 신뢰는 evals 로 확보 후.
4. **telemetry-review 루프**(운영→기획 backward edge) — 주간 event 집계→기획 백로그. 지점에 실트래픽 생기면.
5. **evals 확충** — live-verify·tech-deciding·service-planning 케이스 0. 우선순위는 수정 빈도 순.
5b. **tech-deciding 에 타깃 픽스 이식** — spec-building 에만 적용된 args JSON-문자열 정규화 + 타깃 해석 fail-fast 가 tech-deciding workflow.mjs 에 없음(같은 조용한 폴백 계열). + 구버그: ADR Write 가 상대경로(`workflow.mjs` adrPath, cd 보호 부재 — 2026-06-05 발견 M2) → 엉뚱한 디렉토리 위험. 한 사이클로 묶어 수정 + eval 케이스 신설이 적합.
6. **자동화 수위 상향 검토** — live-verify 의 명시 호출 의존(메인이 지시문 따름)을 Stop hook/workflow 화로 기계화할지. 비가역 게이트(push) 분리가 전제.
7. **comprehension debt** — 에이전트 작성 코드를 사람이 안 읽는 구조. 주요 모듈 "코드 투어" 체크포인트 운영 검토.
8. plugins/ 번들화(`dev-loop`) — 외부 배포 필요 시.

## 7. 참고 계보

루프 엔지니어링(Cherny→Osmani 2026.6, ralph/Huntley 2025.7) 조사 + "Agent-in-the-loop 2층 구조(구축/사용 분리·일반화 검증·배포)" 사례 분석에서 본사/지점 모델 도입. 핵심 채택 원칙: 루프 종결 = 외부 verifier 의 라이브 확인 / 구축·사용 모드 분리 / 문제집(일반화 검증) 통과 후 출시.
