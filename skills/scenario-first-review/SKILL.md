---
name: scenario-first-review
description: 시나리오-First 개발 4단계. 본인이 직접 빌드 결과를 사용해 Job Story 체크리스트 + 6범주 평가 + evidence 첨부. `.harness/templates/REVIEW.md` 를 `scenarios/specs/NNN/REVIEW.md` 로 복사해 채움. 통과 시 누적 게이트 풀에 NNN 추가 + 다음 backbone, 실패 시 5 Whys로 (1) 시나리오 / (2) Spec / (3) 구현 라우팅 (같은 NNN). 시스템 생사를 가르는 단계 — 건너뛰면 자동 MVP 함정으로 회귀.
---

# scenario-first-review

## 목적

3단계까지 자동으로 통과해도 **본인이 실제 쓰는지**는 다른 문제. "주기적 자동 MVP" 함정(가짜 검증)을 막는 마지막 게이트.

원리:
- 체크리스트는 Job Story의 `so I can ...` + walking skeleton 한 줄 (스스로 작성한 것)
- 6범주 평가 (`.harness/templates/REVIEW.md` 양식)
- **evidence 최소 2개 첨부** 없으면 passed 표시 금지 (룰: passing_requires_evidence)
- 사용자가 매 cycle 4단계를 **실제 돌릴 의지**가 시스템 생사
- 실패 라우팅은 5 Whys로 3분류 (시나리오/spec/구현). 직감 라우팅 금지.

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-review <NNN>` | spec NNN 결과물에 대한 체크리스트 + 6범주 + 5 Whys |
| `/scenario-first-review <NNN> --triage` | 3단계 STUCK 상태에서 직접 5 Whys (사용 단계 스킵) |
| `/scenario-first-review <NNN> --skip-use` | 체크리스트만 (이미 사용해본 경우) |

자동 트리거 금지.

## 사전 점검

```bash
# 1. 하네스 깔렸나
test -d .harness && test -d scenarios || {
  echo "ERROR: /scenario-first-init 먼저"
  exit 1
}

# 2. 입력 존재 (--triage 모드면 STUCK.md, 일반은 GOAL.md)
if [[ "$MODE" == "triage" ]]; then
  test -f scenarios/specs/NNN/STUCK.md || { echo "ERROR: STUCK.md 없음"; exit 1; }
else
  test -f scenarios/specs/NNN/GOAL.md || {
    echo "ERROR: GOAL.md 없음 — /scenario-first-goal <NNN> 먼저 (또는 --triage)"
    exit 1
  }
fi

# 3. expanded 존재
test -f scenarios/expanded/NNN-*.md || { echo "ERROR: expanded 없음"; exit 1; }

# 4. REVIEW 템플릿 존재
test -f .harness/templates/REVIEW.md || {
  echo "ERROR: .harness/templates/REVIEW.md 없음 — /scenario-first-init 다시"
  exit 1
}
```

## Workflow

### 1. REVIEW.md 템플릿 복사

```bash
cp .harness/templates/REVIEW.md scenarios/specs/NNN/REVIEW.md
```

placeholder 치환:
- `NNN` → 실제 NNN
- `<Job Story 한 줄>` → `scenarios/throws/NNN-*.md` 의 Job Story 한 줄

### 2. 체크리스트 채우기 (Claude 초안)

`scenarios/throws/NNN-*.md` 의 `so I can ...` + `scenarios/expanded/NNN-*.md` 의 walking skeleton 항목들로 `## 1. 사용 체크리스트` 섹션 자동 채움.

### 3. 사용자에게 안내 (WAITING_ON_USER 표기)

```bash
# STATUS.md WAITING_ON_USER 갱신
sed -i.bak -E "s|^WAITING_ON_USER:.*|WAITING_ON_USER: review NNN since $(date -Iseconds)|" .harness/STATUS.md && rm .harness/STATUS.md.bak
```

응답:
```
✓ 체크리스트 + 6범주 평가표 준비 완료.
   scenarios/specs/NNN/REVIEW.md

지금 직접 빌드 결과를 사용해보세요:
<spec OPS.md의 '사용 명령' 인용 또는 ./init.sh start>

체크 후 다음 중 하나로 답:
- "전부 통과" → 6범주 점수 + evidence 첨부 진행
- "X.Y 실패 — <증상>" → 5 Whys 진단 시작
- "잠깐 — <수정 요청>" → 수정 요청 받아 분기
```

**Claude는 여기서 멈춘다.** 사용자가 돌아올 때까지 대기.

`--skip-use` 또는 `--triage` 모드면 곧바로 6번으로.

### 4. 사용자 응답 처리

#### Case A: 전부 통과

- 6범주 점수 (0~2) 입력 받기 — 합계 ≥10 이어야 Accept
- **evidence 최소 2개** 입력 받기 (스크린샷 경로 / GOAL.md 인용 / commit range / 사용 narrative 등). 미충족 시 passed 표시 금지 — rules.json `passing_requires_evidence` 위반
- REVIEW.md `## 6. 결과` 갱신:
  ```yaml
  review_status: passed
  routed_to: (none)
  reviewed_at: <ISO8601>
  total_score: <합계>/12
  evidence_count: <첨부 개수>
  ```
- 7번 (passed 처리)

#### Case B: 일부 실패
- 실패 항목 + 증상 받기
- 5번 (5 Whys)

#### Case C: 수정 요청
- 사용자가 시나리오 수정 의향이면 1단계 (throw 갱신 — 같은 NNN)
- 사용자가 spec 수정 의향이면 2단계 (expand) 또는 3단계 (spec)
- 모호하면 5번 (5 Whys)

### 5. 5 Whys 진단 (Claude 초안, 본인 최종 결정)

실패 증상에서 시작해 5번 "왜?":

```
[증상] 검색 결과가 0건일 때 placeholder 안 보임

[왜 1] 컴포넌트가 0건 분기 안 함
[왜 2] Then 시나리오에 placeholder 명시 없음
[왜 3] Example Mapping의 Question을 "추천 보여주기"로만 해소
[왜 4] 실제로는 placeholder 원했는데 인터뷰에서 명확하지 않았음
[왜 5] 메타 인터뷰에서 "0건일 때 어떻게?" 선택지를 한정해서 보여줌
```

5번째 또는 **결정 가능한 지점**에서 stop.

### 6. 라우팅 결정 (3분류 — 룰 3.5)

5 Whys 결과를 3분류 중 하나로:

| 라우팅 | 조건 | 다음 단계 (같은 NNN — 룰 3.5) |
|---|---|---|
| **(1) 시나리오 오류** | Job Story·Example·GWT 표현이 본인 의도와 다름 | `/scenario-first-throw --update NNN` 또는 `/scenario-first-expand --rerun NNN` |
| **(2) Spec 누락** | 시나리오는 OK인데 spec에 빠진 슬롯 | `/scenario-first-spec --rerun NNN` |
| **(3) 구현 오류** | 시나리오·spec OK인데 구현이 어긋남 | `/scenario-first-goal --resume NNN` |

Claude가 초안을 제시하고 **사용자가 최종 결정**. 사용자가 거부하면 5 Whys 재시작.

### 7. 결과 처리

#### 7a. passed 처리

`scenarios/expanded/NNN-*.md` frontmatter:
```
review_status: passed
review_at: <ISO8601>
```

`.harness/STATUS.md` 갱신 (룰 3.3):
- `IN_PROGRESS:` → `(none)` 해제
- `WAITING_ON_USER:` → `(none)` 해제
- "## 누적 게이트 풀" 섹션에 NNN 추가 (룰 3.1):
  ```
  - NNN (passed at <ISO8601>) — <Job Story 한 줄>
  ```

`.harness/HANDOFF.md` 갱신:
- LAST_UPDATED, LAST_ACTOR 갱신
- 다음 액션: "/scenario-first-throw \"<다음 backbone 단계 narrative>\""

#### 7b. failed 처리 (라우팅 후)

`scenarios/expanded/NNN-*.md` frontmatter:
```
review_status: failed
routed_to: throw | expand | spec | goal
review_at: <ISO8601>
```

라우팅이 (1) 시나리오 오류 → **throw 폐기 절차** (REGRESSION-POLICY):
- 기존 expanded frontmatter 에 `archived: true` 추가 (보존)
- `tests/e2e/scenario-NNN/` → `.harness/.backups/<NNN>/<ts>/tests/` 이동
- `.harness/STATUS.md` 누적 풀에서 NNN 제거 (있었다면)
- 폐기 사유 한 줄을 `.harness/backlog.md` 에 append

`.harness/STATUS.md` 갱신:
- `WAITING_ON_USER:` 해제 (라우팅 결정됐으니)
- Cycle 로그 한 줄
- `IN_PROGRESS:` 는 그대로 (같은 NNN 재진행)

### 8. STATUS.md cycle 로그 (룰 3.3)

```bash
echo "- $(date -Iseconds) NNN [review] <passed | failed → routed_to=X>" >> .harness/STATUS.md
```

### 9. 응답

성공:
```
✓ review/NNN  passed — 6범주 합계 X/12, evidence Y개
누적 풀 갱신 (NNN 추가)
다음 backbone 슬라이스: /scenario-first-throw "<제안 narrative>"
```

라우팅:
```
⚠ review/NNN  routed to (1) 시나리오 오류
다음: /scenario-first-throw --update NNN  (같은 NNN 갱신)
근거: scenarios/specs/NNN/REVIEW.md 5 Whys
```

폐기 (시나리오 오류):
```
⚠ review/NNN  archived (시나리오 자체 폐기)
누적 풀에서 제거, backlog.md 에 사유 기록
다음 backbone: /scenario-first-throw "<다른 narrative>"
```

## 산출

- `scenarios/specs/NNN/REVIEW.md` (`.harness/templates/REVIEW.md` 기반, 6범주 + evidence + 5 Whys + 라우팅)
- 갱신된 `scenarios/expanded/NNN-*.md` frontmatter
- 갱신된 `.harness/STATUS.md` (IN_PROGRESS, WAITING_ON_USER, 누적 풀, Cycle 로그)
- 갱신된 `.harness/HANDOFF.md` (passed 시)
- (실패 폐기 시) `.harness/backlog.md` append + `.harness/.backups/<NNN>/<ts>/tests/` 이동
- 다음 단계 안내

## 다음 단계

성공: 다음 backbone 슬라이스 = 새 throw (새 NNN)
실패: 라우팅에 따라 같은 NNN으로 throw/expand/spec/goal

## 금지 사항

- 본인 사용 단계를 Claude가 시뮬레이션 (가짜 검증 — 시스템 핵심 함정)
- evidence 0~1개로 passed 표시 (룰: passing_requires_evidence, 최소 2개)
- 6범주 평가 일부 생략
- 5 Whys 5번 다 안 하고 1~2번에서 멈추기 (라우팅 정확도 떨어짐)
- Claude가 라우팅을 단독 결정 (최종 결정은 본인)
- 라우팅 4번째 옵션 ("그냥 둬" 등) 만들기 — 3분류 외 금지
- 실패한 시나리오를 통과한 걸로 기록 (regression 풀에 가짜 PASS 누적)
- Regression을 별도 게이트로 만들기 — 3단계 누적 시나리오 게이트에 흡수
- 라우팅 (1) 시 새 NNN으로 가기 — 같은 NNN 갱신 (룰 3.5)
- 누적 풀 갱신 건너뛰기 (passed 시 의무)
- STATUS.md WAITING_ON_USER 표기 안 하고 멈춤 (다음 에이전트가 못 알아챔)
- 하네스 미설치 상태에서 강행
