#!/usr/bin/env python3
"""
One-time OAuth flow to get a YouTube refresh token.

Usage:
    python3 pipeline/youtube_auth.py --secret client_secret.json

Opens a browser — log in with the Google account that owns your YouTube
channel. Prints the three values to add as GitHub secrets.
"""
import argparse, json
from pathlib import Path


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit("Run: pip install google-auth-oauthlib google-api-python-client")

    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", default="client_secret.json",
                    help="Path to client_secret.json from Google Cloud Console")
    args = ap.parse_args()

    secret_path = Path(args.secret)
    if not secret_path.exists():
        raise SystemExit(f"Not found: {secret_path}\n"
                         "Download it from Cloud Console → APIs & Services → Credentials")

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
    creds = flow.run_local_server(port=0)

    client_data = json.loads(secret_path.read_text())
    client_info = client_data.get("installed") or client_data.get("web")

    print("\n" + "=" * 60)
    print("Add these three values as GitHub repository secrets:")
    print("=" * 60)
    print(f"YOUTUBE_REFRESH_TOKEN  =  {creds.refresh_token}")
    print(f"YOUTUBE_CLIENT_ID      =  {client_info['client_id']}")
    print(f"YOUTUBE_CLIENT_SECRET  =  {client_info['client_secret']}")
    print("=" * 60)
    print("\nDone — client_secret.json is no longer needed and should NOT be committed.")


if __name__ == "__main__":
    main()
