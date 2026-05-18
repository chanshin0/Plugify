---
name: scenario-first-spec
description: 시나리오-First 개발 2단계. 확장된 GWT 시나리오에서 PRD / ARCHITECTURE / 비기능 / 운영 spec을 동일 템플릿으로 도출한다. 결정성 보존을 위해 매번 같은 4개 슬롯을 채우며, 시나리오로 표현 불가한 운영 영역(rollback, migration, observability)은 별도 슬롯에 명시적으로 기록한다. Spec Kit과의 차이: 구조 강제가 아니라 SoT 위치만 강제.
---

# scenario-first-spec

## 목적

`scenario-first-expand`가 만든 GWT 시나리오를 **개발 가능한 spec 4종**으로 변환한다. 매 사이클 같은 템플릿 → 결정성 보존.

원리:
- 시나리오는 SoT, spec은 시나리오에서 **도출된 산출물**
- 운영(rollback, migration, observability)·내부 추상화는 사용자 시나리오로 표현 불가 → 별도 슬롯에 명시
- 단방향: 1(throw) → 2(expand) → **3(spec)** → 4(goal) → 5(review). 양방향 동기 안 함.

Spec Kit과 차이: Spec Kit은 문서 종류·구조를 강제해 결정성을 깎음. 시나리오-First는 **SoT 위치만 강제**하고 spec은 정해진 4슬롯을 매번 동일하게 채움.

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-spec <NNN>` | `.scenarios/expanded/NNN-*.md`에서 spec 도출 |
| `/scenario-first-spec --rerun <NNN>` | 기존 spec 백업 후 재생성 |

자동 트리거 금지.

## 사전 점검

```bash
test -f .scenarios/expanded/NNN-*.md   # 입력 존재
mkdir -p .scenarios/specs/NNN
```

## Workflow

### 1. 확장 로드

`.scenarios/expanded/NNN-*.md`에서 backbone / walking skeleton / GWT 시나리오 전체를 읽는다.

### 2. 4슬롯 spec 도출

**모든 시나리오 대상으로 4개 문서를 동일 템플릿으로 생성**.

#### 2.1 PRD.md — 무엇을 만드는가
```markdown
# PRD: <Job Story 한 줄>

## 목표
<Job Story의 `so I can ...`>

## 사용자
<Job Story의 `When ...` 상황에 처한 누구. 페르소나가 아니라 상황>

## 범위 (walking skeleton 기반)
- backbone 1: <단계> — <walking skeleton 동작>
- ...

## 시나리오 (GWT 인용)
<scenario id 목록 + 한 줄 요약>

## 비범위 (Story 카드 = 다음 사이클 이월)
- <목록>

## 성공 정의
- 모든 GWT 시나리오 자동 게이트 통과
- 본인이 직접 사용해 walking skeleton 한 줄 + `so I can` 체크리스트 모두 ✓
```

#### 2.2 ARCHITECTURE.md — 어떻게 만드는가
```markdown
# ARCHITECTURE

## 구성요소
<시나리오의 When/Then에서 식별된 actor/system 매핑>

## 데이터 모델
<Given에 등장하는 사전 상태로부터 식별된 엔티티·관계>

## 외부 의존성
<시나리오에서 명시·암시된 외부 시스템>

## 흐름
<walking skeleton을 시퀀스로>

## 결정 lock 표
| 변수 | 선택 | 근거 |
|---|---|---|
| <key tech 결정> | <선택> | <시나리오 인용> |
```

ARCH 단계의 결정은 시나리오에서 끌어낼 수 있는 것만 lock. 시나리오와 무관한 결정은 "보류" 슬롯에 명시.

#### 2.3 NONFUNC.md — 비기능 요구
```markdown
# NONFUNC

## 성능
<시나리오의 Then에 응답시간·throughput 언급 있으면 옮김. 없으면 "TBD — 사용 후 측정">

## 보안
<Given의 권한·인증 단서. 없으면 "default — 본인만 사용">

## 가용성
<TBD or 명시>

## 호환성
<브라우저·OS·버전 — 시나리오 When에 단서 있으면 옮김>
```

비어 있어도 슬롯은 남긴다. "TBD"는 정상.

#### 2.4 OPS.md — 운영 spec (시나리오 흡수 불가 영역)
```markdown
# OPS

## 배포
- 환경: <local / staging / prod>
- 절차: <CI/CD or manual>
- 롤백: <git revert / DB migration revert / 명시 없으면 "수동, 본인 결정">

## 마이그레이션
- 데이터 마이그레이션 필요 여부: <yes/no>
- 절차: <명시 또는 "이 슬라이스에는 없음">

## Observability
- 로그: <위치·레벨>
- 메트릭: <측정 항목>
- 알람: <조건>

## 백업
<주기·위치 또는 "없음">
```

**OPS.md는 시나리오로 표현 불가한 영역의 슬롯**. 비어 있어도 "없음" 명시 — 묵시화 금지.

### 3. 사용자 확인

4개 문서를 한 번에 보여주고:
- accept → 4번
- 슬롯별 수정 → diff로
- reject 1개 슬롯 → 해당 슬롯만 재생성

### 4. 저장

`.scenarios/specs/NNN/`에 4개 파일 저장.

expanded의 frontmatter 갱신:
```
spec_id: .scenarios/specs/NNN/
```

### 5. 응답

```
✓ specs/NNN/  PRD + ARCH + NONFUNC + OPS
빈 슬롯: <목록 — TBD나 "없음" 명시된 곳>
Next: /scenario-first-goal NNN
```

## 산출

- `.scenarios/specs/NNN/PRD.md`
- `.scenarios/specs/NNN/ARCHITECTURE.md`
- `.scenarios/specs/NNN/NONFUNC.md`
- `.scenarios/specs/NNN/OPS.md`
- 갱신된 expanded frontmatter

## 다음 단계

- `scenario-first-goal` — spec + GWT 시나리오 기반 goal-directed loop

## 금지 사항

- 4슬롯 외 추가 문서 임의 생성 (Spec Kit 함정)
- 빈 슬롯 삭제 (TBD/없음 명시가 결정성)
- 시나리오에 없는 결정을 spec에 끼워 넣기 (도출 아닌 창작)
- ARCH 결정 lock 표 생략
- OPS.md 생략 — 시나리오 흡수 불가 영역은 반드시 별도 슬롯
