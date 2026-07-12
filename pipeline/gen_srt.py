#!/usr/bin/env python3
"""
gen_srt.py — generate an SRT subtitle file from a HyperFrames narration.json.

Usage:
    python3 pipeline/gen_srt.py hyperframes/ch2-v1/narration.json
    # writes hyperframes/ch2-v1/ch2-v1.srt

The narration.json format:
    {
      "video": "<id>",
      "cues": [
        { "scene": "...", "at": <float>, "end": <float>, "text": "..." },
        ...
      ]
    }
"""

import json, sys
from pathlib import Path


def ts(seconds: float) -> str:
    """Convert float seconds to SRT timestamp HH:MM:SS,mmm."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gen_srt(narr_path: Path) -> Path:
    data = json.loads(narr_path.read_text(encoding="utf-8"))
    cues = data["cues"]
    video_id = data.get("video", narr_path.parent.name)

    lines = []
    for i, cue in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{ts(cue['at'])} --> {ts(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")

    out = narr_path.parent / f"{video_id}.srt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}  ({len(cues)} cues)")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: gen_srt.py <narration.json>")
        sys.exit(1)
    gen_srt(Path(sys.argv[1]))
