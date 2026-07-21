# SYSTEM — 개발 루프 시스템 구조 (이어가기 앵커)

> 새 세션에서 시스템 개선을 이어갈 때 이 문서부터 읽는다. 규칙의 정본은 각 SKILL/AGENTS — 이 문서는 **지도 + 현재 위치 + 열린 개선**만 담는다(중복 금지).
> 마지막 갱신: 2026-07-21 네 번째 사이클 (**scaffold 스킬 신설 — 일회성 병렬 위임 착지 규약, 1단계**. 출처: AX 인재전쟁 해커톤 방법론(컨텍스트/검증/스캐폴딩) 분석에서 이식, 사용자 지시. `skills/scaffold/`(SKILL + 틀 3종: BRIEF·researcher·synthesizer — "틀=버전관리 저금통 / run=인스턴스 증거" 2층 구조, P0 골격→P1 확인→P2 발사→P3 착지→P4 승격 점검). eval `scaffold/case-01` **초안**(출제 confirm 대기 — 채점 금지 가드 부착, 신규 공정이라 첫 실증은 첫 실전 관찰 §3.1). 2단계(perf-review→tech-deciding 착지 어댑터)·3단계(walking-skeleton 원칙)는 §6-10 백로그.)
> 이전 갱신: 2026-07-06 세 번째 사이클 (**★1 Phase D 출하 — 그래프 병렬 실행** + dryforge(fn-opt) 하네스 심층 리뷰에서 채굴한 개선 일괄 반영: ① `graph-workflow.mjs` 신설(JSON 그래프 결정적 검증→wave→worktree 병렬→merge-gate·통합게이트 코드 판정) ② implementer 구조화 계약(status 4값·concerns) + concernDispositions 1:1 코드 대조 = **조용한 기각 금지** ③ 재시도 마지막 시도 opus 자동 상향(MAX>1 한정) ④ 접지 스캔(SKILL 지시문 — assumed 결정은 사용자 확정 후 투입) ⑤ 지점 노트 규약(`.planning/notes.md`, 정본=live-verify SKILL §지점 노트) ⑥ **평가 불능 체크 = 실패** 명문화(spec-building 게이트 룰·프로브·live-verify P3). eval: case-01·02·03 + live-verify case-01 재실행 전부 합격(회귀 무결), case-04 신설 — **② 첫 시험이 실결함을 잡음(다섯째 사례)**: 계측 에이전트가 id 를 브랜치명으로 반환, 판정 조인이 task id 로 조회해 miss → merge-gate·merge 오판. `findByTaskId` 4개 사이트 이중 방어(코드 양쪽 수용+프롬프트 명시) 후 클린 재실행 ② 합격(2 wave·T2 가 T1 산출물 실경로 소비·통합게이트 exit0). case-05(조용한 기각 금지 회귀) 초안 신설. 잔여 = **case-04·05 출제 confirm(사람)** + 첫 실전 관찰 §3.1.)

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
service-planning → tech-deciding → spec-building ────────→ (사람 main merge) → live-verify → 보고
   (기획서)          (ADR)        │ implementer(sonnet)              (prod 최종 확인·스팟체크)
                                  │ → reviewer(opus)(+Codex: 비가역만)
                                  │ → commit(git상태 판정)
                                  │ → 라이브 게이트({PREVIEW_URL}): 브랜치 push→프리뷰 프로브→종결 커밋
                                  └ 상한 3회 자율 반복 → 미통과 시 에스컬레이션 (Phase C)
위성: perf-review(성능 진단, 분석3+judge) · debugger(라이브 증거 진단) · design-explorer(UI 톤)
```
- **루프 종결 신호 = 라이브 동작**(게이트 통과 아님). task 의 라이브 닫힘 = **프리뷰 라이브 게이트**(Phase C — spec-building 이 자율로), prod 최종 = 사람 merge 후 live-verify(스팟체크). 라이브 게이트 규칙 정본 = spec-building SKILL §라이브 게이트, 지점 규격 = `.planning/preview.sh`. 표준 버그 블록 양식 = live-verify SKILL 내(진단→구현 공용 인터페이스).
- 워크플로우 호출 규약: **포인터 파일 먼저** `echo <레포절대경로> > /tmp/spec-building.target` → Workflow 실행 (spec-building SKILL "실행" 참조).
- **trivial 은 공정을 안 태운다**(2026-07-03 명문화): 게이트를 적을 가치가 없는 변경(오타·주석·문서)은 직접 편집+커밋 — 설계된 우회로. 정본 = spec-building SKILL §선행 조건.

## 3. 본사 루프 (공정 개선 — 메타)

```
트리거(사고/신규 공정/정기) → 공정 수정 → evals 문제집 실행 → ANSWER 채점(실상태 대조)
                                   ↑                                │
                                   └── 불합격: 결함 수정 ←──────────┘  합격 → 커밋(출시) + 첫 실전 관찰 선언
```
- 종료조건 = **문제집 통과**(1사례 검증 금지). 출제·합격선 = 사람(굿하트 차단). 사고 → 회귀 케이스 추가(incident-protocol 절차 4).
- 문제집 현황: `evals/spec-building/case-01`(경계 버그픽스 — 타깃정합·committed 실재·범위·게이트 8항목) ✅ 합격(2026-06-11 · 재실행 2026-07-03 ×2 합격 — Codex 조건부·Phase C 재구조화 후에도 기존 경로 불변) + `case-02`(게이트 없는 task 반려) ✅ 재실행 2026-07-03 ×2 합격 + `case-03`(라이브 게이트 — push 실재(원격 서빙 프리뷰)·main 불변·프로브 정직성·커밋 구조 9항목) ✅ **합격(2026-07-03 — 첫 시험 불합격이 실결함 3종을 잡음(넷째 사례): 커밋 에이전트가 라이브 검증 *전에* STATE 게이트 정의를 지우고 "완료·라이브 검증" 거짓 기록 + 코드/STATE 2분할 + 프로브가 지워진 STATE 재독으로 0항목 공허 통과. 방지책 = 게이트 항목 인라인 캡처(STATE 재독 제거)·결과 수 결정적 대조·hasLive 시 커밋 에이전트 STATE 불가침·종결 커밋 분리(라이브 실증 후에만 완료 기록) → 재시험 전 항목 합격)** / `evals/tech-deciding/case-01`(타깃 fail-fast + ADR 절대경로·출처 보존 7항목) ✅ 합격(2026-06-12 — 1차 B3 불합격: haiku ADR 이 출처 URL 유실 → 출처 보존 의무 픽스 후 재시험 합격. 문제집이 실결함을 잡은 첫 사례) / `evals/perf-review/case-01`(심은 버그 3+오탐 함정 1) — ✅ **합격(2026-06-25 첫 실행)**: 심은 버그 3 전부 confirmed(N+1·search·readFileSync)·CATEGORIES 함정 미혼동·환각 0·prober 빌드부재 정직보고. judge 가 분석가 계산오류(240→280B 실측 정정)·per-request 오판을 uncertain 강등 = **오탐 죽이기 실증** / `evals/telemetry-digest/case-01`(계약 수용·skip 3종(계약없음·JSON깨짐·필드누락)·관찰≠task·멱등 9항목) ✅ 합격(2026-06-24, 스크립트와 함께 냉동) / ~~`evals/canary-check/case-01`~~ (2026-07-03 기계와 함께 제거 — 복원=git 89eb2f9) / `evals/live-verify/case-01`(push 미실재→P0 정지·git SSOT·성공 미선언·버그블록 미작성 7항목) ✅ 합격(2026-06-25 — **eval 이 공정 갭 발견**: live-verify P0 실패 행동 미명세 → executor 가 push 누락에 버그블록 오라우팅(spec-building 로). SKILL P0 에 "push 미실재=미완료액션≠버그블록, push 먼저" 명세 후 재실행 클린. 문제집이 실결함 잡은 셋째 사례) / `evals/service-planning/case-01`(completeness-critic — 심은 누락 2(UI상태·예외)+가짜 PMF 주장 정탐 · 정당제외(역할·auth) 오탐억제 6항목) ✅ 합격(2026-06-25 첫 실행 — critic 이 cat4·cat5 누락+PMF 가짜주장 다 잡고 n=1 pruned 카테고리 오탐 0, "(스코프상 제외)" 표기 실확인 후 정당제외 처리 = critic 핵심 실패모드 회피).
- 2026-07-06 재실행·신설: case-01·02·03 + live-verify case-01 **전부 합격**(구조화 계약·접지 스캔·평가불능=실패 반영 후 회귀 무결. case-03 채점 중 ANSWER #4 "항목 2개" 문구가 픽스처 실체({PREVIEW_URL} 1개)와 불일치 발견 — **정답지 문구 결함, 사람 게이트 대기**) / `evals/spec-building/case-04-graph`(그래프 실행 — 반려 4종 + 유효 2wave) **초안·전 하위시험 합격** / `evals/spec-building/case-05-concern-disposition`(조용한 기각 금지 회귀) **초안·confirm 전 채점 금지 가드 부착** — 둘 다 출제 confirm(사람) 대기.
- **첫 실전 관찰 정본 = 아래 §3.1 불릿**(2026-07-03 격하: jsonl 레지스트리+canary-check.sh 는 닫힌 첫 실전 관찰 0건·관리 대상 3줄에 과설계 — 제거, 복원=git 89eb2f9. 재승격 조건 = 지점 3~4개+로 수동 추적이 실제로 깨질 때). **닫기 = 사람이 불릿 줄 제거.** 현황판(status.sh)이 이 목록을 grep 해 표시.

### 3.1 첫 실전 관찰 목록 (고친 뒤 첫 실전 1회를 지켜보는 항목 — 구명 canary) — 닫기 = 사람: 줄 제거

- tech-deciding(2026-06-12 출하): 다음 실전 1회가 포인터 JSON 채널·ADR 절대경로·출처 URL 보존을 실증
- live-verify(2026-06-25 출하): 다음 실전이 push/배포 미실재(P0)를 만나면 버그블록 오라우팅 없이 "push 먼저"로 끝맺는지
- spec-building Codex 조건부(2026-07-03 출하): 다음 실전 1회에서 비가역 표면 유무에 따라 Codex 수행/생략 로그가 맞게 찍히는지
- spec-building 라이브 게이트(2026-07-03 출하, Phase C): 실전 지점 task 1회가 `{PREVIEW_URL}` 게이트→브랜치 push→프리뷰 프로브→종결 커밋으로 닫히는지 (선행 merge 완료 2026-07-05 — 지점 규격 main 반영, 즉시 적용 가능)
- telemetry backward edge(2026-06-24 출하, ★2 냉동과 연동): 지점이 telemetry.sh 계약을 구현·해동한 첫 주에 실신호가 다이제스트+telemetry-log 로 흐르는지
- spec-building 구조화 계약(2026-07-06 출하): 다음 실전 task 1회가 status·concerns→concernDispositions 흐름을 스키마 위반 없이 통과하고, 반환 advisories 를 메인이 실제로 처분(픽스 or STATE 기록)하는지 (+재시도 발생 시 마지막 시도 opus 상향 로그) — **← 2026-07-07 니치마켓 소프트삭제 후속 런이 실증**(concerns 2건 1:1 판정·advisory 가 codex shim 누락을 실발견·처분). opus 상향만 미발화(1회 통과) — 닫기 판단은 사람
- graph-workflow Phase D(2026-07-06 출하): 첫 실전 그래프 task 1회가 wave→merge-gate→통합 게이트로 닫히는지 (+선행: case-04·05 출제 confirm = 사람)
- scaffold 스킬(2026-07-21 출하): 다음 일회성 병렬 위임 실전 1회가 골격 선행(P0)→확인 게이트(P1)→슬롯 착지+빈 슬롯 메인 직접확인(P3)→승격 점검 제안(P4)으로 닫히고, run 디렉토리에 프롬프트 인스턴스·산출물이 실재하는지
- 접지 스캔·지점 노트·평가불능=실패(2026-07-06 출하): 다음 실전 사이클에서 메인이 접지 스캔을 수행하고, 종결 시 `.planning/notes.md` append 여부를 판단하며, 판정 불능 프로브를 실패로 처리하는지 — **← 2026-07-07 같은 런이 실증**(접지 확정 2건·notes.md 신설 4건+양방향 정정 1건). 닫기 판단은 사람

## 4. 하니스 사실 (실증된 것 — 추측 아님)

| 사실 | 실증 |
|---|---|
| Workflow args 는 **JSON 문자열로 도착** | 첫 실전 관찰 로그 `args 수신: "{\"projectRoot\"...}"` → workflow.mjs 가 JSON.parse 정규화. 포인터 파일이 정본 채널(이중화) |
| agentType 레지스트리는 세션 시작에 고정 | 신규 에이전트는 재시작 후 유효. 미등록 세션 폴백 = general-purpose + .md 본문 인라인 + model 파라미터 |
| SessionStart 훅은 메인 세션만 | 서브에이전트에 wiki/컨텍스트 자동 주입 없음 — spawn 프롬프트에 명시 전달 |
| 커밋 실재는 git 상태로만 판정 | committed 오보고 사고(2026-06-11) → workflow.mjs 가 headLog+porcelain 으로 판정, 메인도 push 전 git 직접 확인 |
| node --test 디렉토리 인자 미동작(v22.22) | 글롭(`src/*.test.js`) 사용 |
| macOS 기본 `timeout` 부재 | telemetry-digest 는 계약 hang 방어를 `perl -e 'alarm'` 로 이식(coreutils 비의존). 스키마 검증은 `jq` |
| 지점 발견 = `~/Projects/*/.planning/` 글롭 | status.sh·telemetry-digest 공통 규약. 지점 목록 = 데이터(파일시스템), 본사 코드에 하드코딩 금지 |
| launchd 최소 PATH(`/usr/bin:/bin`)는 brew 못 봄 | jq @/opt/homebrew/bin → heartbeat.sh 가 PATH 선보정. 없으면 launchd 발사 시 telemetry-digest 가 "jq 필요" rc=2 사망. kickstart rc=0 으로 실증 |
| 자기 박동 = launchd LaunchAgent(cron 아님) | darwin 네이티브 + 슬립 후 깨면 누락분 1회 따라잡음. `com.plugify.heartbeat` 매주 월. 설치/해제 `scripts/heartbeat-ctl.sh`(완전 가역). install.sh 에 안 묶음 — 활성화는 명시적(opt-in). **2026-07-03 냉동(해제됨)** — 해동 조건: 지점 telemetry.sh 실구현 |
| 지점 telemetry-log.md 존재 = 실신호 1회+ 발생 | telemetry-digest 는 계약 통과·수집 시에만 그 파일 생성 → telemetry 첫 실전 관찰(§3.1) 닫기 판정 근거(휘발성 현재주 collected 가 아닌 durable 존재성) |

## 5. 2026-06-11 확립된 룰 (정본 위치만 — 내용은 그 파일)

- 버그픽스 수용 기준 = 실코드 경로 실증 + 라이브 닫기 → `skills/spec-building/SKILL.md` "수용 기준 작성 룰"
- reviewer: 재현 실경로성 검증 + **리뷰 대상 레포 git 변조 금지** → `skills/spec-building/agents/reviewer.md`
- 타깃 해석 fail-fast(조용한 폴백 금지) → `skills/spec-building/workflow.mjs` · `skills/tech-deciding/workflow.mjs`(2026-06-12 이식 — 포인터는 JSON 1줄, +ADR 절대경로 정규화·출처 URL 보존)
- 사고→자산 반영→회귀 케이스→첫 실전 관찰 → `skills/incident-protocol/SKILL.md`
- (2026-07-03) 라이브 게이트(`{PREVIEW_URL}`)·지점 프리뷰 규격·신뢰 경계(브랜치 push=워크플로우, main=사람) → `skills/spec-building/SKILL.md` §라이브 게이트 · 검증 전 STATE 완료 기록 금지/종결 커밋 분리 → `skills/spec-building/workflow.mjs`

## 6. 열린 개선 (다음 세션 백로그)

> **다음 큰 방향 = ★1 Phase C/D — 선행: 프리뷰 배포** (2026-07-03 확정: 적대 YAGNI 리뷰(opus)+업계 대조 리서치(sonnet) 수렴 — 업계 주류는 "적응형 깊이 + verifier 를 상대로 자율 반복"(Anthropic·Cursor·OpenAI·Kiro 공통)이고 고정 순차 파이프라인이 이 시스템의 유일한 역행. ★2 는 냉동). ★가 줄기, 1~8은 독립/흡수 항목.

★1 **AI 네이티브 재설계 — 지점 루프를 본사 루프 모양으로**
- 진단: 본사 루프는 이미 AI 네이티브(목표+evals+통과까지 반복)인데 지점 루프(기획→결정→구현→검증)는 사람 조직도 디지털화(폭포수 + 사람이 모든 이음매의 메신저). 신뢰 종류로 가르는 축("속으면 안 되는 건 코드")을 미시엔 쓰면서 거시 파이프라인은 사람-역할 축으로 짬.
- 새 모양: 목표+수용게이트(입구) → 오케스트레이터 깊이 분류(비가역 표면이면 깊은 길 강제) → (큰 것만) 옵션 병렬생성·판정 → 게이트 대고 자율 반복 → 라이브 게이트 통과 → 사람은 게이트 정의+push만. 기존 스킬은 버리지 않고 역할만 변경(service-planning=게이트/옵션 생성기, tech-deciding=비가역축에서만, live-verify=게이트의 라이브 부분).
- 신뢰 경계 불변: 커밋실재·게이트통과=결정적코드, push=사람. 새 안전판: 비가역 표면 → 깊은 길 강제(under-분류가 새 실패 모드).
- 도입(각 단계 본사 루프 통과, 작은 task 경로부터·한번에 갈아엎기 금지): **A 입구를 목표+게이트로 ✅(3cf2c2b)** / **B 적응형 분류+안전판 — 보류**(비가역 게이트는 솔로·수동 트리거 단계엔 사람이 이미 게이트라 값 안 함; 자율 흐름 생기면 실제 위험 모양에 맞춰 재설계) / **C 게이트를 운전대로 ✅(2026-07-03 출하)** — ⓐ 선행 프리뷰 배포: 니치마켓 실증(브랜치 push→Vercel Preview→`.planning/preview.sh` 규격(GitHub Deployments API 폴링)→Deployment Protection bypass 헤더로 200. 지점 사실 정본 = 니치마켓 AGENTS.md §브랜치·배포 플로우) ⓑ spec-building 에 라이브 게이트 이식: `{PREVIEW_URL}` auto 항목 → 커밋 후 작업 브랜치 push(**main 이면 코드가 skip** — prod=사람)→프리뷰 프로브(항목 인라인 캡처+결과 수 결정적 대조 = 공허 통과 차단)→종결 커밋(라이브 실증 후에만 STATE 완료 기록) — 상한 내 자율 반복, live-verify 는 prod 최종 확인으로 재배치. eval case-03 출하 조건 합격. 잔여였던 니치마켓 merge ✅(2026-07-05 사람 지시로 main ff-merge — 지점 실전 라이브 게이트 즉시 가능) / **D 큰 task 병렬 탐색 — 구현됨·출하 대기(2026-07-06)**: 신규 `skills/spec-building/graph-workflow.mjs`(기존 workflow.mjs 불변). STATE "## 다음 task"의 `### 그래프`(fenced **json**: `tasks[{id·goal·targets·depends·risk?}]`·`regenBarriers?`·`verify?`)를 **결정적 파싱·검증**(JSON.parse·id유일·goal비어있지않음·depends/after dangling 금지·비순환(위상정렬)·risk enum 3값 — *생략=미분류≠MECHANICAL, 검증 강한 쪽 편향* — 위반 시 구체 에러 throw, 구현 진입 금지) → 위상정렬 wave(동시 상한 4)로 task별 격리 worktree(`.planning/worktrees/<id>`, git worktree add 직렬)→implementer(sonnet)→reviewer(opus)→커밋(haiku)→**merge-gate**(strictly-ahead + diff∩선언targets, dryforge 이식 핵심)→base 직렬 merge(충돌=abort·에스컬레이션)→regen barrier→**wave 통합 게이트**(verify exit0). **판정 이원화**: haiku 는 git/명령 출력 원문만 반환, merge-gate·통합게이트·그래프유효성·main차단·라이브게이트반려는 전부 순수 JS. **신뢰 경계**: push 금지(로컬 커밋만)·main/master 직접작업 금지(시작 시 fail-fast "작업 브랜치에서")·라이브 게이트({PREVIEW_URL})는 v1 범위 밖(시작 시 반려→단일 task workflow.mjs 안내)·사람이 merge/push. 적대 리뷰(2026-07-06) 반영: **targets 필수**(무선언 merge-gate 우회 차단)·**STATE 불가침 = 게이트 실패**(경고 아님)·implementer/reviewer **신계약 이식**(status 분기·concernDispositions 1:1 대조 — workflow.mjs 와 동일 안전판, 스키마 복제+동기화 주석)·계측↔판정 **id 조인 이중 방어**(`findByTaskId` 4사이트 — case-04 ② 첫 시험이 잡은 실결함, 다섯째 사례). opus 렁은 그래프 경로 **의도적 미이식**(wave 당 병렬 task 수만큼 비용 증폭 — 채택 시 별도 판단). eval `case-04-graph`(**초안** — ① 순환/dangling 반려·구현0 ② 유효 2wave·wave순서·task별커밋·merge-gate로그·통합게이트exit0 ③ main fail-fast ④ livegate 반려) 신설, **전 하위시험 첫 합격(2026-07-06 — 초안 기준·출제 confirm 은 사람)**. 구문검증(export strip→AsyncFunction 래핑)·순수판정부 단위검증(32/32) 통과. 기존 #3(풀체인)·#6(자동화 수위)은 "사람은 push만/메신저 제거"로 이 줄기에 흡수. Codex 부분 축소는 반영됨(2026-07-03: 교차검증 = 비가역 표면 task 만).
- **Phase A 구체(✅ 완료, 3cf2c2b)**: STATE "## 다음 task" 새 형식 = `### 목표` + `### 게이트`(항목마다 `auto:`<명령/테스트/라이브프로브 + 통과 신호> 또는 `human:`<취향·비가역>, auto≥1 권장) + `### 비가역 표면`. workflow.mjs 가 게이트 블록 없음/auto 0개 → **fail-fast 반려**(결정적 코드·조용한 폴백 금지, human-only 는 경고만). eval `spec-building/case-02-no-gate-rejected`(게이트 없는 task → 워크플로우가 구현 안 하고 반려 + 작업트리 무변경 = 합격) = 출하 조건. 완료 task 가 이미 적는 마커를 *회고*에서 *시작 전 계약*으로 앞당기는 것 — 현 SKILL §수용 기준 작성 룰(실코드 경로·게이트≠동작·라이브로 닫기)은 유지하되 형식이 강제하게 격상.

★2 **살아있는 루프 — 현황판·운영→기획 피드백·자기 시계** (★1 위에 얹음) — ✅ P0~P3 완료(2026-06-24) → **❄ 2026-07-03 부분 냉동**(적대 YAGNI 리뷰: 지점 1개·트래픽 0 에서 선건축, heartbeat 3회 발사 전부 `collected 0` = 9일간 실신호 0 — "안 닫는 자동화=소음" 자기규율 위반). 냉동 내역: launchd 박동 해제(`heartbeat-ctl.sh uninstall`), `telemetry-digest.sh`·`heartbeat.sh`·CONTRACT.md·그 eval 은 보존(해동용), 첫 실전 관찰 레지스트리·canary-check.sh·그 eval 은 제거(§3.1 불릿 격하, 복원=git 89eb2f9). **status.sh(P0 현황판)는 산 채로 유지.** 해동 조건 = 지점 `.planning/telemetry.sh` 실구현(#4) → `heartbeat-ctl.sh install`.
- 진단: 지점 루프는 태스크 안의 폐루프지만 human-clocked(매번 사람 트리거). 빠진 OS 속성 3개: 자기 박동(스케줄러)·질의가능 현황(/proc)·운영→기획 backward edge.
- 원칙: **루프(기계)는 본사가 만든다, 신호(데이터)는 지점이 정해진 규격으로 건넨다.** niche-market = 첫 입주자지 의존 대상 아님. 지점 목록 = 데이터(파일 한 줄).
- 단계: **P0 `plugify status` ✅(scripts/status.sh — 본사 evals·첫 실전 관찰·★ + 지점 STATE·git 한 화면, 지점=~/Projects/* 스캔)** → **P1 telemetry backward edge 본사 파트 ✅(2026-06-24 — `scripts/telemetry-digest.sh` 가 지점 계약 호출→주간 다이제스트 `telemetry/digest-<ISO주>.md`+지점 `.planning/telemetry-log.md` 멱등 append. 규격 정본 `telemetry/CONTRACT.md`(지점이 `.planning/telemetry.sh`→JSON stdout). 불변식: 관찰≠task(STATE 다음 task 불가침)·HQ 는 지점 커밋 안 함·skip 사유 출력. 지점 telemetry.sh 구현은 실트래픽 대기 = 기존 #4)** → **P2 자기 박동 ✅(2026-06-24 — `scripts/heartbeat.sh` 가 launchd(`com.plugify.heartbeat`, 매주 월 09:00)로 telemetry-digest 주간 자동 호출 → `heartbeat.json` 요약 → status.sh '박동' 줄(박동→현황판→사람). launchd 최소 PATH 보정으로 jq 사망 방지(kickstart rc=0 실증). 설치/해제 `heartbeat-ctl.sh`(완전 가역, install.sh 비결합·opt-in). 빈 박동은 조용·신호 생기면 현황판에 뜸)** → **P3 첫 실전 관찰 닫기 후보 탐지 ✅(2026-06-24 레지스트리+canary-check.sh 로 출하 → ❄ 2026-07-03 제거·§3.1 불릿 격하 — 위 냉동 내역 참조)**. 규율: 자율성은 트리거·관찰에만, 합격판정·push·첫 실전 관찰 닫기는 결정적/사람. 모든 박동은 "다음 행동(백로그/STATE task)"으로 끝나야(안 닫는 자동화 = 소음).

1. ✅ **perf-review eval 첫 실행 완료**(2026-06-25) — case-01 5항목 합격. perf-review 공정 검증됨(judge 오탐 죽이기 실증). 다음 perf-review 수정 시 회귀로 재실행.
2. ✅ **commit 원자성 — 해결(2026-06-25)**: 진단 = 설계는 이미 단일 atomic(implementer 스폰 프롬프트에 커밋 유도 0 + Commit 단계 haiku 가 `git add -A` 로 코드+STATE 를 한 커밋). 2분할 원인 = implementer.md line30 의 조건부 커밋 loophole("명시 지시 시 atomic")이 모호 → **제거**하고 2분할 안티패턴·"한 task=한 atomic 커밋" 명시(install.sh 동기화). atomicity 는 *지시-강제*(코드-강제 아님 — 양쪽 커밋 다 실재·검증되는 cleanliness 라 결정적 코드 불필요). 재발 시 Commit 단계에 HEAD-이동 감지+fold 검토.
3. **풀체인 모드**(사람은 최종 보고만) — STATE task 큐 자동 순회(spec-building→live-verify→다음). **선행: 프리뷰 배포**(push=즉시 prod 라 완전 무인 불가). 검수자 신뢰는 evals 로 확보 후.
4. **telemetry-review 루프**(운영→기획 backward edge) — *기계 파트는 ★2-P1 에서 완료*(telemetry-digest + CONTRACT, 현재 ❄ 냉동). 잔여 = ⓐ 지점 `.planning/telemetry.sh` 실구현(niche-market, 실트래픽 생기면) **= ★2 해동 조건** ⓑ (선택) 다이제스트를 사람이 주간 리뷰→승격하는 얇은 스킬. 트래픽 전까진 냉동(박동 해제됨 — 2026-07-03).
5. **evals 확충** — ✅ **거의 완료(2026-06-25)**: live-verify case-01(push 미실재→P0 정지; eval 이 SKILL P0 갭 발견·수정) + service-planning case-01(completeness-critic 심은 누락 정탐·정당제외 오탐억제; 퍼지 산출물을 *심은 누락 탐지*로 결정화) 둘 다 신설·합격. perf-review case-01 첫 실행 합격(#1 완료). **잔여 후속 case 후보**(저우선): live-verify case-02(P3 실패→표준 버그 블록 양식) · service-planning은 completeness-critic 외 슬라이스(plan-writer 발명금지 등). 우선순위는 수정 빈도 순.
   - **live-verify 정제 후보(비차단)**: P0 실패(push 미실재) 시 STATE 손대지 말지(보고-only) vs 거짓주장 정정 허용 — case-01 재실행서 executor 가 STATE 헤더를 정정함(버그블록 아님·무해하나 작업트리 dirty + 정정 미커밋). 실사용 빈도 낮아 후순위.
6. **자동화 수위 상향 검토** — live-verify 의 명시 호출 의존(메인이 지시문 따름)을 Stop hook/workflow 화로 기계화할지. 비가역 게이트(push) 분리가 전제.
7. **comprehension debt** — 에이전트 작성 코드를 사람이 안 읽는 구조. 주요 모듈 "코드 투어" 체크포인트 운영 검토.
8. plugins/ 번들화(`dev-loop`) — 외부 배포 필요 시.
9. **spec-building 정제 후보(비차단 — 2026-07-06 적대 리뷰 advisory 기록, 조용한 드랍 금지)**: ⓐ concern 개수 불일치 시 피드백이 implementer 로 재투입됨(실은 리뷰어 판정 누락 — 재구현 불필요할 수 있음, 확률적 자기교정 의존) ⓑ graph 병렬 에이전트의 worktree 고정이 프롬프트 cd-pin 의존(commit-fail·merge-gate 가 backstop — 저위험) ⓒ "평가불능=실패" 문구가 3곳 분산(spec-building 게이트룰·프로브 프롬프트·live-verify P3 — 모순 없음, 표현 통합 여지) ⓓ case-03 ANSWER #4 "항목 2개" 문구 결함(사람 게이트).
10. **scaffold 2·3단계** (2026-07-21 계획 — 1단계 첫 실전 관찰 실증 후 착수): ⓐ **2단계 파이프라인 어댑터** — perf-review 우선(P2 judge 가 분석 보고서 3개를 파일로 직접 읽게 해 메인 raw 운반 제거 — 현행 SKILL 의 알려진 오염 지점) → tech-deciding(workflow.mjs 가 인스턴스 프롬프트·축별 조사 산출물을 run 디렉토리에 기록 — 증거·레인 재실행). 출하 조건 = 기존 evals(perf-review case-01·tech-deciding case-01) 재실행 합격. ⓑ **3단계 walking-skeleton 원칙** — "새 산출물 유형/새 지점은 수용 규격을 역산한 빈 골격 + 실격급 조건(로드·배포·로그) 사전 실증 + 확인 후 내용 작업"(AX 해커톤 scaffold.png 패턴). AGENTS.md 헌법 한 줄 + spec-building 선행 조건 한 항목. ⓒ 후속 후보: 평가자 역설계 심사자 틀(audience-judge — 산출물을 실제로 받아볼 외부인의 행동 모델로 블라인드 채점)을 `skills/scaffold/templates/` 에 추가.

## 7. 참고 계보

루프 엔지니어링(Cherny→Osmani 2026.6, ralph/Huntley 2025.7) 조사 + "Agent-in-the-loop 2층 구조(구축/사용 분리·일반화 검증·배포)" 사례 분석에서 본사/지점 모델 도입. 핵심 채택 원칙: 루프 종결 = 외부 verifier 의 라이브 확인 / 구축·사용 모드 분리 / 문제집(일반화 검증) 통과 후 출시.

2026-07-03 업계 대조 리서치(sonnet, 30여 1차 소스): 원칙 5개 중 4개(라이브 verifier·신뢰 경계·격리 서브에이전트·eval 메타루프)는 업계 검증됨/선점 — 특히 라이브 게이트는 Fowler·Qovery 가 "미해결 갭"으로 자인한 지점. 유일한 역행 = 고정 순차 파이프라인(업계 주류: 단일 spec·적응형 깊이·스킵 가능 — Anthropic/Cursor/OpenAI/Kiro 공통) → ★1 C/D 가 상환 계획. 모델 발전 시 부채화 순위: 파이프라인 이음매 > Codex 교차검증 > 스킬 미세 절차 규칙. 내구적: 격리 컨텍스트(Cognition "Devin manages Devins" 역채택 실증)·결정적 코드 판정·라이브 게이트·사고→회귀 eval.
