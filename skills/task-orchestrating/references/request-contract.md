# Request contract

## 기록 위치

- 프로젝트에 `.planning/`이 있으면 `.planning/requests/<YYYY-MM-DD>-<slug>.md`를 정본으로 사용한다.
- 이미 같은 정보를 담는 STATE·ADR·기획 정본이 있으면 중복 파일을 만들지 말고 해당 정본에 섹션을 추가한다.
- 프로젝트 정본이 없는 일회성 작업이면 Codex task plan과 최종 보고로 충분하다.

## 최소 기록

````markdown
# Request: <id>

## Contract
- outcome: <사용자가 얻게 될 결과>
- constraints: <지켜야 할 경계>
- doneWhen:
  - <에이전트가 확인할 전체 증거>
- nonGoals:
  - <이번 범위 밖>

## Knowledge map
- discoverable: <조사 결과 + 근거>
- assumable: <가정 + 영향 + 뒤집을 조건>
- human-context: <질문 필요 여부>
- approval: <행동 직전 승인 경계>

## Interview ledger
- question: <질문>
  answer: <사람의 답을 요약>
  decision: <그래프에 반영한 결정>
  affects: [T1, T3]

## Execution graph
```json
{
  "contractVersion": "2.0",
  "tasks": [
    {
      "id": "T1",
      "goal": "관찰 가능한 단일 결과",
      "why": "전체 outcome에 기여하는 이유",
      "targets": ["src/example.ts"],
      "depends": [],
      "evidence": [
        {
          "id": "E1",
          "kind": "command",
          "run": "npm test -- example.test.ts",
          "expect": {
            "exit": "0",
            "outputIncludes": [],
            "outputExcludes": []
          }
        }
      ],
      "assumptions": [],
      "risk": "MECHANICAL",
      "replanWhen": ["테스트가 현재 계약과 충돌함을 증명"]
    }
  ],
  "verify": "npm test"
}
```

## Events
- at: <ISO-8601>
  phase: orient | interview | shape | execute | verify | replan | finalize
  transition: <의미 있는 상태 전환>
  actorType: human | orchestrator | implementer | reviewer | probe
  triggerSource: user | workflow | gate | evidence | retry | escalation
  outcome: started | passed | failed | pending
  reasonCode: <짧고 안정적인 코드>
  evidence: [<경로·명령·SHA·URL 등 최소 참조>]
````

프롬프트 전문, 비밀값, 환경변수 값, 불필요한 대화 전문은 기록하지 않는다.

## 그래프 품질 규칙

1. task 하나는 독립적으로 검증 가능한 결과 하나를 만든다.
2. `why`가 전체 outcome에 연결되지 않으면 제거한다.
3. `evidence`는 `{id, kind:"command", run, expect:{exit,outputIncludes,outputExcludes}}` 구조로 쓴다. `run`은 허용된 비대화형 도구 또는 명시적 스크립트 경로로 시작하고, reviewer가 같은 `id·run`의 실제 `exit·output·passed`를 돌려준다. 오케스트레이터는 `exit` 일치, 모든 포함 문자열의 존재, 모든 제외 문자열의 부재를 다시 코드로 판정한다. 사람의 육안 확인·"괜찮아 보임"·사용자 승인은 evidence가 아니다. 승인은 `approval` ledger로 분리한다.
4. `depends`는 이 graph 안에 실재하는 task ID의 산출물 소비 관계만 표시한다. 단순한 서술 순서·사람 인터뷰·승인 문자열을 넣지 않는다. 승인 경계는 Knowledge map의 `approval`에 기록한다.
5. `replanWhen`은 실패 횟수, 계약 충돌, 새 외부 사실처럼 관찰 가능하게 쓴다.
6. 같은 파일을 병렬 task가 겹쳐 수정하면 합치거나 명시적으로 직렬화한다.
7. 질문 답변이 task를 바꾸면 원래 질문을 반복하지 말고 ledger와 graph를 함께 갱신한다.

## 전환 요약

`Agent Self Turn` 집계에는 실제 상태를 바꾼 이벤트만 포함한다. 최초 사용자 요청, commentary, 도구 호출, no-op review, 같은 실패의 무변화 반복은 제외한다. 계획된 `human-context` 인터뷰와 `approval` 대기는 자율성 실패에서 제외하되 이벤트에는 남긴다.
