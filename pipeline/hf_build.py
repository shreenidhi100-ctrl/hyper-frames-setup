#!/usr/bin/env python3
"""
hf_build.py — end-to-end build driver for HyperFrames video compositions.

Replaces build.py for the HyperFrames rendering path (Chapter 2+).

  python3 pipeline/hf_build.py hyperframes/ch2-v1/
  python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts
  python3 pipeline/hf_build.py hyperframes/ch2-v1/ --tts --lang kn
  python3 pipeline/hf_build.py hyperframes/ch2-v1/ --fps 24
  python3 pipeline/hf_build.py hyperframes/ch2-v1/ --lint-only
  python3 pipeline/hf_build.py hyperframes/ch2-v1/ --force

Inputs (inside <video_dir>/):
    index.html       — HyperFrames composition
    narration.json   — { "video": "<id>", "cues": [{"at", "end", "text"}, …] }

Outputs (inside <video_dir>/):
    <video>.mp4           — raw render (no audio)
    <video>.srt           — subtitle file
    <video>-final.mp4     — muxed: video + embedded SRT [+ voice if --tts]
"""

import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).parent.resolve()


# ── helpers ──────────────────────────────────────────────────────────────────

def run(cmd, what):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[{what}] failed:\n{r.stderr[-1200:]}")
    return r.stdout


# ── steps ────────────────────────────────────────────────────────────────────

def step_lint(video_dir):
    print("── lint ─────────────────────────────────────────")
    r = subprocess.run(["hyperframes", "lint", str(video_dir)],
                       capture_output=True, text=True)
    output = (r.stdout + r.stderr).strip()
    print(output)
    errors = [l for l in output.splitlines() if "error" in l.lower() and "0 error" not in l]
    if r.returncode != 0 or errors:
        sys.exit("lint: errors found — fix before rendering")
    print("lint: clean\n")


def step_render(video_dir, video_id, fps, force):
    import shutil
    out_mp4 = video_dir / f"{video_id}.mp4"
    if out_mp4.exists() and not force:
        print(f"── render ───────────────────────────────────────")
        print(f"   {out_mp4.name} already exists — skipping (--force to re-render)\n")
        return out_mp4
    print("── render ───────────────────────────────────────")
    r = subprocess.run(
        ["hyperframes", "render", str(video_dir), "-o", str(out_mp4), "-f", str(fps)],
        # don't capture — let HyperFrames stream its progress bar live
    )
    if r.returncode != 0:
        sys.exit("hyperframes render failed")
    # clean up HyperFrames work directories left in video_dir
    for work_dir in video_dir.glob("work-*"):
        if work_dir.is_dir():
            shutil.rmtree(work_dir, ignore_errors=True)
    print()
    return out_mp4


def step_srt(narr_path):
    print("── subtitles ────────────────────────────────────")
    sys.path.insert(0, str(HERE))
    from gen_srt import gen_srt
    srt_path = gen_srt(narr_path)
    print()
    return srt_path


def step_tts(cues, total_dur, lang, provider, voice, model):
    print(f"── voiceover ({len(cues)} cues, {provider}, lang={lang}) ──────────────────")
    sys.path.insert(0, str(HERE))
    from tts import build_voice_track
    tmp = tempfile.mkdtemp(prefix="hf_tts_")
    voice_wav = build_voice_track(cues, total_dur, lang, tmp,
                                  provider=provider, voice=voice, model=model)
    print()
    return voice_wav


def step_mux(raw_mp4, srt_path, voice_wav, final_mp4):
    print("── mux ──────────────────────────────────────────")
    if voice_wav:
        run([
            "ffmpeg", "-y",
            "-i", str(raw_mp4),
            "-i", str(voice_wav),
            "-i", str(srt_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-c:s", "mov_text", "-metadata:s:s:0", "language=kan",
            "-shortest", "-movflags", "+faststart",
            str(final_mp4),
        ], "mux")
    else:
        run([
            "ffmpeg", "-y",
            "-i", str(raw_mp4),
            "-i", str(srt_path),
            "-c:v", "copy",
            "-an",
            "-c:s", "mov_text", "-metadata:s:s:0", "language=kan",
            "-movflags", "+faststart",
            str(final_mp4),
        ], "mux")
    size_mb = final_mp4.stat().st_size / 1_048_576
    print(f"   {final_mp4.name}  ({size_mb:.1f} MB)\n")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="HyperFrames end-to-end build")
    ap.add_argument("video_dir",
                    help="path to a hyperframes/<video>/ directory containing "
                         "index.html and narration.json")
    ap.add_argument("--fps",       type=int, default=20,
                    help="frames per second (default: 20)")
    ap.add_argument("--tts",       action="store_true",
                    help="synthesize Kannada voiceover (needs internet)")
    ap.add_argument("--tts-provider", default="gtts",
                    choices=["gtts", "sarvam", "elevenlabs"],
                    help="voice engine: gtts (free, robotic), sarvam (Indic-native, "
                         "best Kannada — SARVAM_API_KEY, see docs/tts-sarvam.md), or "
                         "elevenlabs (ELEVENLABS_API_KEY, see docs/tts-elevenlabs.md)")
    ap.add_argument("--voice",     default=None,
                    help="voice/speaker (sarvam speaker e.g. anushka, or elevenlabs "
                         "voice id; else the provider's *_VOICE/SPEAKER env var)")
    ap.add_argument("--tts-model", default=None,
                    help="provider model id (else provider's *_MODEL env var)")
    ap.add_argument("--lang",      default="kn",
                    help="BCP-47 language for gtts provider (default: kn)")
    ap.add_argument("--lint-only", action="store_true",
                    help="lint only, do not render")
    ap.add_argument("--force",     action="store_true",
                    help="re-render even if output already exists")
    ap.add_argument("--upload",    action="store_true",
                    help="after render: upload to Drive (review) then YouTube (private)")
    ap.add_argument("--publish",   action="store_true",
                    help="with --upload: set YouTube visibility to Public instead of Private")
    args = ap.parse_args()

    video_dir = Path(args.video_dir).resolve()
    if not video_dir.is_dir():
        sys.exit(f"Not a directory: {video_dir}")

    narr_path = video_dir / "narration.json"
    if not narr_path.exists():
        sys.exit(f"narration.json not found in {video_dir}")

    data      = json.loads(narr_path.read_text(encoding="utf-8"))
    video_id  = data["video"]
    # normalise 'at' → 'start' for tts.py compatibility
    cues      = [{"start": c["at"], "end": c["end"], "text": c["text"]}
                 for c in data["cues"]]
    total_dur = max(c["end"] for c in cues)

    print(f"\n{'='*50}")
    print(f"  hf_build  {video_id}  ({len(cues)} narration cues, {total_dur:.1f}s)")
    print(f"{'='*50}\n")

    step_lint(video_dir)
    if args.lint_only:
        return

    raw_mp4   = step_render(video_dir, video_id, args.fps, args.force)
    srt_path  = step_srt(narr_path)
    voice_wav = (step_tts(cues, total_dur, args.lang,
                          args.tts_provider, args.voice, args.tts_model)
                 if args.tts else None)
    final_mp4 = video_dir / f"{video_id}-final.mp4"
    step_mux(raw_mp4, srt_path, voice_wav, final_mp4)

    # ── preview artifact ─────────────────────────────────────────────────────
    print("── preview ──────────────────────────────────────")
    from preview import generate as gen_preview
    preview_html = gen_preview(video_dir)

    print("\ndone:")
    print(f"  video   : {final_mp4}")
    print(f"  subs    : {srt_path}")
    print(f"  preview : {preview_html}  ← publish as Artifact")
    if args.tts:
        print(f"  voice   : baked in  ({args.tts_provider}, lang={args.lang})")

    if args.upload:
        # ── Drive upload (for review) ─────────────────────────────────────
        import os
        if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") and os.environ.get("GDRIVE_FOLDER_ID"):
            print("\n── drive upload ─────────────────────────────────")
            from drive_upload import upload_video_and_srt
            links = upload_video_and_srt(final_mp4, srt_path)
            print(f"  Drive review link: {links['video']}")
        else:
            print("\n  (skipping Drive upload — GOOGLE_SERVICE_ACCOUNT_JSON / GDRIVE_FOLDER_ID not set)")

        # ── YouTube upload (private) ──────────────────────────────────────
        if os.environ.get("YOUTUBE_REFRESH_TOKEN"):
            print("\n── youtube upload ────────────────────────────────")
            from youtube_upload import upload as yt_upload
            privacy  = "public" if args.publish else "private"
            yt_url   = yt_upload(video_dir, privacy=privacy)
            print(f"\n  YouTube ({privacy}): {yt_url}")
        else:
            print("\n  (skipping YouTube upload — YOUTUBE_REFRESH_TOKEN not set)")


if __name__ == "__main__":
    main()
