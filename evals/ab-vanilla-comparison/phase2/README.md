# Phase 2 주간 관찰 집계

지점 레포의 현재 HEAD에서 도달 가능한 git 이력과 Claude Code 세션 기록을 ISO 주 × `pipeline` / `direct`로 집계한다. Python 3.9 이상과 git이 필요하며 Python 패키지 설치는 필요 없다. 원본 레포·세션 기록을 수정하지 않는다.

## 실행

```sh
python3 evals/ab-vanilla-comparison/phase2/weekly-report.py \
  --repo /Users/admin/Projects/Plugify --since 2026-08-01

python3 evals/ab-vanilla-comparison/phase2/weekly-report.py \
  --repo /프로젝트/절대경로 --since 2026-08-01 \
  --transcripts /세션기록/디렉터리 --json /원하는/경로/주간.json

bash evals/ab-vanilla-comparison/phase2/selftest.sh
```

`--since` 기본값은 `1970-01-01`이다. 날짜 또는 ISO 시각을 받으며, 시간대가 없으면 UTC로 해석한다. git 커미터 시각·실행 시작 시각·세션 첫 유효 타임스탬프에 같은 포함 하한을 적용한다. ISO 주는 모두 **UTC 월요일 시작**이다. 한국 현지 시각 기준 주와 경계가 다를 수 있다.

기본 세션 디렉터리는 `~/.claude/projects/<레포 절대경로의 /를 -로 치환>/*.jsonl`이다. 하위 디렉터리는 읽지 않는다. `--transcripts`로 덮어쓸 수 있다. JSONL은 한 줄씩 읽으며 잘린 JSON 줄은 경고 후 제외한다. 경고는 stderr, 표는 stdout으로 나간다. 파일이 없는 디렉터리는 경고하고 git 집계는 계속한다.

## 태깅

우선순위는 다음과 같다.

1. 지점 레포의 선택 파일 `.planning/task-tags.tsv`에 명시한 태그.
2. 해당 세션의 spec-building Workflow 호출과 연결된 결과의 `commit.afterHead`, `commit.headLog` 또는 최상위 `headLog`에 등장하는 전체 40자리 해시: `pipeline`.
3. 커밋 메시지 본문에 다음과 **정확히 일치하는 한 줄**이 존재: `pipeline`.
4. 나머지: `direct`.

```text
Co-Authored-By: Claude <noreply@anthropic.com>
```

`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`처럼 모델명이 들어가면 이 트레일러 조건을 충족하지 않는다. 제목만 일치하는 경우도 제외한다. 본문에 동일한 줄을 인용했다면 구별하지 못하므로 수동 태그를 사용한다.

수동 태그는 헤더 없이 `<해시 접두>\t<pipeline|direct>` 형식이며 실제 탭으로 구분한다. 4~40자리 소문자 16진수 해시를 사용하고 git이 유일한 커밋으로 해석할 수 있어야 한다. 빈 줄과 `#`으로 시작하는 줄은 무시한다. 없는 해시·모호한 접두·상충하는 태그·형식 오류는 오류로 종료한다. 수동 `direct`는 워크플로우 근거와 트레일러도 덮어쓴다.

## 열의 뜻

| 열 | 집계 정의 |
|---|---|
| 주(ISO) | UTC ISO 연도와 주 번호. 연초에는 전년도 ISO 주일 수 있음 |
| 태그 | 커밋은 위 우선순위, 실행은 pipeline, 비용은 세션 전체의 호출 유무 기준 |
| 커밋 | 해당 주·태그의 커밋 수 |
| 파일변경 버킷(1/2-3/4+) | 변경 파일 1개, 2~3개, 4개 이상인 커밋 수를 순서대로 표시 |
| 후속수정(48h) | 뒤의 커밋이 0시간 초과 48시간 이하에 공통 파일을 수정하고 제목에 `revert\|되돌\|핫픽스\|hotfix\|재수정\|다시 수정\|fix:\|버그`가 있으면 원래 커밋을 1회 계수. 대소문자 무시 |
| 되돌림 | 제목이 `Revert` 단어로 시작하거나 `되돌`을 포함하는 커밋 자체의 수 |
| 공정 실행 | 해당 주에 시작한 spec-building Workflow 호출 수. 결과가 없는 호출도 포함 |
| verified | 연결된 결과의 `terminalState == "verified"`인 실행 수 |
| escalated/pending | terminalState가 escalated 또는 pending으로 시작하거나 escalation이 null이 아닌 실행 수. 중복 조건은 1회 계수 |
| 재개입 required | `runSummary.humanReintervention == "required"`인 실행 수 |
| 세션 비용 $ | 해당 주에 시작한 세션의 모델별 토큰 비용 합계. 소수 6자리. 가격을 모르면 `토큰 N`으로 표시 |

버킷 층화 표는 조회 기간 전체의 **태그 × 버킷**별 커밋 수와 `후속수정 커밋 수 / 커밋 수`를 표시한다. 관측되지 않은 조합은 생략한다. 변경 파일이 없는 빈 커밋은 주간 커밋 수에 포함하되 세 버킷에서 제외하고, 층화 표와 JSON의 별도 `0` 버킷으로 보존한다.

`--json`은 같은 집계의 `weekly`, `stratified`와 검토용 `commits`, `sessions`, `runs`를 저장한다. 커밋별 파일·태그 근거·후속수정 여부, 세션별 `tokens_by_model`, 실행별 `terminalState`, `attempts`, `humanReintervention`, `escalation`, `startedAt`, `commitHashes`를 포함한다. 경로·커밋 메시지·escalation 원문이 들어갈 수 있다. 비용 불명은 JSON `null`, 비율은 0~1이다.

## 세션 처리와 비용

assistant `message.content`의 `tool_use` 중 이름이 `Workflow`이고 `input.scriptPath`에 `spec-building/workflow.mjs` 또는 `spec-building/graph-workflow.mjs`가 포함된 호출을 찾는다. user 텍스트 및 `tool_result.content`의 텍스트에서 `<result>` 뒤 첫 `{`부터 `JSONDecoder.raw_decode`를 적용한다. `runSummary` 객체와 `terminalState`가 있는 결과만 채택한다.

`tool_use_id`가 있으면 해당 호출에 연결한다. 식별자 없는 텍스트 결과는 미완료 공정 호출이 정확히 하나일 때만 연결한다. 연결 불가 결과와 같은 호출의 중복 결과는 제외한다. 실행 시각은 결과의 `startedAt` → `runSummary.startedAt` → 호출 타임스탬프 → 세션 첫 타임스탬프 순이다. 결과 없는 호출은 `결과없음` 상태이며 escalated/pending으로 임의 분류하지 않는다. 모든 세션을 읽어 커밋의 권위 근거를 수집한 뒤 날짜 필터를 적용하므로 이전 주에 시작한 세션도 커밋 태깅에 기여할 수 있다.

assistant 레코드마다 `message.usage`의 `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`를 `message.model`별로 합산한다. 가격은 로컬 `skills/improve-token-efficiency/scripts/analyze_sessions.py`의 `PRICING` dict를 importlib로 가져온다. import 시 외부 위치에 바이트코드 캐시를 쓰지 않는다. 캐시 생성 상세가 있으면 `ephemeral_5m_input_tokens`와 `ephemeral_1h_input_tokens`에 각각 `cw5`, `cw1h` 가격을 적용하고, 없으면 생성량 전체를 5분 가격으로 계산한다.

가격표 import 실패 또는 미등록 모델이면 경고하고 해당 세션 비용은 null로 둔다. 불명 비용이 하나라도 포함된 주·태그 행은 일부 달러 합계를 전체처럼 표시하지 않고 토큰 합계만 표시한다. 알려진 모델별 토큰은 JSON에서 계속 확인할 수 있다. 가격표는 로컬 스냅샷이며 실청구서와 같다고 가정하지 않는다.

## 알려진 편향과 한계

- **자기선택 편향:** 쉬운 작업은 직접, 어려운 작업은 공정을 선택할 수 있다. 버킷 층화 표에서 같은 변경 파일 수끼리 비교한다. 파일 수가 같아도 난도·언어·작업 종류·개발자 차이는 남는다.
- 세션에 공정 호출이 하나라도 있으면 모든 비용을 pipeline으로 귀속한다. 직접 작업과 공정이 섞인 세션도 분할하지 않는다. 비용은 세션 첫 시각의 주에 전부 귀속하므로 여러 주에 걸친 사용량도 시작 주로 몰린다. 시작일 이전 세션의 후속 비용은 제외된다. 수동 커밋 태그는 세션 비용 태그를 바꾸지 않는다.
- assistant 레코드 단위 합산이다. 로그가 같은 usage를 반복 저장하거나 세션 파일을 복제하면 과대계상할 수 있다. 하위 subagents 기록·다른 도구의 사용료·세션 밖 작업은 포함하지 않는다.
- Workflow 외 호출 방식, 결과 누락, 식별자 없는 동시 공정 호출, short SHA만 있는 결과는 권위 태깅에서 누락될 수 있다. `verified`는 로그의 상태 보고이지 이 스크립트가 검증을 재실행한 결과가 아니다.
- 후속수정은 사고의 대리 신호다. 정상 후속 작업·우연히 같은 파일 수정·관계없는 제목도 잡을 수 있고, 다른 파일로 고친 버그나 다른 제목은 놓친다. 이후 커밋 하나가 여러 원래 커밋에 잡힐 수 있다. 최근 48시간 커밋은 아직 관찰 창이 완성되지 않았다. 같은 시각의 커밋은 후속으로 보지 않는다.
- 현재 HEAD에서 도달 가능한 이력만 읽는다. 커미터 시각을 사용한다. merge 변경량은 첫 부모 대비이며 가지 커밋과 merge가 모두 포함될 수 있다. git의 `--since` 순회는 시각이 역전된 특이 이력을 빠뜨릴 수 있다.
- rename 감지를 끄므로 이름 변경은 이전·새 경로 두 개로 계수한다. 바이너리는 변경 파일로 센다. 경로 이름이 바뀐 뒤의 후속수정은 연결하지 않는다.

## 검증과 실제 관찰 범위

`selftest.sh`는 지정된 mktemp 형식의 임시 디렉터리에만 합성 레포·로그·JSON을 만들고 종료 시 제거한다. 임시 레포에 고정 날짜 8개 커밋을 만들며, 원본 작업트리에는 git 쓰기 명령을 실행하지 않는다. 주간·층화 수치, 정확한 트레일러/모델명 트레일러, 수동 우선순위, afterHead 권위 경로, headLog 대안, 그래프 호출, 후속수정, 되돌림, 비용, 중복 결과, 재개입, ISO 연도와 날짜 필터를 assert한다.

실제 Plugify transcript의 처음 240줄을 제한 조회하여 관찰한 필드는 `type`, `timestamp`, `message.model`, `message.content`, `message.usage`와 네 가지 토큰 키, `cache_creation.ephemeral_1h_input_tokens`, `cache_creation.ephemeral_5m_input_tokens`이다. 추가 제한 검색에서는 user 레코드의 `toolUseResult`, `sourceToolAssistantUUID`도 확인했다. 이 두 필드는 집계 근거로 사용하지 않는다.

후속 제한 검색에서는 실제 assistant `tool_use`의 `id`, `name: "Workflow"`, `input.scriptPath`, `input.args`와 spec-building 경로를 확인했다. 연결된 user `tool_result`에는 `tool_use_id`, 문자열 `content`, `is_error`가 있었고, 본문은 백그라운드 실행 안내였다. 완료 `<result>` 결과 쌍은 제한 표본에서 확인하지 못했다. 완료 결과 형태는 사용자 제공 계약 및 레포의 workflow 결과 필드 정의를 바탕으로 구현하고 합성 기록으로 검증했다.

실제 Plugify에 `--since 2026-08-01`로 실행해 종료 코드 0을 확인했다. 당시 출력은 커밋 38개, 공정 호출 4개, verified 0개였다. 이 실행은 크래시 여부 확인이며 실전 완료 결과 파싱 성공의 증거는 아니다. 다음 실전 관찰 대상은 완료 `<result>`가 있는 호출 한 건의 원문과 집계 실행·해시를 대조하는 것이다.
