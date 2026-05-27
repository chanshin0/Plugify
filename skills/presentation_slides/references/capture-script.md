# PNG 캡처 스크립트

`presentation_slides` §M 모드에서 사용. 개별 슬라이드 HTML 을 Chrome headless 로 PNG 일괄 캡처. Confluence / Notion / 문서 첨부용.

## 사용 패턴

1. 슬라이드 디렉터리 (`<dir>/0*.html`) 와 출력 디렉터리 결정
2. 아래 bash 스크립트를 경로에 맞게 작성
3. `bash capture.sh` 실행
4. 결과 1장 사용자에게 보여주고 검수 받음 (폰트 누락/잘림)

## Bash 스크립트 (전체)

```bash
#!/bin/bash
# 슬라이드 PNG 일괄 캡처 (Chrome headless, retina 2x)

set -e
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SRC=<슬라이드 디렉터리>           # 예: /tmp/git-harness-slides
OUT=<출력 디렉터리>               # 예: /tmp/git-harness-captures
mkdir -p "$OUT"

# Viewport
W=1280
H=720
SCALE=2    # retina 2x → 출력 2560×1440

for f in "$SRC"/0*.html; do
    name=$(basename "$f" .html)
    out="$OUT/$name.png"
    echo "→ $name.png"
    "$CHROME" \
        --headless=new \
        --disable-gpu \
        --hide-scrollbars \
        --window-size=$W,$H \
        --force-device-scale-factor=$SCALE \
        --virtual-time-budget=3000 \
        --screenshot="$out" \
        "file://$f" 2>/dev/null
done

echo ""
echo "captured to $OUT:"
ls -la "$OUT"/*.png
```

## 옵션 설명

| 옵션 | 역할 | 비고 |
|---|---|---|
| `--headless=new` | 신 headless 모드 | 구 `--headless` 보다 폰트·CSS 렌더링 정확 |
| `--disable-gpu` | GPU 비활성 | headless 안정성 |
| `--hide-scrollbars` | 스크롤바 숨김 | viewport 가 정확히 1280×720 |
| `--window-size=1280,720` | viewport | 슬라이드 기본 사이즈와 일치 |
| `--force-device-scale-factor=2` | retina 2x | 출력 2560×1440 (확대해도 깨끗) |
| `--virtual-time-budget=3000` | 3초 가상시간 | cardAppear delay 1.0s + fadeIn 0.4s 여유 |
| `--screenshot=<path>` | 캡처 출력 경로 | PNG 만 지원 |

## Nav 바 제거 옵션

기본 캡처는 하단 50px nav 바가 포함된다.

### 옵션 A: 캡처 후 crop (간단, 권장)

macOS `sips` 사용:

```bash
# 하단 100px (retina 2x) crop → 2560×1340
for f in "$OUT"/*.png; do
    sips --cropToHeightWidth 1340 2560 "$f" --out "${f%.png}-clean.png"
done
```

또는 ImageMagick:

```bash
for f in "$OUT"/*.png; do
    convert "$f" -gravity North -crop 2560x1340+0+0 "${f%.png}-clean.png"
done
```

### 옵션 B: 캡처 직전 CSS 주입 (복잡)

별도 wrapper HTML 만들어서 슬라이드를 iframe 으로 포함하고 nav 를 CSS로 숨긴 후 캡처. 보통 옵션 A 가 더 간단.

## 검수 체크리스트

- [ ] N 장 모두 캡처됐는지 (`ls "$OUT"/*.png | wc -l`)
- [ ] 사용자에게 1~2 장 미리 보여주고 confirm
  - 한글 폰트 (Noto Sans KR) 정상 로드?
  - 등장 애니메이션 완료 상태로 캡처됐는지 (opacity 0 잔여 없음)
  - 그라디언트 텍스트 정상 렌더?
  - 콘텐츠 잘림 없는지

## 디버깅

**증상: 한글이 □□ 또는 시스템 폰트로 보임**
→ Google Fonts CDN 로딩 시간 부족. `--virtual-time-budget` 을 5000 으로 늘려본다. 또는 네트워크 확인.

**증상: 슬라이드 콘텐츠가 opacity 0 으로 캡처됨 (검은 화면)**
→ body `fadeIn` 애니메이션이 완료 전에 캡처됨. `--virtual-time-budget` 을 늘리거나, 슬라이드별 카드 애니메이션 delay 총합 + 1초 여유로 설정.

**증상: 캡처가 1920×1080 등 다른 해상도로 나옴**
→ Chrome 버전에 따라 `--window-size` 가 무시되는 경우 있음. `--screenshot` 옵션 형식 확인 (절대 경로 권장). 또는 `--window-position=0,0` 추가.

**증상: macOS Chrome 경로 못 찾음**
→ `ls /Applications/ | grep -i chrom` 으로 확인. Canary/Beta 라면 경로 다름. Chromium 사용 가능.

## 폴더 출력 형식

```
<출력 디렉터리>/
├── 01-intro.png            (2560×1440, retina 2x)
├── 02-three-layer.png
├── ...
└── 07-summary.png
```

Confluence/Notion 업로드:
- 페이지 본문에 순서대로 드래그앤드롭
- 플랫폼이 자동 다운스케일 — retina 원본 유지하면 줌인해도 선명
