#!/usr/bin/env python3
"""
preview.py — generate a self-contained HTML preview page for a rendered video.

Embeds the MP4 as a base64 data URI so the artifact is fully offline.
Narration cues are shown as a tappable timeline — tap any row to seek.

Usage:
    python3 pipeline/preview.py hyperframes/ch2-v1/

Output: hyperframes/<video>/preview.html
Publish: Claude reads and publishes this file as an Artifact.
"""
import base64, json, sys
from pathlib import Path


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def generate(video_dir: Path) -> Path:
    narr_path = video_dir / "narration.json"
    if not narr_path.exists():
        raise FileNotFoundError(f"narration.json not found in {video_dir}")

    data     = json.loads(narr_path.read_text(encoding="utf-8"))
    vid_id   = data["video"]
    title    = data.get("title", vid_id)
    section  = data.get("section", "")
    trick    = data.get("common_trick", "")
    cues     = data.get("cues", [])

    final_mp4 = video_dir / f"{vid_id}-final.mp4"
    if not final_mp4.exists():
        raise FileNotFoundError(f"{final_mp4.name} not found — run hf_build.py first")

    size_mb  = final_mp4.stat().st_size / 1_048_576
    duration = max(c["end"] for c in cues) if cues else 0
    mins, secs = divmod(int(duration), 60)

    print(f"  encoding {final_mp4.name} ({size_mb:.1f} MB) as base64…")
    b64 = base64.b64encode(final_mp4.read_bytes()).decode()

    # Build cue rows — data-at used by JS for seeking and highlight
    rows = ""
    for i, cue in enumerate(cues):
        scene = cue.get("scene", "")
        rows += (
            f'<tr data-at="{cue["at"]:.2f}" data-end="{cue["end"]:.2f}" '
            f'onclick="seek({cue["at"]:.2f})">'
            f'<td class="ts">{_ts(cue["at"])}</td>'
            f'<td class="scene-tag">{scene}</td>'
            f'<td class="cue-text">{cue["text"]}</td>'
            f"</tr>\n"
        )

    trick_html = (
        f'<p class="trick"><span class="trick-label">💡</span>{trick}</p>'
        if trick else ""
    )

    html = f"""<title>{title} · Preview</title>
<style>
  /* ── tokens ─────────────────────────────────────────── */
  :root {{
    --bg:        #0f172a;
    --surface:   #1e293b;
    --border:    #334155;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --accent:    #e94560;
    --ts-color:  #60a5fa;
    --active-bg: #1e3a5f;
    --active-border: #3b82f6;
  }}
  :root[data-theme="light"], @media (prefers-color-scheme: light) {{
    :root:not([data-theme="dark"]) {{
      --bg:        #f8fafc;
      --surface:   #ffffff;
      --border:    #e2e8f0;
      --text:      #0f172a;
      --muted:     #94a3b8;
      --active-bg: #eff6ff;
      --active-border: #3b82f6;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:        #0f172a;
    --surface:   #1e293b;
    --border:    #334155;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --active-bg: #1e3a5f;
    --active-border: #3b82f6;
  }}

  /* ── base ───────────────────────────────────────────── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    max-width: 860px;
    margin: 0 auto;
    padding: 0 0 48px;
  }}

  /* ── header ─────────────────────────────────────────── */
  header {{
    padding: 20px 16px 14px;
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .header-top {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .badge {{
    background: var(--accent);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .04em;
    padding: 3px 10px;
    border-radius: 20px;
    white-space: nowrap;
  }}
  h1 {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
    text-wrap: balance;
  }}
  .meta {{
    font-size: 12px;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }}
  .trick {{
    font-size: 13px;
    color: var(--ts-color);
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin-top: 2px;
  }}
  .trick-label {{ flex-shrink: 0; }}

  /* ── video ──────────────────────────────────────────── */
  .video-wrap {{
    background: #000;
    position: relative;
  }}
  video {{
    width: 100%;
    display: block;
    max-height: 56vw;
    background: #000;
  }}

  /* ── timeline ───────────────────────────────────────── */
  .timeline-head {{
    padding: 14px 16px 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  tr {{
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }}
  tr:hover {{ background: var(--surface); }}
  tr.active {{
    background: var(--active-bg);
    border-left: 3px solid var(--active-border);
  }}
  tr.active .ts {{ color: var(--active-border); }}
  td {{
    padding: 9px 8px;
    vertical-align: top;
  }}
  td.ts {{
    color: var(--ts-color);
    font-size: 12px;
    font-family: ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    width: 44px;
    padding-left: 16px;
  }}
  td.scene-tag {{
    font-size: 11px;
    color: var(--muted);
    font-family: ui-monospace, monospace;
    white-space: nowrap;
    width: 60px;
  }}
  td.cue-text {{
    font-size: 14px;
    line-height: 1.45;
  }}
</style>

<header>
  <div class="header-top">
    <span class="badge">{section}</span>
    <h1>{title}</h1>
  </div>
  <p class="meta">{vid_id} · {mins}m {secs:02d}s · {len(cues)} cues · {size_mb:.1f} MB</p>
  {trick_html}
</header>

<div class="video-wrap">
  <video id="v" controls playsinline preload="metadata">
    <source src="data:video/mp4;base64,{b64}" type="video/mp4">
  </video>
</div>

<p class="timeline-head">Narration — tap any cue to jump</p>
<table>
  <tbody id="cues">
{rows}  </tbody>
</table>

<script>
  const video = document.getElementById('v');
  const rows  = Array.from(document.querySelectorAll('#cues tr'));

  function seek(t) {{
    video.currentTime = t;
    video.play();
    video.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}

  function highlight(t) {{
    let active = null;
    for (const row of rows) {{
      const at  = parseFloat(row.dataset.at);
      const end = parseFloat(row.dataset.end);
      if (t >= at && t < end) {{ active = row; break; }}
    }}
    rows.forEach(r => r.classList.remove('active'));
    if (active) {{
      active.classList.add('active');
      active.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
    }}
  }}

  video.addEventListener('timeupdate', () => highlight(video.currentTime));
</script>
"""

    out = video_dir / "preview.html"
    out.write_text(html, encoding="utf-8")
    kb = out.stat().st_size // 1024
    print(f"  preview.html  ({kb} KB)")
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: preview.py <hyperframes/video-dir/>")
        sys.exit(1)
    out = generate(Path(sys.argv[1]).resolve())
    print(f"done: {out}")


if __name__ == "__main__":
    main()
