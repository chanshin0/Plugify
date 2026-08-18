---
name: visualize
description: "Create polished, standalone single-file HTML visualizations from ideas, documents, URLs, conversation context, or data. Use when the user asks to visualize or 시각화 content, or requests a dashboard, infographic, flowchart, diagram, timeline, comparison, data story, mind map, kanban, one-pager, poster, or visual HTML. Preserve this skill's file-based Career Hacker Alex workflow rather than an answer-inline visual surface. Do not use for ordinary app/site implementation, repository AI-readiness maps handled by ai-readiness-cartography, or lecture/video slide production handled by presentation_slides unless the user explicitly invokes this skill."
---

# Visualize

Create one polished, portable HTML file that helps a person understand the source material faster.

This Plugify adaptation is derived from Career Hacker Alex's MIT-licensed `visualize` v0.3.0: <https://github.com/careerhackeralex/visualize>. Preserve the copyright and license in [LICENSE](LICENSE). The imported upstream instructions are retained as a non-operative archive in [references/upstream-skill-v0.3.0.md](references/upstream-skill-v0.3.0.md); this top-level SKILL, especially its browser-safety contract, always overrides the archive's auto-open behavior.

## Output contract

- Produce a standalone `.html` file. Do not substitute an answer-inline visualization surface unless the user explicitly asks for inline rendering.
- Write to the user-specified location. Otherwise use `~/Downloads/<descriptive-kebab-name>.html`.
- Keep custom CSS and JavaScript in the file. Use pinned CDN libraries only when they materially improve the result.
- Preview the file with a supported in-app/browser automation tool when available. Do not auto-launch or manipulate the user's everyday Chrome process or profile; if a supported preview is unavailable, finish and return the file link.
- Return a clickable absolute local path. In Codex, use a Markdown file link; in a client that supports `file://`, that form is also acceptable.
- Use real source material from the conversation, provided files, connected sources, or cited URLs. Never invent placeholder metrics when actual data exists.

## Read the references

Before creating a visualization, read:

1. [references/skeleton.md](references/skeleton.md) for the operative HTML base.
2. [references/design-system.md](references/design-system.md) for typography, color, spacing, accessibility, and visual restraint.
3. The matching format section in [references/types.md](references/types.md).

Read additional references only when relevant:

- Charts, diagrams, maps, or 3D: [references/libraries.md](references/libraries.md)
- Motion beyond the base reveal system: [references/animations.md](references/animations.md)
- Utility-menu changes: [references/menu.md](references/menu.md)
- Advanced CSS treatment: [references/css-techniques.md](references/css-techniques.md)
- Final quality review: [references/eval.md](references/eval.md)
- Exact upstream behavior or provenance comparison: [references/upstream-skill-v0.3.0.md](references/upstream-skill-v0.3.0.md)

## Browser verification safety

Treat browser verification as a user-visible safety boundary on macOS.

```json
{
  "schema": "plugify.visualize.browser-safety/1",
  "defaultSandboxChromeGuiBinary": "forbidden",
  "supportedBrowserTool": "first",
  "cliFirstLaunch": "escalated-or-unsandboxed",
  "sandboxProbe": "forbidden",
  "userDataDir": "fresh-temporary-isolated",
  "requiredCliFlags": [
    "--user-data-dir=<fresh-temp-dir>",
    "--no-first-run",
    "--no-default-browser-check"
  ],
  "viewportRuns": "sequential",
  "parallelBrowserProcesses": "forbidden",
  "sandboxCrashSignals": [
    "exit-134",
    "SIGABRT",
    "LaunchServices-sandbox-denial"
  ],
  "onSandboxCrash": "stop-retries-then-tool-fallback-or-report",
  "userChromeProcess": "no-kill",
  "userChromeProfile": "no-reuse"
}
```

- Never directly execute a Chrome or Chromium macOS GUI app binary inside the default sandbox. Do not run a sandbox probe merely to see whether it fails.
- Use the runtime's supported browser automation, browser control, or `agent-browser` tool first.
- If CLI headless Chrome is the only available path, request escalated/unsandboxed execution on the first attempt. Create a fresh temporary directory and pass it through `--user-data-dir`, together with `--no-first-run` and `--no-default-browser-check`.
- Verify desktop and mobile/375px sequentially. Reuse one supported managed session when possible; otherwise run one isolated CLI browser process at a time. Never use `Promise.all` or any other parallel browser-process launch.
- If a launch reports exit 134, `SIGABRT`, or a LaunchServices sandbox denial, stop all retries in that sandbox. Fall back to a supported browser tool or report the environment limitation.
- In every browser-verification plan or handoff, name `exit 134`, `SIGABRT`, and `LaunchServices sandbox denial` explicitly and state that none permits any further retry in the same sandbox.
- Before planning or executing browser verification, include the following preflight block verbatim. A plan missing any line is invalid and must not execute:

  ```text
  BROWSER SAFETY PREFLIGHT
  PATH: supported browser automation/agent-browser first
  CLI: first launch requires escalated/unsandboxed approval; no sandbox probe
  PROFILE: fresh temporary --user-data-dir + --no-first-run + --no-default-browser-check
  VIEWPORTS: desktop then 375px, sequential only; no Promise.all or parallel browser processes
  CRASH STOP: exit 134 / SIGABRT / LaunchServices sandbox denial => no further retry in this sandbox; tool fallback or environment-limit report
  USER CHROME: no kill, attach, reuse, profile access, or alteration
  ```

- Never reinterpret another crash label such as SIGTRAP, Crashpad, or a profile-lock failure as permission to retry the Chrome app binary in the same sandbox. Any browser-process abort during this path stops the CLI fallback.
- Never kill, `pkill`, attach to, reuse, or alter the user's normal Chrome process or everyday Chrome profile.

## Workflow

1. Identify the audience, main message, source facts, and desired output dimensions.
2. Choose the smallest useful format: dashboard for monitored metrics, infographic or data story for narrative, flowchart for process, timeline for chronology, comparison for alternatives, one-pager for a brief, or slide deck only when separate slides are genuinely needed.
3. Copy the complete operative skeleton. Replace its content region; do not start from blank HTML.
4. Establish one dominant visual idea and a clear reading order before styling details.
5. Add at least one meaningful interaction appropriate to the format, such as filtering, drill-down, accordion details, category toggles, slide navigation, or selectable nodes. Theme and download controls alone do not count.
6. Adapt the atmosphere, layout, and accent colors to the subject. Avoid template repetition, ornamental gradients, floating blobs, gratuitous glass effects, and decorative motion.
7. Verify the file through the safe browser contract above at desktop and 375 px width, sequentially. Fix visible overflow, clipped content, unreadable labels, broken controls, console errors, and theme regressions before returning it.

## Non-negotiable quality rules

- Use semantic landmarks and multiple `<section>` elements. Include a skip link and accessible names for interactive controls.
- Support explicit light and dark theme classes with persistent theme selection.
- Include print/PDF styles and `prefers-reduced-motion` handling.
- Keep content visible without animation JavaScript. Use restrained entrance motion and disable it for reduced-motion users.
- Maintain readable hierarchy: body at least 16 px, clearly descending headings, sufficient section spacing, and 44 px touch targets where practical.
- For Korean content, load Noto Sans KR and use Korean-appropriate line height; keep Inter for compact UI labels when useful.
- Give every chart an explicit-height container, accessible description, responsive sizing, enabled tooltips, and theme-aware colors. Guard library loading and avoid blank chart regions.
- Use inline SVG for simple icons. Do not use emoji as interface icons or hotlink arbitrary imagery.
- Do not embed secrets, private tokens, or sensitive source material beyond what the user authorized for the output.
- Keep fixed-canvas posters and social cards within their requested aspect ratio with no scrolling or dead space.
- Never use `body { overflow-x: hidden; }` or an equivalent page-level clipping rule as a responsive fix. It can make width metrics look green while cutting off text. Repair the offending grid, width, padding, `min-width`, or wrapping rule; confine decorative overflow to a non-content wrapper.

## Verification checklist

- The HTML file exists at the reported absolute path and opens successfully through a supported preview path.
- The visualization contains the user's real content and a clear primary insight.
- Light/dark theme, menu, print/PDF, and the format-specific interaction work.
- Desktop and 375 px layouts have no horizontal overflow or clipped controls.
- At 375 px, screenshots show every first-screen headline, summary, and action line wrapping inside the viewport; `scrollWidth == clientWidth` alone is not proof because page-level overflow clipping can hide a defect.
- Charts and diagrams render with no console errors and have accessible labels.
- Keyboard focus, reduced-motion behavior, contrast, and semantic structure are intact.
- The returned response links the file and briefly names what was visualized.

Treat the first real Plugify use as an observation run: retain the generated HTML and browser evidence so an independent reviewer can compare the output against this contract.
