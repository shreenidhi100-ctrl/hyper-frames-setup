#!/usr/bin/env python3
"""
youtube_upload.py — upload a video to YouTube as Private with auto-generated
title, description, and thumbnail.

Environment variables (set as GitHub secrets):
    YOUTUBE_REFRESH_TOKEN
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET

Usage:
    python3 pipeline/youtube_upload.py hyperframes/ch2-v1/
    python3 pipeline/youtube_upload.py hyperframes/ch2-v1/ --publish   # set Public
"""
import argparse, json, os, sys, tempfile
from pathlib import Path


# ── YouTube credentials ───────────────────────────────────────────────────────

def _get_youtube_client():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Run: pip install google-api-python-client google-auth")

    for var in ("YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        if not os.environ.get(var):
            raise RuntimeError(f"Environment variable {var} is not set.\n"
                               "Run pipeline/youtube_auth.py once to obtain it.")

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


# ── metadata generation ───────────────────────────────────────────────────────

def _build_metadata(narr_data: dict) -> dict:
    """Derive title, description, and tags from narration.json."""
    video_id = narr_data.get("video", "")
    title_kn = narr_data.get("title", "ಗಣಿತ ಪ್ರಕಾಶ")
    section  = narr_data.get("section", "")
    trick    = narr_data.get("common_trick", "")
    cues     = narr_data.get("cues", [])

    # Chapter + video number from id like "ch2-v1"
    parts   = video_id.split("-")
    chapter = parts[0].replace("ch", "Chapter ") if parts else ""
    part    = parts[1].replace("v", "Part ") if len(parts) > 1 else ""

    yt_title = (
        f"{title_kn} | {chapter} {section} | "
        f"Class 6 Ganita Prakash | Kannada Medium"
    )[:100]   # YouTube title limit

    # Build timestamped description from scene groups
    seen_scenes, timestamps = set(), []
    for cue in cues:
        scene = cue.get("scene", "")
        if scene and scene not in seen_scenes:
            seen_scenes.add(scene)
            mins, secs = divmod(int(cue["at"]), 60)
            label = scene.upper().replace("-", " ")
            timestamps.append(f"{mins:02d}:{secs:02d}  {label}")

    description = "\n".join([
        f"📚 {title_kn}",
        f"🔖 {section} | {chapter} | Karnataka Class 6 Maths (Ganita Prakash)",
        "",
        "In this video we cover:",
        *[f"  {ts}" for ts in timestamps],
        "",
        f"💡 Key insight: {trick}" if trick else "",
        "",
        "This video is part of a series covering the Karnataka Class 6 Maths",
        "textbook (Ganita Prakash) in Kannada medium, with animated explanations",
        "for each exercise question.",
        "",
        "#KannadaMaths #Class6Maths #GanitaPrakash #KarnatakaBoard #KannadaMedium",
    ]).strip()

    tags = [
        "kannada maths", "class 6 maths", "ganita prakash", "karnataka board",
        "kannada medium", "ncert maths", chapter.lower(), section.lower(),
        "animated maths", "maths explanation kannada",
    ]

    return {
        "title":       yt_title,
        "description": description,
        "tags":        [t for t in tags if t],
        "title_kn":    title_kn,
        "section":     section,
    }


# ── upload ────────────────────────────────────────────────────────────────────

def upload(video_dir: Path, privacy: str = "private") -> str:
    """
    Full upload flow for one video directory:
      1. Load narration.json → build metadata
      2. Generate thumbnail
      3. Upload video to YouTube
      4. Set thumbnail
    Returns the YouTube video URL.
    """
    from googleapiclient.http import MediaFileUpload

    narr_path = video_dir / "narration.json"
    if not narr_path.exists():
        raise FileNotFoundError(f"narration.json not found in {video_dir}")

    narr_data = json.loads(narr_path.read_text(encoding="utf-8"))
    video_id  = narr_data["video"]
    final_mp4 = video_dir / f"{video_id}-final.mp4"

    if not final_mp4.exists():
        raise FileNotFoundError(
            f"{final_mp4.name} not found — run hf_build.py first"
        )

    meta = _build_metadata(narr_data)
    print(f"  title: {meta['title']}")

    # Generate thumbnail
    print("── thumbnail ────────────────────────────────────")
    sys.path.insert(0, str(Path(__file__).parent))
    from thumbnail import generate as gen_thumb

    thumb_path = video_dir / "thumbnail.jpg"
    gen_thumb(
        mp4_path=final_mp4,
        title_kn=meta["title_kn"],
        title_en=meta["title"].split("|")[1].strip() if "|" in meta["title"] else "",
        badge=meta["section"],
        out_path=thumb_path,
    )

    # Upload video
    print("── youtube upload ────────────────────────────────")
    youtube = _get_youtube_client()

    body = {
        "snippet": {
            "title":       meta["title"],
            "description": meta["description"],
            "tags":        meta["tags"],
            "categoryId":  "27",   # Education
        },
        "status": {
            "privacyStatus":           privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(final_mp4), chunksize=10*1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body,
                                       media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  uploading… {pct}%", end="\r")

    yt_id  = response["id"]
    yt_url = f"https://youtu.be/{yt_id}"
    print(f"\n  uploaded: {yt_url}  (status: {privacy})")

    # Set thumbnail
    print("── thumbnail upload ──────────────────────────────")
    youtube.thumbnails().set(
        videoId=yt_id,
        media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
    ).execute()
    print("  thumbnail set")

    return yt_url


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Upload a rendered video to YouTube")
    ap.add_argument("video_dir", help="hyperframes/<video>/ directory")
    ap.add_argument("--publish", action="store_true",
                    help="Upload as Public instead of Private")
    args = ap.parse_args()

    video_dir = Path(args.video_dir).resolve()
    privacy   = "public" if args.publish else "private"

    url = upload(video_dir, privacy=privacy)
    print(f"\ndone: {url}")


if __name__ == "__main__":
    main()
