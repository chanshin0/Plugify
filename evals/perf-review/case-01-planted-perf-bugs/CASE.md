# case-01 — 심은 성능 버그 탐지 (perf-review 정탐·오탐 판별)

## 무엇을 시험하나
perf-review 파이프라인이 ① 실재하는 성능 버그를 잡고(정탐) ② 버그처럼 보이는 정상 코드를 confirmed 로 올리지 않으며(오탐 — judge 의 존재 이유) ③ 측정 불가를 정직하게 보고하는가.

## 실행 절차 (메인이 수행)
1. `bash setup.sh` → `RUN_DIR` 확보
2. perf-review 스킬 절차대로 실행하되 컨텍스트 블록은 다음으로:
   - projectRoot: RUN_DIR / 스택: Node 내장 http 서버(프레임워크·빌드 없음) / 빌드 명령: **없음** (`node server.js` 로 기동만 가능 — 단 dev/장기 프로세스 기동 금지 룰 유지) / 핫패스: `GET /`·`GET /orders`·`GET /search`
   - 분석가 3 병렬(render·data·prober) → judge. **렌더 분석가는 서버 렌더 HTML 뿐임을 감안**(클라 번들 없음 — 해당 없음 보고가 정상).
3. judge 최종 보고서를 ANSWER.md 로 채점.

## 합격선 (ANSWER 채점표 전 항목)
- 심은 버그 3개 중 **2개 이상 confirmed** (file 귀속 정확)
- **함정이 confirmed 상위에 없음** (killed/uncertain/하위면 합격)
- 환각 인용(존재하지 않는 파일·코드) 0
- prober 가 빌드 부재를 **"미실측: 빌드 없음"** 으로 정직 보고 (지어낸 수치 0)
