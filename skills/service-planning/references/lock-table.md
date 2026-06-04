# 결정성 Lock 테이블

> 이 도구가 매번 동일하게 동작하도록 고정한 선택들. 시나리오-First lock 테이블과 같은 형식.

| 변수 | 선택 (locked) | 결정성 보존 방식 |
|---|---|---|
| 스파인 | 완성 (씨앗→백본→빈칸→채우기→스코프) | 검증(Lean/PMF) 아님 |
| 입력 분류 | 씨앗 타입(기능/시나리오/화면) + 청중 스코프(n=1/니치/넓음) | 타입별 확장 + scope pruning 결정성 |
| 백본 방법 | Universal Job Map 8 + USM backbone | 매번 동일 골격 (job-map.md) |
| 빈칸 발견 | 9-카테고리 rubric (pruning 후) | 직감 아님, 고정 체크리스트 (completeness-rubric.md) |
| 빈칸 채우기 | 흔한 처리 자동 + load-bearing만 `[추정]` | 사용자 CLAUDE.md 위임모드 규칙 |
| v1 스코프 | appetite IN/OUT (walking skeleton) | 완성 = 전부 아님 |
| 근거 | pattern-researcher 인용 강제 (있을 때) | 발명 아닌 검증된 패턴 |
| 검증 | 독립 completeness-critic (또는 인-스레드 self-check) | same-context self-check보다 엄격 |
| 휴먼 게이트 | 2개 (P3 빈칸맵 · P4-5 결정/스코프), 위임모드 | Claude 완전초안 → 사용자 redirect, 질문지 아님 |
| 재진입 | 씨앗틀림→P1 / 백본틀림→P2 / 채움틀림→P4 | 최종결정=사용자 |
| 산출물 | `기획서.md` (10섹션 고정) + gaps.md | 사람가독 + 감사가능 |
| 저장 위치 | `~/Documents/service-planning/<YYYY-MM-DD>-<slug>/` | presentation_slides 선례; wiki·sources 불가침 |
| ideas repo 쓰기 | `idea quick`/`new`만 (선택), synth 절대 자동X | sources=CLI only, wiki=synthesis only, synth=user-triggered |
| 메타데이터 | tag=본문 명시 키워드만, topic=제안→confirm | 추측 금지 (ideas repo §4/§4.1) |

## 일부러 안 고정 (판단 surface — 게이트가 보호)
- 어떤 빈칸이 진짜인가
- v1에 무엇을 넣나
- 빈칸을 채우는 결정 내용
- slug 텍스트
