# STATE — 진행 상태 (변형: 라이브 게이트 포함 — v1 범위 밖)

## 현재 위치
- 단계: 라이브 게이트 반려 시험용 — task 목표에 {PREVIEW_URL} 포함.

## 다음 task

### 목표
그래프 task 에 라이브 프리뷰 프로브({PREVIEW_URL})가 섞여 있다. 그래프 실행 v1 은 라이브 게이트를 다루지 않으므로 시작 시 fail-fast 반려하고 단일 task 경로(workflow.mjs)로 안내해야 한다.

### 그래프
```json
{
  "tasks": [
    {"id":"T1","goal":"src/util.js 구현 후 curl {PREVIEW_URL}/health 로 프리뷰에서 확인","targets":["src/util.js"],"depends":[]},
    {"id":"T2","goal":"src/calc.js 구현","targets":["src/calc.js"],"depends":["T1"]}
  ],
  "verify": "node --test test/*.test.js"
}
```

### 비가역 표면
- 없음
