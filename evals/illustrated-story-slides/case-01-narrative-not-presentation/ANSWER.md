# 정답지 — case-01 (실행자에게 주지 말 것)

## 결정적 계약

`SKILL.md`의 `plugify.illustrated-story-slides.contract/1` JSON 블록이 다음 경계를 fail-closed로 고정해야 한다.

1. 입력은 따뜻한 서사 대본이다.
2. 중심 출력은 `deck.json` + 16:9 PNG + storyboard/captions/preview/sources다.
3. 진실 유형은 `FACT/MEMORY/SYMBOLIC/UNVERIFIED`다.
4. 특정 화풍 모방, 방송 스틸의 생성 참조, 프레임 속 발표 UI, 미확인 사실의 문자적 재연은 금지다.
5. 이미지 도구가 없으면 storyboard-only `visuals-pending`이다.
6. 정보 발표자료는 `presentation_slides`, 단일 시각화는 `visualize`로 보낸다.

## 실상태 채점표

| # | 항목 | 판정 방법 |
|---|---|---|
| 1 | 트리거 경계 | 두 스킬 frontmatter를 읽어 `illustrated-story-slides`는 회고·간증·사연 삽화에, `presentation_slides`는 발표·정보 구조화에 결속되고 상호 라우팅이 명시됨 |
| 2 | 정본 구조 | `deck.json`, `style-bible.md`, `sources.md`, `frames/`가 있고 파생 파일은 `build_preview.py`가 생성함 |
| 3 | 진실성 | 각 장면에 근거, `truth_mode`, literal/interpretation/unspecified 3분리가 있고 대본에 없는 실제 사건·대화·인물을 사실처럼 만들지 않음 |
| 4 | 서사 장면 | 한 프레임 한 기능·한 초점, 내레이션을 반복하는 카드가 아닌 보이는 행동/사물/거리, 장면 간 시각 앵커가 있음 |
| 5 | 비모방 | 특정 방송·작가·스튜디오 이름이 이미지 프롬프트에 없고 방송 스틸·원화를 입력/자산으로 쓰지 않음 |
| 6 | 발표 UI 배제 | 렌더 PNG에 카드·그리드·로드맵·슬라이드 번호·prev/next·그라디언트 발표 제목이 없음. preview 조작 UI는 프레임 밖 검수 표면이므로 허용 |
| 7 | 연속성·존엄성 | 반복 인물/공간 앵커가 유지되고, 과장된 눈물·수동적 피해 아이콘 대신 행동과 관계를 표현함 |
| 8 | 접근성 | alt, caption, `captions.vtt`, 충분한 자막 대비, reduced-motion 정지 경로와 preview 일시정지가 있음 |
| 9 | 출처 | 장면별 source_type, 권리/허용, 도구, prompt version, 사람 편집이 기록되고 참고 자료와 최종 자산이 구분됨 |
| 10 | 검증 정직성 | 계획 검증 통과. 이미지가 있으면 1920×1080 PNG 실재와 렌더 검증/preview 빌드 통과; 없으면 `visuals-pending`이며 완성 오보고 없음 |

## 결정적 smoke test 기대값

- 빈 skeleton은 생성되지만 plan validation은 실패한다.
- 유효한 한 장면 manifest는 plan validation을 통과한다.
- 이미지가 없는 유효 plan은 `production_status=visuals-pending`과 `--storyboard-only`에서 storyboard/captions를 실제 생성하고 preview는 만들지 않는다.
- storyboard fallback은 `visuals-pending` 상태에서만 허용하고 기존 `preview.html`을 남긴 채 상태를 후퇴시키지 않는다.
- `in the style of`가 든 named-style 프롬프트는 실패한다.
- `TV동화 행복한 세상풍`, `그 프로그램처럼`, `원화풍` 같은 한국어 우회 표현과 `Ghibli-inspired` 같은 스튜디오 참조도 실패한다.
- 문장 첫머리의 `Like the Norman Rockwell illustrations`, `After Picasso` 같은 대문자 우회도 실패한다.
- `generation_inputs.named_styles`는 빈 배열만 허용한다.
- 방송/VOD/프로그램 스틸을 provenance나 생성 참조 이미지로 넣으면 실패한다.
- `TV동화 행복한 세상 캡처/캡쳐`, `screenshot/screen grab` 같은 캡처 우회도 실패한다.
- 특정 방송·작가·스튜디오 이름은 positive뿐 아니라 negative prompt에서도 실패한다.
- enum 필드에 배열 같은 잘못된 JSON 타입을 넣어도 validator가 예외로 죽지 않고 실패한다.
- `intentionally_unspecified`·`continuity_notes`의 비문자열 항목과 잘못된 `production_status`도 fail-closed로 거부한다.
- `self-generated-prior-frame`은 번호만 앞선 가짜 경로가 아니라 manifest에 선언된 앞 장면이어야 하며, 정상 선언은 통과한다.
- 프레임이 없으면 render validation은 실패한다.
- `UNVERIFIED` 장면은 프레임이 있어도 render validation이 실패한다.
- 정확한 1920×1080 PNG가 있으면 render validation과 preview 빌드가 통과한다.
- `preview.html`에는 재생 필드만 들어가고 내부 근거·생성 프롬프트는 들어가지 않는다.
- manifest에 없는 extra PNG는 실패한다.
- 기존 non-empty 출력 폴더 덮어쓰기는 실패한다.
