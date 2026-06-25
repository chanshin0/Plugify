# STATE — app (eval fixture, 초기/commit1)

## 다음 task
### 목표
Bug-12(상세 페이지 가격이 항상 "0원") 수정.
### 게이트
- auto: `GET /item/42` 응답에 `"price":12900` 포함 (현재 0) — 통과 신호: 실제 가격 표시
### 비가역 표면
없음(읽기 경로)
