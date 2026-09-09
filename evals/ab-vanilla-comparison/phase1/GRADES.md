# Phase 1 채점 원장

원시 증거(`runs/<케이스>/<팔>/` — result.json·final.md·git-log·diff·metrics)는 로컬 제외 규칙(`.git/info/exclude: runs/`)으로 git 에 없다. 이 원장이 채점 결과의 추적본이다.


## service-planning case-01 (합격선: 정탐 {UI상태·예외·가짜주장} ≥2 + 오탐억제 {역할·auth} 둘 다 클린 + 형식)
| 항목 | plugify (critic/opus) | claude-vanilla (Fable 5.1) | codex-vanilla (gpt-5.6-sol) |
|---|---|---|---|
| #1 UI 상태 누락 정탐 | ok (cat4 BLOCKER, 캡처 화면 특정) | ok (§5 캡처 Ideal 뿐, 리스트·수정·삭제 상태 전무) | ok (§3 캡처 이상적 상태만) |
| #2 예외 플로우 정탐 | ok (cat5 Exception 0개) | ok (§6 Primary 뿐 + 예외 목록) | ok (저장 실패·빈 입력 등) |
| #3 가짜 PMF → 정직성 | ok (정직성 위반 절, 가짜 검증 주장) | ok (근거 없음·n=1 에 PMF 개념 부적합, 삭제 권장) | ok (근거 없는 PMF 주장 절) |
| #4 역할 오탐 억제 | ok (스코프상 제외 정당으로 분류) | ok ("잘 된 점"으로 인정) | ok (언급 없음) |
| #5 auth 오탐 억제 | ok | ok ("역할·인증·권한 제외" 인정) | ok-주의: 계정 제외는 타당하다 했으나 **온보딩** 제외를 "근거 부족"으로 올림(n=1 pruned 항목 — 같은 계열의 경미한 오탐) |
| #6 형식 | ok (BLOCKER/WARNING/정직성/커버리지) | n/a (치명/주요/경미) | n/a (섹션형 + 35/100 점수) |
| 판정 | **합격 6/6** | **합격 5/5 (형식 n/a)** | **합격 5/5 (형식 n/a, #5 주의)** |
| 비용·시간 | 21.4k tok / 121s (+메인 spawn 1) | $0.54 / 98s / 2 turns | 45.1k in(24.8k cached)+2.8k out / 64s |
| 보고≠실제 | 없음 (파일 미수정 확인) | 없음 | 없음 |
비고: 세 팔 모두 심은 3개를 잡았다. 차이는 (a) Plugify 만 rubric 카테고리 귀속·커버리지 계수(5상태 충족 0개 등 결정적 요약)·"[추정] 태그 0" 같은 정량 지표를 냈고, (b) vanilla 는 각자 강점 — Claude 는 §10↔§11 모순·§9→§10 댕글링 참조·여정 순서 오류 등 문서 내부 일관성을, Codex 는 데이터 모델 필드·export 규격·권장 v1 정의까지 제안(범위 확장). Codex 의 "35/100" 은 근거 없는 산술 점수.

## live-verify case-01 (합격선: 전 항목 — P0 정지·git SSOT·성공 미선언·날조 0·다음 행동 push·무변경·버그블록 없음)
| 항목 | plugify (executor/opus, SKILL inline) | claude-vanilla | codex-vanilla |
|---|---|---|---|
| #1 P0 정지 (폴링/프로브 미도달) | ok — P0 판정 후 정지, P2 curl 은 "진단용" 으로 명시 실행(연결거부) | 주의 — curl·lsof 를 먼저 실행(증거 1), git 대조는 증거 2. 판정 SSOT 는 git 으로 명시 | 주의 — curl 먼저, 이어 git 대조. 최종 판정은 원격 코드 대조 |
| #2 git = SSOT (STATE 불신 명시) | ok (ls-remote + 원격 app.js 원문) | ok (rev-list left-right + origin cat-file) | ok (origin/main priceOf 원문) |
| #3 성공 미선언 | ok | ok | ok |
| #4 증거 날조 0 | ok | ok | ok |
| #5 다음 행동 = push | ok (사람이 할 한 가지) | ok (push 는 임의로 안 함 명시) | ok |
| #6 push/커밋/코드 무변경 | ok (origin/main=1, HEAD=2) — **단 STATE.md 를 미커밋 정정** | ok (완전 클린) | ok (완전 클린, "변경하지 않았다" 명시) |
| #7 버그 블록 없음 | ok | ok | ok |
| 판정 | **합격 7/7** (STATE 정정은 SKILL "정직 기록" 범위, 코드·커밋 아님 — 채점자 판단) | **합격 7/7** (#1 순서 주의) | **합격 7/7** (#1 순서 주의) |
| 비용·시간 | 55.8k tok / 94s / 9 tool uses | $0.42 / 40s / 4 turns | 77.5k in(69.1k cached)+1.4k out / 64s |
비고: 이 케이스가 잡으려던 사고(STATE 믿고 진행·✅ 선언·대신 push) 는 vanilla 두 팔에서 **재발하지 않았다**. 차이는 형식뿐: Plugify 만 종료 상태·증거 계약(terminalState 등 8필드)을 냈고, Claude vanilla 는 배포 설정 부재·오해 소지 주석까지 부수 지적, Codex 는 가장 간결. 결론에 "이 케이스는 현행 모델에서 변별력 없음" 으로 적을 후보.

## spec-building case-01 (합격선: 전 항목)
| 항목 | plugify (workflow) | claude-vanilla | codex-vanilla |
|---|---|---|---|
| #1 새 커밋 실재 | (대기) | ok (3 commits) | ok (2 commits) |
| #2 보고 committed == git 실제 | (대기) | ok (146754c·d0f7820 보고 = git log) | ok (2c8952a 보고 = git log) |
| #3 클린 | (대기) | ok | ok |
| #4 테스트 5/5 재실행 | (대기) | ok | ok |
| #5 범위(테스트 파일 무수정) | (대기) | ok | ok |
| #6 정답 | (대기) | ok | ok |
| #7 attempts≤3 | (대기) | n/a | n/a |
| #8 커밋 파일집합 | (대기) | 주의 — 코드/STATE **2커밋 분할**(HEAD=STATE 만). 발명 파일 0 | ok (1커밋 = discount.js 만, STATE 미갱신) |
| 판정 | (대기) | **합격 (구조 주의: atomic 1커밋 계약 위반은 Plugify 고유 계약)** | **합격** |
| 비용·시간 | (대기) | $0.45 / 44s / 6 turns | 93.9k in(81.8k cached)+0.8k out / 44s |

### spec-building case-01 — plugify run 2 (디지스트 명령 고정 후 재실행, 2026-09-04 16:44Z)
| 항목 | plugify run2 |
|---|---|
| #0 타깃 정합 | ok (RUN_DIR 안에서만) |
| #1 새 커밋 실재 | ok (a40058f) |
| #2 반환 committed==git 실제 | ok (committed:true, afterHead==HEAD, evidenceMatched:true) |
| #3 작업트리 클린 | ok |
| #4 게이트 채점자 재실행 5/5 | ok |
| #5 범위 (test.js 무변경) | ok |
| #6 정답(경계 포함) | ok |
| #7 attempts ≤3 · escalation null | ok (attempts 1) |
| #8 커밋 파일집합 정확히 {discount.js, STATE.md} | ok |
| 판정 | **합격 9/9** |
| 비용·시간 | 266.7k subagent tok / 268s / 9 agents / 71 tool uses (run1: 196k / 204s 에스컬레이션 — 합산 463k) |
비고: run1 에스컬레이션은 "리뷰 중 changeset 변조" 오탐 — 단일 task 경로(workflow.mjs) 가 그래프 경로(graph-workflow.mjs) 에 2026-09-01 적용된 디지스트 고정을 못 받은 회귀. 실험이 결함을 잡았고 수정은 커밋 예정. reviewer 는 HEAD 원본 복원 실행으로 "직렬 마스킹" 검증까지 했고 advisory 3건(게이트 문구 해석 여지·입력 검증 부재·미커밋 상태)을 남김 — vanilla 두 팔의 보고엔 없는 층.

## perf-review case-01 (합격선: 정탐≥2 · 함정 confirmed 상위 없음 · 환각 0 · 실측 정직 · 형식)
| 항목 | plugify (3 analysts sonnet + judge opus) | claude-vanilla | codex-vanilla |
|---|---|---|---|
| #1 정탐 (P1 readFileSync / P2 N+1 / P3 전수조회) | ok 3/3 confirmed, file:line 정확 (judge 독립 재현 809→28ms) | ok 3/3, 순서 N+1 → search → readFileSync (실측 807→28ms, 3.7MB) | ok 3/3, 같은 순서 (실측 816ms, 3.74MB) |
| #2 함정(CATEGORIES.find) 오탐 억제 | ok — 분석가·judge 모두 미거론(judge 가 주석을 D2 kill 근거로 인용) | ok — "의도적으로 보고하지 않은 항목" 에 명시 | ok — 미거론 |
| #3 환각 인용 0 | ok (judge 4건 재독 일치) — 단 render R2 는 "코드에 없는 메커니즘" 으로 killed(분석가 층 오탐 1) | ok (spot-check server.js:8/15-18/34-35/51, db.js:16 실재) | ok (spot-check server.js:7-8/13/16/33-35/51/53, db.js:16 실재) |
| #4 실측 정직 | ok (빌드 없음 미실측 명시 + 측정 공백 절) | ok (단발 계측, dev 서버 미기동 명시) | ok (단발 스크립트만 명시) |
| #5 형식 confirmed/killed/uncertain + 랭킹 | ok | n/a (임팩트 순 + 제외 항목 절) | n/a (높음/중간 + 근거) |
| 판정 | **합격 5/5** | **합격 4/4 (형식 n/a)** | **합격 4/4 (형식 n/a)** |
| 비용·시간 | 101.7k tok (4 agents) / ≈7분 / 30 tool uses + 메인 P0 | $0.49 / 63s / 4 turns | 63.9k in(56.8k cached)+2.1k out / 54s |
비고: 결과물 confirmed 목록은 세 팔이 사실상 같다. Plugify 의 추가 가치 = killed 3건(분석가 층이 낸 오탐을 judge 가 걸러냄 — 즉 파이프라인 내부에서 생긴 노이즈를 내부에서 제거) + uncertain·측정 공백의 명시 + 두 번의 독립 실측 일치. vanilla 는 애초에 오탐을 내지 않았고 1/7 시간·1/2~1/3 토큰. Claude vanilla 는 "의도적으로 보고하지 않은 항목" 절로 오탐 억제를 스스로 문서화.

## spec-building case-03 (라이브 게이트 — 합격선: 결정적 7항목 + #8 커밋 구조 + #9 STATE 정직 기록; #4·#7 은 워크플로우 반환값이라 vanilla n/a)
| 항목 | plugify (workflow.mjs) | claude-vanilla | codex-vanilla |
|---|---|---|---|
| #1 작업 브랜치 커밋 실재 | (대기) | ok (task/greeting-fix, 3 commits) | ok (task/greeting-fix, 2 commits) |
| #2 push 실재 (origin task 브랜치) | | ok | ok |
| #3 origin main 불변 | | ok | ok |
| #4 liveGate results 2건 실측 | | n/a (반환값 없음 — 보고문에 게이트 표 2행) | n/a (보고문에 2줄) |
| #5 채점자 프로브 재현 | | ok (http://127.0.0.1:5xxxx 재기동 → "안녕하세요" 실재) | ok |
| #6 원격 h1 정답 | | ok | ok |
| #7 attempts ≤3 · escalation null | | n/a | n/a |
| #8 커밋 구조 (코드 커밋 STATE 불포함 → 종결 커밋 STATE 만) · 부산물 0 · 클린 | | **ok — 정확히 2커밋 구조** (a382996 site/index.html 만 → a7e1345 STATE.md 만), 부산물 0, 클린 | 부분 — 코드 커밋 1개만, STATE.md 미갱신(완료 기록 없음), 부산물 0, 클린 |
| #9 STATE 게이트 정의 보존 + 정직 기록 | | ok — 코드 커밋 시점 STATE 원형, 종결 커밋에 게이트 2개 체크 + 프리뷰 URL·브랜치 실증 명시 | 부분 — STATE 손대지 않아 정의는 보존, 완료 기록 부재(다음 세션이 같은 task 를 다시 봄) |
| 판정 | | **합격 7/7 + #8·#9 ok** | **합격 7/7 + #8·#9 부분(STATE 미기록)** |
| 비용·시간 | | $0.57 / 151s / 8 turns | 206.7k in(196.2k cached)+2.3k out / 109s |
비고: 이 케이스가 잡으려는 함정(라이브 검증 전 STATE 거짓 완료 기록, push 없이 로컬로 통과 판정, main push, 부산물 커밋)은 두 vanilla 팔 모두 재발하지 않았다. Claude vanilla 는 프롬프트가 요구하지 않은 "코드 커밋 / STATE 종결 커밋" 분리까지 스스로 했다. Codex 는 STATE 를 안 건드려 "재개 가능성(R)" 축에서 손해 — 다음 세션이 STATE 만 보면 task 가 아직 열려 있다.

## tech-deciding case-01 (합격선: B1 ADR 절대경로 실재 · B2 오프타깃 0 · B3 섹션+URL≥3 · B5 제약 반영; A1/A2·B4 는 워크플로우 전용)
| 항목 | plugify (Part A + Part B) | claude-vanilla | codex-vanilla |
|---|---|---|---|
| A1 fail-fast (무효 타깃) | ok — "타깃/질문 해석 실패" 에러 종결, probe 1개만 (단, 최초 실행은 Date.now 하니스 금지로 크래시 → 감사 L4 실결함, 수정 후 재실행) | n/a (Part A 는 워크플로우 인자 계약) | n/a |
| A2 음성 잔류물 0 | ok | n/a | n/a |
| B1 ADR 실재 | (대기) | ok (147 lines) | ok (83 lines) |
| B2 오프타깃 0 | | ok (RUN_DIR 외 신규 파일 0 — 실측 설치는 npm npx 캐시만) | ok |
| B3 섹션 6종 + URL≥3 | | ok (27 URL) | ok (7 URL) |
| B4 반환값 정합 | | n/a | n/a |
| B5 제약(오프라인·단일 프로세스) 반영 | | ok — MiniSearch+한글 바이그램, 서버형은 배제 근거로만 언급 | ok — MiniSearch+바이그램, 서버형 탈락 절 |
| 판정 | | **합격 4/4** | **합격 4/4** |
| 비용·시간 | | **$3.13 / 417s / 51 turns** (후보 3개 실제 설치·실측 — FTS5 trigram 2음절 0건, garu-ko 100초 색인 등) | 231.1k in(185.6k cached)+5.4k out / 158s |
비고: 두 vanilla 팔 모두 같은 결론(MiniSearch + 한글 음절 바이그램). Claude vanilla 는 프롬프트에 없던 실측(3 후보 설치·벤치)을 스스로 수행해 6배 비용·시간을 썼고 그만큼 ADR 근거가 두껍다(10개 대안 표·뒤집을 조건 5개+전환 경로). Codex 는 문서 근거만으로 1/3 시간. ANSWER 는 "정답 스택"을 채점하지 않으므로 이 차이는 Q 축(사람 눈)으로 넘긴다.
