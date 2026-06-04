---
name: service-planning
description: 떠오른 아이디어 씨앗(핵심 기능 1개·핵심 시나리오 1개·화면 1개)을 완전한 서비스 기획서로 구체화한다. 검증(될까?)이 아니라 완성(구체화) — 씨앗이 가정하는 주변(여정·화면 상태·대안/예외 플로우·스캐폴딩·엣지·NFR)에서 빠진 부분을 결정성 rubric으로 찾아 채운다. '서비스 기획', '기획해줘', '이거 기획', '아이디어 구체화', '이 기능/화면/시나리오를 서비스로', '빠진 부분 채워', '기획서', 'flesh out this idea', 'service planning' 등에 트리거. 산출물: ~/Documents/service-planning/{날짜-slug}/기획서.md
---

# service-planning — 씨앗 → 완전한 서비스 기획서

아이디어는 보통 **씨앗 하나**(기능/시나리오/화면)로 온다. 이 스킬은 그 씨앗이 *실제 사용자에게 제공할 완전한 서비스*가 되기까지 **빠진 부분을 체계적으로 찾아 구체적 기획으로 채운다.** 검증 도구가 아니라 **구체화/완성 도구.**

작동 철학(사용자 CLAUDE.md 위임모드): 한 턴에 초안+트레이드오프, 확인 구하지 말고 진행, 흔한 처리는 Claude가 정하고(에러=토스트, 빈상태=placeholder+CTA, 로딩=skeleton), 결과 바뀌는 가정만 `[추정:]` 표시. 게이트는 질문지가 아니라 완성된 초안 위에서 사용자가 방향 트는 지점.

---

## A. 시작 전 로드

1. 이 references를 읽는다 (스킬 디렉토리 기준):
   - `references/job-map.md` — Universal Job Map 8단계 (백본)
   - `references/completeness-rubric.md` — 9-카테고리 빈칸 체크리스트 + scope pruning
   - `references/seed-types.md` — 기능/시나리오/화면별 확장법
   - `references/gisaekseo-template.md` — 기획서 10섹션 고정 템플릿
   - `references/frameworks.md` / `references/lock-table.md` — 이론·결정성 (필요시)
2. 주입된 `idea ctx` digest(SessionStart hook)에 같은 주제 과거 메모가 있으면 참고.

---

## B. 티어 선택 (자동 + override)

| 티어 | 신호 | 동작 |
|---|---|---|
| **napkin** | "빠르게 / 뭐 빠졌나만 / 대충" | P0~P3만, Job Map + 빈칸 목록 1쪽. 게이트 1회 |
| **standard** (기본) | 진짜 기획 | P0~P5 풀, 9 rubric, v1 스코프, 기획서 10섹션 |
| **deep** | "제대로 / 여러 화면 / 투자/출시" | standard + 화면별 상태 상세 + (Stage2)에이전트 + 선택 `/self-review` |

자동 추정 후 한 줄로 명시("standard로 진행"), 사용자가 바꾸면 수용.

---

## C. 파이프라인

### P0 — 입력 + 분류
- 씨앗(자유 텍스트)을 받는다. 없으면 "어떤 기능/시나리오/화면이 떠올랐어?" 1회 프롬프트.
- **씨앗 타입** 판정: 기능 / 시나리오 / 화면 (애매하면 더 구체적인 쪽). → `seed-types.md`의 해당 확장법 채택.
- **청중 스코프** 판정: `(a) n=1 개인도구` / `(b) 니치` / `(c) 넓은 사용자`. → `completeness-rubric.md` §pruning으로 끌 카테고리 결정.
- 둘 다 한 줄로 명시 (추정이면 `[추정:]`).

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

### P3 — 빈칸 발견 ★ (게이트 1)
- `completeness-rubric.md` 9 카테고리를 (scope pruning 후) 씨앗에 실행.
- **빈칸을 역산으로 찾는다**: "happy 상태가 성립하려면 무엇이 전제되나 → 없을 땐? 가져오는 중엔? 실패하면?"
- (선택, standard/deep에서 근거 필요시) 비슷한 실제 제품이 이 플로우/상태를 어떻게 처리하는지 **인라인 WebSearch** 1~2회 (Stage 2부터는 `pattern-researcher` 에이전트).
- **빈칸 맵** 초안 출력 (카테고리별, 우선순위·v1여부) →
  **게이트 1**: "이 빈칸들 맞아? 이건 v1에 불필요? 이게 빠졌어?" 사용자 redirect 수용.

### P4 — 빈칸 채우기 (게이트 2 일부)
- 각 빈칸에 **구체적 결정** 초안.
  - 흔한 처리는 바로 정함: UI 상태=Hurff 5(empty엔 CTA, loading엔 skeleton, error엔 메시지+재시도), 에러=토스트.
  - 결과 바뀌는 결정만 `[추정:]`.
- **대안/예외 플로우** 도출 (Cockburn): primary 외 alternate + exception.

### P5 — 스코프 + 기획서 + 검증
- **v1 스코프**: Shape Up appetite로 IN(walking skeleton) / OUT(deferred + 이유). "완성 = 전부 아님."
  → **게이트 2**: 채운 결정 + v1 스코프 사용자 확인.
- `gisaekseo-template.md` 10섹션으로 `기획서.md` 합성.
- **Completeness self-check** (§D) 돌려 §10 채움. (Stage 2부터는 `completeness-critic` 에이전트 spawn)
- 저장 (§E).

---

## D. Completeness self-check (헛소리·누락 방지)

기획서 합성 직후 4개를 직접 점검 (deep 티어는 `completeness-critic` 또는 `/self-review`로 독립 검증):
1. **빈칸 빠짐없나** — 9 카테고리(pruning 후) 각각 다뤘나? 안 다룬 건 §10에 "남은 누락"으로 정직하게.
2. **모든 화면 5상태** — ideal만 그린 화면 없나?
3. **happy 외 경로** — 대안/예외가 핵심 플로우마다 있나?
4. **정직성** — 사용자/데이터 없는데 "검증됨"인 척 안 했나? 모르는 건 §9 Open questions로.
출력: §10에 `남은 누락 N개` + 커버리지 한 줄.

---

## E. 저장

- 디렉토리: `~/Documents/service-planning/{YYYY-MM-DD}-{slug}/`
  - slug는 씨앗에서 1회 제안 후 확정 (kebab-case).
  - 날짜는 `date +%F`로 구한다.
- 파일: `기획서.md` (필수) + `gaps.md` (빈칸 맵 raw + 근거, standard/deep).
- 저장 후 경로 + §4 빈칸 맵 요약 + §7 v1 스코프를 응답에 한 줄씩.

---

## F. 금지 사항

- 씨앗 없이 기획 임의 합성 (사용자 입력 없이 추측 금지)
- 검증(시장/PMF) 프로세스로 변질 — 이건 구체화 도구. 불확실은 §9에 가벼운 플래그만.
- scope pruning 무시하고 개인용 n=1 도구에 auth/결제/온보딩 빈칸 강요
- 모르는 걸 채워 넣기 — Open questions로 (Example Mapping Questions 규칙)
- ideas 레포 `sources/*.md` 직접 쓰기 / `idea synth` 자동 호출
- wiki에 기획서 저장 (운영 산출물 — `~/Documents/`에만)
