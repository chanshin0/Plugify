---
name: perf-review
description: 프로젝트 성능을 전문화 에이전트 4종(렌더링·데이터·실측 분석 3개 병렬 → 적대 종합 1개)으로 리뷰한다. "성능 리뷰", "성능 점검", "느린 곳/원인 찾아", "성능 어때", "perf review", "performance audit" 등에 트리거. 진단 전용 — 픽스는 spec-building 으로. 스택 비종속 — 프레임워크·빌드 명령은 메인이 레포에서 추출해 전달. lean-agent-design — 메인은 컨텍스트 추출·spawn·게이트만, 분석 잡음은 격리 에이전트에 가둔다.
---

# perf-review — 성능 리뷰 파이프라인 (3 분석 병렬 → 1 적대 종합)

코드베이스의 성능 문제를 **증거 기반**으로 찾는다. 추측 보고서가 아니라: 도메인별 분석가 3개가 병렬로 file:line 증거를 모으고, 심판 1개가 코드를 재독해 오탐을 죽인 뒤 임팩트 랭킹을 낸다. **진단 전용** — 수정은 하지 않는다(픽스는 spec-building).

## 에이전트와 모델 배치 (SSOT = `agents/*.md`)

| 에이전트 | 모델 | 역할 | 배치 근거 |
|---|---|---|---|
| `perf-render-analyst` | sonnet | UI 렌더링·번들 정적 분석 | 루브릭 명확한 도메인 코드 분석 — 병렬 3개라 비용/속도 균형 |
| `perf-data-analyst` | sonnet | 데이터 계층(쿼리·인덱스·캐싱) 정적 분석 | 동일 |
| `perf-runtime-prober` | sonnet | 프로덕션 빌드 실측 | 측정은 기계적이지만 수치→원인 코드 귀속에 추론 필요 |
| `perf-judge` | opus | 적대 검증 + 종합 + 랭킹 | 오탐 제거가 파이프라인 가치의 핵심 — 거짓 양성 1개가 보고서 신뢰 전체를 깎는다. 최상위 추론 모델 |

- **haiku 미채용 사유**: 성능 안티패턴 판별은 컨텍스트 의존(`'use client'` 자체는 죄가 아니다) — 패턴매칭 단독은 오탐이 폭주해 judge 비용이 더 든다.
- 에이전트는 plugify `scripts/install.sh` 로 전역 등록되어 `agentType` 으로 호출한다. **등록 전/미재시작 세션 폴백**: `general-purpose` + 해당 `agents/<name>.md` 본문을 프롬프트에 인라인 + Agent `model` 파라미터로 동일 모델 지정.

## 플로우

### P0 — 메인: 컨텍스트 블록 + 착지 골격 (분석 전 1회)
1. 레포에서 직접 읽어 아래 블록을 만든다. 에이전트는 스택 비종속이므로 **이 블록이 유일한 프로젝트 지식 주입점**이다.
```
projectRoot: <절대경로>
스택: <프레임워크+버전, 데이터 계층, 스타일링, 배포 타깃>
빌드/테스트 명령: <npm run build 등>
구조: <주요 디렉토리 1줄씩 — 페이지, 컴포넌트, 데이터 액세스, 마이그레이션>
핫패스 전제: <트래픽 가정 — 어떤 화면/쿼리가 가장 자주 불리나. 모르면 "미상" 명시>
확정 결정: <성능 관련 ADR 요약 — 예: 검색=ILIKE. 없으면 생략>
```
2. **착지 골격 생성 (scaffold 스킬 규약과 동형 — 발사 전)**: run = `<projectRoot>/.planning/runs/<YYYY-MM-DD>-perf-review/` (`.planning` 없으면 `<projectRoot>/runs/…`)
   - 파일 생성 전 run 상위 경로를 대상 레포 `.git/info/exclude`에 멱등 추가하고 `git check-ignore -q <run>` 성공을 확인한다. 실패하면 외부 `~/Documents/agent-runs/`로 옮긴다. run 증거가 후속 `spec-building` 제품 커밋에 섞이면 안 된다.
   - `prompts/render.md` · `prompts/data.md` · `prompts/prober.md` — 컨텍스트 블록 + 도메인 지시를 채운 이번 실행의 지시문 파일(역할 정본은 에이전트 `.md`, 이 파일은 인스턴스 증거)
   - `outputs/render.md` · `outputs/data.md` · `outputs/prober.md` — 빈 슬롯 예약(착지 자리)

### P1 — 분석가 3개 **병렬** spawn (Agent tool, 한 메시지에)
- 스폰 프롬프트는 포인터만: "지시문은 `<run>/prompts/<도메인>.md` — Read 후 수행. 산출물은 `<run>/outputs/<도메인>.md` 에 Write. 그 외 파일 수정 금지. 반환은 3줄 요약 + 경로."
- 수확은 코드로 판정: 슬롯 실재·비어있지 않음을 **메인이 ls·wc 로 직접 확인**(에이전트 보고 아님). 빈 슬롯 = 그 레인 실패 — 프롬프트 파일 보강 후 그 레인만 재발사.
- 진단 전용 검증도 코드로: `git -C <projectRoot> status --porcelain` 변경이 run 디렉토리(+prober 빌드 산출물) 밖에 있으면 위반 — 사용자 에스컬레이션.

### P2 — perf-judge spawn
컨텍스트 블록 + run 경로만 전달 — **judge 가 `outputs/` 3개를 직접 Read 한다**(보고서 전문이 메인 컨텍스트를 거치지 않는다). judge 는 인용 코드를 재독해 confirmed / killed / uncertain 3분류 + 임팩트(사용자 체감×빈도)÷노력 랭킹을 **반환**한다 — 최종 보고서 파일은 judge 가 쓰지 않는다(하니스가 서브에이전트의 보고서류 파일 Write 를 차단, 2026-07-22 실증 — SYSTEM §4).

### P3 — 메인: 판정 + relay + 후속 라우팅
- **메인이 judge 반환 전문을 `<run>/REPORT.md` 로 정착**시킨다(기계적 Write — 최종 보고서는 어차피 메인이 relay 하는 유일한 전문이라 추가 컨텍스트 비용 없음). 그 후 사용자에게 전달(재가공 최소화).
- 원 요청이 성능 **리뷰/진단만**이면 결과 보고로 닫고 코드를 수정하지 않는다. 원 요청이 개선·수정까지 포함하면 추가 진행 확인 없이 confirmed 항목을 evidence-bearing task로 만들어 spec-building으로 보내고 재측정한다. 우선순위가 사람만 아는 제품 의도에 따라 크게 달라질 때만 집중 인터뷰한다.
- run 디렉토리는 증거로 남긴다(레인 재실행·사고 조사·프롬프트 개선 — 지시문 결함은 run 이 아니라 에이전트 `.md`/이 SKILL 에 반영, scaffold P4 준용).
- 종료 상태는 슬롯 3개 실재·judge 코드 재독·REPORT.md 정착이 모두 확인됐을 때만 `reviewed`다. 빈/실패 레인이 남으면 `blocked-input`; 개선까지 승인된 요청은 수정·재측정 증거가 끝날 때까지 별도 실행 task로 이어진다. finding 수를 "정확도"로 부르지 않는다 — 정답이 심어진 eval에서만 정탐/오탐률을 계산한다.

## 금지
- 분석가·judge 가 코드를 수정 (진단 전용 — run 슬롯·prober 빌드 산출물만 예외, git 상태로 판정)
- 메인이 raw findings 전체를 컨텍스트에 떠안기 (파일 착지 + judge 종합만 relay — 구조가 강제)
- 추측 수치 보고 (실측이거나 "미실측" 명시 — 에이전트 공통 규칙)
- 함대화 (도메인당 1개, 총 4개 고정. 더 깊이가 필요하면 라운드를 다시 돌리지 에이전트를 늘리지 않는다)
