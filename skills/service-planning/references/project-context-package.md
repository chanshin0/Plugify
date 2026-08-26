# 지속형 프로젝트 문맥 패키지 계약

> `service-planning`의 조건부 확장이다. 한 번 읽고 끝나는 기획서가 아니라 여러 세션·사람·에이전트가 이어서 설계하고 실행할 프로젝트에만 적용한다.

## 1. 활성 조건과 비적용 경계

다음 중 하나면 `persistent-context` profile을 켠다.

- 사용자가 프로젝트 문맥 환경, 재진입, handoff, 역할별 서브에이전트 프롬프트, 전체 디렉터리 구조를 명시적으로 요구한다.
- 기존 서비스·ERP·내부 포털·데이터를 점진 현대화하거나 AX 전환한다.
- 독립 workstream이 2개 이상이고 여러 세션에서 재사용할 정본이 필요하다.

다음만으로는 켜지 않는다.

- `deep` 티어라는 이유만 있는 경우
- 화면이 여러 개인 일회성 기획
- n=1 개인 도구, napkin, 단일 기능의 짧은 상세화

profile 활성 이유를 진행 업데이트에 한 줄로 알린다. profile은 기획 티어와 독립이며, 단순 기획을 비대하게 만들지 않는다.

## 2. 정본 package와 run evidence

- **package root**는 현재 상태·결정·계획·역할 프롬프트가 살아 있는 정본이다.
- 일회성 조사 run, 원문 transcript, agent raw output은 package가 아니다. 허용된 evidence locator로만 연결한다.
- 사용자가 저장 경로를 주면 그 경로를 우선한다. 저장소에 문서화된 planning anchor가 있으면 그 안에 둔다. 둘 다 없으면 service-planning 기본 산출 디렉터리를 쓴다.
- 기존 package를 갱신할 때는 repo의 `AGENTS.md`·정책·정본 소유권을 먼저 읽고 사용자 변경을 보존한다.

## 3. 최소 출력 구조

```text
<package-root>/
├── README.md
├── STATUS.md
├── 기획서.md
├── gaps.md
├── DELIVERY-REPORT.md
└── prompts/
    ├── 00-ORCHESTRATOR.md
    ├── 10-BUSINESS-DISCOVERY.md
    ├── 20-SOURCE-CARTOGRAPHER.md
    ├── 30-WORKFLOW-MODELER.md
    ├── 40-DATA-ARCHITECT.md
    ├── 50-PORTAL-PLANNER.md
    ├── 60-MIGRATION-PLANNER.md
    ├── 70-SECURITY-AI-REVIEWER.md
    └── 90-COMPLETENESS-CRITIC.md
```

역할을 지금 쓰지 않아도 파일을 삭제하지 않는다. 해당 파일의 `중단·질문 조건`에 아직 열리지 않은 gate와 필요한 evidence를 적는다. 이 9개 이름은 persistent-context profile의 고정 탐색 주소다.

프로젝트 복잡도에 따라 아래 정본을 추가할 수 있다. 같은 사실의 소유 문서를 하나만 정하고 README가 읽기 순서와 경계를 연결해야 한다.

- `AGENT-CONTEXT.md`, `AGENTS.md`
- `MILESTONES.md`, `BACKLOG.md`, `WORKSTREAMS.md`
- `DECISIONS.md`, `OPEN-QUESTIONS.md`, `RISKS.md`, `METRICS.md`
- `EVIDENCE-INDEX.md`, `GOVERNANCE.md`, `ARCHITECTURE-GUIDE.md`, `DATA-AI-GUIDE.md`
- `templates/`, `research/`, 선택 산출물 `wireframes.html`, `data-model.md`

## 4. 레거시 현대화 선행 gate

`legacy-modernization` profile이면 다음 세 문서가 최소 추가 산출물이다.

```text
<package-root>/
├── BUSINESS-CAPABILITY-MAP.md
├── PROCESS-CATALOG.md
└── M0A-DISCOVERY-GUIDE.md
```

순서는 아래를 지킨다.

1. capability: 조직·시스템이 안정적으로 **무엇을 하는가**를 메뉴·화면·기술과 분리한다.
2. process/workflow: 직원이 실제로 **어떻게 trigger에서 outcome까지 가는가**를 역할·handoff·writer·예외·복구·shadow work와 함께 발견한다.
3. walking slice: 실제 빈도·중요도·병목·owner·데이터 근거가 있는 workflow를 구현·수용 단위로 선택한다.
4. domain: 목표 논리 모델, 권위 이전, rollback, legacy retire의 단위로 선택한다.
5. architecture/migration: 위 evidence가 모인 뒤 proposed→accepted gate를 연다.

정적 source는 코드·route·schema·연결 능력의 존재만 증명한다. 실제 사용, 운영 활성, 빈도, owner, 모든 writer, 정본은 담당자 또는 승인된 runtime evidence가 없으면 unknown이다. 이 gate가 열려 있으면 물리 DB·제품·벤더·cutover를 accepted로 확정하거나 구현 handoff하지 않는다.

## 5. evidence와 결정 상태

프로젝트가 쓰는 용어가 있으면 그 용어를 따른다. 없으면 최소한 아래를 분리한다.

- `source-confirmed`: 정적 코드·문서·schema의 존재와 내용
- `runtime-confirmed`: 기준 시각과 관찰 범위 안에서 확인한 동작
- `human-confirmed`: 확인자·기준일·답변 범위 안의 업무 사실
- `inferred`: 확인 근거에서 한 해석
- `proposed`: 채택 전 설계안
- `accepted`: 승인자·기준일·뒤집을 조건이 있는 결정
- `unknown`: closing evidence가 아직 없는 항목

코드 존재를 실제 사용으로, 계획 기본값을 accepted 결정으로, 파일 생성을 gate 통과로 승격하지 않는다.

## 6. 역할 프롬프트 공통 schema

9개 프롬프트는 대화 이력을 몰라도 단독 실행 가능해야 하며 아래 절을 정확히 포함한다.

1. `## 역할`
2. `## 필수 읽기`
3. `## 호출 입력`
4. `## 수행`
5. `## 안전·금지 경계`
6. `## 산출물`
7. `## 완료 검증`
8. `## 중단·질문 조건`

`호출 입력`에는 최소 다음 의미가 있어야 한다.

- 이번 호출이 끝낼 `TASK`
- 읽기·쓰기 허용 범위 `TARGETS`
- 단일 소유 산출물 `OUTPUT`
- 사용할 evidence와 상태 `EVIDENCE`
- 이미 받은 접근·실행 승인 `APPROVALS`; 없으면 없음

공통 불변조건:

- 한 산출물에는 writer agent 하나만 둔다. reviewer는 원산출물을 수정하지 않고 별도 review를 소유한다.
- prompt는 repo와 package의 규칙·정본 읽기 순서를 포함한다.
- network, 서버, 운영 데이터, 외부 API, write/delete/external transmission은 이미 승인된 범위가 없으면 금지한다.
- 승인된 로컬 source 사본은 정적으로만 읽고 runtime 사실로 과장하지 않는다.
- 모르는 것은 추측으로 닫지 않고 영향·owner·closing evidence를 적는다.
- 완료는 파일 실재와 validator 결과로 판정한다. agent의 완료 보고을 그대로 믿지 않는다.

## 7. 고정 역할과 소유권

| 프롬프트 | 소유 결과 | 소유하지 않는 것 | 핵심 stop condition |
|---|---|---|---|
| `00-ORCHESTRATOR.md` | stage·DAG·역할·산출물 소유권·검증 보고 | 전문 산출물 대신 작성 | 파일 소유 충돌, 새 승인 필요 |
| `10-BUSINESS-DISCOVERY.md` | 실제 업무·active/dead·shadow work·first-slice evidence | 기술 topology·target architecture | 실제 사용자·owner 근거 없음 |
| `20-SOURCE-CARTOGRAPHER.md` | 승인된 로컬 source의 정적 구조·capability 단서 | runtime·실사용·정본 판정 | 로컬 사본 밖 접근 필요 |
| `30-WORKFLOW-MODELER.md` | workflow 하나의 trigger→outcome·예외·복구 | 전체 IA·물리 모델 | workflow·actor·owner 미선택 |
| `40-DATA-ARCHITECT.md` | 목표 논리 모델·crosswalk·projection·authority state | 제품·벤더 확정·실제 이관 | writer·invariant·restore unknown |
| `50-PORTAL-PLANNER.md` | 내부 work hub IA·화면 상태·수용 기준 | 공개 사이트 우선화·정본 결정 | 역할·workflow evidence 없음 |
| `60-MIGRATION-PLANNER.md` | shadow→read canary→authority 전환·rollback gate | probe·cutover 실행 | source load·복구·승인 없음 |
| `70-SECURITY-AI-REVIEWER.md` | 권한·privacy·audit·agent/tool 적대 검토 | 원산출물 수정·실제 공격 | 분류·policy owner 없음 |
| `90-COMPLETENESS-CRITIC.md` | 독립 누락·과장·gate·실제 tree 판정 | 원산출물 수정 | 필수 파일·합격 기준 없음 |

`00-ORCHESTRATOR.md`는 나머지 8개 파일명을 모두 명시하고 요청→역할→선행조건을 라우팅한다. 병렬 작업은 산출물 소유권이 겹치지 않고 의존성이 없을 때만 허용한다.

## 8. 생성 순서

1. profile과 package root를 정하고 최소 빈 골격을 먼저 만든다.
2. evidence·결정 상태와 legacy discovery gate를 정한다.
3. `기획서.md`·`gaps.md`를 합성하고 현재 상태를 `README.md`·`STATUS.md`에 연결한다.
4. 프로젝트 실제 workstream과 정본 경계에 맞춰 고정 9개 prompt를 구체화한다. 일반 문구만 복제하지 않는다.
5. `DELIVERY-REPORT.md`를 asset template의 순서로 작성한다.
6. validator를 실행한다. 실패하면 `terminalState=partial`이고 완료를 선언하지 않는다.
7. 검증 직후 파일시스템을 다시 읽어 `실제 디렉터리 구조`를 갱신하고 validator를 재실행한다.

## 9. DELIVERY-REPORT 출력 계약

`assets/DELIVERY-REPORT.md`를 사용한다. 결과 보고는 최소 다음 순서를 가진다.

1. 결과와 현재 gate
2. 사실·가정·미확인
3. 핵심 결정과 중단선
4. 검증
5. `## 실제 디렉터리 구조`
6. 재진입 경로
7. 다음 gate
8. 유보·승인 필요

디렉터리 구조는 계획이나 예시를 복사하지 않는다. 검증 직후 실제 package root를 순회해 모든 파일 leaf를 포함한다. 보고 tree leaf set과 실제 file set이 다르면 validator가 실패하며 완료를 선언할 수 없다.

역할 prompt와 DELIVERY-REPORT의 계약 구조는 Markdown heading과 fenced text block으로만 쓴다. raw HTML block은 렌더링상 구조를 숨겨 검증을 우회할 수 있으므로 금지한다.

최종 사용자 응답에도 package 경로, profile·gate·terminal 상태, 검증 결과와 실제 디렉터리 구조를 포함한다. 사용자가 앞선 commentary를 읽어야 이해되는 요약으로 대체하지 않는다.

## 10. 검증 명령

```bash
python3 skills/service-planning/scripts/validate-project-context.py <package-root>
python3 skills/service-planning/scripts/validate-project-context.py --legacy-modernization <package-root>
```

첫 명령은 최소 package, 9개 prompt schema·route, DELIVERY-REPORT의 실제 tree exact match를 검사한다. 두 번째는 capability/process/discovery 선행 산출물까지 요구한다.
