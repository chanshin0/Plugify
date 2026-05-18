---
name: scenario-first-review
description: 시나리오-First 개발 4단계. 본인이 직접 빌드 결과를 사용해 Job Story 체크리스트(`so I can` + walking skeleton 한 줄)와 대조한다. 통과 시 다음 backbone 슬라이스로 진행, 실패 시 5 Whys로 (1) 시나리오 오류 / (2) Spec 누락 / (3) 구현 오류 셋 중 하나로 라우팅. Regression은 3단계 게이트에 흡수되어 별도 분기 없음. 시스템 생사를 가르는 단계 — 건너뛰면 자동 MVP 함정으로 회귀.
---

# scenario-first-review

## 목적

3단계까지 자동으로 통과해도 **본인이 실제 쓰는지**는 다른 문제. `01KQ6H94XX`의 "주기적 자동 MVP" 함정(가짜 검증)을 막는 마지막 게이트.

원리:
- 체크리스트는 Job Story의 `so I can ...` + walking skeleton 한 줄 (스스로 작성한 것)
- 사용자가 매 cycle 4단계를 **실제 돌릴 의지**가 시스템 생사
- 실패 라우팅은 5 Whys로 3분류 (시나리오/spec/구현). 직감 라우팅 금지.

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-review <NNN>` | spec NNN 결과물에 대한 체크리스트 + 5 Whys |
| `/scenario-first-review <NNN> --triage` | 3단계 STUCK 상태에서 직접 5 Whys (사용 단계 스킵) |
| `/scenario-first-review <NNN> --skip-use` | 체크리스트만 (이미 사용해본 경우) |

자동 트리거 금지.

## 사전 점검

```bash
test -f .scenarios/specs/NNN/GOAL.md     # 게이트 통과 기록 (있어야 사용 단계 의미 있음)
# 또는 --triage 모드면 STUCK.md
test -f .scenarios/expanded/NNN-*.md
```

## Workflow

### 1. 체크리스트 생성

`.scenarios/throws/NNN-*.md`의 Job Story `so I can ...` + `.scenarios/expanded/NNN-*.md`의 walking skeleton 항목들로:

```markdown
# 사용 체크리스트 NNN

## Job Story 결과 (so I can ...)
- [ ] <so I can 절>

## Walking skeleton (각 단계 한 줄)
- [ ] 1.1 <동작> — 실제 동작했는가
- [ ] 2.1 <동작>
- [ ] ...
```

### 2. 사용자에게 안내

```
✓ 체크리스트 준비 완료.

지금 직접 빌드 결과를 사용해보세요:
<실행 명령 또는 URL — spec의 OPS.md에서 추출>

체크 후 다음 중 하나로 답:
- "전부 통과" → 다음 backbone 슬라이스로 진행
- "X.Y 실패 — <증상>" → 5 Whys 진단 시작
- "잠깐 — <수정 요청>" → 수정 요청 받아 분기
```

**Claude는 여기서 멈춘다.** 사용자가 돌아올 때까지 대기.

`--skip-use` 모드면 곧바로 5번으로.

### 3. 사용자 응답 처리

#### Case A: 전부 통과
- `.scenarios/specs/NNN/REVIEW.md`에 ✓ 기록
- expanded frontmatter `review_status: passed`
- 다음 backbone 슬라이스(= 다음 throw) 안내:
  ```
  ✓ review/NNN  passed
  다음: /scenario-first-throw "<다음 backbone 단계의 결과 narrative>"
  ```

#### Case B: 일부 실패
- 실패 항목 + 증상 받기
- 5번 5 Whys로

#### Case C: 수정 요청
- 사용자가 시나리오 수정 의향이면 1단계 (throw 갱신)
- 사용자가 spec 수정 의향이면 2단계 (expand) 또는 3단계 (spec)
- 모호하면 5번으로

### 4. (선택) `--triage` 모드 진입

3단계가 STUCK으로 escalate된 경우:
- `.scenarios/specs/NNN/STUCK.md` 읽기
- 사용 단계 스킵
- 5번 직행

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

### 6. 라우팅 결정 (3분류)

5 Whys 결과를 3분류 중 하나로:

| 라우팅 | 조건 | 다음 단계 |
|---|---|---|
| **(1) 시나리오 오류** | Job Story·Example·GWT 표현이 본인 의도와 다름 | `/scenario-first-throw` 갱신 또는 `/scenario-first-expand --rerun` |
| **(2) Spec 누락** | 시나리오는 OK인데 spec에 빠진 슬롯 | `/scenario-first-spec --rerun NNN` (PRD/ARCH/NONFUNC/OPS 보강) |
| **(3) 구현 오류** | 시나리오·spec OK인데 구현이 어긋남 | `/scenario-first-goal --resume NNN` |

Claude가 초안을 제시하고 **사용자가 최종 결정**. 사용자가 거부하면 5 Whys 재시작.

### 7. 라우팅 기록

`.scenarios/specs/NNN/REVIEW.md`:
```markdown
# Review NNN

## 사용 결과
- [x] so I can ...
- [ ] 2.1 검색 결과 보기 — 0건 placeholder 안 보임

## 5 Whys
1. ...
2. ...

## 라우팅
**(1) 시나리오 오류** — Example Mapping Question "0건 처리"를 본인 의도(placeholder)로 명시
다음: /scenario-first-expand --rerun NNN
```

expanded frontmatter:
```
review_status: failed
routed_to: throw | expand | spec | goal
```

### 8. 응답

성공:
```
✓ review/NNN  passed — 모든 체크리스트 통과
다음 backbone 슬라이스: /scenario-first-throw "<제안 narrative>"
```

라우팅:
```
⚠ review/NNN  routed to (1) 시나리오 오류
다음: /scenario-first-expand --rerun NNN
근거: .scenarios/specs/NNN/REVIEW.md 5 Whys
```

## 산출

- `.scenarios/specs/NNN/REVIEW.md` (체크리스트 결과 + 5 Whys + 라우팅)
- 갱신된 expanded frontmatter
- 다음 단계 안내

## 다음 단계

성공: 다음 backbone 슬라이스 = 새 throw
실패: 라우팅에 따라 1/2/3 단계로

## 금지 사항

- 본인 사용 단계를 Claude가 시뮬레이션 (가짜 검증 — 시스템 핵심 함정)
- 5 Whys 5번 다 안 하고 1~2번에서 멈추기 (라우팅 정확도 떨어짐)
- Claude가 라우팅을 단독 결정 (최종 결정은 본인)
- 라우팅 4번째 옵션 ("그냥 둬" 등) 만들기 — 3분류 외 금지
- 실패한 시나리오를 통과한 걸로 기록 (regression 풀에 가짜 PASS 누적)
- Regression을 별도 게이트로 만들기 — 3단계 누적 시나리오 게이트에 흡수
