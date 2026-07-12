#!/usr/bin/env python3
"""
tts.py — Kannada TTS helpers, importable by build.py and usable standalone.

Standalone usage (reads existing SRT, writes MP3):
  python3 tts.py                          # uses out/patterns-kn.srt
  python3 tts.py --srt out/custom.srt
  python3 tts.py --out out/voice.mp3
  python3 tts.py --dry-run                # print cues, no audio

When imported by build.py, use build_voice_track() directly with the
narration list already in memory — no SRT round-trip needed.

Requires: pip install gTTS
"""
import argparse, re, subprocess, sys, tempfile
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
# Per-cue TTS
# ---------------------------------------------------------------------------

def _tts_cue(text, lang, tmp_dir, index):
    """Synthesize one narration cue → WAV path."""
    try:
        from gtts import gTTS
    except ImportError:
        raise RuntimeError("gTTS not installed — run: pip install gTTS")
    mp3 = Path(tmp_dir) / f"cue_{index:04d}.mp3"
    wav = Path(tmp_dir) / f"cue_{index:04d}.wav"
    gTTS(text=text, lang=lang, slow=False).save(str(mp3))
    _run(["ffmpeg", "-y", "-i", str(mp3), str(wav)], f"cue {index} decode")
    return str(wav)


# ---------------------------------------------------------------------------
# Public API used by build.py
# ---------------------------------------------------------------------------

def build_voice_track(narr, total_dur, lang, tmp_dir):
    """
    Synthesize all narration cues and assemble them into a single timed WAV.

    narr      — list of {start, end, text} in absolute seconds (from narration())
    total_dur — total video duration in seconds
    lang      — BCP-47 language code, e.g. "kn"
    tmp_dir   — writable directory for intermediate files

    Returns path to the assembled voice WAV.
    """
    inputs = [
        "-f", "lavfi", "-t", str(total_dur + 1),
        "-i", "anullsrc=r=44100:cl=stereo",
    ]
    delays = []

    for i, cue in enumerate(narr):
        print(f"  TTS cue {i+1:3d}/{len(narr)}: {cue['text'][:55]}…")
        wav = _tts_cue(cue["text"], lang, tmp_dir, i)
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
    ap.add_argument("--srt",     default=str(out_dir / "patterns-kn.srt"))
    ap.add_argument("--out",     default=str(out_dir / "patterns-kn-voice.mp3"))
    ap.add_argument("--lang",    default="kn")
    ap.add_argument("--dry-run", action="store_true")
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
            voice_wav = build_voice_track(narr, total_dur, args.lang, tmp)
            _run(["ffmpeg", "-y", "-i", voice_wav,
                  "-c:a", "libmp3lame", "-q:a", "4", args.out], "mp3 encode")
    except RuntimeError as e:
        sys.exit(str(e))

    print(f"done: {args.out}")


if __name__ == "__main__":
    main()
