# 단일 HTML 번들 스크립트

`presentation_slides` §L 모드에서 사용. 개별 슬라이드 HTML 7~N 개를 iframe srcdoc 기반 단일 HTML 1개로 묶는다.

## 사용 패턴

1. 슬라이드 디렉터리(`<dir>/01-*.html` ~ `<dir>/NN-*.html`) 와 출력 경로(`<dir>/bundle.html` 등) 결정
2. 아래 Python 스크립트를 그 디렉터리에 맞게 조정 (경로 / 슬라이드 목록 / 출력 경로)
3. `python3 build-single.py` 실행 → 단일 HTML 생성
4. `open <output.html>` 으로 검수

## Python 빌드 스크립트 (전체)

```python
#!/usr/bin/env python3
"""Bundle individual slide HTMLs into a single self-contained file with iframe srcdoc."""
import re
import json
from pathlib import Path

SRC = Path("<슬라이드 디렉터리>")          # 예: /tmp/git-harness-slides
OUT = Path("<출력 단일 HTML 경로>")        # 예: /tmp/git-harness-3-layer.html
TITLE = "<프레젠테이션 제목>"               # 예: Git Harness — 3-Layer

# 순서대로 (filename, 슬라이드 제목)
SLIDES = [
    ("01-intro.html",        "사람·AI가 같이 쓰는 레포의 위험"),
    ("02-three-layer.html",  "3-Layer 가드"),
    # ...
]

def strip_nav(html: str) -> str:
    """슬라이드의 nav 바와 자체 keydown 리스너 제거 (부모가 네비게이션 제공)."""
    # Remove <nav class="slide-nav">...</nav>
    html = re.sub(r'<nav class="slide-nav">.*?</nav>', '', html, flags=re.DOTALL)
    # Remove the per-slide arrow-key keydown listener
    html = re.sub(
        r"document\.addEventListener\('keydown',\s*function\(e\)\s*\{[^}]*\}\);",
        '', html, flags=re.DOTALL,
    )
    # body 의 padding-bottom (nav 공간) 제거
    html = html.replace('padding-bottom: 50px;', 'padding-bottom: 0;')
    return html

slides_data = []
for fname, title in SLIDES:
    html = (SRC / fname).read_text(encoding="utf-8")
    html = strip_nav(html)
    slides_data.append({"title": title, "html": html})

# 🔴 CRITICAL: JSON 안의 </ 를 <\/ 로 escape
# 슬라이드의 </script> 가 부모 <script> 블록을 조기 종료시키는 것을 막는다.
# JSON spec상 \/ 는 / 와 동일하므로 데이터 의미는 보존됨.
slides_json = json.dumps(slides_data, ensure_ascii=False).replace("</", "<\\/")

OUT.write_text(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1280">
<title>{TITLE}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
  background: #0a0f1a;
  font-family: 'Noto Sans KR', sans-serif;
  color: #e6edf3;
  height: 100vh;
  overflow: hidden;
}}
.app {{ display: flex; flex-direction: column; height: 100vh; }}
.stage {{ flex: 1; position: relative; overflow: hidden; }}
#frame {{ width: 100%; height: 100%; border: 0; display: block; background: #0a0f1a; }}
.bar {{
  height: 50px;
  background: rgba(10, 15, 26, 0.95);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(124, 58, 237, 0.2);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}}
.bar-inner {{
  width: 100%; max-width: 1280px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 60px;
}}
.bar button, .bar .disabled {{
  background: none; border: none;
  font-family: 'Noto Sans KR', sans-serif;
  font-size: 14px; font-weight: 700;
  cursor: pointer; padding: 6px 12px; border-radius: 6px;
  transition: all 0.2s;
}}
.bar button {{ color: #7c3aed; }}
.bar button:hover {{ color: #a78bfa; background: rgba(124, 58, 237, 0.08); }}
.bar .disabled {{ color: #484f58; cursor: default; }}
.bar-center {{ display: flex; align-items: center; gap: 14px; font-size: 13px; color: #8b949e; }}
.bar-center .title {{ color: #c9d1d9; font-weight: 500; }}
.bar-center .counter {{ font-weight: 700; color: #a78bfa; font-variant-numeric: tabular-nums; }}
.dots {{ display: flex; gap: 6px; }}
.dot {{
  width: 8px; height: 8px; border-radius: 50%;
  background: rgba(139, 148, 158, 0.25);
  cursor: pointer; transition: all 0.2s;
}}
.dot:hover {{ background: rgba(167, 139, 250, 0.6); transform: scale(1.2); }}
.dot.active {{ background: linear-gradient(135deg, #7c3aed, #38bdf8); transform: scale(1.3); }}
.hint {{
  position: absolute;
  bottom: 12px; right: 16px;
  font-size: 11px; color: #484f58;
  pointer-events: none; z-index: 10;
}}
.hint kbd {{
  display: inline-block;
  padding: 1px 6px; border-radius: 4px;
  background: rgba(139, 148, 158, 0.1);
  border: 1px solid rgba(139, 148, 158, 0.2);
  font-family: monospace; font-size: 10px; color: #8b949e;
}}
</style>
</head>
<body>
<div class="app">
  <div class="stage">
    <iframe id="frame" sandbox="allow-same-origin allow-scripts"></iframe>
    <div class="hint"><kbd>←</kbd> <kbd>→</kbd> 또는 <kbd>Space</kbd> 로 이동</div>
  </div>
  <div class="bar">
    <div class="bar-inner">
      <button id="prev">&larr; 이전</button>
      <div class="bar-center">
        <span class="counter"><span id="cur">1</span> / <span id="total">7</span></span>
        <span class="title" id="cur-title">—</span>
        <div class="dots" id="dots"></div>
      </div>
      <button id="next">다음 &rarr;</button>
    </div>
  </div>
</div>

<script>
const SLIDES = {slides_json};
const frame = document.getElementById('frame');
const prev = document.getElementById('prev');
const next = document.getElementById('next');
const curEl = document.getElementById('cur');
const totalEl = document.getElementById('total');
const titleEl = document.getElementById('cur-title');
const dotsEl = document.getElementById('dots');
let idx = 0;

totalEl.textContent = SLIDES.length;

SLIDES.forEach((s, i) => {{
  const d = document.createElement('div');
  d.className = 'dot';
  d.title = s.title;
  d.addEventListener('click', () => go(i));
  dotsEl.appendChild(d);
}});
const dots = dotsEl.querySelectorAll('.dot');

function render() {{
  frame.srcdoc = SLIDES[idx].html;
  curEl.textContent = idx + 1;
  titleEl.textContent = SLIDES[idx].title;
  dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  prev.classList.toggle('disabled', idx === 0);
  next.classList.toggle('disabled', idx === SLIDES.length - 1);
}}

function go(n) {{
  if (n < 0 || n >= SLIDES.length || n === idx) return;
  idx = n;
  render();
}}

prev.addEventListener('click', () => go(idx - 1));
next.addEventListener('click', () => go(idx + 1));

function handleKey(e) {{
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{ e.preventDefault(); go(idx - 1); }}
  else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {{ e.preventDefault(); go(idx + 1); }}
  else if (e.key === 'Home') {{ e.preventDefault(); go(0); }}
  else if (e.key === 'End') {{ e.preventDefault(); go(SLIDES.length - 1); }}
  else if (/^[1-9]$/.test(e.key)) {{ const n = parseInt(e.key, 10) - 1; if (n < SLIDES.length) go(n); }}
}}

document.addEventListener('keydown', handleKey);

// 🔴 iframe srcdoc 은 same-origin → iframe 내부 document 에도 동일 리스너 부착
// (iframe 포커스 상태에서도 키보드 네비 동작하도록)
frame.addEventListener('load', () => {{
  try {{
    const doc = frame.contentDocument || frame.contentWindow.document;
    if (doc) doc.addEventListener('keydown', handleKey);
  }} catch (e) {{ /* cross-origin or detached - ignore */ }}
}});

render();
</script>
</body>
</html>
""", encoding="utf-8")

size = OUT.stat().st_size
print(f"OK {OUT} ({size:,} bytes, {size/1024:.1f} KB) - {len(SLIDES)} slides")
```

## 검수 체크리스트

스크립트 실행 후:

- [ ] 출력 파일 사이즈가 예상 범위 (슬라이드당 5~10KB 합산 + wrapper 2KB)
- [ ] 브라우저에서 `open <output.html>` 으로 열어 본문 콘텐츠 정상 표시되는지
- [ ] `←/→` 키로 슬라이드 이동되는지 (iframe 포커스 상태에서도)
- [ ] 슬라이드 전환 시 등장 애니메이션이 매번 재생되는지 (cardAppear, stepIn 등)
- [ ] 하단 dot 네비게이션 클릭으로 점프 동작
- [ ] 첫/마지막 슬라이드에서 prev/next 비활성 표시

## 디버깅

**증상: 본문이 안 보임 (검은 화면만)**
→ `</script>` escape 누락. JSON 임베드 부분에 `.replace("</", "<\\/")` 적용했는지 확인.

**증상: 키보드 화살표가 안 먹음**
→ iframe `load` 이벤트에서 `contentDocument.addEventListener` 부착 누락. sandbox 속성에 `allow-same-origin` 있는지 확인.

**증상: 슬라이드 전환 시 애니메이션이 한 번만 재생**
→ iframe `srcdoc` 재할당이 안 일어남. `frame.srcdoc = SLIDES[idx].html` 가 매 `go()` 호출마다 실행되는지 확인.

**증상: nav 바가 슬라이드 위에 중첩**
→ `strip_nav()` 가 호출 안 됨, 또는 정규식이 매칭 안 함. 슬라이드 HTML의 nav 마크업이 `<nav class="slide-nav">...</nav>` 형식인지 확인.

**증상: 슬라이드 콘텐츠가 잘림**
→ 원본 슬라이드가 `padding-bottom: 50px` 로 nav 공간 확보돼 있는데, 번들에선 nav 없으니 그 공간이 빔. `strip_nav()` 에서 padding 0 으로 치환됨 — 누락됐는지 확인.
