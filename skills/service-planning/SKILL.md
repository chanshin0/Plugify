---
name: service-planning
description: >-
  떠오른 아이디어 씨앗(핵심 기능 1개·핵심 시나리오 1개·화면 1개)을 완전한 서비스 기획서로 구체화한다. 검증(될까?)이 아니라 완성(구체화) — 씨앗이 가정하는 주변(여정·화면 상태·대안/예외 플로우·스캐폴딩·엣지·NFR)에서 빠진 부분을 결정성 rubric으로 찾아 채운다. 장기·복합·레거시 현대화 프로젝트에서는 재진입 문맥·고정 역할 프롬프트·실제 디렉터리 보고까지 조건부로 만든다. '서비스 기획', '기획해줘', '이거 기획', '아이디어 구체화', '이 기능/화면/시나리오를 서비스로', '빠진 부분 채워', '기획서', 'flesh out this idea', 'service planning' 등에 트리거. 기본 산출물은 ~/Documents/service-planning/{날짜-slug}/기획서.md이며 persistent-context profile은 사용자 지정 경로나 저장소 planning anchor를 우선한다.
---

# service-planning — 씨앗 → 완전한 서비스 기획서

아이디어는 보통 **씨앗 하나**(기능/시나리오/화면)로 온다. 이 스킬은 그 씨앗이 *실제 사용자에게 제공할 완전한 서비스*가 되기까지 **빠진 부분을 체계적으로 찾아 구체적 기획으로 채운다.** 검증 도구가 아니라 **구체화/완성 도구.**

작동 철학: 한 턴에 초안+트레이드오프를 만들고, 흔한 처리는 에이전트가 정한다(에러=토스트, 빈상태=placeholder+CTA, 로딩=skeleton). 조사 가능한 빈칸은 조사하고, 저위험 기본값은 `[가정:]`으로 기록해 진행한다. 사람만 아는 의도·우선순위가 결과를 크게 바꿀 때만 `task-orchestrating` 인터뷰 형식으로 1~3개 질문한다. 사용자는 routine 기획 체크리스트의 승인자가 아니다.

**실행 구조 — 메인 컨텍스트 신선도가 1순위 (가장 중요):** 메인 세션은 *오케스트레이터*다 — 진행·조율·인터뷰·승인 경계·검증 요약만 들고 컨텍스트를 가볍게 유지한다. **무거운 단발 생성·리서치**(긴 `기획서.md`/`gaps.md` 합성, 패턴 리서치, completeness 검증, 와이어프레임, 데이터모델)는 *격리된 단일 서브에이전트*에 위임하고 **결과 요약만** 받는다 — 긴 텍스트를 메인 컨텍스트에 직접 쌓지 않는다. 단 **사용자와의 인터뷰·실제 승인 경계·redirect 반영은 메인이 직접** 한다(서브에이전트는 사용자와 대화 못 함). 위임은 *산출물 1개당 단일 에이전트*(함대 금지는 이 신선도 원칙의 부산물). 위임 결과는 메인이 grep 등으로 가볍게 검증하고 보고-실제 차이를 정직하게 surface.

---

## A. 시작 전 로드

1. 이 references를 읽는다 (스킬 디렉토리 기준):
   - `references/job-map.md` — Universal Job Map 8단계 (백본)
   - `references/completeness-rubric.md` — 9-카테고리 빈칸 체크리스트 + scope pruning
   - `references/seed-types.md` — 기능/시나리오/화면별 확장법
   - `references/gisaekseo-template.md` — 기획서 10섹션 고정 템플릿
   - `references/frameworks.md` / `references/lock-table.md` — 이론·결정성 (필요시)
   - `references/project-context-package.md` — 장기 재사용·handoff·역할별 프롬프트가 필요한 persistent-context 또는 legacy modernization profile일 때만 전문을 읽는다.
2. 주입된 `idea ctx` digest(SessionStart hook)에 같은 주제 과거 메모가 있으면 참고.

---

## B. 티어 선택 (자동 + override)

| 티어 | 신호 | 동작 |
|---|---|---|
| **napkin** | "빠르게 / 뭐 빠졌나만 / 대충" | P0~P3만, Job Map + 빈칸 목록 1쪽. 필요할 때만 human-context 인터뷰 |
| **standard** (기본) | 진짜 기획 | P0~P5 풀, 9 rubric, v1 스코프, 기획서 10섹션 |
| **deep** | "제대로 / 여러 화면 / 투자/출시" | standard + 화면별 상태 상세 + (Stage2)에이전트 + P6 와이어프레임 + P7 데이터모델 + 선택 `/self-review` |

P6(와이어프레임)·P7(데이터모델)은 deep 기본, standard에선 사용자가 "와이어프레임 그려줘" / "데이터 모델·스키마 짜줘" 요청 시 on-demand. 둘은 서로 독립(하나만 해도 됨).

**Persistent-context profile (티어와 독립):** 사용자가 프로젝트 문맥 환경·재진입·handoff·역할별 서브에이전트 프롬프트·전체 디렉터리 구조를 요구하거나, 기존 서비스/ERP/내부 포털/데이터의 현대화·AX 전환이면 켠다. 그 밖에는 독립 workstream 2개 이상이 여러 세션에서 이어질 때만 켠다. `deep`, 다중 화면, 일회성 서브에이전트 호출만으로는 켜지 않는다. 활성 이유와 `legacy-modernization` 여부를 한 줄로 명시한다.

자동 추정 후 한 줄로 명시("standard로 진행"), 사용자가 바꾸면 수용.

---

## C. 파이프라인

### P0 — 입력 + 분류
- 씨앗(자유 텍스트)을 받는다. 없으면 "어떤 기능/시나리오/화면이 떠올랐어?" 1회 프롬프트.
- **씨앗 타입** 판정: 기능 / 시나리오 / 화면 (애매하면 더 구체적인 쪽). → `seed-types.md`의 해당 확장법 채택.
- **청중 스코프** 판정: `(a) n=1 개인도구` / `(b) 니치` / `(c) 넓은 사용자`. → `completeness-rubric.md` §pruning으로 끌 카테고리 결정.
- 둘 다 한 줄로 명시 (추정이면 `[추정:]`).

### P0b — 지속 문맥 골격과 legacy discovery gate (profile 전용)
- `references/project-context-package.md`를 전문 로드하고 package root를 정한다. 기존 repo의 planning anchor·정본 소유권·사용자 변경을 우선한다.
- 최소 package 골격과 evidence/decision 상태를 먼저 잡는다. 원문 조사 run과 정본 package를 섞지 않는다.
- `legacy-modernization`이면 capability(무엇)→실제 process/workflow(어떻게)→walking slice→domain(권위 이전 단위) 순서를 고정한다. 정적 source는 존재 단서일 뿐 실제 사용·owner·writer·정본 증거가 아니다.
- 첫 workflow/domain·owner·writer/invariant가 미확인이면 architecture·물리 data model·제품·cutover는 `proposed/HOLD`만 허용한다.

### P1 — 씨앗 정착 (anchor)
- 타입에 맞게 정밀화:
  - 시나리오 → **Job Story** `When <상황>, I want to <동기>, so I can <결과>` + trigger + outcome.
  - 기능 → "누가 / 무엇을 / 왜" + Job 전환.
  - 화면 → "무엇을 보여주고 / 무엇을 위한 / 어디서 진입".
- A4 test: 한 단락에 안 맑게 들어가면 더 좁힌다.

### P2 — 백본 매핑
- `job-map.md` 8단계를 씨앗에 돌려 전체 여정을 그린다. **씨앗 위치 ★ 표시** (보통 Execute).
- 씨앗 앞(Define~Prepare)과 뒤(Monitor~Conclude)를 채운다. before/during/after 한 줄 서사.
- 비어있고 *필요한* 단계 → 빈칸 후보로 메모. 불필요하면 "(N/A: 이유)".

### P3 — 빈칸 발견 + 필요한 인터뷰
- `completeness-rubric.md` 9 카테고리를 (scope pruning 후) 씨앗에 실행.
- **빈칸을 역산으로 찾는다**: "happy 상태가 성립하려면 무엇이 전제되나 → 없을 땐? 가져오는 중엔? 실패하면?"
- **패턴 근거 (티어 기준 — "Stage 2부터" 대체)**: napkin=생략 / standard=빈칸 5개↑면 `pattern-researcher` 위임, 아니면 인라인 WebSearch 1~2회 / deep=항상 `pattern-researcher` 위임. (비슷한 실제 제품이 이 플로우/상태/엣지를 어떻게 처리하는지 cited 패턴 — 메인 컨텍스트 안 더럽히게 위임.)
- 빈칸을 `discoverable / assumable / human-context / approval`로 분류한다. discoverable은 패턴·정본 조사로 채우고, assumable은 영향과 뒤집을 조건을 적어 진행한다.
- `human-context` 중 답에 따라 핵심 여정·대상 사용자·v1 범위가 크게 달라지는 항목만 메인이 1~3개 집중 인터뷰한다. 현재 이해·확인 사실·권장안·대안 차이·영향 섹션을 먼저 보여주고 구체 질문한다. 그 외에는 멈추지 않는다.
- 인터뷰가 필요 없으면 빈칸 맵을 `resolved-gaps.md`로 바로 내리고 P4~P5로 간다. 필요하면 `terminalState=pending-human-context`로 두되 독립 조사·골격 작업은 계속한다. 답을 받으면 `질문→답→결정→영향 섹션`을 기록하고 추가 진행 승인 없이 재개한다.

### P4~P5 — 채우기 + 스코프 + 기획서 합성 (plan-writer 위임 ★)
파이프라인에서 **가장 무거운 단일 쓰기** — 메인에서 직접 쓰지 않고 위임해 컨텍스트를 신선하게 유지한다.
- 필요한 인터뷰가 해결된 뒤 **`plan-writer` 전용 에이전트를 스폰** (Agent `subagent_type: plan-writer`, 정의 `agents/plan-writer.md`). 한 번에 합성: ① 해결된 빈칸별 결정(흔한 처리=Hurff 5/토스트 등 결정성, 저위험은 `[가정]`)·대안/예외(Cockburn) ② v1 스코프(IN walking skeleton / OUT+이유) ③ `gisaekseo-template.md` 10섹션 `기획서.md`·`gaps.md`. **프롬프트엔 입력만**: 씨앗·백본맵·`resolved-gaps.md` 경로·패턴 근거·티어·산출 경로. 메인엔 요약만 회신.
- persistent-context profile이면 package root·profile·현재 gate·evidence/decision 상태·workstream map도 입력한다. plan-writer는 우선 `기획서.md`·`gaps.md`를 합성하고 P8 package builder가 재진입 문맥을 정착할 수 있게 정본 경계를 명시한다.
- **단일 에이전트 — 함대 금지.** fallback: `plan-writer` subagent_type 미등록 시 general-purpose로 스폰하되 `agents/plan-writer.md`를 읽혀 따르게.
- plan-writer가 돌려준 §5 결정 + §7 v1 스코프 요약을 메인이 진행 업데이트로 제시한다. 새 `human-context`가 발견되지 않았다면 답을 기다리지 않고 completeness 검증으로 간다. 사용자가 redirect하면 영향 섹션만 갱신한다.
- napkin·짧은 세션은 인-스레드 합성 허용(위임 생략 가능).

### P5b — 검증 + 저장
- **Completeness 검증 (티어 기준 — "Stage 2부터" 대체)**: napkin=메인 self-check(§D 4항목) / standard·deep=`completeness-critic` 에이전트 spawn(독립 적대 검증). critic 에는 씨앗·청중/pruning·완성 기획서만 주고 plan-writer 보고·결정 rationale·기존 self-check는 주지 않는다(블라인드 누락 검토). 결과로 §10 갱신.
- **(옵션) 외부 모델 교차 누락검토**: deep 티어이거나 누락 비용이 큰 기획이면, `completeness-critic`(Claude) 검증 후 다른 모델 family(Codex/Gemini)에게도 누락 검토를 받아 교차한다(같은 family 맹점 보완 — `/self-review` R3 철학). 외부 호출은 비용·시간 승인 경계이므로 원 요청에 이미 포함됐으면 반복 확인 없이 실행하고, 포함되지 않았을 때만 사용자에게 한 번 승인받는다(기본 off). 예: `codex exec -c model='gpt-5.6-sol' -c model_reasoning_effort='xhigh' "기획서.md 의 9-카테고리(여정·역할·화면·UI상태·대안예외·스캐폴딩·엣지·NFR·Open) 누락을 적대적으로 지적"`. 발견을 critic 결과와 종합해 §10 갱신.
- 메인이 grep 등으로 산출물 가볍게 확인 — 보고-실제 차이 정직하게 surface.
- 저장 (§E).
- 필요한 인터뷰 해결 + completeness 검증 + 실제 파일 확인이 끝나야 `terminalState=planned`다. 남은 누락이 조사 가능하면 에이전트가 채우고, 사람만 아는 load-bearing 맥락이면 `pending-human-context`로 되돌린다. 복합 점수로 완료를 대신하지 않는다.
- persistent-context profile의 최종 `terminalState=planned`는 P8 package validator까지 통과해야 한다. P5b의 기획서 합격만으로 전체 package 완료를 선언하지 않는다.

### P6 — 와이어프레임 (선택 산출물)
- **트리거**: deep 티어 기본 / 사용자가 "와이어프레임·화면 그려줘" 요청 시(standard에서도 on-demand). 기획서(P5)가 완성된 뒤에만.
- **전용 에이전트를 스폰한다** — Agent 도구 `subagent_type: wireframe-builder` (정의: `agents/wireframe-builder.md`). 에이전트가 명세(lo-fi 규칙·구조·self-contained·anti-pattern)를 이미 들고 있으므로 **프롬프트엔 입력만 전달**: ① `기획서.md` 절대경로 ② 그릴 화면 목록(없으면 "§6에서 도출하라") ③ `wireframes.html` 산출 절대경로. → general-purpose에 긴 명세를 다시 박지 말 것.
- **단일 에이전트 1개 — 함대 금지**. 화면이 여러 개여도 *한 에이전트*가 만든다(lo-fi 스타일·화면 간 네비·이벤트 핀의 일관성이 한 컨텍스트에서 나와야 함).
- **fallback**: 실행 환경에 `wireframe-builder` subagent_type이 아직 없으면(에이전트 등록 전), general-purpose로 스폰하되 `agents/wireframe-builder.md`를 읽혀 그 명세를 따르게 한다.
- **검증(정직성)**: 생성 후 오케스트레이터가 직접 grep으로 외부 의존성 0·화면 수·상태·핀을 확인. 에이전트 보고와 실제가 다르면 정직하게 사용자에게 차이 보고(추정으로 통과시키지 않음).

### P7 — 데이터 모델 (선택 산출물)
- **트리거**: deep 티어 기본 / 사용자가 "데이터 모델·스키마·DB 짜줘" 요청 시. 기획서(P5)가 완성된 뒤에만. P6와 독립. 단 `legacy-modernization`에서는 선택 workflow/domain·owner·writer/invariant discovery gate가 열려 있으면 물리 모델을 만들지 않고 논리 모델 gap/질문만 남긴다.
- **전용 에이전트를 스폰한다** — Agent 도구 `subagent_type: data-model-builder` (정의: `agents/data-model-builder.md`). 명세를 에이전트가 들고 있으므로 **프롬프트엔 입력만 전달**: ① `기획서.md` 절대경로 ② 엔티티 힌트(없으면 "§6·부록에서 도출하라") ③ `data-model.md` 산출 절대경로. → general-purpose에 긴 명세를 다시 박지 말 것.
- **단일 에이전트 1개 — 함대 금지**. 엔티티가 많아도 한 에이전트(관계·정규화·인덱스·집계의 일관성이 한 컨텍스트에서 나와야 함).
- **fallback**: 환경에 `data-model-builder` subagent_type이 아직 없으면 general-purpose로 스폰하되 `agents/data-model-builder.md`를 읽혀 그 명세를 따르게 한다.
- **검증(정직성)**: 생성 후 오케스트레이터가 grep으로 엔티티 수·ERD·DDL·집계·상태전이·v1 OUT을 확인. 특히 **§7 OUT 항목이 스키마로 새어들지 않았나**(YAGNI 위반)·기획서에 없는 엔티티 발명 안 했나를 점검. 보고와 실제가 다르면 정직하게 차이 보고.

> **P6·P7 병렬 실행**: 둘 다 진행할 때(deep 티어 등)는 `wireframe-builder` 와 `data-model-builder` 를 **병렬로 spawn**한다 — 둘 다 `기획서.md` 만 읽고 서로 의존이 0인 **독립 산출물**이라 "함대 금지"(산출물 1개당 1에이전트)에 위배되지 않는다. 순차로 기다리지 말 것(wall-clock 절감).

### P8 — 지속형 프로젝트 문맥 패키지 (profile 전용)
- 기획서·gaps와 필요한 선택 산출물이 정착된 뒤 `context-package-builder` 전용 에이전트를 스폰한다(정의: `agents/context-package-builder.md`). package 전체를 하나의 compound artifact로 소유하는 단일 에이전트다.
- **프롬프트엔 입력만** 전달한다: package root, profile, 기획서/gaps 경로, 현재 gate, evidence/decision 상태, workstream map, 기존 정본 경계. fallback은 general-purpose에 agent 정의와 reference 전문을 읽혀 따른다.
- builder는 `README.md`, `STATUS.md`, `DELIVERY-REPORT.md`와 정확한 9개 `prompts/*.md`를 만든다. legacy profile이면 capability map·process catalog·discovery guide도 요구한다. 역할이 아직 gate 전이어도 prompt 파일을 삭제하지 않고 stop condition을 기록한다.
- 메인이 `scripts/validate-project-context.py`를 직접 실행한다. 그 뒤 `completeness-critic`에 package root·profile·현재 gate만 주어 evidence 과장, discovery-before-architecture, prompt 실행 가능성, 실제 tree 일치를 블라인드 검토시킨다.
- validator 실패 또는 critic BLOCKER가 남으면 `terminalState=partial`. 수정과 리뷰가 끝난 뒤 실제 filesystem에서 `DELIVERY-REPORT.md`의 tree를 다시 생성하고 **validator를 재실행**한다. 이 최종 재검증을 통과하지 않았거나 계획 tree와 실제 tree가 다르면 완료 선언을 금지한다.

---

## D. Completeness self-check (헛소리·누락 방지)

기획서 합성 직후 4개를 직접 점검 (deep 티어는 `completeness-critic` 또는 `/self-review`로 독립 검증):
1. **빈칸 빠짐없나** — 9 카테고리(pruning 후) 각각 다뤘나? 안 다룬 건 §10에 "남은 누락"으로 정직하게.
2. **모든 화면 5상태** — ideal만 그린 화면 없나?
3. **happy 외 경로** — 대안/예외가 핵심 플로우마다 있나?
4. **정직성** — 사용자/데이터 없는데 "검증됨"인 척 안 했나? 모르는 건 §9 Open questions로.
출력: §10에 `남은 누락 N개` + 커버리지 한 줄.

persistent-context profile은 위 4개에 더해 ⑤ 9개 역할 prompt 실재·공통 8절·전체 route ⑥ legacy discovery gate ⑦ `DELIVERY-REPORT.md` tree와 실제 file set exact match를 검사한다.

---

## E. 저장

- 기본 디렉토리: `~/Documents/service-planning/{YYYY-MM-DD}-{slug}/`
  - slug는 씨앗에서 에이전트가 결정한다(kebab-case). 충돌이 있을 때만 바꾼다.
  - 날짜는 `date +%F`로 구한다.
- persistent-context profile은 기본 디렉토리보다 사용자가 지정한 package root를 먼저, 그다음 저장소의 문서화된 planning anchor를 우선한다. 둘 다 없을 때만 위 기본 디렉토리를 쓴다.
- 파일: `기획서.md` (필수) + `gaps.md` (빈칸 맵 raw + 근거, standard/deep) + `wireframes.html` (P6 실행 시) + `data-model.md` (P7 실행 시).
- persistent-context profile은 reference의 package 구조와 `DELIVERY-REPORT.md`가 추가로 필수다.
- 저장 후 경로 + §4 빈칸 맵 요약 + §7 v1 스코프를 응답에 한 줄씩. profile이면 profile/gate/terminal 상태, validator 결과, **검증 직후 실제 디렉터리 구조**도 반드시 포함한다.

---

## F. 금지 사항

- 씨앗 없이 기획 임의 합성 (사용자 입력 없이 추측 금지)
- 검증(시장/PMF) 프로세스로 변질 — 이건 구체화 도구. 불확실은 §9에 가벼운 플래그만.
- scope pruning 무시하고 개인용 n=1 도구에 auth/결제/온보딩 빈칸 강요
- 모르는 걸 채워 넣기 — Open questions로 (Example Mapping Questions 규칙)
- ideas 레포 `sources/*.md` 직접 쓰기 / `idea synth` 자동 호출
- 일반 profile의 기획서를 wiki에 저장하거나 `~/Documents/` 밖에 임의 정본화. 단 persistent-context profile은 사용자 지정 package root 또는 저장소 planning anchor가 정본이며 이 금지의 예외다.
- persistent-context profile인데 `DELIVERY-REPORT.md`·고정 9개 prompt·실제 filesystem tree 없이 package 완료 보고
- 메뉴·route·schema·정적 source 존재를 실제 사용·owner·writer·운영 활성으로 승격
- legacy discovery gate 전에 architecture·물리 data model·vendor·cutover를 accepted로 확정
- **에이전트 함대화** — P6 와이어프레임을 화면당, P7 데이터모델을 엔티티당 에이전트로 쪼개거나, 목적에 불필요한 에이전트를 다수 스폰. 산출물 1개당 단일 에이전트만(lean).
