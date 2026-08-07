# service-planning — 나를 위한 설명서

> 이 문서는 **배경지식 + 이론→도구 매핑**이다. "기획 이론(프로세스)엔 이런 단계가 있고, 이 도구가 그걸 어떻게 채우는가"를 이해하기 위한 것. 마케팅 아님, 레퍼런스.

---

## 1. 이 도구가 푸는 문제

내 아이디어는 보통 **씨앗 하나**로 떠오른다 — 핵심 기능 1개("회의 녹음에서 할 일 추출"), 핵심 시나리오 1개("3개월 전 대화 찾기"), 혹은 화면 하나의 모습("식물 물주기 대시보드").

그 씨앗은 *서비스의 한 점*일 뿐이다. 실제 사용자에게 내놓을 수 있는 서비스가 되려면 — 그 기능에 도달하는 화면, 데이터가 없을 때의 모습, 실패했을 때, 권한, 설정, 다음에 일어나는 일 — 빠진 게 많다.

이 도구는 그 **빠진 부분을 체계적으로 찾아(빈칸 발견) 구체적 기획으로 채운다(빈칸 채우기).**

⚠ **이건 "이 아이디어가 될까?"를 묻는 검증(discovery) 도구가 아니다.** 그건 시장·PMF·지불의사를 따지는 다른 일이다. 이 도구는 *"이미 만들기로 한 씨앗을 완전한 서비스로 구체화"*(elaboration)하는 데 집중한다. (불확실/위험은 기획서 §9에 가볍게 플래그만 남긴다.)

---

## 2. 기획 이론의 단계 (배경지식)

성공적 기획팀이 하나의 씨앗을 완전한 스펙으로 확장하는 프로세스는, 이론이 달라도 **5단계**로 수렴한다. 각 단계의 이론적 출처와 *왜 필요한지*:

**① 씨앗 정착 (anchor)**
- 모호한 한 줄을 *정밀한* 한 줄로. 시나리오면 Job Story(`When/I want to/so I can`), 기능이면 "누가·무엇을·왜".
- *왜*: Amazon Working Backwards(PR/FAQ)·Intercom의 "A4 test"가 보여주듯, 한 장에 맑게 안 써지면 사고가 안 맑은 것. 정착이 안 되면 뒤의 모든 확장이 흔들린다.

**② 타입 분류 (기능/시나리오/화면)**
- 씨앗 타입마다 확장 진입각이 다르다. 기능은 *주변 lifecycle*, 시나리오는 *대안/예외 경로*, 화면은 *상태와 연결 화면*이 주로 빠진다.

**③ 백본 / 여정 매핑**
- 씨앗이 사는 *전체 여정*을 그린다.
- **User Story Mapping** (Jeff Patton, 2014): 사용자 활동을 좌→우 backbone으로 늘어놓고, 세부를 아래(ribs)로. **빈 backbone 칸 = 빠진 것.** "walking skeleton"(각 칸 최소 1개)이 MVP 슬라이스.
- **Universal Job Map** (Tony Ulwick, HBR 2008): *모든 일*은 8단계 — Define·Locate·Prepare·Confirm·**Execute**·Monitor·Modify·Conclude. 씨앗은 보통 Execute 1개만 담는다. 나머지 7개가 빠진 것의 1차 후보. → 이게 이 도구의 핵심 결정성 체크리스트.

**④ 빈칸 발견 (gap detection)**
- 백본 위에서 *무엇이 빠졌나*를 rubric으로 스캔. 이 도구의 심장.
- **UI Stack** (Scott Hurff): 모든 화면은 5상태 — ideal/empty/loading/partial/error. 씨앗은 ideal만 담는다.
- **Use Case Extensions** (Alistair Cockburn): happy path(primary) 외에 alternate·exception 플로우.
- **Example Mapping** (Matt Wynne): 채우다 나온 *미결정 질문*(Questions)을 표면화 — 모르는 건 채우지 말고 올린다.
- **Service Blueprint** (Shostack) / Journey Map: 보이지 않는 backstage·before/after.
- **ISO 25010**: 비기능(성능·보안·프라이버시·접근성)도 완성의 일부.

**⑤ 빈칸 채우기 + v1 스코프**
- 빈칸마다 구체적 결정. 흔한 처리(에러=토스트, 빈상태=CTA)는 바로, 중요한 가정만 표시.
- **Shape Up appetite** (Basecamp): *완성 = 전부 아님.* 시간 예산으로 v1에 넣을 것(walking skeleton)과 미룰 것을 자른다.

---

## 3. 도구가 각 단계를 어떻게 채우나 (이론 → 동작 매핑)

| 이론 단계 / 프레임워크 | 도구 파이프라인 | 기획서 산출물 |
|---|---|---|
| 씨앗 정착 (Job Story, A4 test) | **P1** | §2 정착된 Job |
| 타입 분류 (기능/시나리오/화면) | **P0** | §1 씨앗 |
| Universal Job Map 8단계 (Ulwick) | **P2** 백본 매핑 | §3 백본/여정 맵 |
| User Story Mapping backbone (Patton) | **P2** | §3 |
| 9-카테고리 완성 rubric | **P3** 빈칸 발견 | §4 빈칸 맵 ★ |
| UI Stack 5상태 (Hurff) | **P4** | §6 화면/플로우 |
| Alternate/Exception (Cockburn) | **P4** | §6 |
| Example Mapping Questions (Wynne) | P3~P4 | §9 Open questions |
| ISO 25010 NFR | **P3** | §8 비기능 |
| Shape Up appetite (Singer) | **P5** 스코프 | §7 v1 스코프 |
| Completeness 검증 | **P5b** self-check(napkin) / `completeness-critic`(standard+) | §10 Completeness 체크 |
| 기획서 합성 (결정·스코프·10섹션) | **P4~P5** `plan-writer` 단일 에이전트 | `기획서.md`·`gaps.md` |
| lo-fi 와이어프레임 (선택) | **P6** `wireframe-builder` 단일 에이전트 | `wireframes.html` |
| v1 데이터 모델 (선택) | **P7** `data-model-builder` 단일 에이전트 | `data-model.md` |

파이프라인 P0~P7 전체와 인터뷰·승인 경계는 `SKILL.md` §C 참고.

---

## 4. 9-카테고리 완성 rubric (무엇을, 왜 잡나)

P3에서 씨앗에 돌리는 체크리스트 (상세: `references/completeness-rubric.md`):

1. **여정 단계** — Job Map 8단계 중 빈 칸 (가장 흔한 누락)
2. **역할/페르소나** — 1인? 팀? admin? (n=1이면 스킵)
3. **주변 화면 + entry/exit** — 도달·다음·이탈 경로
4. **UI 상태** — 모든 화면의 empty/loading/error (ideal만 그리기 쉬움)
5. **대안/예외 플로우** — happy path 밖의 분기·에러
6. **기능→제품 스캐폴딩** — auth·권한·온보딩·설정·데이터수명주기·알림·도움말·오프보딩
7. **엣지 케이스** — 빈 리스트·최대값·특수문자·오프라인·타임존…
8. **비기능** — 성능·보안·프라이버시·접근성
9. **미결정 질문** — 채우지 말고 올릴 것

**scope pruning (중요)**: 무지성으로 다 적용하면 *내 개인용 도구*에 auth·결제·다중사용자 같은 엔터프라이즈 빈칸을 강요해 기획서가 부풀고 오도된다. 그래서 P0에서 청중 스코프(`n=1 개인도구 / 니치 / 넓은 사용자`)를 정하고, 그에 맞게 카테고리를 *잘라낸다*. n=1 도구엔 auth/온보딩/결제 빈칸을 띄우지 않는다 — 내 아이디어 대부분이 이런 니치/개인 도구라서 핵심 설계.

---

## 5. 쓰는 법

- **트리거**: "이거 기획해줘", "이 기능/화면/시나리오 서비스로 구체화", "빠진 부분 채워" 등.
- **티어** (자동 추정, override 가능):
  - `napkin` (~10분): 빈칸 목록만 빠르게 1쪽.
  - `standard` (기본): 5단계 풀 + 기획서 10섹션.
  - `deep`: 화면별 상태 상세 + 에이전트 + P6 와이어프레임 + P7 데이터모델 + 선택 `/self-review`.
- **와이어프레임(P6)·데이터모델(P7)**: deep 기본 / standard에선 "와이어프레임 그려줘" · "데이터 모델 짜줘" 요청 시. 각각 단일 `wireframe-builder`·`data-model-builder` 에이전트가 `wireframes.html`·`data-model.md` 생성(함대 금지, 산출물 1개당 1에이전트).
- **산출물**: `~/Documents/service-planning/{날짜}-{slug}/기획서.md` (+ `gaps.md`, + `wireframes.html`, + `data-model.md`).
- **사람이 개입하는 곳**:
  - 조사로 알 수 없고 결과를 크게 바꾸는 의도·우선순위가 있을 때만 P3에서 1~3개 집중 인터뷰를 받는다.
  - 외부 전송·유료 호출·파괴·비가역 행동은 실제 실행 직전에 승인한다.
  - 빈칸 발견, 흔한 처리, v1 스코프 초안, completeness 확인은 도구가 증거와 가정을 남기며 진행한다. 사용자는 routine 체크리스트의 승인자가 아니다.

---

## 6. 더 읽을거리

- Jeff Patton, *User Story Mapping* — https://jpattonassociates.com/story-mapping/
- Tony Ulwick, "The Customer-Centered Innovation Map" (HBR 2008) — https://jobs-to-be-done.com/mapping-the-job-to-be-done-45336427b3bc
- Matt Wynne, Example Mapping — https://cucumber.io/docs/bdd/example-mapping/
- Scott Hurff, "The UI Stack" — https://www.scotthurff.com/posts/why-your-user-interface-is-awkward-youre-ignoring-the-ui-stack/
- Alistair Cockburn, *Writing Effective Use Cases*
- Ryan Singer, *Shape Up* (appetite/scope) — https://basecamp.com/shapeup
- NN/g, "Journey Mapping 101" — https://www.nngroup.com/articles/journey-mapping-101/
- Lenny Rachitsky, PRD templates — https://www.lennysnewsletter.com/p/prds-1-pagers-examples

---

*관련: 나는 USM + Example Mapping을 `시나리오-first-개발` wiki에서 이미 쓰고 있다. 이 도구는 같은 어휘를 쓰되 그 빌드 파이프라인엔 연결하지 않는 독립 기획 도구다.*
