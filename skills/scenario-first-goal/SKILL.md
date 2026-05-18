---
name: scenario-first-goal
description: 시나리오-First 개발 3단계. spec + 누적 GWT 시나리오 전체를 게이트로 두고 goal-directed agentic loop을 실행한다. 1차 게이트는 GWT의 E2E 자동 변환(Playwright 등), 2차 fallback은 LLM judge, manual은 4단계로 분리. max iterations / cost budget / stuck detection으로 thrashing 방지. 게이트 = 이번 시나리오 + 모든 누적 시나리오 통과.
---

# scenario-first-goal

## 목적

`scenario-first-spec`이 만든 spec을 코드로 구현하되, **목표는 "GWT 시나리오 통과"** 이며 통과는 자동으로 측정한다. 사용자가 "맞나?" 물어볼 일 없이 게이트로 정답을 정의.

원리:
- 게이트 = **이번 시나리오 + 누적된 모든 이전 시나리오** 통과 (regression이 이 조건에 흡수)
- 1차: GWT → E2E 자동 변환 (Playwright/Cucumber/Pytest 등)
- Fallback: 자동 변환 불가 케이스만 LLM judge
- Manual은 3단계 게이트에 두지 않음 (4단계의 일 — `scenario-first-review`)

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-goal <NNN>` | spec NNN 기반 goal loop 실행 |
| `/scenario-first-goal --dry-run <NNN>` | E2E 변환·계획만 출력, 구현 안 함 |
| `/scenario-first-goal --resume <NNN>` | 마지막 stuck 지점에서 재개 |

자동 트리거 금지 — 비용 큼.

## 사전 점검

```bash
test -d .scenarios/specs/NNN              # spec 존재
test -f .scenarios/expanded/NNN-*.md      # GWT 시나리오 존재
ls .scenarios/expanded/                   # 누적 시나리오 목록
```

E2E 프레임워크 감지:
```bash
test -f package.json && grep -E "(playwright|cypress|cucumber)" package.json
test -f pytest.ini && grep -E "(pytest-bdd|behave)" *.ini *.toml 2>/dev/null
```

없으면 사용자에게 1회 묻기 ("E2E 프레임워크 없음 — Playwright 자동 설치할까요?")

## Workflow

### 1. GWT → E2E 자동 변환

`.scenarios/expanded/NNN-*.md`의 GWT 시나리오를 프로젝트 E2E 프레임워크의 테스트 파일로 변환.

#### 변환 매핑
| Gherkin | 변환 대상 |
|---|---|
| `Scenario:` | `test(...)` / `it(...)` / `def test_...` |
| `Given` | `beforeEach` / `fixture` / setup |
| `When` | 액션 호출 (page.click 등) |
| `Then` | assertion |

**누적 시나리오 포함**: NNN뿐 아니라 `.scenarios/expanded/*`의 모든 GWT를 함께 테스트 생성. 이게 regression 게이트.

저장: `tests/e2e/scenario-NNN/`.

#### 자동 변환 불가 케이스

LLM judge fallback 대상으로 마킹 (`@llm-judge` 태그 또는 별도 디렉토리):
- 시각적 검증 ("디자인이 좋아 보인다" 류)
- 주관적 품질
- 매우 복잡한 상태 검증

### 2. 초기 구현 (Claude)

spec의 PRD + ARCH + NONFUNC + OPS를 읽고 구현 1차 시도:
- ARCH의 결정 lock 표 준수
- walking skeleton 순서대로
- 가장 작은 단위 commit (각 walking skeleton = 1 commit)

### 3. 게이트 실행

```bash
<프로젝트 e2e 실행 명령> tests/e2e/
```

결과 분석:
- 전체 PASS → 6번 (성공)
- 일부 FAIL → 4번 (반복 루프)
- 변환 불가 케이스 → 5번 (LLM judge)

### 4. 반복 루프 (실패 진단 + 수정)

failure 출력 분석:
- assertion 실패 → 구현 수정
- timeout → 구현 또는 시나리오의 When 액션 검토
- setup 실패 → Given 검토

수정 후 게이트 재실행. **commit은 매 반복마다** (`fix: scenario-NNN.x.y assertion`).

#### Stuck detection
- 같은 시나리오 ID가 M회 연속 실패 (기본 M=3) → 4단계 escalate
- 누적 iteration N회 초과 (기본 N=10) → escalate
- Cost budget 초과 (기본 1회 실행당 $5, 환경변수 `SCENARIO_GOAL_BUDGET`) → escalate

Escalate 시: `.scenarios/specs/NNN/STUCK.md`에 진단 기록 후 사용자에게 보고.

### 5. LLM judge fallback (선택)

자동 변환 불가 시나리오에 한해:
- Claude가 결과물(스크린샷·HTML·DOM·로그)을 보고 GWT의 Then을 판정
- 판정 기준은 시나리오의 Then을 그대로 사용 — 새 기준 만들지 않음
- 결과: PASS / FAIL / UNCERTAIN
- UNCERTAIN은 4단계 escalate

### 6. 성공 결과 기록

`.scenarios/specs/NNN/GOAL.md` 생성:
```markdown
# Goal 실행 결과

- 시나리오 NNN: PASS
- 누적 시나리오: <목록> 모두 PASS
- iteration 수: N
- 비용 추정: $X
- commit 범위: <hash range>
- E2E 변환 위치: tests/e2e/scenario-NNN/

## LLM judge 사용 시나리오
<목록 + 판정 근거 인용>
```

expanded frontmatter 갱신:
```
goal_status: passed
goal_at: <ISO8601>
```

### 7. 응답

성공:
```
✓ goal/NNN  PASS (누적 K개 모두 통과, iteration N회)
Next: /scenario-first-review NNN  (본인 직접 사용)
```

Escalate:
```
⚠ goal/NNN  STUCK at scenario-NNN.x.y (M회 연속 실패)
진단: .scenarios/specs/NNN/STUCK.md
Next: /scenario-first-review NNN --triage
```

## 산출

- `tests/e2e/scenario-NNN/` (자동 생성된 E2E)
- `.scenarios/specs/NNN/GOAL.md` 또는 `STUCK.md`
- commit history (각 walking skeleton 단위)
- 갱신된 expanded frontmatter

## 다음 단계

- `scenario-first-review` — 본인 직접 사용 + 5 Whys 라우팅

## 금지 사항

- 누적 시나리오 빼고 NNN만 게이트화 (regression 누락)
- Manual 테스트를 게이트에 끼우기 (4단계의 일)
- Stuck detection 비활성화 (thrashing 위험)
- Cost budget 무한 (`SCENARIO_GOAL_BUDGET=0` 등) — 명시 동의 없이 금지
- LLM judge로 자동 변환 가능 케이스 처리 (LLM 의존도 증가)
- `--no-verify`, `git push --force` 등 안전장치 우회
- 시나리오 임의 수정 — 게이트가 정답이므로 시나리오를 못 통과한다고 시나리오를 깎으면 안 됨 (4단계에서 사용자가 결정)
