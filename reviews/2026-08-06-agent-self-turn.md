# Agent Self Turn 관점 Plugify 메타리뷰

## 목표

자연어 요구가 들어오면 사람이 완료 조건을 작성·채점하는 대신, 에이전트가 필요한 사실을 조사하고 사람만 알 수 있는 빈칸을 인터뷰해 실행 그래프와 완료 증거를 만든 뒤 실행·검증·재계획까지 이어가게 한다.

완료 조건:

1. 요구 해석·정보 분류·인터뷰·분해 계약이 정본에 있다.
2. 사람은 의도·맥락·비가역 승인만 맡고 routine 완료 판정은 에이전트가 맡는다.
3. `spec-building` 그래프가 `why·evidence·assumptions·replanWhen`을 받아 실제 구현·리뷰 입력으로 사용한다.
4. Agent Self Turn은 의미 있는 상태 전환으로 기록되며 호출 수로 부풀릴 수 없다.
5. 사람 전가·과잉 질문·무의미한 분해·거짓 완료를 막는 eval이 있다.
6. 기존 증거 기반 안전장치와 회귀가 유지되고, fresh Codex 검증과 설치가 통과한다.

## 선행 연구에서 채택한 것

두 DV 문서는 공통으로 raw message나 agent 호출 횟수가 아니라 **사용자 재호출 없이 시작된 의미 있는 상태 전환**을 측정하라고 했다. `spec-building`을 첫 파일럿으로 삼고, 블라인드 리뷰·최소 run summary·anti-Goodhart eval을 둔 뒤 실제 관찰 전 전 스킬로 확장하지 말라는 방향도 명시했다.

메타리뷰 문서는 감사자·구현자·블라인드 리뷰어·Goodhart 리뷰어·판정자·수정자·fresh 재검토자의 입력을 분리하고, 독립성을 말이 아니라 별도 컨텍스트로 실증하라고 했다. 이번 작업은 협업 서브에이전트 대신 별도 `codex exec --ephemeral` 프로세스로 최종 독립 검증한다.

## 현행 감사

### 이미 강한 부분

- `spec-building`은 구현→블라인드 리뷰→수정→재검증→커밋·프리뷰를 상한 안에서 반복한다.
- Git HEAD·파일집합·digest·원격/배포 SHA 등 완료 자기보고를 대체할 독립 증거가 있다.
- 그래프 경로는 의존성·wave·target·merge·통합 게이트를 코드로 판정한다.
- `runSummary`에 terminal state와 의미 있는 전환의 초기 스키마가 있다.

### 빠진 부분

- 진입 계약은 `.planning/STATE.md`에 목표·게이트·그래프가 이미 존재한다고 전제한다.
- 누가 자연어 요구를 조사하고 실행 계약으로 만드는지 정본이 없다.
- 접지되지 않은 load-bearing 결정을 거의 모두 사용자 확인으로 보내 조사 가능/저위험 가정/사람 고유 맥락을 구분하지 않는다.
- 그래프 task는 `goal·targets·depends·risk`만 가져 전체 목표 기여 이유, task별 완료 증거, 가정, 재계획 조건이 없다.
- eval 출제와 완료 조건 확인을 routine 사람 역할로 두어, 사용자가 작업 사이의 메신저·채점자가 된다.

## 이전 구현의 방향 이탈

첫 구현은 거짓 완료 방지와 human gate 강화에 집중했다. 그 안전장치는 유용하지만 DV가 요청한 핵심인 `요구 이해 → 능동 조사/인터뷰 → 작업 분해 → 자율 전환 측정`을 구현하지 못했다. 특히 모든 기술 결정을 사람에게 보이는 것, human 게이트가 남으면 완료를 막는 것, 새 CASE/ANSWER를 다시 사람이 확인해야만 쓰는 것은 사용자를 routine checker로 남긴다.

교정 원칙:

- 유지: 블라인드 리뷰, Git/digest/SHA 증거, 구조화 terminal state, 상한·reason code.
- 수정: `human:`을 routine 품질 확인이 아니라 사람만 제공할 맥락 또는 비가역 승인으로 제한.
- 추가: 범용 `task-orchestrating` 앞단, 4종 knowledge map, interview ledger, evidence-bearing graph, replan contract.
- 파일럿: 새 계약의 실행 결속과 계측은 먼저 `spec-building`에만 적용.

## 설계 결정과 이유

| 문제 | 이유 | 변경 | 확인 방법 |
|---|---|---|---|
| 자연어 요청을 STATE로 바꾸는 주체 없음 | 실행기 앞단 공백 | `task-orchestrating` 신설 | 모호한 요청 forward-test |
| 질문 과다 또는 필요한 질문 누락 | unknown 종류가 한 덩어리 | discoverable/assumable/human-context/approval 분류 | eval 시나리오 1~4 |
| 사람이 완료 체크 | 게이트 소유권이 모호 | doneWhen/evidence를 에이전트 책임으로 명시 | 스킬·AGENTS 문구 검사 |
| task가 전체 목표와 분리 | `why` 없음 | graph에 `why` 필수 | 코드 validator |
| 구현 성공 기준이 task에 없음 | overall verify만 존재 | task별 `evidence` 필수·프롬프트 주입 | validator+계약 테스트 |
| 같은 실패 반복 | 재계획 조건 없음 | `replanWhen` 필수 | eval 시나리오 7 |
| 호출 수 Goodhart | 이벤트 의미 기준 없음 | actor/trigger/meaningful·전환 집계 | runSummary 계약 테스트 |
| 자기 시험 자기 승인 방지 때문에 사람 고정 | 독립성 수단과 사람 역할을 혼동 | fresh blind reviewer가 합격선 결속을 검증; 사람은 요구 변경·완화만 승인 | eval 규약+fresh review |

## 범위와 한계

- 이번에는 범용 계약을 만들되 실행 코드와 계측은 `spec-building` 파일럿에만 적용한다.
- 대시보드, 전 스킬 공통 이벤트 저장소, 자동 스케줄러는 만들지 않는다.
- 세션 밖 사용자 재개입률과 완료 후 누출률은 연결 데이터가 없으므로 `not_observable`이다.
- instruction-only 앞단의 실제 인터뷰 품질은 결정적 코드만으로 증명할 수 없어 독립 forward-test와 첫 실전 관찰이 필요하다.

## Forward-test 발견

첫 read-only fresh Codex 실행은 저장소를 직접 조사해 `contractVersion` 타입 혼동을 발견했다. 문자열 `"2.0"`은 필수 실행 계약을 검사하지만 숫자 `2.0`, boolean, null, 객체는 버전 없음으로 정규화되어 legacy로 수용됐다. `Object.hasOwn`으로 필드 존재를 먼저 판정하고, 필드가 있으면 정확한 문자열 `"2.0"` 외 전부 fail-closed하도록 수정했으며 다섯 타입 회귀를 추가했다.

같은 실행은 사용자에게 조사 사실을 되묻지 않았지만, 응답용 그래프에서 `why·assumptions`를 암묵화했다. 두 번째 인터뷰/파괴 승인 simulation은 질문과 승인 위치는 정확했으나 일부 task의 `goal·why`를 생략하고 `depends`에 task ID가 아닌 승인 문자열을 넣었다. 따라서 사용자 응답에서도 validator 호환 JSON을 강제하고, `depends`는 task ID만, 승인은 knowledge map에 별도 기록하도록 보강했다. dirty main의 기존 미커밋 변경 소유권을 물은 것은 자료 훼손을 피하기 위한 human-context 경계로 유지한다.

## 첫 독립 적대 리뷰와 수정

구현 중간에 두 개의 read-only `codex exec --ephemeral` 컨텍스로 런타임 계약과 정책 전수를 따로 검토했다. 구현 설명 대신 실제 파일·diff를 입력으로 줌다.

| 발견 | 영향 | 반영 |
|---|---|---|
| `contractVersion` 누락이 legacy로 조용히 강등 | v2 필수 계약 전체 우회 | 기본 fail-closed, `allowLegacyGraph:true` 명시 마이그레이션만 허용 |
| task evidence가 프롬프트에만 있고 실제 결과와 미결속 | reviewer가 다른/가짜 검증으로 pass 가능 | `{id,kind,run,expect:{exit,outputIncludes,outputExcludes}}` 구조화 + `evidenceResults` 순서·id·run 1:1 및 실제 exit/output 코드 대조 |
| `replanWhen`이 설명용이고 같은 graph를 재시도 | 적응형 분해가 아닌 spinning | 실패 증거 대조 후 `replan-required`, 통합 실패도 즉흥 패치 대신 graph 재계획 |
| 승인 문구를 evidence command로 위장 가능 | 사람 권한 경계 우회 | 비대화형 command/명시 스크립트 허용목록 + 사용자/사람/manager/operator/담당자/관리자/manual QA 등 approval 신호 결정적 반려 |
| reviewer의 Codex 호출이 sandbox/approval bypass 사용 | 리뷰가 자체 보안 경계 우회 | `--ephemeral --ignore-user-config --sandbox read-only` 로 교체, 실패 시 reviewer 단독 판정 |
| 프리뷰 branch push가 명시 승인 없이 실행 | 외부 전송·원격 변경 권한 우회 | 게이트 판독 boolean을 폐기하고 STATE 원문에서 정확한 독립 행 `preview-push: authorized`를 코드 대조; 없으면 구현 전 `pending-human` |
| self-review·slides·scaffold·live-verify·service-planning의 routine 사람 confirm/판정 | 사용자가 메신저·채점자로 남음 | 요청 범위 안은 자동 반영·재검증, 사람은 load-bearing 맥락·실제 approval만 제공 |

## 현재 검증 증거

- 첫 최종 read-only Codex 적대 리뷰는 두 P1을 재현했다. (a) reviewer가 `passed:true`를 반환하면 선언 `expect`와 실제 output이 달라도 통과, (b) approval 문구 차단이 user/human 일부 단어만 보는 blacklist여서 manager/operator/담당자/관리자/manual QA 표현으로 우회 가능. 자유문장 `expect`를 기계 판정 객체로 바꾸고, command 허용목록·확장 approval 신호·실제 exit/output 재판정과 회귀를 추가했다.
- 두 번째 read-only Codex 적대 리뷰는 추가 P1 두 건을 재현했다. (a) 프리뷰 승인 여부가 STATE 원문이 아니라 게이트 판독 에이전트의 boolean에 의존해 거짓 `true`로 push 경로에 진입, (b) approval 신호 검사가 `evidence.run·expect`만 보고 `id="manager approval"`을 놓침. 게이트 판독은 `## 다음 task` 원문을 반환하고 코드가 정확한 독립 행을 판정하도록 바꿨으며, approval 정규화 검사를 `id·run·expect` 전체에 적용했다. 평가의 상위 요구·하위 불변식·실행 시나리오 수가 다른 이유도 CASE/ANSWER에 명시했다.
- 세 번째 read-only Codex 적대 리뷰는 `expect.exit="manager approval"`이 approval 검사에서 빠져 worktree 생성까지 도달하는 P1을 재현했다. 검사 대상을 `expect.exit`까지 넓히고 exit 자체도 0 이상의 정수 문자열만 허용했다.
- 네 번째 read-only Codex 적대 리뷰는 `managerApproval`처럼 camelCase/무구분 결합형을 `id·run·outputIncludes·outputExcludes`에 넣으면 단어 경계 검사를 우회하는 P1을 재현했다. camelCase 경계를 분리하고 공백 없는 역할+승인 동작 결합도 탐지하도록 정규화를 강화했다.
- 다섯 번째 final fresh/blind 리뷰는 인메모리 AsyncFunction 재현으로 `manager approval`·`managerApproval`·`managerapproval` 전 필드, 잘못된/정상 exit, evidenceResults의 run/output 위조, STATE 원문 preview 승인 경계를 다시 검사했다. 결과는 `HARNESS_PASS`, `FULL_GRAPH_BOUNDARY_PASS`, 최종 **PASS**였다.
- `node scripts/test-spec-building-contracts.mjs`: **50/50 green**. 버전 누락, 승인-위장 evidence 동의어·필드·camelCase/결합형, reviewer의 거짓 `passed:true`와 출력 불일치, task/통합 재계획, preview push 승인 누락 회귀 포함.
- `node scripts/test-tech-deciding-contracts.mjs`: **6/6 green**.
- `workflow.mjs`·`graph-workflow.mjs`·`tech-deciding/workflow.mjs`: marker 이후 body를 `AsyncFunction`으로 컴파일, 모두 구문 통과.
- `skill-creator` quick validator: `task-orchestrating` **Skill is valid!**. 기본 Python에 PyYAML이 없어 Ruby stdlib YAML을 쓰는 임시 read-only adapter로 검증기를 그대로 실행했고 임시 파일은 즉시 제거했다.
- `bash scripts/install.sh`: 새 `task-orchestrating` 링크와 implementer/reviewer 에이전트 정의를 Claude/Codex 양쪽에 동기화, 경고 없이 통과. 에이전트 정의는 새 세션부터 유효하다.
- `voice-note/SKILL.md`는 이 작업 전부터 있던 사용자 변경으로, 이 작업에서 수정·스테이징하지 않는다.

자동 계약 검증과 final fresh/blind 재검토는 완료됐다. 새 task-orchestrating 평가는 작성자의 green만으로 confirmed하지 않고, 첫 실전 행동 관찰과 그 실행에 대한 독립 판정 전에는 `confirmed-cases.txt`에 추가하지 않는다.
