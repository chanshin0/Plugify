# 기획 프레임워크 응축 — 도구가 흡수하는 이론

> 각 프레임워크가 "씨앗 → 완전한 서비스" 어디에 기여하는지. 깊은 배경은 README.md, 여기는 *실행용 응축*.

---

## 스파인 (5단계)
① 씨앗 정착 → ② 타입 분류 → ③ 백본/여정 매핑 → ④ 빈칸 발견 → ⑤ 빈칸 채우기 + v1 스코프.

---

## 프레임워크 → 단계 매핑

| 프레임워크 | 출처 | 기여 | 도구 단계 |
|---|---|---|---|
| **User Story Mapping** | Jeff Patton, *User Story Mapping* (2014); jpattonassociates.com | backbone(좌→우 활동) + ribs(세부) + walking skeleton(최소슬라이스). 빈 backbone = 빠진 것 | P2 백본, P5 스코프 |
| **Universal Job Map** | Tony Ulwick, HBR 2008; jobs-to-be-done.com | 모든 일의 8보편단계. 씨앗 주변 완성 체크리스트 | P2 백본 (job-map.md) |
| **Example Mapping** | Matt Wynne, Cucumber; cucumber.io/docs/bdd/example-mapping | Rules/Examples/**Questions** — Questions가 미결정 표면화 | P3 빈칸, P4 결정, §9 |
| **UI Stack (5 states)** | Scott Hurff, "Why Your UI Is Awkward"; scotthurff.com | 모든 화면 ideal/empty/loading/partial/error | P4 (rubric 4), §6 |
| **Use Case Extensions** | Alistair Cockburn, *Writing Effective Use Cases* | primary/alternate/exception 플로우 | P4 (rubric 5), §6 |
| **Service Blueprint** | G. Lynn Shostack (1984); nngroup.com | frontstage/backstage/line of visibility — 보이지 않는 인프라 | P3 (rubric 1·6) |
| **Customer Journey Map** | nngroup.com "Journey Mapping 101" | before/during/after, 터치포인트 | P2 백본 |
| **Shape Up appetite** | Ryan Singer, Basecamp; basecamp.com/shapeup | 시간예산으로 v1 IN/OUT. 완성≠전부 | P5 스코프 |
| **PRD 강제함수** | Lenny Rachitsky; Amazon Working Backwards (PR/FAQ); Intercom A4 test | 문제진술·범위·릴리스 섹션이 빠진 부분 직면 강제 | P1 정착, §전체 |
| **ISO 25010** | 품질모델 8특성 | NFR 완성 (성능·보안·프라이버시·접근성…) | P3 (rubric 8), §8 |

---

## 핵심 원리 (도구가 따르는 것)

1. **씨앗은 happy/ideal/Execute만 담는다** — 완성은 그게 전제하는 주변을 역산하는 일.
2. **빈 backbone 단계 = 빠진 것** (USM). 결정성 있게 8단계로 스캔.
3. **모든 화면 5상태** (Hurff). ideal만 그린 화면은 미완성.
4. **happy path → alternate → exception** (Cockburn). 씨앗은 primary일 뿐.
5. **완성 = 전부 아님** (Shape Up). appetite로 v1을 자르고 나머지는 deferred로 명시.
6. **Questions는 채우지 말고 올린다** (Example Mapping). 모르는 건 Open questions로.
7. **스코프 인지** — 청중에 따라 rubric pruning. 개인 도구에 엔터프라이즈 빈칸 강요 금지.
