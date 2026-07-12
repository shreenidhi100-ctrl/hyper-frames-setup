#!/usr/bin/env python3
"""
thumbnail.py — generate a 1280×720 YouTube thumbnail from a rendered MP4.

Extracts the sharpest reveal frame (at 65% of video duration), darkens it,
and overlays the Kannada title, English subtitle, and chapter badge.

Usage:
    python3 pipeline/thumbnail.py hyperframes/ch2-v1/ch2-v1-final.mp4 \
        --title-kn "ಬಿಂದು, ರೇಖಾಖಂಡ, ರೇಖೆ" \
        --title-en "Points, Lines & Rays" \
        --badge "Ch.2 · §2.4"

Requires: pip install Pillow
Kannada font: Noto Sans Kannada (auto-detected from system or HF cache)
"""
import argparse, subprocess, sys
from pathlib import Path


# ── font discovery ────────────────────────────────────────────────────────────

def _find_font(name_fragments: list[str], fallback: str = None) -> str | None:
    """Return path to first font file whose name contains any fragment."""
    try:
        result = subprocess.run(
            ["fc-list", "--format=%{file}\n"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            lower = line.lower()
            if any(f.lower() in lower for f in name_fragments):
                return line.strip()
    except FileNotFoundError:
        pass
    # Check HyperFrames font cache
    hf_cache = Path.home() / ".cache" / "hyperframes" / "fonts"
    for pattern in ["*kannada*", "*Kannada*"]:
        found = list(hf_cache.glob(f"**/{pattern}"))
        if found:
            return str(found[0])
    return fallback


def _video_duration(mp4: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


# ── core ─────────────────────────────────────────────────────────────────────

def generate(mp4_path: Path, title_kn: str, title_en: str, badge: str,
             out_path: Path = None) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        raise RuntimeError("Run: pip install Pillow")

    if out_path is None:
        out_path = mp4_path.parent / "thumbnail.jpg"

    # 1. Extract frame at 65% of video (typically mid-question reveal)
    dur   = _video_duration(mp4_path)
    seek  = dur * 0.65
    frame = mp4_path.parent / "_thumb_frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{seek:.2f}", "-i", str(mp4_path),
         "-vframes", "1", "-vf", "scale=1280:720", str(frame)],
        capture_output=True, check=True,
    )

    img = Image.open(frame).convert("RGB").resize((1280, 720))
    frame.unlink(missing_ok=True)

    # 2. Dark gradient overlay
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    draw_o  = ImageDraw.Draw(overlay)
    for y in range(720):
        alpha = int(180 * (y / 720) ** 0.5 + 60)   # heavier at bottom
        draw_o.line([(0, y), (1280, y)], fill=(10, 17, 42, min(alpha, 210)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # 3. Fonts
    kn_font_path = _find_font(["noto sans kannada", "notosans-kannada", "NotoSansKannada"])
    en_font_path = _find_font(["noto sans", "dejavu", "freesans", "arial"])

    def _font(path, size, bold=False):
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_kn_big  = _font(kn_font_path, 72, bold=True)
    font_kn_mid  = _font(kn_font_path, 44)
    font_en      = _font(en_font_path,  36)
    font_badge   = _font(en_font_path,  28)

    # 4. Chapter badge — top right
    badge_text = badge
    bw, bh = draw.textbbox((0, 0), badge_text, font=font_badge)[2:]
    pad = 14
    bx, by = 1280 - bw - pad*2 - 24, 24
    draw.rounded_rectangle([bx, by, bx+bw+pad*2, by+bh+pad], radius=20,
                            fill="#e94560")
    draw.text((bx+pad, by+pad//2), badge_text, font=font_badge, fill="white")

    # 5. Kannada title — centred, bold white with shadow
    def shadowed_text(x, y, text, font, fill="white", shadow_offset=3):
        draw.text((x+shadow_offset, y+shadow_offset), text, font=font,
                  fill=(0, 0, 0, 180), anchor="mm")
        draw.text((x, y), text, font=font, fill=fill, anchor="mm")

    shadowed_text(640, 340, title_kn, font_kn_big)

    # 6. English subtitle
    shadowed_text(640, 430, title_en, font_en, fill="#94a3b8")

    # 7. Bottom brand bar
    draw.rectangle([0, 660, 1280, 720], fill=(15, 23, 42, 230))
    draw.text((40, 683), "ಗಣಿತ ಪ್ರಕಾಶ · Class 6 · Karnataka",
              font=font_en, fill="#60a5fa", anchor="lm")
    draw.text((1240, 683), "🎓", font=font_en, fill="white", anchor="rm")

    img.save(str(out_path), "JPEG", quality=95)
    print(f"  thumbnail: {out_path}  ({out_path.stat().st_size//1024} KB)")
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--title-kn", required=True)
    ap.add_argument("--title-en", required=True)
    ap.add_argument("--badge",    default="Ch.2")
    ap.add_argument("--out",      default=None)
    args = ap.parse_args()

    out = generate(
        Path(args.mp4), args.title_kn, args.title_en, args.badge,
        Path(args.out) if args.out else None,
    )
    print(f"done: {out}")


if __name__ == "__main__":
    main()
