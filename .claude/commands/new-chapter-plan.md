Plan video coverage for a new chapter/exercise: $ARGUMENTS

## Step 1 — Locate the source PDF
Find the chapter PDF in `source/`. Naming convention: `ganita-prakash-ch<N>.pdf`.
- If $ARGUMENTS specifies a chapter number, open that file (e.g. `source/ganita-prakash-ch2.pdf`).
- If not specified, list PDFs in `source/` and ask the user which to use.

## Step 2 — Read and catalog every question
Read all pages of the chapter. For each ಕಂಡುಹಿಡಿಯಿರಿ / exercise block, produce a
**complete question catalog** in this format:

| Section | Q# | Description (one line) |
|---------|-----|------------------------|
| §2.4    | Q1  | Rihaana vs Sheetal — how many lines through 1 vs 2 points? |

Do not skip or summarize questions. If a question has sub-parts (a, b, c…),
list each sub-part separately if they have distinct solving steps; group them
on one row only if they are trivially similar.

## Step 3 — Template audit
List which existing visual templates apply to this chapter's questions:

**Known templates (Ch.1):** sequence-row, dot-triangle, growing-grids,
layered-square, hex-rings, polygon-row, mosaic, complete-graphs.

For each question group, state:
- `REUSE <template-name>` if an existing template covers it, or
- `NEW <proposed-template-name>` with a one-line description of what it renders.

Flag clearly if new templates must be built before scenes can be written.
New templates are a blocker — do not proceed to scene writing without them.

## Step 4 — Group into videos
Apply the acceptance criteria from CLAUDE.md ("Video planning acceptance criteria"):

**Duration targets:**
- Simple identification questions: ~1–1.5 min each
- Drawing/classification questions: ~1.5–2 min each
- Measurement/construction questions: ~2–3 min each
- Target total per video: **5–10 minutes** (hard constraint)
- Exception: the final video of a chapter/exercise may be shorter if it
  exhausts all remaining questions.

**Grouping rules:**
1. Each video must have ONE unifying trick or method. Name it explicitly.
2. Questions must share a concept or solving approach within a video.
3. Preserve section order unless you explicitly justify reordering.

Output a **video grouping table**:

| Video | Title (Kannada) | Questions | Common trick/method | Est. duration |
|-------|-----------------|-----------|---------------------|---------------|
| V1    | ಬಿಂದು, ರೇಖೆ, ಕಿರಣ | §2.4 Q1–Q6 | Notation rules: capital=point, arrow=direction | ~7–8 min |

## Step 5 — Runtime estimate and approval gate
- Sum the estimated durations across all videos.
- State total scene count estimate (duration_per_video / avg_scene_duration).
  Use ~90s average scene duration as the baseline.
- **Stop here and get user approval before writing any code or scenes.**
  Do not proceed to `/new-scene` until the plan is confirmed.

## Step 6 — After approval
Once approved, scenes are added one video at a time using `/new-scene`.
Reference the approved plan when writing each scene so the common trick
is woven into the narration of every question in that video group.
