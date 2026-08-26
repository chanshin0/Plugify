# case-02 — persistent project context package와 실제 tree 보고

## 사용자 요구에서 역산한 시험

장기 운영할 레거시 내부 업무 서비스를 기획·현대화한다. 기획 결과만 남기지 말고 다음 세션과 서브에이전트가 재진입할 Markdown 문맥 환경을 만든다. 역할 prompt는 아래 9개 고정 탐색 주소를 가져야 하며, 기획·설계 결과 보고에는 계획이 아니라 검증 직후 실제 디렉터리 구조가 포함돼야 한다.

정적 source 단서는 실제 사용·owner·writer·정본을 증명하지 않는다. capability와 실제 workflow 발견이 architecture·migration 승인보다 먼저다. 단순 기획에는 이 package를 강제하지 않는다.

## 시험 범위

이 케이스의 결정적 코드는 LLM을 실행해 산출물 품질을 판정하는 end-to-end 시험이 아니다. 요청 fixture가 legacy profile을 활성화해야 한다는 **지시 계약**, package validator의 구조·우회 방지, 출하 asset의 존재를 고정하는 회귀 시험이다. 실제 지시 이행은 이번 아침지기 forward test와 fresh/blind review로 보완하고, 출하 뒤 첫 실제 프로젝트 1회는 `SYSTEM.md §3.1`의 첫 실전 관찰로 별도 닫는다. forward test를 그 관찰의 대체 증거로 쓰지 않는다.

## 결정적 계약 시험

`python3 check-contract.py [setup.sh가 출력한 REQUEST 경로]`는 아래 19개 이름의 테스트를 실행한다. 인자를 생략하면 저장된 `fixture/REQUEST.md`를 읽는다.

1. `explicit_legacy_request_contract`
2. `valid_legacy_package`
3. `missing_prompt_rejected`
4. `missing_prompt_heading_rejected`
5. `fenced_heading_rejected`
6. `orchestrator_route_gap_rejected`
7. `commented_route_rejected`
8. `stale_actual_tree_rejected`
9. `fenced_tree_rejected`
10. `long_fence_rejected`
11. `trailing_text_fence_rejected`
12. `raw_html_structure_rejected`
13. `processing_instruction_structure_rejected`
14. `flattened_tree_rejected`
15. `legacy_discovery_gap_rejected`
16. `conflicting_profile_rejected`
17. `invalid_profile_rejected`
18. `valid_nonlegacy_package`
19. `shipped_contract_assets`

validator는 package의 최소 정본, 보고서가 자가 선언한 profile, 정확한 9개 prompt, 각 prompt의 공통 8절, 00의 전체 route, legacy 추가 3문서, `DELIVERY-REPORT.md` tree leaf set과 실제 file set의 exact match를 판정해야 한다. 호출자가 legacy flag를 빼도 보고서가 `legacy-modernization`이면 discovery 3문서를 요구한다.

## 실행

1. `bash setup.sh`로 요청 fixture를 격리 사본에 두고 출력된 `REQUEST` 경로를 기록한다.
2. `python3 check-contract.py <REQUEST 경로>`를 실행한다. 하니스가 그 요청을 실제로 읽어 활성화 계약과 첫 실전 관찰 선언을 검사한다.
3. 별도 fresh/blind reviewer에게 SKILL·reference·agent·validator·CASE/ANSWER만 주고 다음을 검토시킨다.
   - 단순 deep 기획을 부당하게 persistent profile로 승격하지 않는가.
   - legacy discovery gate 전 architecture/data model/cutover 확정을 막는가.
   - 고정 9개 파일이 generic placeholder가 아니라 프로젝트 정본·gate에 맞게 구체화되도록 요구하는가.
   - 보고 tree가 파일명 언급만으로 우회되지 않고 실제 file set과 대조되는가.

## 합격선

- 19개 결정적 테스트가 이름·개수 그대로 전부 PASS한다. 하니스가 실행 이름을 manifest와 exact 비교하므로 실행 누락도 실패다.
- 기존 case-01 completeness critic 회귀가 다시 합격한다.
- 아침지기 forward test package가 동일 validator를 통과하고 fresh/blind reviewer가 BLOCKER 0으로 판정한다.
- `SYSTEM.md §3.1`에 출하 후 첫 실제 사용 관찰이 열려 있어야 하며, forward test로 이를 닫지 않는다.
- 신규 케이스는 reviewer 판정 전까지 draft이며 `confirmed-cases.txt`에 넣지 않는다.
