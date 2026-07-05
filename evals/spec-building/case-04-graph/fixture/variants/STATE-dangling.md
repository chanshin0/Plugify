# STATE — 진행 상태 (변형: dangling depends — 무효)

## 현재 위치
- 단계: 무효 그래프 시험용 — 실재하지 않는 id(TX) 참조.

## 다음 task

### 목표
depends 가 실재하지 않는 task id 를 가리킨다. 워크플로우는 dangling 참조로 구현 진입 전 반려해야 한다.

### 그래프
```json
{
  "tasks": [
    {"id":"T1","goal":"util 구현","targets":["src/util.js"],"depends":["TX"]}
  ]
}
```

### 비가역 표면
- 없음
