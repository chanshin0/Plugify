---
name: scenario-first-throw
description: 시나리오-First 개발 1단계. 사용자가 떠올린 "쓰는 모습"을 Job Story 1~2개로 캡처. `When <상황>, I want to <동기>, so I can <결과>` 형식. User Story의 페르소나·사후합리화·trigger 누락 약점을 거부하고 상황(trigger)을 명시화한다. 자유 텍스트로 던지면 Claude가 Job Story 1~2개로 변환·확인. 결과는 `scenarios/throws/`에 저장. 하네스 layer는 `/scenario-first-init` 으로 사전 설치 필수.
---

# scenario-first-throw

## 목적

시나리오-First 개발 파이프라인의 **시작점**. 사용자 머릿속의 "쓰는 모습"을 Job Story 형식으로 외화(externalize)한다.

원리:
- SoT(Source of Truth)는 코드도 spec도 아니고 **유저가 결과를 어떻게 쓰는지의 narrative**
- Job Story = `When <상황>, I want to <동기>, so I can <결과>`
- User Story 거부 이유: 페르소나 가정 + 사후 합리화 동기 + trigger 누락

출처: Paul Adams @ Intercom 2013, Alan Klement 정리. JTBD(Christensen) 운동의 실무 표현.

## 트리거

수동 호출만:

| 인자 | 동작 |
|---|---|
| `/scenario-first-throw "<자유 텍스트>"` | 텍스트에서 Job Story 1~2개 추출 (신규 NNN) |
| `/scenario-first-throw` | 사용자에게 "쓰는 모습 설명해주세요" 프롬프트 후 캡처 (신규 NNN) |
| `/scenario-first-throw --update <NNN>` | review (1) 시나리오 오류로 라우팅된 같은 NNN 백업 후 갱신 (룰 3.5) |
| `/scenario-first-throw --list` | `scenarios/throws/` 목록 |

자동 트리거 금지. 본인이 떠올렸을 때만.

## 사전 점검

```bash
# 1. 하네스 깔렸나 (필수)
test -d .harness && test -d scenarios || {
  echo "ERROR: 하네스 미설치. /scenario-first-init 먼저 실행"
  exit 1
}

# 2. cycle lock 확인 (신규 NNN 시만; --update 모드는 예외)
if [[ "$MODE" != "update" ]]; then
  grep -qE "^IN_PROGRESS: \(none\)$" .harness/STATUS.md || {
    echo "ERROR: 이미 진행 중인 cycle 있음 (.harness/STATUS.md IN_PROGRESS). 종료 후 시도"
    exit 1
  }
fi
```

기존 `scenarios/throws/NNN-*.md` 카운트해서 다음 번호 결정.

## Workflow

### 1. 입력 받기

자유 텍스트 또는 대화. 사용자가 명시적으로 Job Story 형식을 안 써도 OK — Claude가 변환.

### 2. Job Story 변환

추출 규칙:
- **When** = trigger 상황 (시간·장소·이벤트·심리 상태)
- **I want to** = 그 상황에서 사용자가 하고 싶은 동작
- **so I can** = 동작으로 얻고자 하는 결과·가치

검증:
- trigger가 비어있거나 모호하면 사용자에게 1회 되묻기 ("어떤 상황에서?")
- 동기와 결과가 같으면 분리 시도 ("뭘 위해서?")
- 페르소나가 들어가 있으면 ("개발자가" 등) 제거하고 상황으로 치환

복수의 Job Story가 추출되면 **최대 2개**까지. 더 있으면 사용자에게 우선순위 묻기.

### 3. 사용자 확인

추출한 Job Story를 보여주고 확인:
- accept → 4번
- 수정 → 사용자가 직접 편집한 텍스트로 저장
- reject → 1번부터 재시도

### 4. (--update 모드만) 백업

```bash
TS=$(date -Iseconds)
mkdir -p ".harness/.backups/<NNN>/$TS"
cp "scenarios/throws/NNN-"*.md ".harness/.backups/<NNN>/$TS/"
echo "- $TS <NNN> scenarios/throws/NNN-*.md → .harness/.backups/<NNN>/$TS/" >> .harness/STATUS.md
```

### 5. 저장

`scenarios/throws/NNN-<slug>.md`로 저장 (신규) 또는 덮어쓰기 (--update):

```markdown
---
id: <NNN>
created_at: <ISO8601>
status: thrown
expanded_to: null
---

# Job Story <NNN>

When <상황>,
I want to <동기>,
so I can <결과>.

## 원본 입력
<사용자가 던진 자유 텍스트>

## 메모
<추출 시 잡힌 모호함·대안·페르소나 제거 흔적 등>
```

### 6. STATUS.md 갱신 (룰 3.3·3.4 — 의무)

```bash
# 신규 NNN 시 IN_PROGRESS 채움
sed -i.bak -E "s|^IN_PROGRESS: \(none\)$|IN_PROGRESS: NNN-<slug>|" .harness/STATUS.md && rm .harness/STATUS.md.bak

# Cycle 로그 한 줄 append
echo "- $(date -Iseconds) NNN-<slug> [throw] <Job Story 한 줄>" >> .harness/STATUS.md
```

### 7. 응답

```
✓ throws/NNN  When ..., I want to ..., so I can ...
STATUS: IN_PROGRESS=NNN
Next: /scenario-first-expand NNN  (USM + Example Mapping + GWT 변환)
```

## 산출

- `scenarios/throws/NNN-<slug>.md` (frontmatter + Job Story + 원본 + 메모)
- 갱신된 `.harness/STATUS.md` (IN_PROGRESS, Cycle 로그)
- (--update 시) `.harness/.backups/<NNN>/<TS>/` 백업
- 응답에 ID와 한 줄 요약

## 다음 단계

- `scenario-first-expand` — Job Story 확장 (USM + Example Mapping → GWT)

## 금지 사항

- Job Story 임의 합성 (사용자 입력 없이 추측해서 만들지 않는다)
- 페르소나 추가
- 동기·결과를 "그럴듯하게" 미화
- `scenarios/throws/` 외부에 저장
- 하네스 미설치 상태에서 강행 (init 먼저)
- IN_PROGRESS 차 있는데 새 NNN 만들기 (cycle lock 룰 3.4)
- STATUS.md 갱신 건너뛰기 (룰 3.3)
