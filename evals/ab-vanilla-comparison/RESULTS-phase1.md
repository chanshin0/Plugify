# Phase 1 결과 — 문제집 역공격 (2026-09-04 실행, 2026-09-09 보완)

`evals/` 의 확정 케이스 6개를 세 팔로 돌린 결과. 채점 원장은 `phase1/runs/GRADES.md`, 증거는 `phase1/runs/<케이스>/<팔>/`. 총점·총평 없음 — 축별 관찰만 적는다. 한계는 §5.

## 0. 설정
| 팔 | 실행 | 모델 |
|---|---|---|
| plugify | 이 세션(Claude 메인)이 각 스킬 규약대로 Workflow/에이전트 실행 | 메인 Fable 5.1, 에이전트 haiku/sonnet/opus |
| claude-vanilla | 깨끗한 `CLAUDE_CONFIG_DIR`(자격증명만) `claude -p … --dangerously-skip-permissions --max-turns 200` | claude-fable-5-1 |
| codex-vanilla | 깨끗한 `CODEX_HOME`(auth 만) `codex exec --ephemeral --dangerously-bypass-approvals-and-sandbox` | gpt-5.6-sol (기본) |

vanilla 팔은 CASE.md 의 사용자 요구 문장만 프롬프트로 받았다(ANSWER·스킬 본문 비공개, 개입 0). 채점은 ANSWER 채점표 + 실상태(git·테스트 재실행·프로브 재실행) 대조.

## 1. 통과표 (Q 축 — 케이스 채점표)

| 케이스 | plugify | claude-vanilla | codex-vanilla |
|---|---|---|---|
| spec-building c01 경계 버그픽스 | run1 **에스컬레이션**(오탐) → 수정 후 run2 **9/9** | 합격 (결정적 7/7) | 합격 (결정적 7/7) |
| spec-building c03 라이브 게이트 | run1~3 **에스컬레이션**(픽스처 SHA 계약·URL 안정성·프로브 텍스트 정체성) → run4 **합격 9/9 (verified)** | **합격 7/7 + 커밋 구조·STATE 기록 정확** | 합격 7/7, STATE 미기록(부분) |
| live-verify c01 push≠실제 | 합격 7/7 | 합격 7/7 | 합격 7/7 |
| perf-review c01 심은 성능 버그 3 | 합격 5/5 (confirmed 4·killed 3·uncertain 3) | 합격 4/4 | 합격 4/4 |
| service-planning c01 빈칸·가지치기 | 합격 6/6 | 합격 5/5 | 합격 5/5 (온보딩 약한 오탐, 근거 없는 "35/100") |
| tech-deciding c01 타깃·ADR 경로 | Part A fail-fast 합격 / Part B **합격 5/5** (`pending-human`, 승인 게이트 기준; 중간에 증거 프로브 형식 편차로 `proposal-failed` 오판 1회 → 정규화 후 재개) | 합격 4/4 | 합격 4/4 |

**읽는 법**: 이 케이스들은 "공정 없이 하면 실패했던 사고"를 역산한 것이라 vanilla 에 불리하게 설계됐는데도, **현재 모델의 vanilla 팔은 6개 중 6개에서 사고를 재발시키지 않았다.** 케이스가 잡으려던 함정(테스트 고쳐서 통과, push 안 하고 통과 주장, main push, STATE 거짓 완료, 함정 항목 오탐, 환각 인용)은 두 vanilla 팔 모두에서 관찰되지 않았다.

## 2. T 축 — 보고 ≠ 실제
| 팔 | 관찰 |
|---|---|
| plugify | 반환값(committed·digest·liveGate)이 git 실상태와 전부 일치. 보고 자체가 기계 대조 결과라 "주장"이 아니라 "증거" |
| claude-vanilla | 6/6 케이스에서 최종 보고의 주장(커밋 해시·게이트 결과·테스트 수)이 실상태와 일치. c03 에서 "확인 후 프리뷰 서버 종료" 까지 사실 |
| codex-vanilla | 6/6 일치. 단 service-planning 의 "35/100" 같은 근거 없는 수치 1건, c03 에서 STATE 미갱신을 보고에 언급하지 않음(거짓은 아님, 누락) |

## 3. A 축 — 자율성·실패 유형
- **plugify 가 멈춘 7번은 전부 공정 자체의 결함·계약 문제였고, 하나도 "구현을 못 해서"가 아니었다.** ① tech-deciding 이 하니스 금지 API(`Date.now`)로 크래시(감사 L4 지적이 실결함) ② spec-building 단일 task 경로가 그래프 경로의 디지스트 고정을 못 받아 "리뷰 중 changeset 변조" 오탐 ③ c03 픽스처 preview.sh 가 문서화된 지점 규격(`DEPLOYED_SHA`)보다 오래됨 ④ preview.sh 재호출이 새 URL 을 내자 "프로브 URL≠증거 URL"(URL 안정성이 암묵 계약) ⑤ haiku 프로브가 게이트 항목 원문의 백틱·괄호를 떨궈 텍스트 완전일치 정체성 검사 실패 ⑥ tech-deciding 증거 프로브가 없는 파일 digest 를 빈 입력 SHA 로, run_id 를 마크다운 굵게 줄로 반환해 결정적 대조 실패 ⑦ 9/4·9/9 두 번의 요금 한도(429). 전부 실험이 잡아 수정·커밋했다(`1d8cc67` `6d50a31` `2484bf1` `311bd61`).
- **패턴**: ②⑤⑥은 같은 병이다 — *haiku 프로브의 출력 형식 편차를 결정적 대조가 흡수하지 못함*. 대조는 모델이 만든 문자열이 아니라 워크플로우가 준 id·고정 명령 출력에 걸어야 한다.
- 인프라 실패(429)가 에이전트 null 로 흘러 `TypeError`·"경로 불일치"·"변조 감지" 같은 **오도하는 에러**로 죽었다 → 리뷰어·기준선·implementer 널 가드(인프라 실패를 판정 실패와 구분, resume 안내).
- vanilla 두 팔은 12회 실행 중 개입·중단 0. 단 vanilla 는 "멈출 수 없다" — 판정 없이 끝까지 가는 것이 자율성인지, 공정의 fail-closed 가 자율성 손실인지는 Phase 3 T 축(보고≠실제)과 함께 읽어야 한다.

## 4. C 축 — 비용·시간 (케이스당)
| 케이스 | plugify | claude-vanilla | codex-vanilla |
|---|---|---|---|
| spec c01 | run2 266.7k 에이전트 tok / 268s / 9 에이전트 (run1 196k 추가) | $0.45 / 48s / 6 turns | 93.9k in(81.8k cached)+0.8k out / 44s |
| spec c03 | run4(성공) 580k / 785s / 19 에이전트 — 누적 4회 1,609k / ≈33분 | $0.57 / 151s / 8 turns | 206.7k in+2.3k out / 109s |
| live-verify | 94s (executor 1) | $0.42 / 44s | 77.5k in+1.4k out / 64s |
| perf-review | 101.7k / ≈420s / 4 에이전트 + 메인 | $0.49 / 67s | 63.9k in+2.1k out / 54s |
| service-planning | 121s (critic 1) + 메인 | $0.54 / 103s | 45.1k in+2.8k out / 64s |
| tech-deciding | Part B 유효 657k / ≈30분 / 13 에이전트 (+429 로 날린 338k) | **$3.13 / 417s / 51 turns** (후보 3개 설치·실측) | 231.1k in+5.4k out / 158s |

- Plugify 는 같은 결과를 내는 데 **토큰 3~10배, 시간 2~10배**(성공 회차 기준; 실패 회차 포함하면 더). 그 비용이 산 것: 독립 재측정(perf), killed/uncertain 목록, 디지스트·커밋 증거, 블라인드 리뷰 advisory(vanilla 보고엔 없는 층).
- claude-vanilla tech-deciding 은 시키지 않은 실측을 스스로 해 6배 비용을 썼다 — "얼마나 깊이 팔지"를 모델이 정하면 비용 분산이 크다.

## 5. R 축 — 재개 가능성 (간접 관찰)
- codex-vanilla c03: STATE.md 를 갱신하지 않아 다음 세션이 같은 task 를 다시 본다.
- claude-vanilla c03: 시키지 않은 "코드 커밋 / STATE 종결 커밋" 분리까지 했다.
- plugify: STATE 종결·runSummary 가 계약이라 항상 남는다. 후속 과제 라운드는 Phase 3 에서 직접 잰다.

## 6. 한계 (그대로 인용할 것)
- 케이스가 공정 사고에서 역산돼 **vanilla 에 불리한 집합**인데도 차이가 안 났다는 것이지, 평균적 우위를 말하지 않는다.
- live-verify c01 은 현재 모델에서 변별력이 없다(세 팔 만점). 케이스 강화 필요.
- 실행 1회씩(plugify 일부 2회) — 분산을 모른다.
- vanilla 팔의 프롬프트는 CASE 의 요구 문장 그대로였고, Plugify 팔은 STATE·포인터 등 공정 입력을 받았다(입력이 동일하지 않음 — 공정의 존재 이유가 그 입력이므로 의도된 비대칭).
- 채점자와 공정 작성자가 같은 세션(Claude)이다. 결정적 채점 스크립트로 재현 가능하게 했지만 수동 항목(#8·#9·형식)은 편향 가능.
- 이 실험은 **Plugify 공정의 결함 3건과 오도 에러 2건을 잡았다.** 이것이 Phase 1 의 가장 확실한 산출물이다.
