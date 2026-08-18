#!/usr/bin/env python3
"""Build storyboard.md, captions.vtt, and an accessible preview.html from deck.json."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
from validate_deck import validate


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def vtt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def build_storyboard(data: dict[str, Any]) -> str:
    lines = [
        f"# {data['title']} — storyboard",
        "",
        f"- Schema: `{data['schema']}`",
        f"- Production status: `{data['production_status']}`",
        f"- Coverage: `{data['source']['coverage_mode']}`",
        f"- Privacy: `{data['source']['privacy']}`",
        f"- Canvas: `{data['canvas']['width']}×{data['canvas']['height']}`",
        "",
        "| ID | 기능·진실 | 내레이션 | 시각적 해석 | 프레임 | 초·움직임 |",
        "|---|---|---|---|---|---|",
    ]
    for scene in data["scenes"]:
        lines.append(
            "| {id} | {function}<br>{truth} | {narration} | {visual} | `{frame}` | {duration}s<br>{motion} |".format(
                id=md(scene["id"]),
                function=md(scene["function"]),
                truth=md(scene["truth_mode"]),
                narration=md(scene["narration_excerpt"]),
                visual=md(scene["visual_interpretation"]),
                frame=md(scene["frame"]),
                duration=md(scene["duration_sec"]),
                motion=md(scene["motion"]["type"]),
            )
        )
    lines.extend(["", "## 장면 상세", ""])
    for scene in data["scenes"]:
        composition = scene["composition"]
        provenance = scene["provenance"]
        lines.extend(
            [
                f"### {scene['id']} — {scene['slug']}",
                "",
                f"- 근거: {scene['source_basis']}",
                f"- 진실 장부: {', '.join(scene['truth_refs'])}",
                f"- 대본이 직접 말한 것: {scene['literal_content']}",
                f"- 시각적 해석: {scene['visual_interpretation']}",
                f"- 의도적으로 비운 것: {', '.join(scene['intentionally_unspecified'])}",
                f"- 구도: {composition['shot']} / {composition['subject']} / {composition['action']}",
                f"- 공간·여백: {composition['setting']} / {composition['negative_space']}",
                f"- 이전 장면 앵커: {composition['anchor_from_previous']}",
                f"- 연속성: {'; '.join(scene['continuity_notes'])}",
                f"- 화면 문구: {scene['on_screen_text'] or '(없음)'}",
                f"- 대체 텍스트: {scene['alt']}",
                f"- 출처 유형·도구: {provenance['source_type']} / {provenance.get('tool', '')}",
                f"- 사람 편집: {provenance.get('human_edit', '')}",
                "",
                "**Positive prompt**",
                "",
                scene["prompt"]["positive"],
                "",
                "**Negative prompt**",
                "",
                scene["prompt"]["negative"],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_vtt(data: dict[str, Any]) -> str:
    lines = ["WEBVTT", ""]
    cursor = 0.0
    for scene in data["scenes"]:
        end = cursor + float(scene["duration_sec"])
        lines.extend(
            [
                scene["id"],
                f"{vtt_time(cursor)} --> {vtt_time(end)}",
                scene["caption"].strip(),
                "",
            ]
        )
        cursor = end
    return "\n".join(lines)


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — preview</title>
<style>
:root { color-scheme: dark; --paper:#ede4d3; --ink:#211d19; --chrome:#171512; --muted:#b9afa0; }
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; background:#0d0c0a; color:#f6f0e8; font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif; display:grid; place-items:center; }
.app { width:min(100vw, 1280px); padding:16px; }
.skip { position:absolute; left:-9999px; }
.skip:focus { left:16px; top:16px; z-index:20; background:#fff; color:#000; padding:10px; }
.stage { position:relative; aspect-ratio:16/9; overflow:hidden; background:var(--paper); box-shadow:0 24px 70px rgba(0,0,0,.55); }
.stage img { width:100%; height:100%; object-fit:cover; display:block; transform:scale(1); transform-origin:center; }
.stage.motion-slow-push img { animation:slowPush var(--scene-duration) linear forwards; }
.stage.motion-slow-pan-left img { width:106%; max-width:none; animation:panLeft var(--scene-duration) linear forwards; }
.stage.motion-slow-pan-right img { width:106%; max-width:none; animation:panRight var(--scene-duration) linear forwards; }
.stage.paused img { animation-play-state:paused; }
@keyframes slowPush { from { transform:scale(1); } to { transform:scale(1.06); } }
@keyframes panLeft { from { transform:translateX(0); } to { transform:translateX(-5.65%); } }
@keyframes panRight { from { transform:translateX(-5.65%); } to { transform:translateX(0); } }
.onscreen { position:absolute; top:7%; left:7%; right:7%; text-align:center; font-family:Georgia,"Noto Serif KR",serif; font-size:clamp(24px,3.1vw,52px); line-height:1.35; font-weight:700; color:#fff; text-shadow:0 2px 9px rgba(0,0,0,.8); white-space:pre-line; }
.caption { position:absolute; left:8%; right:8%; bottom:6%; margin:auto; width:fit-content; max-width:84%; padding:.5em .8em; border-radius:8px; background:rgba(15,13,11,.82); color:#fff; font-size:clamp(16px,2vw,30px); line-height:1.55; text-align:center; text-wrap:balance; }
.caption[hidden], .onscreen:empty { display:none; }
.controls { min-height:64px; display:flex; align-items:center; gap:9px; padding:10px 2px 0; }
button { min-width:44px; min-height:44px; border:1px solid #4c443a; border-radius:9px; background:#211e1a; color:#f6f0e8; font:inherit; cursor:pointer; }
button:hover, button:focus-visible { border-color:#d1b98e; outline:2px solid transparent; }
button:disabled { opacity:.35; cursor:default; }
.meta { min-width:0; flex:1; padding:0 10px; }
.title { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; font-weight:650; }
.status { color:var(--muted); font-size:14px; }
.progress { height:3px; background:#383129; overflow:hidden; }
.progress > span { display:block; height:100%; background:#d1b98e; width:0; transition:width .25s ease; }
@media (max-width:640px) { .app { padding:0; } .controls { padding:8px; flex-wrap:wrap; } .meta { order:-1; flex-basis:100%; } }
@media (prefers-reduced-motion:reduce) { *, *::before, *::after { animation:none!important; transition:none!important; } }
</style>
</head>
<body>
<a class="skip" href="#controls">재생 조작으로 이동</a>
<main class="app">
  <section id="stage" class="stage" aria-label="삽화 장면">
    <img id="frame" alt="">
    <div id="onscreen" class="onscreen"></div>
    <div id="caption" class="caption" aria-live="polite"></div>
  </section>
  <div class="progress" aria-hidden="true"><span id="progress"></span></div>
  <nav id="controls" class="controls" aria-label="애니매틱 재생 조작">
    <button id="prev" type="button" aria-label="이전 장면">←</button>
    <button id="play" type="button" aria-label="재생">▶</button>
    <button id="next" type="button" aria-label="다음 장면">→</button>
    <div class="meta">
      <div id="sceneTitle" class="title"></div>
      <div id="status" class="status"></div>
    </div>
    <button id="captions" type="button" aria-pressed="true">자막</button>
  </nav>
</main>
<script>
const scenes = __SCENES__;
let index = 0, timer = null, playing = false, captionsVisible = true;
const stage = document.getElementById('stage');
const frame = document.getElementById('frame');
const onscreen = document.getElementById('onscreen');
const caption = document.getElementById('caption');
const play = document.getElementById('play');

function stopTimer() { if (timer) clearTimeout(timer); timer = null; }
function queueNext() {
  stopTimer();
  if (!playing) return;
  timer = setTimeout(() => {
    if (index < scenes.length - 1) { index += 1; render(); }
    else { setPlaying(false); }
  }, scenes[index].duration_sec * 1000);
}
function setPlaying(value) {
  playing = value;
  play.textContent = playing ? 'Ⅱ' : '▶';
  play.setAttribute('aria-label', playing ? '일시정지' : '재생');
  stage.classList.toggle('paused', !playing);
  if (playing) queueNext(); else stopTimer();
}
function render() {
  const scene = scenes[index];
  stage.className = 'stage paused';
  void stage.offsetWidth;
  stage.classList.add(`motion-${scene.motion.type}`);
  stage.style.setProperty('--scene-duration', `${scene.duration_sec}s`);
  frame.src = scene.frame;
  frame.alt = scene.alt;
  onscreen.textContent = scene.on_screen_text;
  caption.textContent = scene.caption;
  caption.hidden = !captionsVisible;
  document.getElementById('sceneTitle').textContent = `${scene.id} · ${scene.slug}`;
  document.getElementById('status').textContent = `${index + 1} / ${scenes.length} · ${scene.truth_mode} · ${scene.duration_sec}s`;
  document.getElementById('progress').style.width = `${((index + 1) / scenes.length) * 100}%`;
  document.getElementById('prev').disabled = index === 0;
  document.getElementById('next').disabled = index === scenes.length - 1;
  stage.classList.toggle('paused', !playing);
  if (playing) queueNext();
}
document.getElementById('prev').addEventListener('click', () => { if (index > 0) { index -= 1; render(); } });
document.getElementById('next').addEventListener('click', () => { if (index < scenes.length - 1) { index += 1; render(); } });
play.addEventListener('click', () => setPlaying(!playing));
document.getElementById('captions').addEventListener('click', (event) => {
  captionsVisible = !captionsVisible;
  event.currentTarget.setAttribute('aria-pressed', String(captionsVisible));
  caption.hidden = !captionsVisible;
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'ArrowLeft' && index > 0) { index -= 1; render(); }
  if (event.key === 'ArrowRight' && index < scenes.length - 1) { index += 1; render(); }
  if (event.key === ' ') { event.preventDefault(); setPlaying(!playing); }
});
render();
</script>
</body>
</html>
'''


def build_html(data: dict[str, Any]) -> str:
    preview_fields = (
        "id",
        "slug",
        "frame",
        "alt",
        "on_screen_text",
        "caption",
        "duration_sec",
        "motion",
        "truth_mode",
    )
    preview_scenes = [
        {key: scene[key] for key in preview_fields}
        for scene in data["scenes"]
    ]
    scene_json = json.dumps(preview_scenes, ensure_ascii=False).replace("</", "<\\/")
    scene_json = scene_json.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return HTML_TEMPLATE.replace("__TITLE__", html.escape(data["title"])).replace(
        "__SCENES__", scene_json
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck_dir")
    parser.add_argument(
        "--storyboard-only",
        action="store_true",
        help="Validate the plan and build storyboard/captions without frames or preview",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.deck_dir).expanduser().resolve()
    validation_stage = "plan" if args.storyboard_only else "render"
    errors = validate(root, validation_stage)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"ERROR {validation_stage} validation failed; outputs were not written", file=sys.stderr)
        return 1
    data = json.loads((root / "deck.json").read_text(encoding="utf-8"))
    if args.storyboard_only and data.get("production_status") != "visuals-pending":
        print(
            "ERROR --storyboard-only requires production_status=visuals-pending",
            file=sys.stderr,
        )
        return 1
    if args.storyboard_only and (root / "preview.html").exists():
        print(
            "ERROR refusing storyboard-only output while a stale preview.html exists",
            file=sys.stderr,
        )
        return 1
    outputs = {
        "storyboard.md": build_storyboard(data),
        "captions.vtt": build_vtt(data),
    }
    if not args.storyboard_only:
        outputs["preview.html"] = build_html(data)
    for filename, content in outputs.items():
        (root / filename).write_text(content, encoding="utf-8")
        print(f"WROTE {root / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
