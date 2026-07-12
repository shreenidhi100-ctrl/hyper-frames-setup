Add a new question scene to a HyperFrames composition for: $ARGUMENTS

## Pre-flight checks (do these first, write no code until done)

1. **Plan exists.** A `/new-chapter-plan` must have been approved for this
   chapter. Confirm the scene belongs to a planned video with a named
   common trick/method.

2. **Target directory.** Identify the video directory:
   `hyperframes/<chapter>-<video>/`   e.g. `hyperframes/ch2-v1/`
   It must contain `index.html` and `narration.json`.

3. **Template exists.** The visual layout this scene needs must already
   appear in another scene in the same `index.html`. If not, build the
   CSS template first — do not inline one-off styles.

4. **Duration budget.** Check the video's current total duration:
   - Sum `end` values of the last cue in `narration.json`.
   - Adding this scene must keep the video ≤ 10 min (600s).

---

## Scene timing targets (match to question complexity)

| Question type             | Scene duration | Reveal at (G) |
|---------------------------|---------------|---------------|
| Simple identification     | 15–20s        | 8–10s         |
| Drawing / classification  | 20–26s        | 12–16s        |
| Measurement / multi-step  | 28–36s        | 18–25s        |
| Complex / exploration     | 36–46s        | 28–35s        |

---

## What to write

### A) Scene div in `index.html`

Insert **before** `</div><!-- /root composition -->` and **before** the
outro scene div. Follow this structure exactly:

```html
<!-- ═══════════════════════════════════════════════════
     QN — short description (startTime – endTime s)
════════════════════════════════════════════════════ -->
<div id="s-qN" class="scene">
  <div class="badge">§X.Y · QN</div>
  <div class="q-label h" id="qN-lbl">ಪ್ರಶ್ನೆ N</div>
  <div class="question h" id="qN-q">Question text in Kannada</div>

  <div class="diagram h" id="qN-d">
    <svg viewBox="0 0 720 240">
      <!-- static skeleton always visible when diagram fades in -->
      <!-- animated reveal elements start with opacity="0" -->
    </svg>
  </div>

  <div class="reveal h" id="qN-rev">Short answer in Kannada</div>
  <div class="trick" id="qN-trick">Common trick — woven from the video plan</div>
</div>
```

Rules:
- All interactive elements that animate in start with `opacity: 0`
  (use `opacity="0"` on SVG elements, class `h` on HTML elements).
- Lesson arc: question visible → diagram builds → reveal → trick banner.
- SVG `viewBox="0 0 720 240"` for landscape diagrams; adjust height for
  taller content but keep width ≤ 720.
- Use `font-family="sans-serif"` on SVG text for Latin labels;
  Kannada text in SVG needs `font-family="Noto Sans Kannada, sans-serif"`.
- The `.trick` div always shows the video's **common trick** (from the
  plan), not a scene-specific tip.
- **Animation is mandatory (see CLAUDE.md → "Animation is mandatory").**
  Give the diagram parts that build progressively (each line/arc/dot its own
  reveal element) and at least one element that can carry a *continuous*
  loop (a pulsing guess prompt, a breathing focus ring, a sweeping arrow).
  A scene where everything fades in once and then holds still is a defect.

### B) GSAP keyframes in the `<script>` block

Add inside the `<script>` block, **after** the preceding scene's
`hideScene(...)` call and **before** `window.__timelines[...]`:

```javascript
// ── QN (startTime – endTime s) ──────────────────────
showScene('s-qN', tl, START);
fadeIn('#qN-lbl',  tl, START + 0.2, 0.3);
slideIn('#qN-q',   tl, START + 0.5);
fadeIn('#qN-d',    tl, START + 1.2, 0.4);
// diagram BUILDS progressively — each part its own reveal, staggered:
tl.to('#qN-elem1', { opacity: 1, duration: 0.4 }, START + 2.0);
drawOn('#qN-line', tl, START + 2.6);          // stroke draws on, not a cut
tl.to('#qN-elem2', { opacity: 1, duration: 0.4 }, START + 3.5);
// CONTINUOUS motion so the frame is never still (loops until scene hides):
pulse('#qN-guess', tl, START + 4.0);          // e.g. the guess prompt
// reveal with an overshoot pop, not an instant appearance:
tl.fromTo('#qN-rev', { opacity: 0, scale: 0.8 },
          { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.7)' }, REVEAL_TIME);
fadeIn('#qN-trick',  tl, REVEAL_TIME + 2.0);
hideScene('s-qN', tl, END);
```

Replace START / REVEAL_TIME / END with absolute seconds (matching the
scene duration table above). The hideScene time = START of the next
scene.

**Continuous motion is required** — at least one element per scene must
loop so no ~2s window is a dead still frame (CLAUDE.md rule 3). If the
composition doesn't already have these helpers, add them once to the
`<script>` block alongside `showScene`/`fadeIn`/`slideIn`:

```javascript
// looping "breathing" scale — deterministic (timeline seeks to t)
function pulse(sel, tl, at, scale=1.08, dur=0.7) {
  tl.set(sel, { opacity: 1, transformOrigin: '50% 50%' }, at);
  tl.to(sel, { scale, duration: dur, ease: 'sine.inOut',
               repeat: -1, yoyo: true }, at);
}
// stroke draw-on for an SVG <line>/<path> (set pathLength or use its length)
function drawOn(sel, tl, at, dur=0.6) {
  tl.set(sel, { opacity: 1, strokeDasharray: 1000, strokeDashoffset: 1000 }, at);
  tl.to(sel, { strokeDashoffset: 0, duration: dur, ease: 'power1.inOut' }, at);
}
```

These are pure GSAP tweens — no `Date.now`, `setTimeout`, or CSS keyframes —
so `renderFrame(t)` stays deterministic.

### C) Narration cues in `narration.json`

Append 2–4 cue objects to the `"cues"` array, **before** any outro cues:

```json
{ "scene": "qN", "at": START + 0.5, "end": START + 4.5,
  "text": "Kannada narration — intro to question" },
{ "scene": "qN", "at": START + 5.0, "end": START + 9.0,
  "text": "Kannada narration — hint or build" },
{ "scene": "qN", "at": REVEAL_TIME + 0.5, "end": REVEAL_TIME + 4.0,
  "text": "Kannada narration — explain answer" }
```

Narration rules:
- Text in spoken Kannada. Numbers as Kannada words (ಇಪ್ಪತ್ತೊಂದು not 21).
- Keep each cue ≤ 15 chars/sec: `len(text) / (end - at) ≤ 15`.
- No gaps > 5s without a narration cue (silence feels dead on video).
- Weave the video's **common trick** into the reveal cue's text.

---

## After editing

1. From the video directory, run lint:
   ```bash
   cd hyperframes/ch2-v1 && hyperframes lint .
   ```
   Fix any errors before continuing.

2. Spot-check with hf_build (lint + render + SRT + mux):
   ```bash
   python3 pipeline/hf_build.py hyperframes/ch2-v1/
   ```

3. Extract one frame at the reveal moment to verify layout:
   ```bash
   ffmpeg -ss REVEAL_TIME -i hyperframes/ch2-v1/ch2-v1-final.mp4 \
          -vframes 1 /tmp/spot.png
   ```
   Open `/tmp/spot.png` and confirm: Kannada shapes correctly, diagram
   visible, reveal text readable, no overflow.

4. Confirm scene duration matches the complexity tier in the table above.
   If > 20% off, adjust the timing and re-run.
