---
name: tech-deciding
description: 되돌리기 비싼 기술/아키텍처 결정을 추측이 아니라 기능→난제→축별 웹조사→종합→적대검증→ADR 로 내린다. "스택 정해", "어떤 프레임워크/DB/라이브러리 쓸지", "기술 선정", "아키텍처 결정", "이거 뭐로 만들지", "조사하고 선정해" 등에 트리거. 기획(service-planning) 다음, 구현(spec-building) 전 단계.
---

# tech-deciding — 기술 결정 → ADR

되돌리기 비싼 기술 선택(스택·프레임워크·인프라·라이브러리)을 *추측이 아니라 기능에서 역산*해 내린다: 기능→기술난제 정의 → 난제 축별 격리 웹조사(최신·cited) → 종합 선정 → 적대 검증 → ADR 산출.

## 선행 조건
- 기획 산출물(`.planning/planning/`)이 있으면 난제 도출에 쓴다(없어도 `question` 만으로 가능).
- 결과는 `.planning/decisions/NNN-<slug>.md` ADR 로 남긴다(다음 단계 spec-building 의 SSOT).

## 실행
메인은 Workflow 도구로 **이 스킬 디렉토리의 `workflow.mjs`** 를 절대경로로 실행한다:
```
Workflow({ scriptPath: "<이 스킬 디렉토리 절대경로>/workflow.mjs",
           args: { question: "<결정할 질문>", projectRoot: "<레포 절대경로>",
                   adrPath: ".planning/decisions/NNN-<slug>.md" } })
```
- 진행: define(sonnet 난제 매핑) → researcher(sonnet) **축별 병렬** 조사 → synthesize(opus) → critique(opus 적대검증) → ADR(haiku Write).
- 에이전트(`agents/researcher.md`)는 plugify 전역등록되어 `agentType: researcher` 로 호출된다(모델·규칙은 `.md` SSOT).
- 산출: 선정안 + 적대 검증 + ADR 파일.

## 게이트 (메인 직접)
- 선정안이 load-bearing(되돌리기 비쌈)이면 메인이 **사용자에게 제시·확인**한다(서브에이전트는 사용자와 대화 못 함). 추정은 표시해 사용자가 쉽게 뒤집게.
- critique 가 짚은 약점은 ADR "뒤집을 조건" 에 반영한다.

## 금지
- 조사 없이 추측 선정 · 에이전트 함대화(축 1개당 researcher 1개) · 출처 없는 주장 · 사용자 확인 없이 load-bearing 결정 확정.
