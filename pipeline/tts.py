#!/usr/bin/env python3
"""
tts.py — Kannada TTS helpers, importable by build.py and usable standalone.

Three voice providers:
  • gtts       — free, no key, robotic. Default. Requires: pip install gTTS
  • sarvam     — Indic-native, best for Kannada. Needs SARVAM_API_KEY +
                 a speaker. No extra pip install (stdlib urllib).
                 See docs/tts-sarvam.md.
  • elevenlabs — natural general voice, needs ELEVENLABS_API_KEY + a
                 Kannada-capable voice. See docs/tts-elevenlabs.md.

Standalone usage (reads existing SRT, writes MP3):
  python3 tts.py                          # uses out/patterns-kn.srt, gtts
  python3 tts.py --srt out/custom.srt
  python3 tts.py --out out/voice.mp3
  python3 tts.py --provider sarvam --voice anushka
  python3 tts.py --provider elevenlabs --voice <voice_id>
  python3 tts.py --dry-run                # print cues, no audio

When imported by build.py, use build_voice_track() directly with the
narration list already in memory — no SRT round-trip needed.
"""
import argparse, os, re, subprocess, sys, tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def _run(cmd, what):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"[{what}] failed:\n{r.stderr[-800:]}")


def audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def _fit_to_window(src_wav, window_sec, tmp_dir):
    """Return path to speed-adjusted WAV that fits within window_sec."""
    dur = audio_duration(src_wav)
    if dur <= 0 or window_sec <= 0:
        return src_wav
    ratio = max(0.5, min(2.0, dur / window_sec))
    if abs(ratio - 1.0) < 0.02:
        return src_wav
    out = Path(tmp_dir) / (Path(src_wav).stem + "_fit.wav")
    _run(["ffmpeg", "-y", "-i", src_wav, "-filter:a", f"atempo={ratio:.4f}", str(out)], "atempo")
    return str(out)


# ---------------------------------------------------------------------------
# Per-cue TTS — provider dispatch
# ---------------------------------------------------------------------------

def _tts_cue_gtts(text, lang, tmp_dir, index):
    """Synthesize one narration cue with Google TTS → WAV path."""
    try:
        from gtts import gTTS
    except ImportError:
        raise RuntimeError("gTTS not installed — run: pip install gTTS")
    mp3 = Path(tmp_dir) / f"cue_{index:04d}.mp3"
    wav = Path(tmp_dir) / f"cue_{index:04d}.wav"
    gTTS(text=text, lang=lang, slow=False).save(str(mp3))
    _run(["ffmpeg", "-y", "-i", str(mp3), str(wav)], f"cue {index} decode")
    return str(wav)


def elevenlabs_config(voice=None, model=None):
    """Resolve ElevenLabs settings from args + environment.

    Env vars (see docs/tts-elevenlabs.md):
      ELEVENLABS_API_KEY   — required
      ELEVENLABS_VOICE_ID  — voice to use if --voice not passed
      ELEVENLABS_MODEL     — model id (default eleven_v3, best language coverage)
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set — see docs/tts-elevenlabs.md")
    voice_id = voice or os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice_id:
        raise RuntimeError(
            "No ElevenLabs voice — pass --voice <voice_id> or set "
            "ELEVENLABS_VOICE_ID (see docs/tts-elevenlabs.md)")
    model_id = model or os.environ.get("ELEVENLABS_MODEL", "eleven_v3")
    return {"api_key": api_key, "voice_id": voice_id, "model_id": model_id}


def _tts_cue_elevenlabs(text, tmp_dir, index, cfg):
    """Synthesize one narration cue with ElevenLabs → WAV path.

    Uses stdlib urllib so no extra dependency is needed in the render env.
    """
    import json, urllib.request, urllib.error
    mp3 = Path(tmp_dir) / f"cue_{index:04d}.mp3"
    wav = Path(tmp_dir) / f"cue_{index:04d}.wav"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}"
    payload = json.dumps({
        "text": text,
        "model_id": cfg["model_id"],
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "xi-api-key": cfg["api_key"],
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            mp3.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"ElevenLabs API error {e.code} on cue {index}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ElevenLabs network error on cue {index}: {e.reason}")
    _run(["ffmpeg", "-y", "-i", str(mp3), str(wav)], f"cue {index} decode")
    return str(wav)


def sarvam_config(speaker=None, model=None):
    """Resolve Sarvam settings from args + environment.

    Env vars (see docs/tts-sarvam.md):
      SARVAM_API_KEY  — required
      SARVAM_SPEAKER  — voice name if --voice not passed (default: anushka)
      SARVAM_MODEL    — TTS model (default: bulbul:v2)
    """
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY not set — see docs/tts-sarvam.md")
    speaker_id = speaker or os.environ.get("SARVAM_SPEAKER", "anushka")
    model_id = model or os.environ.get("SARVAM_MODEL", "bulbul:v2")
    return {"api_key": api_key, "speaker": speaker_id, "model": model_id}


def _sarvam_lang_code(lang):
    """Map the pipeline's BCP-47-ish lang to Sarvam's target code (kn → kn-IN)."""
    return lang if "-" in lang else f"{lang}-IN"


def _tts_cue_sarvam(text, lang, tmp_dir, index, cfg):
    """Synthesize one narration cue with Sarvam → WAV path.

    Sarvam returns base64-encoded WAV in a JSON `audios` list. Stdlib only.
    """
    import base64, json, urllib.request, urllib.error
    raw = Path(tmp_dir) / f"cue_{index:04d}_sarvam.wav"
    wav = Path(tmp_dir) / f"cue_{index:04d}.wav"
    payload = json.dumps({
        "inputs": [text],
        "target_language_code": _sarvam_lang_code(lang),
        "speaker": cfg["speaker"],
        "model": cfg["model"],
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.0,
        "speech_sample_rate": 22050,
        "enable_preprocessing": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech",
        data=payload, method="POST", headers={
            "api-subscription-key": cfg["api_key"],
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"Sarvam API error {e.code} on cue {index}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sarvam network error on cue {index}: {e.reason}")
    audios = data.get("audios") or []
    if not audios:
        raise RuntimeError(
            f"Sarvam returned no audio on cue {index}: {str(data)[:200]}")
    raw.write_bytes(base64.b64decode(audios[0]))
    _run(["ffmpeg", "-y", "-i", str(raw), "-ar", "44100", str(wav)],
         f"cue {index} decode")
    return str(wav)


def _tts_cue(text, lang, tmp_dir, index, provider, cfg):
    """Synthesize one narration cue with the chosen provider → WAV path."""
    if provider == "elevenlabs":
        return _tts_cue_elevenlabs(text, tmp_dir, index, cfg)
    if provider == "sarvam":
        return _tts_cue_sarvam(text, lang, tmp_dir, index, cfg)
    return _tts_cue_gtts(text, lang, tmp_dir, index)


# ---------------------------------------------------------------------------
# Public API used by build.py
# ---------------------------------------------------------------------------

def build_voice_track(narr, total_dur, lang, tmp_dir,
                      provider="gtts", voice=None, model=None):
    """
    Synthesize all narration cues and assemble them into a single timed WAV.

    narr      — list of {start, end, text} in absolute seconds (from narration())
    total_dur — total video duration in seconds
    lang      — BCP-47 language code, e.g. "kn" (used by gtts provider)
    tmp_dir   — writable directory for intermediate files
    provider  — "gtts" (default), "sarvam", or "elevenlabs"
    voice     — provider voice/speaker (falls back to that provider's env var)
    model     — provider model id (falls back to that provider's env var)

    Returns path to the assembled voice WAV.
    """
    if provider == "elevenlabs":
        cfg = elevenlabs_config(voice, model)
    elif provider == "sarvam":
        cfg = sarvam_config(voice, model)
    else:
        cfg = None

    inputs = [
        "-f", "lavfi", "-t", str(total_dur + 1),
        "-i", "anullsrc=r=44100:cl=stereo",
    ]
    delays = []

    for i, cue in enumerate(narr):
        print(f"  TTS cue {i+1:3d}/{len(narr)} [{provider}]: {cue['text'][:50]}…")
        wav = _tts_cue(cue["text"], lang, tmp_dir, i, provider, cfg)
        wav = _fit_to_window(wav, cue["end"] - cue["start"], tmp_dir)
        inputs += ["-i", wav]
        ms = int(cue["start"] * 1000)
        delays.append(f"[{i+1}:a]adelay={ms}|{ms}[c{i}]")

    n = len(narr)
    mix_label = "[0:a]" + "".join(f"[c{i}]" for i in range(n))
    fc = ";".join(delays + [f"{mix_label}amix=inputs={n+1}:normalize=0[voice]"])

    voice_wav = Path(tmp_dir) / "voice_mix.wav"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
          "-map", "[voice]", str(voice_wav)], "voice mix")
    return str(voice_wav)


# ---------------------------------------------------------------------------
# SRT parsing (standalone CLI only)
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")

def _parse_ts(s):
    m = _TS_RE.match(s.strip())
    if not m:
        raise ValueError(f"bad timestamp: {s!r}")
    h, mi, sec, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + sec + ms / 1000


def _parse_srt(path):
    cues = []
    blocks = re.split(r"\n{2,}", path.read_text(encoding="utf-8").strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        parts = lines[1].split("-->")
        if len(parts) != 2:
            continue
        start = _parse_ts(parts[0])
        end   = _parse_ts(parts[1])
        text  = " ".join(lines[2:]).strip()
        cues.append({"index": idx, "start": start, "end": end, "text": text})
    return cues


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def main():
    here = Path(__file__).parent.resolve()
    out_dir = here / ".." / "out"

    ap = argparse.ArgumentParser(description="Generate voiced MP3 from SRT")
    ap.add_argument("--srt",      default=str(out_dir / "patterns-kn.srt"))
    ap.add_argument("--out",      default=str(out_dir / "patterns-kn-voice.mp3"))
    ap.add_argument("--lang",     default="kn")
    ap.add_argument("--provider", default="gtts",
                    choices=["gtts", "sarvam", "elevenlabs"])
    ap.add_argument("--voice",    default=None,
                    help="voice/speaker id (sarvam speaker or elevenlabs voice id)")
    ap.add_argument("--model",    default=None, help="provider model id")
    ap.add_argument("--dry-run",  action="store_true")
    args = ap.parse_args()

    srt_path = Path(args.srt)
    if not srt_path.exists():
        sys.exit(f"SRT not found: {srt_path}\nRun build.py first.")

    narr = _parse_srt(srt_path)
    if not narr:
        sys.exit("No cues found in SRT.")

    total_dur = max(c["end"] for c in narr)
    print(f"SRT: {len(narr)} cues, {total_dur:.1f}s total")

    if args.dry_run:
        for c in narr:
            print(f"  [{c['index']:3d}] {c['start']:6.1f}–{c['end']:.1f}s  {c['text'][:60]}")
        return

    try:
        with tempfile.TemporaryDirectory(prefix="tts_") as tmp:
            voice_wav = build_voice_track(
                narr, total_dur, args.lang, tmp,
                provider=args.provider, voice=args.voice, model=args.model)
            _run(["ffmpeg", "-y", "-i", voice_wav,
                  "-c:a", "libmp3lame", "-q:a", "4", args.out], "mp3 encode")
    except RuntimeError as e:
        sys.exit(str(e))

    print(f"done: {args.out}")


if __name__ == "__main__":
    main()
