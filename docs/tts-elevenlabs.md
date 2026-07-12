# Natural Kannada voiceover with ElevenLabs

The pipeline supports two TTS providers. `gtts` (Google) is the default —
free, no key, but robotic and flat. **ElevenLabs** produces natural,
expressive Kannada that holds a child's attention far better. Use it for
anything you actually publish.

No extra `pip install` is needed — the integration uses Python's stdlib
`urllib`. You only need an API key and a voice.

---

## 1. Get an API key

1. Create an account at <https://elevenlabs.io> (the free tier includes a
   monthly character quota — enough to draft a video or two; a paid tier is
   needed for regular publishing).
2. Profile → **API Keys** → create a key.
3. Copy it. This is your `ELEVENLABS_API_KEY`.

## 2. Pick a Kannada-capable voice

Kannada (ಕನ್ನಡ) is **only** supported by the multilingual models — never by
the English-only ones. Use `eleven_v3` (widest language coverage, ~70+
languages incl. Kannada) or `eleven_multilingual_v2`. The model is set by
`ELEVENLABS_MODEL` (default `eleven_v3`).

To find a voice id:

- **Voice Library** (elevenlabs.io → Voices): filter/search for a voice that
  lists Kannada or Indic support, add it to *My Voices*, then open it and
  copy the **Voice ID** (a 20-character string like `pNInz6obpgDQGcFmaJgB`).
- Or list your available voices from the API:

  ```bash
  curl -s -H "xi-api-key: $ELEVENLABS_API_KEY" \
       https://api.elevenlabs.io/v1/voices \
    | python3 -c "import sys,json; [print(v['voice_id'], '·', v['name']) for v in json.load(sys.stdin)['voices']]"
  ```

That voice id is your `ELEVENLABS_VOICE_ID`.

> **Always verify Kannada shaping by ear.** Model coverage of Kannada varies
> by voice. Render one cue (see §4) and listen before committing to a voice —
> some voices read Kannada with a heavy English accent or mangle conjuncts
> (ಲ್ಲಿ, ನ್ಯಾ, ಕ್ಕೆ). Numbers must already be Kannada words in the narration
> text (per CLAUDE.md), which helps here too.

## 3. Configure the environment

Set these as environment **Variables** in the Claude Code cloud environment
(the same "Hyperframes setup" dialog where the setup script lives) — **not**
in the setup script, and never committed to git:

| Variable | Required | Purpose |
|---|---|---|
| `ELEVENLABS_API_KEY` | yes | your API key |
| `ELEVENLABS_VOICE_ID` | recommended | default voice (override per-run with `--voice`) |
| `ELEVENLABS_MODEL` | optional | default `eleven_v3`; set `eleven_multilingual_v2` to switch |

Locally, export them in your shell instead:

```bash
export ELEVENLABS_API_KEY="sk_..."
export ELEVENLABS_VOICE_ID="pNInz6obpgDQGcFmaJgB"
```

## 4. Use it

Full build with ElevenLabs voiceover baked into the final MP4:

```bash
python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts --tts-provider elevenlabs
# or override the voice for this run only:
python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts --tts-provider elevenlabs --voice <voice_id>
```

Quick standalone test on an existing SRT (cheap way to audition a voice
before a full render):

```bash
python3 pipeline/tts.py --provider elevenlabs --voice <voice_id> \
        --srt hyperframes/ch2-v1/ch2-v1.srt --out /tmp/audition.mp3
```

Default (free, robotic) is still just:

```bash
python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts        # gtts
```

## 5. How timing stays in sync

Each narration cue is synthesized independently, then time-stretched with
ffmpeg `atempo` (0.5×–2.0×) to fit exactly inside its `at`→`end` window from
`narration.json`, and laid onto a silent base track at its absolute offset
(`tts.py: build_voice_track`). So the voice can never drift from the
animation — the SRT and the audio come from the same cue list. Write cues at
~11–15 chars/sec (the validator flags >17) so ElevenLabs isn't forced into an
unnatural speed-up.

## 6. Cost & failure notes

- ElevenLabs bills per character. A ~7-minute video is a few thousand
  characters — check your plan's quota before batch-rendering a whole chapter.
- On an API error the build stops with the HTTP status and response body
  (e.g. quota exhausted `401/429`, bad voice id `400`). Fix the cause and
  re-run; the segmented build resumes from `out/manifest.json`.
- If the key/voice isn't set, `hf_build.py --tts-provider elevenlabs` fails
  fast with a message pointing back to this doc. Fall back to `gtts` anytime
  by dropping `--tts-provider elevenlabs`.
