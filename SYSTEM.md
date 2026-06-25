# SYSTEM — 개발 루프 시스템 구조 (이어가기 앵커)

> 새 세션에서 시스템 개선을 이어갈 때 이 문서부터 읽는다. 규칙의 정본은 각 SKILL/AGENTS — 이 문서는 **지도 + 현재 위치 + 열린 개선**만 담는다(중복 금지).
> 마지막 갱신: 2026-06-24 (★2-**P3 canary 닫기 후보 탐지 출하 — ★2(살아있는 루프) 완결** — canary 를 `telemetry/canaries.jsonl` 레지스트리로 승격 + `scripts/canary-check.sh`(탐지하되 닫기는 사람) + 현황판/박동 연동. eval `canary-check/case-01` 합격. ★2 P0~P3 전부 완료. 다음 큰 방향 = ★1 Phase C/D.)

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
- 문제집 현황: `evals/spec-building/case-01`(경계 버그픽스 — 타깃정합·committed 실재·범위·게이트 8항목) ✅ 1회 합격(2026-06-11) / `evals/tech-deciding/case-01`(타깃 fail-fast + ADR 절대경로·출처 보존 7항목) ✅ 합격(2026-06-12 — 1차 B3 불합격: haiku ADR 이 출처 URL 유실 → 출처 보존 의무 픽스 후 재시험 합격. 문제집이 실결함을 잡은 첫 사례) / `evals/perf-review/case-01`(심은 버그 3+오탐 함정 1) — ✅ **합격(2026-06-25 첫 실행)**: 심은 버그 3 전부 confirmed(N+1·search·readFileSync)·CATEGORIES 함정 미혼동·환각 0·prober 빌드부재 정직보고. judge 가 분석가 계산오류(240→280B 실측 정정)·per-request 오판을 uncertain 강등 = **오탐 죽이기 실증** / `evals/telemetry-digest/case-01`(계약 수용·skip 3종(계약없음·JSON깨짐·필드누락)·관찰≠task·멱등 9항목) ✅ 합격(2026-06-24) / `evals/canary-check/case-01`(닫기 후보 탐지·레지스트리 불변·순수성 8항목) ✅ 합격(2026-06-24) / `evals/live-verify/case-01`(push 미실재→P0 정지·git SSOT·성공 미선언·버그블록 미작성 7항목) ✅ 합격(2026-06-25 — **eval 이 공정 갭 발견**: live-verify P0 실패 행동 미명세 → executor 가 push 누락에 버그블록 오라우팅(spec-building 로). SKILL P0 에 "push 미실재=미완료액션≠버그블록, push 먼저" 명세 후 재실행 클린. 문제집이 실결함 잡은 셋째 사례) / `evals/service-planning/case-01`(completeness-critic — 심은 누락 2(UI상태·예외)+가짜 PMF 주장 정탐 · 정당제외(역할·auth) 오탐억제 6항목) ✅ 합격(2026-06-25 첫 실행 — critic 이 cat4·cat5 누락+PMF 가짜주장 다 잡고 n=1 pruned 카테고리 오탐 0, "(스코프상 제외)" 표기 실확인 후 정당제외 처리 = critic 핵심 실패모드 회피).
- **현재 canary**: 정본 = `telemetry/canaries.jsonl`(구조화 레지스트리, ★2-P3). 상태 점검 = `scripts/canary-check.sh`(현황판·박동이 호출). 닫기 신호 = `telemetry-signal`(지점 telemetry-log 출현) / `manual`. **탐지·표시는 자동, 닫기 확정(레지스트리 줄 제거)은 사람**(자동편집 금지 — P1 "승격은 사람" 형제). 현재 2건: telemetry-digest-2026-06-24(=대기, 첫 지점 계약 구현 대기) · tech-deciding-2026-06-12(=수동, 다음 실전 1회 실증).

## 4. 하니스 사실 (실증된 것 — 추측 아님)

| 사실 | 실증 |
|---|---|
| Workflow args 는 **JSON 문자열로 도착** | canary 로그 `args 수신: "{\"projectRoot\"...}"` → workflow.mjs 가 JSON.parse 정규화. 포인터 파일이 정본 채널(이중화) |
| agentType 레지스트리는 세션 시작에 고정 | 신규 에이전트는 재시작 후 유효. 미등록 세션 폴백 = general-purpose + .md 본문 인라인 + model 파라미터 |
| SessionStart 훅은 메인 세션만 | 서브에이전트에 wiki/컨텍스트 자동 주입 없음 — spawn 프롬프트에 명시 전달 |
| 커밋 실재는 git 상태로만 판정 | committed 오보고 사고(2026-06-11) → workflow.mjs 가 headLog+porcelain 으로 판정, 메인도 push 전 git 직접 확인 |
| node --test 디렉토리 인자 미동작(v22.22) | 글롭(`src/*.test.js`) 사용 |
| macOS 기본 `timeout` 부재 | telemetry-digest 는 계약 hang 방어를 `perl -e 'alarm'` 로 이식(coreutils 비의존). 스키마 검증은 `jq` |
| 지점 발견 = `~/Projects/*/.planning/` 글롭 | status.sh·telemetry-digest 공통 규약. 지점 목록 = 데이터(파일시스템), 본사 코드에 하드코딩 금지 |
| launchd 최소 PATH(`/usr/bin:/bin`)는 brew 못 봄 | jq @/opt/homebrew/bin → heartbeat.sh 가 PATH 선보정. 없으면 launchd 발사 시 telemetry-digest 가 "jq 필요" rc=2 사망. kickstart rc=0 으로 실증 |
| 자기 박동 = launchd LaunchAgent(cron 아님) | darwin 네이티브 + 슬립 후 깨면 누락분 1회 따라잡음. `com.plugify.heartbeat` 매주 월. 설치/해제 `scripts/heartbeat-ctl.sh`(완전 가역). install.sh 에 안 묶음 — 활성화는 명시적(opt-in) |
| 지점 telemetry-log.md 존재 = 실신호 1회+ 발생 | telemetry-digest 는 계약 통과·수집 시에만 그 파일 생성 → canary-check 의 `telemetry-signal` 닫기 판정 근거(휘발성 현재주 collected 가 아닌 durable 존재성) |

## 5. 2026-06-11 확립된 룰 (정본 위치만 — 내용은 그 파일)

- 버그픽스 수용 기준 = 실코드 경로 실증 + 라이브 닫기 → `skills/spec-building/SKILL.md` "수용 기준 작성 룰"
- reviewer: 재현 실경로성 검증 + **리뷰 대상 레포 git 변조 금지** → `skills/spec-building/agents/reviewer.md`
- 타깃 해석 fail-fast(조용한 폴백 금지) → `skills/spec-building/workflow.mjs` · `skills/tech-deciding/workflow.mjs`(2026-06-12 이식 — 포인터는 JSON 1줄, +ADR 절대경로 정규화·출처 URL 보존)
- 사고→자산 반영→회귀 케이스→canary → `skills/incident-protocol/SKILL.md`

## 6. 열린 개선 (다음 세션 백로그)

> **다음 큰 방향 = ★1·★2** (2026-06-22 결정). ★가 줄기, 1~8은 독립/흡수 항목.

★1 **AI 네이티브 재설계 — 지점 루프를 본사 루프 모양으로**
- 진단: 본사 루프는 이미 AI 네이티브(목표+evals+통과까지 반복)인데 지점 루프(기획→결정→구현→검증)는 사람 조직도 디지털화(폭포수 + 사람이 모든 이음매의 메신저). 신뢰 종류로 가르는 축("속으면 안 되는 건 코드")을 미시엔 쓰면서 거시 파이프라인은 사람-역할 축으로 짬.
- 새 모양: 목표+수용게이트(입구) → 오케스트레이터 깊이 분류(비가역 표면이면 깊은 길 강제) → (큰 것만) 옵션 병렬생성·판정 → 게이트 대고 자율 반복 → 라이브 게이트 통과 → 사람은 게이트 정의+push만. 기존 스킬은 버리지 않고 역할만 변경(service-planning=게이트/옵션 생성기, tech-deciding=비가역축에서만, live-verify=게이트의 라이브 부분).
- 신뢰 경계 불변: 커밋실재·게이트통과=결정적코드, push=사람. 새 안전판: 비가역 표면 → 깊은 길 강제(under-분류가 새 실패 모드).
- 도입(각 단계 본사 루프 통과, 작은 task 경로부터·한번에 갈아엎기 금지): **A 입구를 목표+게이트로 ✅(3cf2c2b)** / **B 적응형 분류+안전판 — 보류**(비가역 게이트는 솔로·수동 트리거 단계엔 사람이 이미 게이트라 값 안 함; 자율 흐름 생기면 실제 위험 모양에 맞춰 재설계) / C 게이트를 운전대로(live-verify 흡수) / D 큰 task 병렬 탐색. 기존 #3(풀체인)·#6(자동화 수위)은 "사람은 push만/메신저 제거"로 이 줄기에 흡수.
- **Phase A 구체(✅ 완료, 3cf2c2b)**: STATE "## 다음 task" 새 형식 = `### 목표` + `### 게이트`(항목마다 `auto:`<명령/테스트/라이브프로브 + 통과 신호> 또는 `human:`<취향·비가역>, auto≥1 권장) + `### 비가역 표면`. workflow.mjs 가 게이트 블록 없음/auto 0개 → **fail-fast 반려**(결정적 코드·조용한 폴백 금지, human-only 는 경고만). eval `spec-building/case-02-no-gate-rejected`(게이트 없는 task → 워크플로우가 구현 안 하고 반려 + 작업트리 무변경 = 합격) = 출하 조건. 완료 task 가 이미 적는 마커를 *회고*에서 *시작 전 계약*으로 앞당기는 것 — 현 SKILL §수용 기준 작성 룰(실코드 경로·게이트≠동작·라이브로 닫기)은 유지하되 형식이 강제하게 격상.

★2 **살아있는 루프 — 현황판·운영→기획 피드백·자기 시계** (★1 위에 얹음) — ✅ P0~P3 완료(2026-06-24). 잔여 활성화 = 지점 telemetry.sh 구현(트래픽 대기).
- 진단: 지점 루프는 태스크 안의 폐루프지만 human-clocked(매번 사람 트리거). 빠진 OS 속성 3개: 자기 박동(스케줄러)·질의가능 현황(/proc)·운영→기획 backward edge.
- 원칙: **루프(기계)는 본사가 만든다, 신호(데이터)는 지점이 정해진 규격으로 건넨다.** niche-market = 첫 입주자지 의존 대상 아님. 지점 목록 = 데이터(파일 한 줄).
- 단계: **P0 `plugify status` ✅(scripts/status.sh — 본사 evals·canary·★ + 지점 STATE·git 한 화면, 지점=~/Projects/* 스캔)** → **P1 telemetry backward edge 본사 파트 ✅(2026-06-24 — `scripts/telemetry-digest.sh` 가 지점 계약 호출→주간 다이제스트 `telemetry/digest-<ISO주>.md`+지점 `.planning/telemetry-log.md` 멱등 append. 규격 정본 `telemetry/CONTRACT.md`(지점이 `.planning/telemetry.sh`→JSON stdout). 불변식: 관찰≠task(STATE 다음 task 불가침)·HQ 는 지점 커밋 안 함·skip 사유 출력. 지점 telemetry.sh 구현은 실트래픽 대기 = 기존 #4)** → **P2 자기 박동 ✅(2026-06-24 — `scripts/heartbeat.sh` 가 launchd(`com.plugify.heartbeat`, 매주 월 09:00)로 telemetry-digest 주간 자동 호출 → `heartbeat.json` 요약 → status.sh '박동' 줄(박동→현황판→사람). launchd 최소 PATH 보정으로 jq 사망 방지(kickstart rc=0 실증). 설치/해제 `heartbeat-ctl.sh`(완전 가역, install.sh 비결합·opt-in). 빈 박동은 조용·신호 생기면 현황판에 뜸)** → **P3 canary 닫기 후보 탐지 ✅(2026-06-24 — canary 를 `telemetry/canaries.jsonl` 레지스트리로 승격. `scripts/canary-check.sh` 가 닫기 신호(`telemetry-signal`=지점 telemetry-log 출현 / `manual`)를 평가해 후보/대기/수동 분류 → 현황판·박동이 표시. **순수 평가기 — 레지스트리·SYSTEM 자동편집 0, 닫기 확정은 사람**(P1 "승격은 사람" 형제). eval case-01 합격(대기↔후보 전환·레지스트리 불변·순수성 8항목))**. **→ ★2(살아있는 루프) P0~P3 완결.** 규율: 자율성은 트리거·관찰에만, 합격판정·push·canary 닫기는 결정적/사람. 모든 박동은 "다음 행동(백로그/STATE task)"으로 끝나야(안 닫는 자동화 = 소음).

1. ✅ **perf-review eval 첫 실행 완료**(2026-06-25) — case-01 5항목 합격. perf-review 공정 검증됨(judge 오탐 죽이기 실증). 다음 perf-review 수정 시 회귀로 재실행.
2. **commit 원자성** — canary 관찰: implementer 가 픽스 직접 커밋 + commit 에이전트가 STATE 별도 커밋(2분할). implementer.md 에 "커밋은 commit 단계 소관" 명시 검토.
3. **풀체인 모드**(사람은 최종 보고만) — STATE task 큐 자동 순회(spec-building→live-verify→다음). **선행: 프리뷰 배포**(push=즉시 prod 라 완전 무인 불가). 검수자 신뢰는 evals 로 확보 후.
4. **telemetry-review 루프**(운영→기획 backward edge) — *기계 파트는 ★2-P1 에서 완료*(telemetry-digest + CONTRACT). 잔여 = ⓐ 지점 `.planning/telemetry.sh` 실구현(niche-market, 실트래픽 생기면) ⓑ (선택) 다이제스트를 사람이 주간 리뷰→승격하는 얇은 스킬. 트래픽 전까진 박동이 그냥 skip.
5. **evals 확충** — ✅ **거의 완료(2026-06-25)**: live-verify case-01(push 미실재→P0 정지; eval 이 SKILL P0 갭 발견·수정) + service-planning case-01(completeness-critic 심은 누락 정탐·정당제외 오탐억제; 퍼지 산출물을 *심은 누락 탐지*로 결정화) 둘 다 신설·합격. perf-review case-01 첫 실행 합격(#1 완료). **잔여 후속 case 후보**(저우선): live-verify case-02(P3 실패→표준 버그 블록 양식) · service-planning은 completeness-critic 외 슬라이스(plan-writer 발명금지 등). 우선순위는 수정 빈도 순.
   - **live-verify 정제 후보(비차단)**: P0 실패(push 미실재) 시 STATE 손대지 말지(보고-only) vs 거짓주장 정정 허용 — case-01 재실행서 executor 가 STATE 헤더를 정정함(버그블록 아님·무해하나 작업트리 dirty + 정정 미커밋). 실사용 빈도 낮아 후순위.
6. **자동화 수위 상향 검토** — live-verify 의 명시 호출 의존(메인이 지시문 따름)을 Stop hook/workflow 화로 기계화할지. 비가역 게이트(push) 분리가 전제.
7. **comprehension debt** — 에이전트 작성 코드를 사람이 안 읽는 구조. 주요 모듈 "코드 투어" 체크포인트 운영 검토.
8. plugins/ 번들화(`dev-loop`) — 외부 배포 필요 시.

## 7. 참고 계보

루프 엔지니어링(Cherny→Osmani 2026.6, ralph/Huntley 2025.7) 조사 + "Agent-in-the-loop 2층 구조(구축/사용 분리·일반화 검증·배포)" 사례 분석에서 본사/지점 모델 도입. 핵심 채택 원칙: 루프 종결 = 외부 verifier 의 라이브 확인 / 구축·사용 모드 분리 / 문제집(일반화 검증) 통과 후 출시.
