---
name: tech-deciding
description: 되돌리기 비싼 기술/아키텍처 결정을 추측이 아니라 기능→난제→축별 웹조사→종합→적대검증→ADR 로 내린다. "스택 정해", "어떤 프레임워크/DB/라이브러리 쓸지", "기술 선정", "아키텍처 결정", "이거 뭐로 만들지", "조사하고 선정해" 등에 트리거. 기획(service-planning) 다음, 구현(spec-building) 전 단계.
---

# tech-deciding — 기술 결정 → ADR

되돌리기 비싼 기술 선택(스택·프레임워크·인프라·라이브러리)을 *추측이 아니라 기능에서 역산*해 내린다: 기능→기술난제 정의 → 난제 축별 격리 웹조사(최신·cited) → 종합 선정 → 적대 검증 → ADR 산출.

## 선행 조건
- 기획 산출물(`.planning/planning/`)이 있으면 난제 도출에 쓴다(없어도 `question` 만으로 가능).
- 워크플로우 결과는 먼저 `.planning/decisions/NNN-<slug>.md.proposed` 로 남긴다. 사용자가 승인한 뒤 메인이 최종 `.md`로 승격해야 다음 단계 spec-building 의 SSOT 가 된다.

## 실행
메인은 **① 타깃 포인터 파일(JSON 1줄)을 먼저 쓰고** ② Workflow 도구로 이 스킬 디렉토리의 `workflow.mjs` 를 절대경로로 실행한다:
```
echo '{"question":"<결정할 질문>","projectRoot":"<레포 절대경로>","adrPath":".planning/decisions/NNN-<slug>.md"}' \
  > /tmp/tech-deciding.target   # 정본 채널 — args 는 하니스에 따라 미전달(2026-06-11 실증). question 까지 필요해 JSON 포맷(spec-building 의 경로 1줄과 다름)
Workflow({ scriptPath: "<이 스킬 디렉토리 절대경로>/workflow.mjs",
           args: { question: "<결정할 질문>", projectRoot: "<레포 절대경로>",
                   adrPath: ".planning/decisions/NNN-<slug>.md" } })
```
- 워크플로우는 question·projectRoot 를 해석·검증하고, 무효면 **조용한 폴백 없이 즉시 실패**한다(placeholder question 으로 비싼 조사 낭비 금지·엉뚱한 레포 실행 차단).
- `adrPath` 상대경로는 `pwd -P`로 확인한 projectRoot 기준 canonical 절대경로로 정규화되며, 루트 밖으로 탈출하는 경로는 조사 전에 거부한다.
- 진행: define(sonnet 난제 매핑) → researcher(sonnet) **축별 병렬** 조사 → 기록(haiku — 인스턴스 프롬프트·조사 원문을 `<타깃>/.planning/runs/<날짜>-tech-deciding/` 에 정착, 증거·비파괴) → synthesize(opus, 출처 URL 보존 의무) → critique(opus 적대검증) → ADR **제안**(`.md.proposed`, haiku Write, 출처 부족 시 run 조사 원문에서 회수) → 독립 read-only 증거로 proposed 실재·SHA-256·상태 문구·현재 `proposal_run_id` 결속·최종 ADR 불변·다른 decision 파일 불변을 대조 → 확인되면 `terminalState=pending-human`, 아니면 `proposal-failed`. 과거 실행의 stale `.proposed`는 현재 run 표식이 없어 승인 대상으로 승격되지 않는다.
- 에이전트(`agents/researcher.md`)는 plugify 전역등록되어 `agentType: researcher` 로 호출된다(모델·규칙은 `.md` SSOT).
- 산출: 선정안 + 적대 검증 + ADR 제안 파일. 최종 ADR은 사용자 승인 후에만 생성한다.

## 게이트 (메인 직접)
- 선정안은 load-bearing 결정이므로 메인이 **사용자에게 제시·확인**한다(서브에이전트는 사용자와 대화 못 함). 승인 전에는 `.proposed`를 최종 경로로 이름 바꾸거나 상태를 채택으로 바꾸지 않는다. 승인 후 메인이 critique 반영 여부를 확인하고 최종 `.md`를 기록한다.
- critique 가 짚은 약점은 ADR "뒤집을 조건" 에 반영한다.

## 금지
- 조사 없이 추측 선정 · 에이전트 함대화(축 1개당 researcher 1개) · 출처 없는 주장 · 사용자 확인 없이 load-bearing 결정 확정.
