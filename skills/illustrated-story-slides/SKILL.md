---
name: illustrated-story-slides
description: 따뜻한 회고·간증·편지·사연형 대본을 발표자 없이도 감정선이 이어지는 독창적 삽화형 16:9 영상 장면과 스토리보드로 변환한다. “TV동화 행복한 세상 같은 그림 이야기”, “간증·회고 대본을 삽화 슬라이드로”, “나레이션용 그림 장면”, “감성 영상용 장면 PNG” 요청에 사용한다. 기술 발표·정보 카드·로드맵·비교표·아키텍처·일반 HTML 프레젠테이션은 presentation_slides를 사용하며, 단일 인포그래픽·대시보드는 visualize를 사용한다.
---

# Illustrated Story Slides

대본의 감정선을 독창적인 삽화 장면으로 번역한다. 특정 방송·작가의 그림체를 복제하지 말고, 따뜻한 인간 이야기·여백·상징·최소 움직임이라는 고수준 문법만 사용한다.

## 먼저 읽기

제작 전에 다음을 모두 읽는다.

1. [references/visual-language.md](references/visual-language.md) — 화면·색·움직임·비모방 원칙
2. [references/storyboard-contract.md](references/storyboard-contract.md) — `deck.json` 필드·장면 분해·프롬프트 계약
3. [references/review-rubric.md](references/review-rubric.md) — 렌더·사실성·접근성 검수

## 경계 결정

- 회고, 간증, 편지, 사연, 위로, 한 사람의 기억처럼 **서사가 중심**이면 이 스킬을 사용한다.
- 강의, 기술 설명, 단계, 비교, 로드맵, 아키텍처, 카드 요약처럼 **정보 구조가 중심**이면 `presentation_slides`를 사용한다.
- 대시보드, 인포그래픽, 한 장짜리 데이터 스토리는 `visualize`를 사용한다.
- 사용자가 “영상 슬라이드”라고만 말해 어느 쪽인지 판별할 수 없으면, 대본의 주된 동력이 `이야기/감정`인지 `설명/정보`인지 한 가지만 묻는다.
- 한 대본 안에 서사와 정보가 섞이면 서사 장면을 이 스킬로 만들고, 표·연표·근거 화면만 별도 정보 슬라이드로 분리한다. 한 프레임 안에서 두 문법을 섞지 않는다.

```json
{
  "schema": "plugify.illustrated-story-slides.contract/1",
  "primaryInput": "warm-narrative-script",
  "primaryOutput": [
    "deck.json",
    "frames/*.png",
    "storyboard.md",
    "captions.vtt",
    "preview.html",
    "sources.md"
  ],
  "canvas": "1920x1080",
  "truthModes": [
    "FACT",
    "MEMORY",
    "SYMBOLIC",
    "UNVERIFIED"
  ],
  "namedStyleImitation": "forbidden",
  "broadcastFramesAsGenerationReference": "forbidden",
  "presentationUIInFrames": "forbidden",
  "unverifiedLiteralReenactment": "forbidden",
  "promptPolicy": "english-observable-attributes-only",
  "generationInputs": "structured-per-scene",
  "namedStyleList": "must-be-empty",
  "broadcastReferenceTokens": "reject",
  "imageToolUnavailable": "storyboard-only-visuals-pending",
  "storyboardFallbackOutput": [
    "deck.json",
    "storyboard.md",
    "captions.vtt",
    "sources.md"
  ],
  "storyboardFallbackCommand": "python3 $ILLUSTRATED_STORY_SKILL_DIR/scripts/build_preview.py --storyboard-only",
  "productionStatuses": [
    "planning",
    "visuals-pending",
    "rendered"
  ],
  "informationDeckRoute": "presentation_slides",
  "singleVisualizationRoute": "visualize"
}
```

## 출력 계약

사용자가 위치를 지정하지 않으면 `~/Documents/illustrated-story-slides/<YYYY-MM-DD-slug>/`에 만든다.

```text
<deck>/
├── deck.json          # 장면·사실·연속성·출처의 SSOT
├── style-bible.md     # 이번 작품만의 독창적 아트 디렉션
├── storyboard.md      # deck.json에서 생성한 사람이 읽는 장면표
├── captions.vtt       # 장면 길이에 맞춘 접근 가능한 자막
├── frames/            # 01-*.png부터 이어지는 16:9 원본 프레임
├── preview.html       # 검수용 애니매틱; 프레임 자체에는 UI 없음
└── sources.md         # 자료·권리·생성 도구·사람 편집 기록
```

- `deck.json`을 정본으로 유지한다. `storyboard.md`, `captions.vtt`, `preview.html`을 직접 따로 고쳐 불일치를 만들지 않는다.
- 프레임은 이미지 한 장 자체로 성립하게 만든다. 카드, 슬라이드 번호, 화살표, 발표 내비게이션, 그라디언트 제목 UI를 프레임 안에 넣지 않는다.
- 프로젝트의 로컬 정책이 `.pptx` 같은 전달 형식을 요구하면 그 정책을 따른다. PPTX는 검증된 프레임을 한 장씩 전체 배경으로 배치하고, 대본·진실 유형·출처는 발표자 노트 또는 별도 문서에 둔다.

## 워크플로우

아래 명령의 `ILLUSTRATED_STORY_SKILL_DIR`은 **현재 읽은 이 `SKILL.md`가 들어 있는 디렉토리의 절대경로**로 먼저 설정한다. 호출한 프로젝트의 현재 작업 디렉토리를 기준으로 `scripts/...`를 찾지 않는다.

```bash
ILLUSTRATED_STORY_SKILL_DIR="<absolute path to this skill directory>"
```

### 0. 입력과 공개 경계를 확인한다

현재 대화, 지정 파일, 프로젝트 정책에서 먼저 찾고 다음 실행 계약을 정한다.

- 대본 경로 또는 본문
- 청중과 사용처: 영상 전체를 삽화로 만드는 `full-animatic`, 실사 인터뷰를 받치는 `supporting-slides`
- 화면비와 해상도: 기본 `16:9`, `1920×1080`
- 실제 인물·사진·장소의 사용 권한과 식별 허용 범위
- 공개 범위: `public`, `internal`, `confidential`

조사 가능한 값은 사용자에게 묻지 않는다. 대본에 없는 개인 기억, 사실관계, 공개 권한처럼 결과를 바꾸는 인간 맥락만 짧게 확인한다.

대외비 세부를 외부 이미지 생성 도구에 보내지 않는다. 공개 가능한 표현으로 비식별화하거나 상징 장면으로 바꾸고, 그것도 불가능하면 스토리보드까지만 작성해 `visuals-pending`으로 보고한다.

### 1. 빈 프로젝트를 먼저 실증한다

새 폴더를 만들기 전에 같은 경로가 있는지 확인하고 덮어쓰지 않는다.

```bash
python3 "$ILLUSTRATED_STORY_SKILL_DIR/scripts/new_deck.py" \
  --output <deck-dir> \
  --title "<제목>" \
  --script <script-path> \
  --coverage-mode supporting-slides \
  --privacy internal
```

생성된 `deck.json`이 열리고 `style-bible.md`·`frames/`가 실재하는지 확인한 뒤 내용 작업으로 넘어간다.

### 2. 대본의 진실 장부와 이야기 등뼈를 만든다

대본을 요약하기 전에 다음을 분리한다.

- `FACT`: 문서·사진·공개 자료로 검증된 사실
- `MEMORY`: 화자가 기억하거나 느꼈다고 말한 내용
- `SYMBOLIC`: 주제와 정서를 보여 주는 비문자적 장면
- `UNVERIFIED`: 확인 전이며 사실처럼 시각화하면 안 되는 내용

각 항목을 `truth_ledger`에 넣고 근거 위치를 기록한다. 기억의 빈칸을 사실적인 가짜 장면으로 채우지 않는다. 실제 사진이 없으면 얼굴·정확한 복장·간판·제3자의 행동을 발명하는 대신 손, 길, 창, 빈 의자, 빛, 사물처럼 비식별 상징을 사용한다.

대본의 등뼈를 `상태/공간 → 결핍 또는 질문 → 선택/행동 → 눈에 보이는 변화 → 여운`으로 찾되, 원문이 다른 구조라면 억지로 맞추지 않는다. 교훈을 새로 쓰지 말고 화자의 마지막 고백이나 관찰 가능한 변화로 닫는다.

### 3. 장면을 변화점으로 나눈다

- 문단 수가 아니라 장소, 시간, 행동, 관계, 정서가 달라지는 지점에서 자른다.
- 한 장면에는 행동 하나, 관계 변화 하나, 감정 정지 하나 중 하나만 맡긴다.
- `supporting-slides`에서는 핵심 장면만 뽑고 A-roll을 가리지 않는다. `full-animatic`에서는 대본 전체의 시각적 변화가 끊기지 않게 충분한 장면을 둔다.
- 내레이션을 화면 문장으로 복사하지 않는다. 화면은 내레이션의 **보이는 증거**를 제공한다.
- 장면마다 `대본이 직접 말한 것 / 시각적 해석 / 의도적으로 비운 것`을 기록한다.
- 장면마다 `generation_inputs`를 기록한다. 이름 있는 화풍 목록은 항상 비우고, 참조 이미지는 소유·권한·SHA-256·용도를 구조화한다.
- 같은 인물·장소가 반복되면 외형·옷·소품·광원·카메라 방향 중 최소 두 개를 `continuity_notes`로 고정한다.

`deck.json`의 장면 계약은 [references/storyboard-contract.md](references/storyboard-contract.md)를 그대로 따른다. 채운 뒤 계획 단계 검증을 실행한다.

```bash
python3 "$ILLUSTRATED_STORY_SKILL_DIR/scripts/validate_deck.py" <deck-dir> --stage plan
```

### 4. 작품 고유의 스타일 바이블을 만든다

`style-bible.md`에 아래를 구체적으로 적는다.

- 한 문장 콘셉트와 정서 온도
- 재료감: 종이 결, 연필 윤곽, 불균일한 채색 등 일반적 매체 특성
- 주조색 1개, 보조색 2개, 강조색 1개
- 현재/회상/전환/여운의 색 변화
- 반복 인물·장소·소품의 고정 특징
- 피할 요소: 특정 작품/작가/스튜디오 이름, 로고, 고유 캐릭터, 과장된 눈물, 3D 광고 렌더, 프레젠테이션 UI, 생성된 글자

“TV동화 행복한 세상 스타일”, “○○ 작가풍”을 이미지 프롬프트에 쓰지 않는다. `부드러운 종이 질감 + 제한 팔레트 + 넓은 여백 + 절제된 표정 + 장면당 한 행동`처럼 관찰 가능한 속성으로 번역한다.

이미지 생성용 `prompt.positive`는 영어의 관찰 가능한 속성만 사용한다. `style`, `inspired by`, `reminiscent of`, `like the`, 방송·작가·스튜디오·에피소드 이름, URL, 한국어 `풍/처럼/원화풍`을 넣지 않는다. 한국어 대본·자막·장면 설명은 다른 필드에 보존한다.

### 5. 기준 장면부터 이미지를 만든다

이미지 생성 기능이 있으면 런타임의 이미지 생성/편집 도구를 사용한다. Codex에서는 `imagegen` 지침을 함께 따른다.

1. 반복 인물과 핵심 공간이 함께 보이는 기준 장면 1장을 먼저 만든다.
2. 직접 열어 인물 존엄성, 시대·공간, 손·얼굴 오류, 텍스트 흔적, 팔레트를 검사한다.
3. 기준 장면을 승인된 시각 앵커로 삼아 같은 인물이 나오는 다음 장면에 참조한다.
4. 다음 장면마다 직전 프레임을 무조건 복제하지 말고, `continuity_notes`만 유지하면서 구도와 행동을 새로 만든다.
5. 생성 이미지에 한글·제목·자막을 굽지 않는다. `preview.html`이나 영상 편집 단계에서 정확한 텍스트를 오버레이한다.

도구가 참조 이미지를 지원하지 않으면 동일한 캐릭터 앵커 문장을 매 프롬프트에 반복하고, 각 결과를 직접 비교한다. 웹에서 찾은 원화·스틸을 이미지 생성 입력으로 사용하지 않는다.

원본 생성 비율이 16:9가 아니면 중요한 얼굴·손·상징을 보호하며 크롭한다.

```bash
uv run --with pillow python "$ILLUSTRATED_STORY_SKILL_DIR/scripts/normalize_frame.py" \
  <input-image> <deck-dir>/frames/01-scene.png --width 1920 --height 1080
```

### 6. 장면을 조립한다

- `frame` 경로, 대체 텍스트, 자막, 길이, 움직임 목적, 생성 도구·프롬프트 버전·사람 편집 내역을 `deck.json`에 기록한다.
- 이미지 생성에 사용한 모든 참조는 `generation_inputs.reference_images`에 기록한다. 허용 origin은 같은 프로젝트에서 생성한 이전 프레임, 사용자가 소유한 사진, 권리가 확인된 제작 자산뿐이다. 방송 VOD·스틸·원화·웹에서 찾은 작품은 허용하지 않는다.
- 기본은 정지 삽화다. 움직임은 서사 목적이 있을 때만 `slow-push`, `slow-pan-left`, `slow-pan-right` 중 하나를 쓰고 장면당 하나로 제한한다.
- 얼굴, 핵심 행동, 강조 소품과 자막 안전 영역이 겹치지 않게 한다.
- 표제·시간 도약·마지막 여운 외에는 화면 문구를 비운다. 긴 내레이션은 `caption`에만 둔다.

모든 프레임을 만든 뒤 `deck.json.production_status`를 `rendered`로 바꾸고 렌더 단계 검증과 조립을 실행한다.

```bash
python3 "$ILLUSTRATED_STORY_SKILL_DIR/scripts/validate_deck.py" <deck-dir> --stage render
python3 "$ILLUSTRATED_STORY_SKILL_DIR/scripts/build_preview.py" <deck-dir>
```

이미지 생성 기능이 없으면 무관한 대체 이미지를 넣지 않는다. `deck.json.production_status`를 `visuals-pending`으로 바꾸고 계획 검증을 통과시킨 뒤, 실제로 다음 fallback을 실행한다. 이 모드는 `storyboard.md`와 `captions.vtt`만 만들며 `preview.html` 완성을 주장하지 않는다.

```bash
python3 "$ILLUSTRATED_STORY_SKILL_DIR/scripts/build_preview.py" \
  <deck-dir> --storyboard-only
```

### 7. 실제 결과를 검수한다

에이전트 보고가 아니라 파일과 이미지를 직접 확인한다.

- `view_image` 또는 런타임의 이미지 미리보기로 기준 장면과 모든 프레임을 순서대로 본다.
- 최소한 첫 장면, 전환점, 마지막 장면은 원본 해상도로 확인한다.
- contact sheet만 보고 인물 손·얼굴·텍스트 오류를 통과시키지 않는다.
- `$ILLUSTRATED_STORY_SKILL_DIR/scripts/validate_deck.py --stage render`가 0이어도 미학·사실성·존엄성 검수는 끝난 것이 아니다. [references/review-rubric.md](references/review-rubric.md)를 모두 대조한다.
- `preview.html` 브라우저 검증이 필요하면 지원되는 in-app/browser automation 도구를 먼저 사용하고 [../visualize/SKILL.md](../visualize/SKILL.md)의 브라우저 안전 계약을 따른다. 사용자의 평상시 Chrome 프로세스·프로필을 종료·재사용·변경하지 않는다.

### 8. 결과를 전달한다

다음을 보고한다.

- 프로젝트 절대경로와 `preview.html` 링크
- 장면 수, coverage mode, 핵심 시각 모티프
- `FACT/MEMORY/SYMBOLIC/UNVERIFIED` 처리 요약
- 실제 이미지 생성 여부와 출처·권리 기록 위치
- 남은 인간 확인 항목
- 첫 실전 관찰이면 원 대본, `deck.json`, 렌더 프레임, 검증 로그를 보존해 fresh reviewer가 대조할 수 있게 한다.

## 금지

- 특정 방송·에피소드·현존 작가·스튜디오의 고유 화풍이나 원화를 그대로 복제하기
- 웹 스틸·방송 원화·무권리 사진을 생성 참조나 최종 프레임으로 사용하기
- 대본에 없는 기적, 대화, 표정, 가족사, 실제 장소를 사실처럼 발명하기
- 노년·장애·가난·신앙·가족애를 눈물 유발 소품과 수동적 표정으로 환원하기
- 모든 문단을 베이지 수채화와 인용문 카드로 바꾸기
- 한 장면에 줌, 패럴랙스, 입자, 흔들림을 겹치기
- 누락된 이미지를 무관한 스톡 사진이나 임시 플레이스홀더로 메우고 완성이라고 보고하기
