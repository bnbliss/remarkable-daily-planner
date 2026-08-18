#!/usr/bin/env python3
"""
Run this script on the Pi to authenticate with Google Calendar.
It will open a browser and save the credentials for the web app to use.
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

import os

def _env(name: str) -> str:
    """Read a credential from the environment, falling back to .env.

    These used to be inline literals. GitHub push protection rejected the
    push, correctly -- a client secret in source is a secret in every clone
    and every backup.
    """
    v = os.environ.get(name)
    if v:
        return v
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    try:
        with open(p) as fh:
            for line in fh:
                k, _, val = line.partition('=')
                if k.strip() == name:
                    return val.strip()
    except OSError:
        pass
    raise RuntimeError(f'{name} not set -- add it to .env or the environment')


SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
TOKEN_FILE = 'token.json'

CLIENT_ID = _env('GOOGLE_CLIENT_ID')
CLIENT_SECRET = _env('GOOGLE_CLIENT_SECRET')

def get_client_config():
    return {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

def main():
    print("=" * 60)
    print("Google Calendar Authentication")
    print("=" * 60)
    print()

    flow = InstalledAppFlow.from_client_config(get_client_config(), SCOPES)

    # Try to run with local server first, fall back to manual if no display
    try:
        print("Attempting to open browser...")
        creds = flow.run_local_server(port=8085, open_browser=True)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print()
        print("Manual authentication mode:")
        print("-" * 40)

        # Generate auth URL
        auth_url, _ = flow.authorization_url(prompt='consent')

        print()
        print("1. Open this URL in your browser:")
        print()
        print(auth_url)
        print()
        print("2. Sign in and authorize the app")
        print("3. You'll be redirected to a localhost URL that won't load")
        print("4. Copy the 'code' parameter from that URL")
        print("   (It's the part after 'code=' and before '&')")
        print()

        code = input("Paste the code here: ").strip()

        flow.fetch_token(code=code)
        creds = flow.credentials

    # Save credentials
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())

    print()
    print("=" * 60)
    print("Authentication successful!")
    print(f"Credentials saved to {TOKEN_FILE}")
    print("=" * 60)
    print()
    print("Now restart the remarkable-planner service:")
    print("  sudo systemctl restart remarkable-planner")

if __name__ == '__main__':
    main()
