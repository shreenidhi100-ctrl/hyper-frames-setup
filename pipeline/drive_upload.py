#!/usr/bin/env python3
"""
drive_upload.py — upload a file to Google Drive using a service account.

The service account must have Editor access to the target folder.

Environment variables (or passed directly):
    GOOGLE_SERVICE_ACCOUNT_JSON  — full JSON content of the service account key
    GDRIVE_FOLDER_ID             — ID of the target Drive folder
"""
import json, os, sys
from pathlib import Path


def get_drive_service(sa_json: str):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Run: pip install google-api-python-client google-auth")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def upload_file(local_path: Path, folder_id: str, sa_json: str,
                mime_type: str = "video/mp4") -> str:
    """
    Upload local_path to Google Drive folder_id.
    Returns the webViewLink of the uploaded file.
    """
    from googleapiclient.http import MediaFileUpload

    drive = get_drive_service(sa_json)
    metadata = {"name": local_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

    print(f"  uploading {local_path.name} to Drive…")
    file = drive.files().create(
        body=metadata, media_body=media, fields="id,webViewLink"
    ).execute()

    link = file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}/view")
    print(f"  uploaded: {link}")
    return link


def upload_video_and_srt(video_path: Path, srt_path: Path) -> dict:
    """Convenience wrapper — reads env vars, uploads both files."""
    sa_json   = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")

    if not sa_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")
    if not folder_id:
        raise RuntimeError("GDRIVE_FOLDER_ID env var not set")

    video_link = upload_file(video_path, folder_id, sa_json, "video/mp4")
    srt_link   = upload_file(srt_path,   folder_id, sa_json, "text/plain")
    return {"video": video_link, "srt": srt_link}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="path to *-final.mp4")
    ap.add_argument("srt",   help="path to *.srt")
    args = ap.parse_args()

    links = upload_video_and_srt(Path(args.video), Path(args.srt))
    print(f"\nDrive links:\n  video: {links['video']}\n  srt:   {links['srt']}")
