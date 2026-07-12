#!/usr/bin/env python3
"""
build.py — stable, resumable video build for long explainer videos.

Each scene is rendered and encoded as its own segment. A manifest marks
completed segments so a crashed or interrupted run resumes where it stopped.
The final video is a lossless concat of segments + one audio pass + SRT.

  python3 build.py                    # full build (resumes if partial)
  python3 build.py --validate         # fast pre-flight check, no render
  python3 build.py --scenes 3,4       # re-render only scenes 3 and 4
  python3 build.py --force            # ignore manifest, rebuild all
  python3 build.py --tts              # synthesize Kannada voiceover (needs gTTS)
  python3 build.py --tts --lang kn    # explicit language (default: kn)

Output: out/patterns-kn.mp4  (video + audio + embedded SRT)
        out/patterns-kn.srt  (standalone subtitle file)

Why this is stable for long videos:
  * failure isolation  — a crash costs one scene, not the whole render
  * resumability       — done segments are skipped on re-run
  * bounded memory     — Chromium restarts every BROWSER_RECYCLE scenes
  * early validation   — --validate catches JS errors, narration overlaps,
                         and text overflow in seconds, before rendering
"""
import argparse, json, math, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

BROWSER_RECYCLE = 4          # restart Chromium every N scenes
W, H = 1280, 720


def srt_ts(sec):
    h=int(sec//3600); m=int(sec%3600//60); s=int(sec%60)
    ms=int(round((sec-math.floor(sec))*1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def run(cmd, what):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[{what}] failed:\n{r.stderr[-800:]}")


def page_open(p, renderer):
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": W, "height": H})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"file://{renderer}")
    pg.wait_for_timeout(400)          # fonts settle
    return b, pg, errs


def validate(renderer):
    """Fast pre-flight: JS errors, narration overlaps, on-screen text overflow."""
    problems = []
    with sync_playwright() as p:
        b, pg, errs = page_open(p, renderer)
        sched = pg.evaluate("sceneSchedule()")
        narr  = pg.evaluate("narration()")
        for i, s in enumerate(sched):
            for frac in (0.1, 0.5, 0.9):
                pg.evaluate(f"renderFrame({s['start'] + s['dur']*frac})")
        if errs:
            problems += [f"JS error: {e}" for e in errs]
        total = pg.evaluate("totalDuration()")
        prev_end = 0
        for i, nl in enumerate(narr, 1):
            if nl["end"] <= nl["start"]:
                problems.append(f"cue {i}: end <= start ({nl['text'][:30]}…)")
            if nl["start"] < prev_end - 0.01:
                problems.append(f"cue {i}: overlaps previous cue by {prev_end-nl['start']:.2f}s")
            if nl["end"] > total + 0.01:
                problems.append(f"cue {i}: ends after video ({nl['end']:.1f}s > {total:.1f}s)")
            prev_end = nl["end"]
        import re as _re
        strip_marks = lambda s: _re.sub(r"[\u0CBE-\u0CCD\u0CD5\u0CD6\u200C\u200D]", "", s)
        for i, nl in enumerate(narr, 1):
            base = strip_marks(nl["text"])
            rate = len(base) / max(nl["end"] - nl["start"], 0.1)
            if rate > 8.5:
                problems.append(f"cue {i}: {rate:.1f} base-chars/sec — too fast to narrate "
                                f"({nl['text'][:34]}…)")
        b.close()
    return problems, len(sched), total


def build_chimes(chimes, total, out):
    """Synthesize the two-note chime WAV and overlay copies at reveal timestamps."""
    chime = out / "chime.wav"
    run(["ffmpeg","-y",
         "-f","lavfi","-i","sine=frequency=659.25:duration=0.18",
         "-f","lavfi","-i","sine=frequency=987.77:duration=0.35",
         "-filter_complex",
         "[0]afade=t=out:st=0.08:d=0.1[a];[1]adelay=140|140,afade=t=out:st=0.15:d=0.2[b];"
         "[a][b]amix=inputs=2:normalize=0,volume=0.35", chime], "chime")
    inputs=["-f","lavfi","-t",str(total),"-i","anullsrc=r=44100:cl=stereo"]
    fc, mix = [], ["[0:a]"]
    for i, t in enumerate(chimes):
        inputs += ["-i", str(chime)]
        ms = int(t * 1000)
        fc.append(f"[{i+1}:a]adelay={ms}|{ms}[c{i}]")
        mix.append(f"[c{i}]")
    fc.append("".join(mix) + f"amix=inputs={len(chimes)+1}:normalize=0[out]")
    chimes_wav = out / "chimes.wav"
    run(["ffmpeg","-y",*inputs,"-filter_complex",";".join(fc),"-map","[out]",chimes_wav], "chimes mix")
    return chimes_wav


def mix_audio(chimes_wav, voice_wav, out):
    """Mix chimes + voice into a single WAV. voice_wav may be None."""
    if voice_wav is None:
        return chimes_wav
    mixed = out / "audio_mixed.wav"
    run(["ffmpeg","-y",
         "-i", str(chimes_wav), "-i", str(voice_wav),
         "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0[out]",
         "-map", "[out]", str(mixed)], "mix chimes+voice")
    return mixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer", default="../renderer/renderer_kn.html")
    ap.add_argument("--out",      default="../out")
    ap.add_argument("--fps",      type=int, default=20)
    ap.add_argument("--name",     default="patterns-kn")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--scenes",   help="comma-separated scene indices to (re)render")
    ap.add_argument("--force",    action="store_true")
    ap.add_argument("--tts",      action="store_true",
                    help="synthesize Kannada voiceover with gTTS (requires internet)")
    ap.add_argument("--lang",     default="kn",
                    help="BCP-47 language for gTTS (default: kn)")
    args = ap.parse_args()

    here = Path(__file__).parent.resolve()
    renderer = here / args.renderer
    out = here / args.out
    seg_dir = out / "segments"; seg_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"

    # ---------- validation (always run; --validate stops after) ----------
    problems, n_scenes, total = validate(renderer)
    if problems:
        print("VALIDATION PROBLEMS:")
        for pr in problems: print("  -", pr)
        if args.validate or any("JS error" in p for p in problems):
            sys.exit(1)
        print("(continuing — only warnings)")
    else:
        print(f"validation clean: {n_scenes} scenes, {total:.1f}s total")
    if args.validate:
        return

    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() and not args.force else {}
    want = set(map(int, args.scenes.split(","))) if args.scenes else None

    # ---------- per-scene segment rendering ----------
    with sync_playwright() as p:
        b = pg = None
        since_restart = 0
        sched = None
        for i in range(n_scenes):
            if pg is None or since_restart >= BROWSER_RECYCLE:
                if b: b.close()
                b, pg, _ = page_open(p, renderer)
                sched = pg.evaluate("sceneSchedule()")
                since_restart = 0
            s = sched[i]
            key = f"scene{i:02d}"
            seg_mp4 = seg_dir / f"{key}.mp4"
            if want is not None and i not in want:
                continue
            if manifest.get(key) == s["dur"] and seg_mp4.exists() and want is None:
                print(f"{key}: cached, skipping")
                continue
            fdir = seg_dir / key; fdir.mkdir(exist_ok=True)
            n = round(s["dur"] * args.fps)
            print(f"{key}: {n} frames…")
            for f in range(n):
                pg.evaluate(f"renderFrame({s['start'] + f/args.fps})")
                pg.screenshot(path=str(fdir / f"{f:05d}.png"))
            run(["ffmpeg","-y","-framerate",args.fps,"-i",fdir/"%05d.png",
                 "-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p",
                 seg_mp4], f"{key} encode")
            for png in fdir.glob("*.png"): png.unlink()
            fdir.rmdir()
            manifest[key] = s["dur"]
            manifest_path.write_text(json.dumps(manifest, indent=1))
            since_restart += 1
        narr   = pg.evaluate("narration()")
        chimes = pg.evaluate("chimeTimes()")
        b.close()

    # ---------- concat ----------
    concat_txt = out / "concat.txt"
    concat_txt.write_text("".join(f"file 'segments/scene{i:02d}.mp4'\n" for i in range(n_scenes)))
    silent = out / f"{args.name}-silent.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",concat_txt,"-c","copy",silent], "concat")

    # ---------- SRT ----------
    srt = out / f"{args.name}.srt"
    srt.write_text("\n".join(
        f"{i}\n{srt_ts(n['start'])} --> {srt_ts(n['end'])}\n{n['text']}\n"
        for i, n in enumerate(narr, 1)), encoding="utf-8")

    # ---------- audio ----------
    print("building chimes…")
    chimes_wav = build_chimes(chimes, total, out)

    voice_wav = None
    if args.tts:
        print(f"synthesizing voiceover ({len(narr)} cues, lang={args.lang})…")
        try:
            from tts import build_voice_track
        except ImportError:
            sys.exit("tts.py not found next to build.py")
        tts_tmp = tempfile.mkdtemp(prefix="tts_")
        try:
            voice_wav = build_voice_track(narr, total, args.lang, tts_tmp)
        except RuntimeError as e:
            sys.exit(str(e))

    audio = mix_audio(chimes_wav, voice_wav, out)

    # ---------- mux ----------
    final = out / f"{args.name}.mp4"
    run(["ffmpeg","-y",
         "-i", str(silent), "-i", str(audio),
         "-i", str(srt),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-c:s", "mov_text", "-metadata:s:s:0", "language=kan",
         "-shortest", "-movflags", "+faststart",
         str(final)], "mux")

    print(f"done:\n  {final}\n  {srt}")
    if args.tts:
        print("  (voiceover baked in)")


if __name__ == "__main__":
    main()
