# Kannada voiceover with Sarvam AI

Sarvam's TTS is built specifically for Indian languages, so for Kannada it's
the **recommended provider** — better conjunct shaping and prosody than the
general-purpose alternatives, and cheaper for this workload. No extra
`pip install` is needed (the integration uses stdlib `urllib`); you only need
an API key and a speaker.

---

## 1. Get an API key

1. Sign up at <https://dashboard.sarvam.ai>.
2. Create an **API subscription key**.
3. Copy it — this is your `SARVAM_API_KEY`.

## 2. Pick a speaker

The default model is `bulbul:v2`. Its Kannada speakers include:

| Female | Male |
|---|---|
| `anushka`, `manisha`, `vidya`, `arya` | `abhilash`, `karun`, `hitesh` |

For a kids' math explainer a warm female voice like `anushka` or `vidya`
works well. Set your choice as `SARVAM_SPEAKER` (or pass `--voice` per run).

> Speaker names must match the model. If you switch `SARVAM_MODEL` to the
> older `bulbul:v1`, its speaker set is different (`meera`, `pavithra`,
> `maitreyi`, `arvind`, `amol`, `amartya`, …). A wrong speaker/model pairing
> returns a 400 with a clear message — just fix `SARVAM_SPEAKER`.

## 3. Configure the environment

Set these as environment **Variables** in the Claude Code cloud environment
(the "Hyperframes setup" dialog) — **not** in the setup script, never in git:

| Variable | Required | Purpose |
|---|---|---|
| `SARVAM_API_KEY` | yes | your API subscription key |
| `SARVAM_SPEAKER` | recommended | default speaker (override per-run with `--voice`) |
| `SARVAM_MODEL` | optional | default `bulbul:v2`; set `bulbul:v1` to switch |

Locally, export them in your shell instead:

```bash
export SARVAM_API_KEY="..."
export SARVAM_SPEAKER="anushka"
```

## 4. Use it

Full build with Sarvam voiceover baked into the final MP4:

```bash
python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts --tts-provider sarvam
# override the speaker for this run only:
python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts --tts-provider sarvam --voice vidya
```

Quick standalone audition on an existing SRT (cheap — no full render):

```bash
python3 pipeline/tts.py --provider sarvam --voice anushka \
        --srt hyperframes/ch2-v1/ch2-v1.srt --out /tmp/audition.mp3
```

## 5. How it works / sync

- Language is derived from the pipeline `--lang` (`kn` → `kn-IN`); Sarvam also
  supports `hi-IN`, `ta-IN`, `te-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `bn-IN`, etc.
- `enable_preprocessing` is on, which helps with mixed-script text — but keep
  following CLAUDE.md and write numbers as Kannada words in narration.
- Each cue is synthesized on its own, then time-stretched with ffmpeg
  `atempo` to fit exactly inside its `at`→`end` window and laid at its
  absolute offset (`tts.py: build_voice_track`), so the voice can't drift from
  the animation. Write cues at ~11–15 chars/sec so no cue gets an unnatural
  speed-up. Each Sarvam input is capped at 500 characters, which a single cue
  never approaches.
- Sarvam returns base64-encoded WAV; the code decodes it and normalises to
  44.1 kHz before mixing.

## 6. Failure notes

- On an API error the build stops with the HTTP status and response body
  (bad key, quota, wrong speaker). Fix and re-run — the segmented build
  resumes.
- Missing key/speaker fails fast with a message pointing here. Fall back to
  `gtts` anytime by dropping `--tts-provider sarvam`.
