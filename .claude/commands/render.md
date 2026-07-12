Render a video from a HyperFrames composition or the Chapter 1 Playwright renderer.

---

## HyperFrames videos (Chapter 2+)

All videos in `hyperframes/` use the automated HyperFrames pipeline:

```bash
# Render + SRT + mux in one command:
python3 pipeline/hf_build.py hyperframes/<video>/

# With Kannada voiceover (gTTS, requires internet):
python3 pipeline/hf_build.py hyperframes/<video>/ --tts

# Lint only (fast check before committing):
python3 pipeline/hf_build.py hyperframes/<video>/ --lint-only

# Force re-render even if output already exists:
python3 pipeline/hf_build.py hyperframes/<video>/ --force
```

**What hf_build.py does (in order):**
1. `hyperframes lint .` — catch composition errors before wasting render time
2. `hyperframes render . -o <video>.mp4 -f 20` — render frames via headless Chrome
3. `gen_srt.py narration.json` — generate `<video>.srt` from narration cues
4. _(optional)_ `tts.py` — synthesize Kannada voiceover from the SRT cues
5. `ffmpeg mux` — combine video + subtitles [+ voice] → `<video>-final.mp4`

**After running, always verify:**
```bash
# Check duration matches narration.json total
ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 \
        hyperframes/<video>/<video>-final.mp4

# Spot-check 3 frames: intro, mid-video, reveal
ffmpeg -ss 5   -i hyperframes/<video>/<video>-final.mp4 -vframes 1 /tmp/f1.png
ffmpeg -ss 50  -i hyperframes/<video>/<video>-final.mp4 -vframes 1 /tmp/f2.png
ffmpeg -ss 90  -i hyperframes/<video>/<video>-final.mp4 -vframes 1 /tmp/f3.png
```
Open each frame and confirm: Kannada renders correctly, scene transitions
fired, no blank frames, SVG diagrams visible.

---

## Chapter 1 (Playwright renderer)

The original Chapter 1 video uses the Playwright/Canvas pipeline:

```bash
cd pipeline
python3 build.py --validate    # fast pre-flight: JS errors, cue overlaps, speech-rate
python3 build.py               # full build (resumes from manifest if interrupted)
python3 build.py --scenes 3,4  # re-render only scenes 3 and 4 after edits
python3 build.py --force       # ignore manifest, rebuild everything
python3 build.py --tts         # add Kannada voiceover
```

Output: `out/patterns-kn.mp4` + `out/patterns-kn.srt`

**Always run `--validate` before a full build** — it catches JS errors
and narration problems in seconds.
