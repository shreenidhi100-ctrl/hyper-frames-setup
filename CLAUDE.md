# Ganita Video Pipeline

Generates Kannada-language animated math explainer videos (with synced
SRT subtitle files for voiceover production) from the Karnataka Class 6
*Ganita Prakash* textbook. Currently covers Chapter 1, "Patterns in
Mathematics" (ಗಣಿತದಲ್ಲಿ ವಿನ್ಯಾಸಗಳು).

## Architecture (read this before changing anything)

The whole system is built on ONE principle: **every frame is a pure
function of time**. `renderer/renderer_kn.html` exposes
`window.renderFrame(t)` which deterministically draws the video at
second `t` on a 1280×720 canvas. Everything else derives from that:

- **Frames**: Playwright (headless Chromium) calls `renderFrame(i/fps)`
  and screenshots — no screen recording, zero timing jitter.
- **Subtitles**: narration lines live INSIDE each scene definition
  (`narr` arrays with `at`/`end` offsets). `window.narration()` returns
  absolute-timed cues; the SRT is generated from it. Subs can therefore
  never drift from the animation. NEVER hand-write SRT timings.
- **Audio**: `window.chimeTimes()` returns answer-reveal timestamps;
  ffmpeg synthesizes a two-note chime and overlays copies at those
  offsets on a silent base track.
- **Assembly**: `pipeline/build.py` renders each scene as an
  independent MP4 segment (resumable via `out/manifest.json`), then
  losslessly concats + muxes audio + writes the SRT.

### Scene anatomy (renderer_kn.html)
Each scene in the `SCENES` array has:
- `dur` — seconds; question scenes derive it from `timeline(G)` where
  G = guess-prompt time, R = G+3 (reveal), B = G+4 (banner), DUR = G+9.5
- `tag`, `tagColor` — corner badge (textbook section reference)
- `narr` — narration cues `{at, end, text}` in scene-local seconds
- `draw(t)` — canvas drawing for scene-local time t

The teaching arc per scene: question (0.3s) → hint line (2.2s) → slow
animated build with captions → pulsing guess prompt (G..R) → reveal
with arithmetic (R) → explanation banner (B). Preserve this arc when
adding scenes.

## Commands

```bash
cd pipeline
python3 build.py --validate        # fast pre-flight: JS errors, cue overlaps, speech-rate
python3 build.py                   # full build, resumes from manifest if interrupted
python3 build.py --scenes 3,4      # re-render only scenes 3 and 4 after edits
python3 build.py --force           # ignore manifest, rebuild everything
```
Output: `out/patterns-kn.mp4` + `out/patterns-kn.srt`.

ALWAYS run `--validate` after editing the renderer and BEFORE a full
build. It catches in seconds what would otherwise fail after minutes.

## Environment requirements
- Python 3.10+, `playwright` (`playwright install chromium`), ffmpeg
- A Kannada-shaping font. FreeSerif (fonts-freefont-ttf) works;
  Noto Sans Kannada is better if available. Verify shaping by
  rendering a frame containing conjuncts (ಲ್ಲಿ, ನ್ಯಾ, ಕ್ಕೆ) and checking
  visually — fc-list alone doesn't prove shaping works.

## Hard-won gotchas (violate these at your peril)
1. **Playwright font settling**: after `page.goto`, wait ~400ms before
   the first `renderFrame` call or early frames render with fallback
   glyph metrics. `page_open()` already does this.
2. **Long processes die between tool sessions**: never rely on
   `nohup`/background processes surviving. The segmented build exists
   precisely so interrupted runs resume. Keep ffmpeg calls in the
   foreground.
3. **ffmpeg concat**: segments must share codec/fps/pix_fmt (they do —
   all come from the same encode settings). Use `-c copy` concat; do
   not re-encode segments together.
4. **Narration pacing**: Kannada TTS speaks ~11–15 chars/sec. The
   validator flags cues >17 chars/sec. Numbers in narration text should
   be Kannada words (ಇಪ್ಪತ್ತೊಂದು), not digits — TTS reads digits in
   English or awkwardly. On-screen text keeps Western digits (matches
   the textbook).
5. **Terminology**: use the textbook's own terms — ಎಣಿಕೆ/ಬೆಸ/ಸಮ/
   ತ್ರಿಕೋನೀಯ/ವರ್ಗ/ಘನ ಸಂಖ್ಯೆಗಳು, ಷಡ್ಭುಜ, ಸಪ್ತಭುಜ, ಕೋಷ್ಟಕ (table).
   Source: Ganita Prakash Ch.1, pages 1–10 (§1.1–§1.6).
6. **Canvas fonts**: use the F_HEAD / F_BODY / F_MONO constants, never
   raw font stacks — captions containing Kannada must not use pure
   monospace fonts (missing glyphs).
7. **Chromium recycling**: build.py restarts the browser every 4 scenes
   (BROWSER_RECYCLE). Don't remove this; memory drifts on very long
   captures.

## Video planning acceptance criteria (enforce for every chapter)

These rules govern how questions are grouped into videos. They are checked
during `/new-chapter-plan` and must not be violated when writing scenes.

### Duration targets
- **Target: 5–10 minutes per video.** This is a hard constraint.
  - Simple definition/identification questions: ~1–1.5 min each
  - Drawing/classification questions: ~1.5–2 min each
  - Measurement/construction questions: ~2–3 min each
- The **only** exception: the last video in a chapter or exercise may be
  shorter if it exhausts all remaining questions.
- Never pad a video with filler; never split a tightly related group just
  to hit the lower bound.

### Grouping principles
1. **One common trick per video.** Every video must have a single unifying
   method or insight (e.g., "vertex in the middle of angle notation",
   "right angle as benchmark", "estimate-first strategy"). State it
   explicitly in the plan before writing any scenes.
2. **Topical coherence.** Questions in the same video must share a concept
   or solving method. Don't mix unrelated section questions just to fill time.
3. **Sequential within a section.** Don't skip questions or reorder them
   across videos unless the grouping rationale is explicitly stated.

### Planning output format (required)
Every `/new-chapter-plan` run must produce:
- A **complete question catalog** (section → question number → one-line description).
- A **video grouping table** with columns:
  `Video | Title (Kannada) | Questions covered | Common trick/method | Estimated duration`
- A **template audit**: which existing visual templates apply, which are new.
- A **flag** if any new canvas templates are needed before scenes can be written.

### Template audit (known templates as of Ch.1)
Existing: `sequence-row`, `dot-triangle`, `growing-grids`, `layered-square`,
`hex-rings`, `polygon-row`, `mosaic`, `complete-graphs`.
For each new chapter, explicitly list which templates are reused and which
must be built first. Do not write question scenes that depend on a template
that doesn't exist yet.

## Roadmap / invariants for extension
- **Data-driven scenes** (next big step): extract the reusable visual
  templates into a template library and define scenes in
  `content/<chapter>.json` (template + params + narration). New exercises
  then need JSON only.
- **Per-question videos**: prefer several short videos per exercise over one
  long one — better for attention span and render robustness. Target 5–10
  min each (see acceptance criteria above). The segment architecture already
  supports this: a "video" is just a contiguous range of scenes.
- Keep `renderFrame(t)` pure. No Date.now(), no Math.random() without
  a fixed seed, no CSS animations, no setTimeout in draw paths.
