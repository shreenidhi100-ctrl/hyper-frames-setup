#!/usr/bin/env python3
"""
Builds "Video 1: What Even IS Artificial Intelligence?" end to end:
  1. Synthesizes narration audio per beat (gTTS).
  2. Renders a matching 1920x1080 frame per beat (Pillow).
  3. Encodes each beat to a short mp4 (ffmpeg) and concatenates them.

Run: python3 build_video.py
Output: output/video1_what_is_ai.mp4
"""
import os
import subprocess
import textwrap
from dataclasses import dataclass, field
from typing import Callable

from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.join(ROOT, "frames")
AUDIO_DIR = os.path.join(ROOT, "audio")
CLIPS_DIR = os.path.join(ROOT, "clips")
OUTPUT_DIR = os.path.join(ROOT, "output")
for d in (FRAMES_DIR, AUDIO_DIR, CLIPS_DIR, OUTPUT_DIR):
    os.makedirs(d, exist_ok=True)

W, H = 1920, 1080
FPS = 30

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------
BG_TOP = (12, 17, 32)       # #0c1120
BG_BOTTOM = (20, 27, 46)    # #141b2e
INK = (248, 250, 252)       # near-white text
INK_DIM = (148, 163, 184)   # slate-400
CYAN = (56, 189, 248)       # accent
AMBER = (251, 191, 36)      # accent 2
GREEN = (74, 222, 128)
RED = (248, 113, 113)
PANEL = (30, 41, 59)        # slate-800 panel fill
PANEL_LINE = (51, 65, 85)   # slate-700 border

FONT_DIR = "/usr/share/fonts/truetype"
F_BOLD = os.path.join(FONT_DIR, "dejavu", "DejaVuSans-Bold.ttf")
F_REG = os.path.join(FONT_DIR, "dejavu", "DejaVuSans.ttf")
F_EMOJI = os.path.join(FONT_DIR, "noto", "NotoColorEmoji.ttf")

_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


_emoji_font = font(F_EMOJI, 109)


def emoji_img(char, target_size):
    """Render a color emoji glyph, cropped and scaled to target_size (square)."""
    tmp = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((0, 0), char, font=_emoji_font, embedded_color=True)
    bbox = tmp.getbbox()
    if not bbox:
        return Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    cropped = tmp.crop(bbox)
    return cropped.resize((target_size, target_size), Image.LANCZOS)


def paste_emoji(base, char, center_xy, size):
    img = emoji_img(char, size)
    x, y = center_xy
    base.paste(img, (int(x - size / 2), int(y - size / 2)), img)


def vgradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(0, w, 4):  # coarse fill then blit rows fast
            pass
        row = Image.new("RGB", (w, 1), (r, g, b))
        img.paste(row, (0, y))
    return img


_BG_CACHE = None


def base_canvas():
    global _BG_CACHE
    if _BG_CACHE is None:
        _BG_CACHE = vgradient((W, H), BG_TOP, BG_BOTTOM)
    return _BG_CACHE.copy()


def wrap_text(draw, text, f, max_width):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=f) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_centered_text(draw, text, f, cy, fill, max_width, line_spacing=1.3):
    lines = wrap_text(draw, text, f, max_width)
    ascent, descent = f.getmetrics()
    line_h = int((ascent + descent) * line_spacing)
    total_h = line_h * len(lines)
    y = cy - total_h / 2
    for line in lines:
        w = draw.textlength(line, font=f)
        draw.text(((W - w) / 2, y), line, font=f, fill=fill)
        y += line_h
    return y  # bottom y after last line


def chip(draw, img, text, xy, fill=PANEL, text_fill=INK, f=None, pad_x=22, pad_y=12, emoji=None):
    f = f or font(F_BOLD, 30)
    w = draw.textlength(text, font=f)
    ascent, descent = f.getmetrics()
    h = ascent + descent
    emoji_w = h + 16 if emoji else 0
    x, y = xy
    box = (x, y, x + emoji_w + w + pad_x * 2, y + h + pad_y * 2)
    draw.rounded_rectangle(box, radius=(h + pad_y * 2) / 2, fill=fill)
    text_x = x + pad_x + emoji_w
    if emoji:
        paste_emoji(img, emoji, (x + pad_x + h / 2, y + pad_y + h / 2), int(h * 1.1))
    draw.text((text_x, y + pad_y), text, font=f, fill=text_fill)
    return box


def centered_chip(draw, img, text, cy, emoji=None, **kwargs):
    f = kwargs.get("f") or font(F_BOLD, 34)
    pad_x = kwargs.get("pad_x", 22)
    pad_y = kwargs.get("pad_y", 12)
    ascent, descent = f.getmetrics()
    h = ascent + descent
    emoji_w = h + 16 if emoji else 0
    text_w = draw.textlength(text, font=f)
    total_w = emoji_w + text_w + pad_x * 2
    x = (W - total_w) / 2
    return chip(draw, img, text, (x, cy), emoji=emoji, **kwargs)


def header(draw, chapter_label):
    # Series branding, top-left
    f_series = font(F_BOLD, 26)
    draw.text((70, 56), "AI OLYMPIAD PREP", font=f_series, fill=INK_DIM)
    f_video = font(F_REG, 26)
    draw.text((70, 92), "Video 1 of 3 · What Even IS Artificial Intelligence?",
               font=f_video, fill=(100, 112, 134))
    # Chapter chip, top-right
    f_chip = font(F_BOLD, 28)
    dctx = draw
    w = dctx.textlength(chapter_label, font=f_chip)
    pad_x, pad_y = 26, 14
    box_w = w + pad_x * 2
    ascent, descent = f_chip.getmetrics()
    box_h = ascent + descent + pad_y * 2
    x1 = W - 70 - box_w
    y1 = 60
    draw.rounded_rectangle((x1, y1, x1 + box_w, y1 + box_h), radius=box_h / 2,
                            outline=CYAN, width=3)
    draw.text((x1 + pad_x, y1 + pad_y), chapter_label, font=f_chip, fill=CYAN)


def measure_box_height(draw, label, sub, w, emoji=None):
    f_sub = font(F_REG, 22)
    label_lines = label.split("\n")
    sub_lines = wrap_text(draw, sub, f_sub, w - 40) if sub else []
    top_pad, bottom_pad = 28, 28
    content_h = top_pad + bottom_pad
    if emoji:
        content_h += 78
    content_h += len(label_lines) * 40 + (6 if sub_lines else 0)
    content_h += len(sub_lines) * 28
    return max(content_h, 180)


def diagram_box(draw, img, label, sub, center, size=(380, None), active=False,
                 fill_active=CYAN, emoji=None, height=None):
    w, _ = size
    cx, cy = center
    f_label = font(F_BOLD, 34)
    f_sub = font(F_REG, 22)
    label_lines = label.split("\n")
    sub_lines = wrap_text(draw, sub, f_sub, w - 40) if sub else []

    top_pad = 28
    h = height if height is not None else measure_box_height(draw, label, sub, w, emoji)

    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    border = fill_active if active else PANEL_LINE
    fillcol = (18, 32, 48) if active else PANEL
    draw.rounded_rectangle((x1, y1, x2, y2), radius=24, fill=fillcol,
                            outline=border, width=5 if active else 3)
    top_y = y1 + top_pad
    if emoji:
        paste_emoji(img, emoji, (cx, top_y + 34), 64)
        top_y += 78
    for line in label_lines:
        tw = draw.textlength(line, font=f_label)
        draw.text((cx - tw / 2, top_y), line, font=f_label, fill=INK)
        top_y += 40
    if sub_lines:
        top_y += 6
        for line in sub_lines:
            lw = draw.textlength(line, font=f_sub)
            draw.text((cx - lw / 2, top_y), line, font=f_sub, fill=INK_DIM)
            top_y += 28
    return h


def row_height(draw, boxes, w=380):
    """boxes: iterable of (label, sub, emoji) -> the max height needed across the row."""
    return max(measure_box_height(draw, label, sub, w, emoji) for label, sub, emoji in boxes)


def arrow(draw, p1, p2, color=INK_DIM, width=6):
    x1, y1 = p1
    x2, y2 = p2
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 16
    for side in (0.5, -0.5):
        a = ang + math.pi - side
        draw.line((x2, y2, x2 + ah * math.cos(a), y2 + ah * math.sin(a)),
                   fill=color, width=width)


# ---------------------------------------------------------------------------
# Scene renderers -- each returns a PIL.Image (1920x1080)
# ---------------------------------------------------------------------------

def scene_hook():
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "HOOK")
    # divider
    d.line((W / 2, 260, W / 2, H - 140), fill=PANEL_LINE, width=3)
    for side, char, label in ((-1, "🐱", "CAT"), (1, "🐶", "DOG")):
        cx = W / 2 + side * W / 4
        paste_emoji(img, char, (cx, 520), 420)
        f_label = font(F_BOLD, 44)
        lw = d.textlength(label, font=f_label)
        d.text((cx - lw / 2, 760), label, font=f_label, fill=CYAN if side < 0 else AMBER)
    f_q = font(F_BOLD, 56)
    draw_centered_text(d, "How did YOU learn to tell them apart?", f_q, 200, INK, 1500)
    f_sub = font(F_REG, 32)
    draw_centered_text(d, "No rulebook. You just saw examples — and your brain found the pattern.",
                        f_sub, H - 90, INK_DIM, 1400)
    return img


def scene_traditional():
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "TRADITIONAL PROGRAMS")
    f_title = font(F_BOLD, 52)
    draw_centered_text(d, "A traditional program is a cookbook", f_title, 210, INK, 1600)

    cy = 540
    rh = row_height(d, [
        ("Input", "e.g. “2 + 2”", "⌨️"),
        ("Fixed Rules", "written by a person,\nline by line", "\U0001F4D0"),
        ("Output", "e.g. “4”", "✅"),
    ])
    diagram_box(d, img, "Input", "e.g. “2 + 2”", (W / 2 - 620, cy), emoji="⌨️", height=rh)
    arrow(d, (W / 2 - 440, cy), (W / 2 - 200, cy))
    diagram_box(d, img, "Fixed Rules", "written by a person,\nline by line", (W / 2, cy),
                active=True, emoji="\U0001F4D0", height=rh)
    arrow(d, (W / 2 + 200, cy), (W / 2 + 440, cy))
    diagram_box(d, img, "Output", "e.g. “4”", (W / 2 + 620, cy), emoji="✅", height=rh)

    centered_chip(d, img, "Cookbook — exact steps, no learning", 830, emoji="\U0001F373",
                  fill=(46, 34, 14), text_fill=AMBER, f=font(F_BOLD, 34))
    return img


def scene_ai_diff():
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "WHAT MAKES AI DIFFERENT")
    f_title = font(F_BOLD, 52)
    draw_centered_text(d, "AI flips the recipe around", f_title, 210, INK, 1600)

    cy = 540
    rh = row_height(d, [
        ("Examples", "1,000s of cat &\ndog photos", "\U0001F4C2"),
        ("Model Finds\nthe Pattern", "studies the data\non its own", "\U0001F9E0"),
        ("Prediction", "“cat” or “dog”\non a NEW photo", "\U0001F3AF"),
    ])
    diagram_box(d, img, "Examples", "1,000s of cat &\ndog photos", (W / 2 - 620, cy),
                emoji="\U0001F4C2", height=rh)
    arrow(d, (W / 2 - 430, cy), (W / 2 - 210, cy))
    diagram_box(d, img, "Model Finds\nthe Pattern", "studies the data\non its own", (W / 2, cy),
                active=True, fill_active=CYAN, emoji="\U0001F9E0", height=rh)
    arrow(d, (W / 2 + 210, cy), (W / 2 + 430, cy))
    diagram_box(d, img, "Prediction", "“cat” or “dog”\non a NEW photo", (W / 2 + 620, cy),
                emoji="\U0001F3AF", height=rh)

    centered_chip(d, img, "AI = learns from examples, not exact rules", 830, emoji="\U0001F9E0",
                  fill=(11, 40, 51), text_fill=CYAN, f=font(F_BOLD, 34))
    return img


def scene_pipeline(stage):
    """stage in {'intro','data','model','prediction','loop'}"""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "DATA → MODEL → PREDICTION")
    f_title = font(F_BOLD, 50)
    draw_centered_text(d, "Three simple pieces", f_title, 190, INK, 1600)

    cy = 560
    positions = {
        "data": (W / 2 - 620, cy),
        "model": (W / 2, cy),
        "prediction": (W / 2 + 620, cy),
    }
    active_map = {
        "intro": set(),
        "data": {"data"},
        "model": {"data", "model"},
        "prediction": {"data", "model", "prediction"},
        "loop": {"data", "model", "prediction"},
    }
    active_set = active_map[stage]

    rh = row_height(d, [
        ("1. Data", "lots of labeled\nexamples", "\U0001F4CA"),
        ("2. Model", "the “learner” —\nfinds the pattern", "⚙️"),
        ("3. Prediction", "best guess on\nsomething NEW", "\U0001F3AF"),
    ])
    diagram_box(d, img, "1. Data", "lots of labeled\nexamples", positions["data"],
                active="data" in active_set, emoji="\U0001F4CA", height=rh)
    arrow(d, (positions["data"][0] + 190, cy), (positions["model"][0] - 190, cy))
    diagram_box(d, img, "2. Model", "the “learner” —\nfinds the pattern", positions["model"],
                active="model" in active_set, emoji="⚙️", height=rh)
    arrow(d, (positions["model"][0] + 190, cy), (positions["prediction"][0] - 190, cy))
    diagram_box(d, img, "3. Prediction", "best guess on\nsomething NEW", positions["prediction"],
                active="prediction" in active_set, emoji="\U0001F3AF", height=rh)

    if stage == "loop":
        centered_chip(d, img, "Data in → pattern found → prediction out", 840,
                      fill=(11, 40, 51), text_fill=CYAN, f=font(F_BOLD, 34))
    return img


def scene_realworld(active):
    """active in {'intro','spam','netflix','faceid','close'}"""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "AI IN YOUR EVERYDAY LIFE")
    f_title = font(F_BOLD, 50)
    draw_centered_text(d, "You already use AI every day", f_title, 200, INK, 1600)

    items = [
        ("spam", "\U0001F4E7", "Spam Filter", "learned from millions\nof labeled emails"),
        ("netflix", "\U0001F4FA", "Recommendations", "learned patterns from\nwhat people watch"),
        ("faceid", "\U0001F4F1", "Face ID", "learned the pattern\nof YOUR face"),
    ]
    cy = 560
    xs = (W / 2 - 620, W / 2, W / 2 + 620)
    rh = row_height(d, [(label, sub, em) for _, em, label, sub in items])
    for (key, em, label, sub), cx in zip(items, xs):
        is_active = active in ("close",) or active == key
        diagram_box(d, img, label, sub, (cx, cy), active=is_active, emoji=em, height=rh)

    if active == "close":
        centered_chip(d, img, "Examples in → pattern learned → prediction out", 840,
                      fill=(11, 40, 51), text_fill=CYAN, f=font(F_BOLD, 34))
    return img


def scene_quiz(revealed):
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "QUICK CHECK-IN")
    paste_emoji(img, "\U0001F9EE", (W / 2, 300), 160)
    f_q = font(F_BOLD, 58)
    draw_centered_text(d, "Is a basic calculator AI?", f_q, 470, INK, 1500)
    f_sub = font(F_REG, 32)
    draw_centered_text(d, "Pause for a second and think about why.", f_sub, 540, INK_DIM, 1300)

    if revealed:
        d.rounded_rectangle((W / 2 - 560, 620, W / 2 + 560, 880), radius=28,
                             fill=(43, 16, 16), outline=RED, width=4)
        f_no = font(F_BOLD, 70)
        tw = d.textlength("NO — it's not AI", font=f_no)
        d.text((W / 2 - tw / 2, 650), "NO — it's not AI", font=f_no, fill=RED)
        f_exp = font(F_REG, 30)
        draw_centered_text(d, "It follows exact, fixed rules a programmer wrote.\nIt never learns anything new. A cookbook, not a student.",
                            f_exp, 800, INK_DIM, 1000, line_spacing=1.4)
    else:
        d.rounded_rectangle((W / 2 - 300, 660, W / 2 + 300, 780), radius=28,
                             outline=PANEL_LINE, width=4)
        f_dots = font(F_BOLD, 60)
        tw = d.textlength("? ? ?", font=f_dots)
        d.text((W / 2 - tw / 2, 690), "? ? ?", font=f_dots, fill=INK_DIM)
    return img


def scene_recap(n_bullets, show_endcard=False):
    img = base_canvas()
    d = ImageDraw.Draw(img)
    header(d, "RECAP" if not show_endcard else "UP NEXT")
    bullets = [
        "AI learns patterns from examples — it doesn't follow a fixed set of rules.",
        "The process: Data → Model → Prediction.",
        "You already interact with AI: spam filters, recommendations, Face ID.",
    ]
    f_title = font(F_BOLD, 52)
    draw_centered_text(d, "So, to sum it up:", f_title, 180, INK, 1600)

    y = 320
    f_b = font(F_REG, 34)
    for i, b in enumerate(bullets):
        shown = i < n_bullets
        col = INK if shown else (40, 48, 64)
        dotcol = CYAN if shown else (40, 48, 64)
        d.ellipse((260, y + 6, 292, y + 38), fill=dotcol)
        for line in wrap_text(d, b, f_b, 1300):
            d.text((330, y), line, font=f_b, fill=col)
            y += 44
        y += 26

    if show_endcard:
        d.rounded_rectangle((W / 2 - 700, 800, W / 2 + 700, 980), radius=26,
                             fill=(11, 40, 51), outline=CYAN, width=4)
        f_next = font(F_BOLD, 40)
        draw_centered_text(d, "Next up: Supervised vs. Unsupervised Learning ▶",
                            f_next, 890, CYAN, 1300)
    return img


# ---------------------------------------------------------------------------
# Beats: (id, narration, chapter, render_fn)
# ---------------------------------------------------------------------------

@dataclass
class Beat:
    id: str
    text: str
    render: Callable[[], Image.Image]


BEATS = [
    Beat("01_hook", (
        "Quick question. How did YOU learn to tell a cat from a dog? "
        "Did somebody hand you a rulebook that said, if it has pointy ears and whiskers, it's a cat? "
        "No. You just saw a bunch of cats and dogs, and your brain figured it out. "
        "That's basically what Artificial Intelligence does. "
        "Today, we're breaking down what AI actually is. No confusing jargon, promise."
    ), scene_hook),

    Beat("02_traditional", (
        "Normal computer programs are like a cookbook. "
        "Every single step is written out by a person: if this happens, do that. "
        "A calculator app doesn't learn what two plus two is; someone coded the rule in. "
        "It's exact, it's predictable, and it never changes unless a programmer changes it."
    ), scene_traditional),

    Beat("03_ai_diff", (
        "AI flips this around. Instead of a programmer writing every single rule, "
        "we show the computer thousands of examples: pictures of cats, pictures of dogs, "
        "and the computer looks for patterns on its own. "
        "Once it's seen enough examples, we can show it a brand new picture it's never seen before, "
        "and it makes a guess: cat, or dog. "
        "That's the core idea of Machine Learning, which is the most common type of AI."
    ), scene_ai_diff),

    Beat("04a_pipeline_intro", "Let's slow that down into three simple pieces.",
         lambda: scene_pipeline("intro")),
    Beat("04b_pipeline_data", (
        "One: Data. Lots and lots of examples. The more, the better."
    ), lambda: scene_pipeline("data")),
    Beat("04c_pipeline_model", (
        "Two: Model. This is the part that actually studies the data and finds the pattern. "
        "Think of it like a student cramming for a test by looking at hundreds of practice questions."
    ), lambda: scene_pipeline("model")),
    Beat("04d_pipeline_prediction", (
        "Three: Prediction. Once the model has learned the pattern, "
        "you give it something new, and it makes its best guess."
    ), lambda: scene_pipeline("prediction")),
    Beat("04e_pipeline_loop", (
        "Data in, pattern found, prediction out. That's it. That's the whole loop."
    ), lambda: scene_pipeline("loop")),

    Beat("05a_realworld_intro", (
        "You already use AI every single day and probably don't even notice."
    ), lambda: scene_realworld("intro")),
    Beat("05b_realworld_spam", (
        "Your email's spam filter? It learned from millions of emails "
        "that were already labeled spam or not spam."
    ), lambda: scene_realworld("spam")),
    Beat("05c_realworld_netflix", (
        "Netflix recommending a show? It learned patterns from what you "
        "and millions of other people watched."
    ), lambda: scene_realworld("netflix")),
    Beat("05d_realworld_faceid", (
        "Face ID unlocking your phone? It learned the pattern of YOUR face from a bunch of angles."
    ), lambda: scene_realworld("faceid")),
    Beat("05e_realworld_close", (
        "Same idea every time: examples in, pattern learned, prediction out."
    ), lambda: scene_realworld("close")),

    Beat("06a_quiz_q", (
        "Let's test it. Pause for a second. Is a calculator AI?"
    ), lambda: scene_quiz(False)),
    Beat("06b_quiz_a", (
        "Nope! A calculator follows exact, fixed rules a programmer wrote. "
        "It never learns anything new. It's a cookbook, not a student. "
        "AI specifically means the computer is learning patterns from data."
    ), lambda: scene_quiz(True)),

    Beat("07a_recap_1", (
        "So to sum it up: AI is a computer system that learns patterns from examples "
        "instead of following a fixed set of rules."
    ), lambda: scene_recap(1)),
    Beat("07b_recap_2", "The process is Data, then Model, then Prediction.",
         lambda: scene_recap(2)),
    Beat("07c_recap_3", (
        "And you interact with AI more than you probably realized: "
        "spam filters, recommendations, Face ID."
    ), lambda: scene_recap(3)),
    Beat("07d_transition", (
        "Now here's the big question: how does the AI actually learn from that data? "
        "Turns out there are three totally different ways it can do that, "
        "and that's exactly what we're covering in the next video: "
        "Supervised versus Unsupervised Learning. See you there."
    ), lambda: scene_recap(3, show_endcard=True)),
]

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def synth_audio(beat: Beat):
    mp3_path = os.path.join(AUDIO_DIR, f"{beat.id}.mp3")
    if not os.path.exists(mp3_path):
        gTTS(beat.text, lang="en", tld="com").save(mp3_path)
    return mp3_path


def render_frame(beat: Beat):
    png_path = os.path.join(FRAMES_DIR, f"{beat.id}.png")
    if not os.path.exists(png_path):
        img = beat.render()
        img.save(png_path)
    return png_path


HOLD_TAIL = 0.5  # seconds to hold the frame after narration ends


def build_clip(beat: Beat, png_path, mp3_path):
    clip_path = os.path.join(CLIPS_DIR, f"{beat.id}.mp4")
    if os.path.exists(clip_path):
        return clip_path
    dur = ffprobe_duration(mp3_path) + HOLD_TAIL
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", png_path,
        "-i", mp3_path,
        "-filter_complex",
        f"[0:v]scale={W}:{H},format=yuv420p[v];"
        f"[1:a]apad=pad_dur={HOLD_TAIL}[a]",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-pix_fmt", "yuv420p",
        clip_path,
    ])
    return clip_path


def concat_clips(clip_paths, out_path):
    list_path = os.path.join(CLIPS_DIR, "concat_list.txt")
    with open(list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", out_path,
    ])


def main():
    print(f"Building {len(BEATS)} beats...")
    clip_paths = []
    total = 0.0
    for i, beat in enumerate(BEATS, 1):
        mp3_path = synth_audio(beat)
        png_path = render_frame(beat)
        clip_path = build_clip(beat, png_path, mp3_path)
        d = ffprobe_duration(clip_path)
        total += d
        clip_paths.append(clip_path)
        print(f"  [{i:2d}/{len(BEATS)}] {beat.id:<22} {d:5.1f}s  (running total {total/60:4.1f} min)")

    out_path = os.path.join(OUTPUT_DIR, "video1_what_is_ai.mp4")
    concat_clips(clip_paths, out_path)
    final_dur = ffprobe_duration(out_path)
    print(f"\nDone: {out_path}")
    print(f"Total length: {final_dur/60:.2f} min ({final_dur:.1f}s)")


if __name__ == "__main__":
    main()
