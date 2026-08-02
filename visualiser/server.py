#!/usr/bin/env python3
"""
Textbook visualiser prototype.

A child pastes in the passage they're currently reading (any subject) and
gets it turned into a looping animated canvas diagram of the underlying
concept — a reading companion, not a general chatbot prompt box.

Flask app with one endpoint: POST /api/visualize {text} -> a scene spec JSON
that static/renderer.js animates live on an HTML canvas. No audio, no
pre-rendering, no video export, no OCR (text is pasted, not photographed) —
and this is a standalone prototype, not part of the Ganita video pipeline.

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile) in the
environment the server runs in.

Run:
    pip install -r requirements.txt
    python3 server.py
    open http://localhost:5000
"""

import json
from pathlib import Path

import anthropic
from flask import Flask, jsonify, request, send_from_directory

HERE = Path(__file__).parent.resolve()

app = Flask(__name__, static_folder=str(HERE / "static"))
client = anthropic.Anthropic()

MODEL = "claude-opus-5"

CANVAS_W = 1000
CANVAS_H = 600

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "duration": {"type": "number", "description": "total loop length in seconds, 10-30"},
        "background": {"type": "string", "description": "hex color, e.g. #0b0f19"},
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ["text", "circle", "rect", "line", "arrow", "polygon"]},
                    "props": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "x2": {"type": "number"},
                            "y2": {"type": "number"},
                            "w": {"type": "number"},
                            "h": {"type": "number"},
                            "r": {"type": "number"},
                            "points": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                                    "required": ["x", "y"],
                                    "additionalProperties": False,
                                },
                            },
                            "content": {"type": "string"},
                            "fontSize": {"type": "number"},
                            "align": {"type": "string", "enum": ["left", "center", "right"]},
                            "color": {"type": "string"},
                            "fill": {"type": "boolean"},
                        },
                        "required": [],
                        "additionalProperties": False,
                    },
                    "enter": {
                        "type": "object",
                        "properties": {
                            "at": {"type": "number"},
                            "duration": {"type": "number"},
                            "style": {"type": "string", "enum": ["fade", "slide", "draw", "pop"]},
                        },
                        "required": ["at", "duration", "style"],
                        "additionalProperties": False,
                    },
                    "loop": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["pulse", "none"]},
                            "from": {"type": "number"},
                        },
                        "required": ["type"],
                        "additionalProperties": False,
                    },
                },
                "required": ["id", "type", "props", "enter"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["duration", "background", "elements"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""A child is reading a textbook and pasted in a passage \
they want visualized. The passage may be several sentences of prose from any \
subject (math, science, history, language, ...) — it is not a question \
addressed to you. First identify the single core concept the passage is \
teaching, then turn *that concept* into a looping animated canvas diagram. \
Do not just re-render the passage's sentences as on-screen text; draw the \
thing the passage describes.

Canvas is {CANVAS_W}x{CANVAS_H}, origin top-left, y grows downward.

Rules:
- 4-10 elements. Always include at least one text title near the top.
- Stagger every element's `enter.at` — nothing enters at the same instant as \
another element unless they are visually one group.
- Use `enter.style: "draw"` for lines/arrows/polygons that represent a \
diagram being built, not "fade" — the viewer should watch it construct.
- Use `enter.style: "pop"` for reveals/answers/key numbers.
- Exactly one element should carry a `loop: {{"type": "pulse", "from": <time \
its entrance finishes>}}` so the scene is never fully still after it settles \
— pick the single most important focus element (the answer, or the moving \
part of the diagram).
- All other elements: `loop: {{"type": "none"}}` or omit loop.
- `duration` is the full loop length in seconds (10-30); after the last \
element's entrance finishes, leave a few seconds before it loops back to 0.
- Colors: pick a small cohesive palette against `background`. Don't use pure \
black/white only.
- Keep coordinates inside the canvas bounds with margin.
"""


@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.route("/api/visualize", methods=["POST"])
def visualize():
    body = request.get_json(force=True, silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    # This is mechanical layout work (passage -> shape positions), not deep
    # reasoning, so thinking stays off and effort stays low for latency —
    # the schema already constrains the output shape.
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "disabled"},
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCENE_SCHEMA}},
        messages=[{"role": "user", "content": text}],
    )

    if response.stop_reason == "refusal":
        return jsonify({"error": "the model declined to visualize this prompt"}), 422

    scene_text = next(b.text for b in response.content if b.type == "text")
    scene = json.loads(scene_text)
    return jsonify(scene)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
