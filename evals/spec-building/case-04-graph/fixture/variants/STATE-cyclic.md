# STATE — 진행 상태 (변형: 순환 그래프 — 무효)

## 현재 위치
- 단계: 무효 그래프 시험용 — T1↔T2 상호 의존(순환).

## 다음 task

### 목표
순환 의존 그래프. 워크플로우는 위상정렬 실패로 구현 진입 전 반려해야 한다.

### 그래프
```json
{
  "tasks": [
    {"id":"T1","goal":"util 구현","targets":["src/util.js"],"depends":["T2"]},
    {"id":"T2","goal":"calc 구현","targets":["src/calc.js"],"depends":["T1"]}
  ]
}
```

### 비가역 표면
- 없음
