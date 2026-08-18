# Storyboard contract

## 목차

1. Coverage mode
2. Truth mode
3. 장면 기능
4. `deck.json` 구조
5. 프롬프트 조립
6. 연속성
7. 출력 파일

## 1. Coverage mode

### `supporting-slides`

실사 인터뷰·간증·강연의 A-roll을 보조한다. 대본 전체를 장면으로 치환하지 말고, 말만으로 보기 어려운 기억·상징·전환에만 프레임을 둔다. 얼굴이 중요한 고백 구간은 삽화보다 실제 화자의 표정을 남긴다.

### `full-animatic`

삽화가 영상의 주 화면이다. 장면 사이에 원인–행동–결과 또는 시각적 앵커가 이어져야 한다. 같은 구도와 상징을 반복해 분량을 채우지 않는다.

## 2. Truth mode

| 값 | 의미 | 시각화 규칙 |
|---|---|---|
| `FACT` | 문서·사진·검증 자료로 확인 | 근거에 있는 세부만 사용하고 `source_basis`를 기록 |
| `MEMORY` | 화자의 주관적 기억·감각 | 제한된 시점, 부분 대상, 불확실성을 유지 |
| `SYMBOLIC` | 주제·정서를 비문자적으로 표현 | 실제 사건이 아님을 내부 데이터에 명시; 실명·로고 제외 |
| `UNVERIFIED` | 확인 전 주장 | 사실적 재현 금지; 확인하거나 상징으로 낮춤 |

각 장면에 다음 세 줄을 반드시 채운다.

- `literal_content`: 대본이 직접 말한 것
- `visual_interpretation`: 화면이 보태는 해석
- `intentionally_unspecified`: 의도적으로 만들지 않은 세부

`visual_interpretation`이 새로운 사실 명제를 만들면 `FACT`로 렌더링하지 않는다.

## 3. 장면 기능

다음 중 하나를 고른다.

- `setting`: 시간·장소·관계의 출발점
- `absence`: 결핍·거리·질문의 감각적 증거
- `action`: 인물의 선택이나 작은 행동
- `turn`: 관계나 이해가 달라지는 눈에 보이는 순간
- `reflection`: 화자의 현재 관점과 과거 장면의 연결
- `afterglow`: 행동이 남긴 사물·빛·거리의 변화

하나의 장면에 여러 기능을 억지로 넣지 않는다.

## 4. `deck.json` 구조

`scripts/new_deck.py`가 만든 구조를 유지한다. 장면 예시는 다음과 같다.

최상위 `production_status`는 다음 상태만 사용한다.

- `planning`: 장면 계획 중이며 렌더 완료를 주장하지 않음
- `visuals-pending`: 이미지 도구가 없어 plan 검증 후 storyboard/captions만 만든 상태
- `rendered`: 모든 PNG가 실재하고 render 검증을 통과할 준비가 된 상태

```json
{
  "id": "01",
  "slug": "window-before-dawn",
  "narration_excerpt": "아버지는 새벽마다 먼저 불을 켜셨습니다.",
  "caption": "아버지는 새벽마다 먼저 불을 켜셨습니다.",
  "function": "setting",
  "truth_mode": "MEMORY",
  "truth_refs": ["T01"],
  "source_basis": "script.md §2, speaker memory",
  "literal_content": "화자는 아버지가 새벽마다 불을 켰다고 기억한다.",
  "visual_interpretation": "얼굴 대신 어두운 복도 끝의 불빛과 문고리를 잡은 손을 보인다.",
  "intentionally_unspecified": ["아버지의 얼굴", "정확한 집 구조", "연도"],
  "composition": {
    "shot": "wide interior",
    "subject": "a hand on a wooden door handle",
    "action": "the door opens toward a small warm light",
    "setting": "quiet predawn hallway",
    "negative_space": "dark wall occupies the left forty percent",
    "anchor_from_previous": "none"
  },
  "continuity_notes": ["warm amber light is the recurring motif"],
  "on_screen_text": "",
  "duration_sec": 8.0,
  "motion": {"type": "slow-push", "purpose": "move from distance toward the remembered light"},
  "frame": "frames/01-window-before-dawn.png",
  "alt": "어두운 새벽 복도 끝에서 문이 열리며 작은 불빛이 비친다.",
  "generation_inputs": {
    "named_styles": [],
    "reference_images": []
  },
  "prompt": {
    "positive": "...",
    "negative": "text, logo, photoreal reenactment, presentation UI"
  },
  "provenance": {
    "source_type": "AI-generated",
    "source_reference": "",
    "license_permission": "project-authorized generation",
    "tool": "image generation tool",
    "prompt_version": "v1",
    "human_edit": "scene selection, crop, color review"
  }
}
```

필드 의미:

- `caption`: 접근 가능한 동기 자막. 내레이션이 없으면 의미 있는 환경음을 적을 수 있다.
- `truth_refs`: 이 장면이 의존하는 `truth_ledger` ID 목록. 존재하지 않는 ID를 참조하지 않는다.
- `on_screen_text`: 이미지 위에 항상 보일 짧은 표제/시간 도약/마지막 여운. 보통 빈 문자열이다.
- `frame`: `frames/NN-slug.png`; 번호는 장면 ID와 일치한다.
- `alt`: 내레이션이 아니라 화면의 주 행동과 관계를 설명한다.
- `provenance`: 장면별 출처·권리·생성·사람 편집 기록이다.
- `generation_inputs.named_styles`: 항상 빈 배열이다. 화풍·방송·작가·스튜디오 이름을 프롬프트로 우회하지 않는다.
- `generation_inputs.reference_images`: 실제 생성 도구에 넣은 이미지 입력만 기록한다. 각 항목은 `origin`, `source_reference`, `sha256`, `permission`, `purpose`를 가진다.

허용 `origin`:

- `self-generated-prior-frame`: 같은 deck의 앞 장면을 연속성 앵커로 사용
- `user-owned-photo`: 사용자가 제공하고 생성 입력 사용을 허용한 사진
- `licensed-production-asset`: 해당 제작에서 생성 입력 사용권이 확인된 자산

방송 VOD·방송 스틸·프로그램 원화·작가 작품·웹 검색 이미지는 권리 문구가 있더라도 이 스킬의 생성 입력으로 사용하지 않는다.

## 5. 프롬프트 조립

다음 순서로 쓰고 한 덩어리의 모호한 감성 형용사로 끝내지 않는다.

1. `original illustration`과 화면비
2. 스타일 바이블의 재료·팔레트·시대·공간
3. 반복 인물/장소 앵커
4. 이 장면의 피사체·한 행동·관계 거리
5. 구도, 렌즈 느낌, 여백, 광원
6. 진실 모드에 맞춘 제한: 얼굴 비식별, 기억의 불확실성, 상징임을 명시
7. 금지: text, logo, watermark, presentation UI, extra fingers, duplicated people, melodramatic tears, photoreal fake archival image

`prompt.positive`는 영어로 쓰고 관찰 가능한 속성만 나열한다. `style`, `inspired by`, `reminiscent of`, `like the`, `as seen in`, `frame/still from`, URL과 특정 방송·작가·스튜디오·프랜차이즈 이름을 넣지 않는다. 한국어 `풍/처럼/원화풍`도 금지하며, 한국어 대본과 장면 설명은 구조화 필드에 둔다.

## 6. 연속성

반복 인물은 다음 중 최소 두 가지를 고정한다.

- 헤어 실루엣
- 연령대와 체형
- 상의 색·재질
- 반복 소지품
- 자세나 걸음의 특징

같은 장소는 광원 방향과 문·창·가구 하나를 고정한다. 반대 앵글로 바뀌면 먼저 기준 사물을 보여 공간 방향을 재설정한다.

감정 강도는 한 장면에 한 단계씩만 변한다. `관찰 → 불편함 → 행동 → 완화 → 여운`을 한 프레임에서 모두 표현하지 않는다.

## 7. 출력 파일

- `deck.json`: 유일한 편집 정본
- `style-bible.md`: 아트 디렉션과 금지 요소
- `frames/*.png`: 렌더 프레임
- `storyboard.md`, `captions.vtt`, `preview.html`: `build_preview.py`로 재생성
- `sources.md`: 자산·권리·도구·편집 기록과 외부 참고 링크

이미지 도구가 없을 때는 `production_status=visuals-pending`으로 두고 `build_preview.py --storyboard-only`를 실행한다. 이 fallback은 `storyboard.md`와 `captions.vtt`만 생성하며, 프레임이나 `preview.html`이 없는 상태를 완성 렌더로 보고하지 않는다.

생성 프롬프트나 대외비 대본 전문을 공개용 `sources.md`에 자동 복사하지 않는다. 공개본과 내부 제작 장부가 다르면 파일명을 분리하고 공개 범위를 명확히 적는다.
