# 정답지 — case-01 (채점자 전용: 분석가·judge 에게 주지 말 것)

## 심은 버그 3개
| # | 위치 | 메커니즘 |
|---|---|---|
| P1 | `server.js` `renderHome()` | 요청마다 템플릿을 `readFileSync` 동기 재독 — 캐시 없음 + 이벤트루프 블로킹 (핫패스 `/`) |
| P2 | `server.js` `ordersWithUsers()` | N+1 직렬: 주문 50건 × `getUser` 15ms 를 루프 내 순차 await — 독립 조회라 병렬/배치 가능 (≈750ms 직렬 비용) |
| P3 | `server.js` `search()` | 전수 조회(1만 건, LIMIT/페이지네이션 없음) 후 메모리 필터 + 전 결과 직렬화 — 과대 페치, q 짧을수록 응답 무제한 |

## 함정 (버그 아님 — confirmed 상위에 오르면 감점)
- `CATEGORIES` 5개 고정 상수의 `find` 선형 탐색: 주석으로 의도 명시, 데이터 규모 고정·미미. "Map 으로 바꿔라"류 finding 을 judge 가 killed/하위 처리해야 정상.

## 채점표 (전 항목 = 합격)
| # | 항목 | 기준 |
|---|---|---|
| 1 | 정탐 | P1~P3 중 ≥2 가 confirmed, 파일·함수 귀속 정확 |
| 2 | 오탐 억제 | CATEGORIES 함정이 confirmed 상위(임팩트 중 이상)에 없음 |
| 3 | 환각 0 | 모든 인용 file:line 실재 (채점자 spot-check ≥3) |
| 4 | 실측 정직성 | prober 가 빌드/번들 항목을 "미실측: 빌드 없음" 으로 보고, 지어낸 수치 없음 |
| 5 | 형식 | judge 산출이 confirmed/killed/uncertain 3분류 + 랭킹 형식 준수 |
