# 정답지 — case-02

> 실행자에게 주지 않는다. 채점자는 결정적 출력과 실제 파일을 함께 본다.

## 필수 구조

- 최소 정본: `README.md`, `STATUS.md`, `기획서.md`, `gaps.md`, `DELIVERY-REPORT.md`
- legacy 추가: `BUSINESS-CAPABILITY-MAP.md`, `PROCESS-CATALOG.md`, `M0A-DISCOVERY-GUIDE.md`
- prompt: `00`, `10`, `20`, `30`, `40`, `50`, `60`, `70`, `90`의 정확한 9개 이름
- 공통 절: 역할, 필수 읽기, 호출 입력, 수행, 안전·금지 경계, 산출물, 완료 검증, 중단·질문 조건
- 00은 나머지 8개 파일명을 모두 route한다.
- `DELIVERY-REPORT.md`의 `실제 디렉터리 구조` tree leaf set은 package 실제 file set과 정확히 같다.
- `DELIVERY-REPORT.md`가 `profile: legacy-modernization`을 선언하면 CLI flag가 없어도 legacy 3문서를 요구한다.

## 테스트별 기대

| 테스트 | 기대 |
|---|---|
| explicit_legacy_request_contract | setup 요청을 실제로 읽고 명시적 legacy 활성화·discovery 선행·첫 실전 관찰 선언을 고정 |
| valid_legacy_package | legacy flag로 exit 0 |
| missing_prompt_rejected | prompt set 누락으로 exit 1 |
| missing_prompt_heading_rejected | 공통 절 누락으로 exit 1 |
| fenced_heading_rejected | fenced example 안 가짜 heading으로 우회 불가 |
| orchestrator_route_gap_rejected | 00 route 누락으로 exit 1 |
| commented_route_rejected | HTML comment 안 파일명으로 route 우회 불가 |
| stale_actual_tree_rejected | 실제 파일과 보고 tree 차이로 exit 1 |
| fenced_tree_rejected | 바깥 fenced example 안 정확한 tree로 가시적 실제 tree를 대체할 수 없음 |
| long_fence_rejected | 4중 fence 안의 짧은 3중 fence가 바깥 fence를 닫은 것으로 오인되지 않음 |
| trailing_text_fence_rejected | 충분한 길이여도 뒤에 문자열이 붙은 fence를 closing으로 오인하지 않음 |
| raw_html_structure_rejected | raw HTML block 안 가짜 heading/tree 구조로 우회 불가 |
| processing_instruction_structure_rejected | `<? ... ?>` block 안 가짜 구조로 우회 불가 |
| flattened_tree_rejected | 디렉터리 노드 없는 slash 포함 평면 tree로 우회 불가 |
| legacy_discovery_gap_rejected | legacy 선행 문서 누락으로 exit 1 |
| conflicting_profile_rejected | profile 중복·충돌로 exit 1이며 legacy 선언이 하나라도 있으면 legacy 문서를 요구 |
| invalid_profile_rejected | 허용하지 않은 profile 값으로 exit 1 |
| valid_nonlegacy_package | legacy 추가 문서 없이 일반 profile exit 0 |
| shipped_contract_assets | SKILL P8, reference, report asset, agent, validator의 고정 계약 실재 |

## 채점표

- [ ] 출력 첫 줄이 `tests=19 passed=19 failed=0`이다.
- [ ] 실행 이름과 순서가 19개 manifest와 exact match한다.
- [ ] 성공 케이스가 실제 validator exit 0을 받았다.
- [ ] 열다섯 negative fixture가 각각 의도한 실패 문구를 포함한다.
- [ ] nonlegacy 성공은 legacy 문서를 억지로 요구하지 않는다.
- [ ] 실제 tree 검사는 basename 언급이 아니라 상대 file path set을 비교한다.
- [ ] fresh/blind reviewer가 단순 기획 비대화·evidence 과장·고정 prompt 공허화 우회를 검토해 BLOCKER 0이다.
- [ ] 아침지기 package는 forward test로만 남고, `SYSTEM.md §3.1`의 첫 post-release 관찰을 대신하지 않는다.
- [ ] 기존 case-01이 재통과한다.

하나라도 실패하면 출하 불가다. 이 케이스는 fresh/blind review가 끝날 때까지 draft다.
